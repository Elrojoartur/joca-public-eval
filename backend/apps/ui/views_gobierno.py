from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import hashlib
import json
import secrets
import smtplib
import csv
from io import BytesIO, StringIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from apps.ui.views import role_required
from apps.authn.decorators import rate_limit
from apps.accounts.models import Rol
from apps.governance.models import EventoAuditoria, ParametroSistema, Permiso, RespaldoSistema, RolPermiso
from apps.governance.services.audit import log_event
from apps.school.models import Curso, Aula, Docente
from apps.sales.models import Concepto
from apps.governance.services.security_policy import (
    get_attempt_window_seconds,
    get_captcha_enabled,
    get_idle_timeout_seconds,
    get_lockout_seconds,
    get_max_attempts,
    get_password_min_length,
)
from apps.ui.input_validation import (
    validate_auth_code,
    sanitize_csv_cell,
    validate_email_value,
    validate_human_name,
    validate_periodo_value,
    validate_phone,
    validate_required_text,
    validate_text_general,
)


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def gobierno_home(request):
    cards = [
        {"title": "Usuarios", "desc": "Alta, edición y estado de cuentas.",
            "href": "/panel/gobierno/usuarios/"},
        {"title": "Roles", "desc": "Asignar y retirar roles a usuarios.",
            "href": "/panel/gobierno/roles/"},
        {"title": "Bitácora", "desc": "Trazabilidad de cambios de usuarios y roles.",
            "href": "/panel/gobierno/auditoria/"},
        {"title": "Seguridad", "desc": "Políticas de acceso y permisos.",
            "href": "/panel/gobierno/seguridad/"},
        {"title": "Excepciones", "desc": "Catálogo de excepciones controladas.",
            "href": "/panel/gobierno/excepciones/"},
        {"title": "Respaldos", "desc": "Generar y restaurar respaldos.",
            "href": "/panel/gobierno/respaldos/"},
        {"title": "Parámetros",
            "desc": "Parámetros generales del sistema.", "href": "/panel/gobierno/parametros/"},
    ]
    return render(request, "ui/gobierno_home.html", {"cards": cards})


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def gobierno_excepciones(request):
    excepciones = [
        {
            "nombre": "IntegrityError",
            "modulo": "Escolar / Ventas",
            "origen": "Duplicidad de registros o choque de restricciones unicas.",
            "manejo": "Se informa en pantalla con messages.error y se redirige al flujo seguro.",
            "referencias": [
                "backend/apps/ui/views_school.py:431",
                "backend/apps/sales/views.py:477",
                "backend/apps/sales/views.py:1000",
            ],
        },
        {
            "nombre": "ValidationError",
            "modulo": "Modelos y formularios",
            "origen": "Datos invalidos en CURP/RFC, reglas de formularios o serializers.",
            "manejo": "Se muestra mensaje por campo y se evita persistir datos invalidos.",
            "referencias": [
                "backend/apps/school/validators.py:42",
                "backend/apps/ui/forms.py:63",
                "backend/apps/school/api/v1/serializers.py:36",
            ],
        },
        {
            "nombre": "Http404",
            "modulo": "Portal publico",
            "origen": "Recurso solicitado no existe (p. ej. curso no encontrado).",
            "manejo": "Respuesta 404 controlada sin exponer trazas internas.",
            "referencias": [
                "backend/apps/public_portal/views.py:285",
            ],
        },
        {
            "nombre": "ValueError",
            "modulo": "Portal / Ventas / Validadores",
            "origen": "Conversiones y parseo de datos no validos.",
            "manejo": "Se captura y transforma en mensaje funcional para el usuario.",
            "referencias": [
                "backend/apps/public_portal/views.py:77",
                "backend/apps/sales/views.py:472",
                "backend/apps/school/validators.py:52",
            ],
        },
        {
            "nombre": "Exception (fallback)",
            "modulo": "Reportes / Alumno / Gobierno",
            "origen": "Falla externa o no prevista (correo, dependencia opcional, IO).",
            "manejo": "Fallback seguro, sin romper UI, y registro de auditoria/diagnostico.",
            "referencias": [
                "backend/apps/ui/views_reportes.py:337",
                "backend/apps/ui/views_alumno.py:145",
                "backend/apps/ui/views_gobierno.py:376",
            ],
        },
    ]

    return render(
        request,
        "ui/gobierno_excepciones.html",
        {"excepciones": excepciones, "updated_at": timezone.now()},
    )


_POLICY_SPECS = [
    {
        "key": "security_password_min_length",
        "label": "Longitud mínima de contraseña",
        "tipo": "int",
        "min": 6, "max": 64,
        "hint": "Caracteres (6–64)",
    },
    {
        "key": "security_max_attempts",
        "label": "Intentos máximos de acceso",
        "tipo": "int",
        "min": 1, "max": 20,
        "hint": "Número (1–20)",
    },
    {
        "key": "security_attempt_window_seconds",
        "label": "Ventana de intentos (s)",
        "tipo": "int",
        "min": 60, "max": 86400,
        "hint": "Segundos (60–86400)",
    },
    {
        "key": "security_lockout_seconds",
        "label": "Duración de bloqueo (s)",
        "tipo": "int",
        "min": 60, "max": 86400,
        "hint": "Segundos (60–86400)",
    },
    {
        "key": "security_idle_timeout_seconds",
        "label": "Tiempo de inactividad (s)",
        "tipo": "int",
        "min": 1, "max": 86400,
        "hint": "Segundos (1–86400)",
    },
    {
        "key": "security_captcha_enabled",
        "label": "CAPTCHA habilitado",
        "tipo": "bool",
        "hint": "Activa el CAPTCHA en el login",
    },
]


def _load_policy_values():
    return {
        "security_password_min_length": get_password_min_length(),
        "security_max_attempts": get_max_attempts(),
        "security_attempt_window_seconds": get_attempt_window_seconds(),
        "security_lockout_seconds": get_lockout_seconds(),
        "security_idle_timeout_seconds": get_idle_timeout_seconds(),
        "security_captcha_enabled": get_captcha_enabled(),
    }


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def gobierno_seguridad(request):
    if request.method == "POST":
        section = (request.POST.get("section") or "").strip().lower()
        if section != "policy":
            messages.error(request, "Sección de seguridad inválida.")
            return redirect("ui:gobierno_seguridad")

        updates = {}
        error_msg = None
        for spec in _POLICY_SPECS:
            key = spec["key"]
            raw = request.POST.get(key)
            if spec["tipo"] == "bool":
                value = "1" if raw in {"on", "1", "true", "TRUE"} else "0"
            else:
                value = (raw or "").strip()
                if not value:
                    error_msg = f"El campo «{spec['label']}» no puede estar vacío."
                    break
                try:
                    int_val = int(value)
                except ValueError:
                    error_msg = f"«{spec['label']}» debe ser un número entero."
                    break
                if int_val < spec["min"] or int_val > spec["max"]:
                    error_msg = (
                        f"«{spec['label']}» debe estar entre "
                        f"{spec['min']} y {spec['max']}."
                    )
                    break
                value = str(int_val)
            ParametroSistema.objects.update_or_create(
                clave=key,
                defaults={
                    "categoria": ParametroSistema.CATEGORIA_SEGURIDAD,
                    "valor": value,
                    "activo": True,
                },
            )
            updates[key] = value

        if error_msg:
            messages.error(request, error_msg)
            return redirect("ui:gobierno_seguridad")

        log_event(
            request,
            accion="GOBIERNO::POLITICAS_SEGURIDAD_UPDATE",
            entidad="ParametroSistema",
            entidad_id="seguridad",
            resultado="ok",
            detalle=updates,
        )
        messages.success(request, "Políticas de seguridad actualizadas.")
        return redirect("ui:gobierno_seguridad")

    # ─── GET ──────────────────────────────────────────────────────────────────
    modo = request.GET.get("modo", "politicas")
    pagina = request.GET.get("page", 1)

    rp = (
        RolPermiso.objects
        .select_related("rol", "permiso")
        .order_by("rol__nombre", "permiso__codigo")
    )
    rol_to_perms = {}
    for x in rp:
        rol_to_perms.setdefault(x.rol_id, []).append(x.permiso)

    roles_qs = Rol.objects.order_by("nombre")
    roles_paginator = Paginator(roles_qs, 3)
    roles_page = roles_paginator.get_page(pagina)

    roles_rows = [
        {"rol": r, "permisos": rol_to_perms.get(r.id, [])}
        for r in roles_page
    ]

    policy_values = _load_policy_values()

    return render(
        request,
        "ui/gobierno_seguridad.html",
        {
            "modo": modo,
            "roles_rows": roles_rows,
            "roles_page": roles_page,
            "permisos": list(Permiso.objects.order_by("modulo", "codigo")),
            "policy": policy_values,
            "policy_specs": _POLICY_SPECS,
            "active": "gobierno_seguridad",
        },
    )


@rate_limit("export_auditoria", max_calls=30, period_seconds=300)
@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def gobierno_auditoria(request):
    from urllib.parse import urlencode as _urlencode

    qs = EventoAuditoria.objects.select_related("actor").order_by("-id")

    actor_q = (request.GET.get("actor") or "").strip()
    accion_q = (request.GET.get("accion") or "").strip()
    resultado_q = (request.GET.get("resultado") or "").strip()
    fecha_desde_q = (request.GET.get("fecha_desde") or "").strip()
    fecha_hasta_q = (request.GET.get("fecha_hasta") or "").strip()

    if actor_q:
        qs = qs.filter(actor__username__icontains=actor_q)
    if accion_q:
        qs = qs.filter(accion__icontains=accion_q)
    if resultado_q:
        qs = qs.filter(resultado=resultado_q)
    if fecha_desde_q:
        try:
            from datetime import date as _date
            from datetime import datetime as _dt
            qs = qs.filter(creado_en__date__gte=_dt.strptime(
                fecha_desde_q, "%Y-%m-%d").date())
        except ValueError:
            fecha_desde_q = ""
    if fecha_hasta_q:
        try:
            from datetime import datetime as _dt
            qs = qs.filter(creado_en__date__lte=_dt.strptime(
                fecha_hasta_q, "%Y-%m-%d").date())
        except ValueError:
            fecha_hasta_q = ""

    filtros = {k: v for k, v in {
        "actor": actor_q,
        "accion": accion_q,
        "resultado": resultado_q,
        "fecha_desde": fecha_desde_q,
        "fecha_hasta": fecha_hasta_q,
    }.items() if v}

    export_format = (request.GET.get("export") or "").strip().lower()
    if export_format in {"csv", "pdf"}:
        return _exportar_auditoria(request, list(qs[:200]), export_format)

    paginator = Paginator(qs, 3)
    page_obj = paginator.get_page(request.GET.get("p", 1))
    filtros_qs = _urlencode(filtros) if filtros else ""

    return render(request, "ui/gobierno_auditoria.html", {
        "page_obj": page_obj,
        "filtros": filtros,
        "filtros_qs": filtros_qs,
        "active": "gobierno_auditoria",
    })


def _exportar_auditoria(request, eventos, export_format):
    parametros = list(
        ParametroSistema.objects.order_by("categoria", "clave").values(
            "categoria",
            "clave",
            "valor",
            "activo",
        )
    )
    if export_format == "csv":
        content_bytes = _build_auditoria_csv_bytes(eventos, parametros)
        content_type = "text/csv; charset=utf-8"
        extension = "csv"
    else:
        content_bytes = _build_auditoria_pdf_bytes(eventos, parametros)
        content_type = "application/pdf"
        extension = "pdf"

    digest = hashlib.sha256(content_bytes).hexdigest()
    timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    filename = f"auditoria_evidencia_{timestamp}_{digest[:12]}.{extension}"

    response = HttpResponse(content_bytes, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Export-SHA256"] = digest

    log_event(
        request,
        accion="GOBIERNO::AUDITORIA_EXPORT",
        entidad="EventoAuditoria",
        entidad_id=str(len(eventos)),
        resultado="ok",
        detalle={
            "format": export_format,
            "sha256": digest,
            "eventos": len(eventos),
            "parametros": len(parametros),
            "filename": filename,
        },
    )
    return response


def _build_auditoria_csv_bytes(eventos, parametros):
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(["tipo", "id", "actor", "accion", "entidad",
                    "entidad_id", "resultado", "ip", "creado_en", "detalle_json"])
    for e in eventos:
        writer.writerow(
            [
                sanitize_csv_cell("AUDITORIA"),
                sanitize_csv_cell(e.id),
                sanitize_csv_cell(getattr(e.actor, "username", "")),
                sanitize_csv_cell(e.accion),
                sanitize_csv_cell(e.entidad),
                sanitize_csv_cell(e.entidad_id or ""),
                sanitize_csv_cell(e.resultado),
                sanitize_csv_cell(e.ip),
                sanitize_csv_cell(e.creado_en.isoformat()
                                  if e.creado_en else ""),
                sanitize_csv_cell(json.dumps(
                    e.detalle or {}, ensure_ascii=True, sort_keys=True)),
            ]
        )

    writer.writerow([])
    writer.writerow(["tipo", "categoria", "clave", "valor", "activo"])
    for p in parametros:
        writer.writerow([
            sanitize_csv_cell("CONFIG"),
            sanitize_csv_cell(p["categoria"]),
            sanitize_csv_cell(p["clave"]),
            sanitize_csv_cell(p["valor"]),
            sanitize_csv_cell("1" if p["activo"] else "0"),
        ])

    content = stream.getvalue()
    stream.close()
    return content.encode("utf-8")


def _build_auditoria_pdf_bytes(eventos, parametros):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(40, y, "Exportacion de bitacora y evidencias")
    y -= 18
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, y, f"Generado: {timezone.now().isoformat()}")
    y -= 12
    pdf.drawString(
        40, y, f"Eventos: {len(eventos)} | Parametros: {len(parametros)}")
    y -= 18

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Bitacora (ultimos eventos)")
    y -= 14
    pdf.setFont("Helvetica", 8)
    for e in eventos[:120]:
        line = f"#{e.id} {e.accion} {e.entidad}({e.entidad_id or '-'}) {e.resultado}"
        pdf.drawString(40, y, line[:120])
        y -= 11
        if y < 70:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 8)

    y -= 6
    if y < 90:
        pdf.showPage()
        y = height - 50
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Evidencia de configuracion")
    y -= 14
    pdf.setFont("Helvetica", 8)
    for p in parametros[:180]:
        line = f"[{p['categoria']}] {p['clave']}={p['valor']} (activo={1 if p['activo'] else 0})"
        pdf.drawString(40, y, line[:120])
        y -= 11
        if y < 70:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 8)

    pdf.save()
    content = buffer.getvalue()
    buffer.close()
    return content


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def gobierno_parametros(request):
    _PARAM_SPECS = {
        "institucion": {
            "categoria": ParametroSistema.CATEGORIA_INSTITUCION,
            "campos": ["institucion_nombre", "institucion_rfc", "institucion_direccion"],
            "label": "institución",
            "accion": "GOBIERNO::PARAMETROS_INSTITUCION_UPDATE",
            "modo": "inst",
        },
        "periodo": {
            "categoria": ParametroSistema.CATEGORIA_PERIODO,
            "campos": ["periodo_activo", "periodo_inicio", "periodo_fin"],
            "label": "periodos",
            "accion": "GOBIERNO::PARAMETROS_PERIODO_UPDATE",
            "modo": "periodo",
        },
        "smtp": {
            "categoria": ParametroSistema.CATEGORIA_SMTP,
            "campos": ["smtp_host", "smtp_port", "smtp_user", "smtp_from", "smtp_enabled"],
            "label": "SMTP",
            "accion": "GOBIERNO::PARAMETROS_SMTP_UPDATE",
            "modo": "smtp",
        },
        "pasarela": {
            "categoria": ParametroSistema.CATEGORIA_PASARELA,
            "campos": ["pasarela_proveedor", "pasarela_public_key", "pasarela_enabled"],
            "label": "pasarela",
            "accion": "GOBIERNO::PARAMETROS_PASARELA_UPDATE",
            "modo": "pasarela",
        },
    }

    if request.method == "POST":
        section = (request.POST.get("section") or "").strip().lower()
        operation = (request.POST.get("operation") or "save").strip().lower()
        spec = _PARAM_SPECS.get(section)

        if not spec:
            # ─── Alta de parámetro genérico ──────────────────────────────
            if section == "nuevo_param":
                clave = (request.POST.get("clave") or "").strip()
                valor = (request.POST.get("valor") or "").strip()
                categoria = (request.POST.get("categoria") or "").strip()
                activo = request.POST.get("activo") in {"on", "1", "true"}
                try:
                    clave = validate_required_text(clave, "Clave")
                    if not valor:
                        raise ValueError("El valor es obligatorio.")
                    valid_cats = [c[0]
                                  for c in ParametroSistema.CATEGORIA_CHOICES]
                    if categoria not in valid_cats:
                        raise ValueError("Categoría inválida.")
                    if ParametroSistema.objects.filter(clave=clave).exists():
                        raise ValueError(
                            f"Ya existe un parámetro con clave «{clave}».")
                except Exception as exc:
                    messages.error(request, str(exc))
                    return redirect("/panel/gobierno/parametros/?modo=nuevo")
                p = ParametroSistema.objects.create(
                    clave=clave, valor=valor, categoria=categoria, activo=activo)
                log_event(request, accion="GOBIERNO::PARAMETRO_CREAR",
                          entidad="ParametroSistema", entidad_id=p.pk,
                          resultado="ok", detalle={"clave": clave, "categoria": categoria})
                messages.success(request, f"Parámetro «{clave}» creado.")
                return redirect("ui:gobierno_parametros")

            # ─── Edición de parámetro genérico ───────────────────────────
            if section == "editar_param":
                param_id = (request.POST.get("param_id") or "").strip()
                p = get_object_or_404(ParametroSistema, pk=param_id)
                clave_nueva = (request.POST.get("clave") or "").strip()
                valor = (request.POST.get("valor") or "").strip()
                categoria = (request.POST.get("categoria") or "").strip()
                activo = request.POST.get("activo") in {"on", "1", "true"}
                try:
                    clave_nueva = validate_required_text(clave_nueva, "Clave")
                    if not valor:
                        raise ValueError("El valor es obligatorio.")
                    valid_cats = [c[0]
                                  for c in ParametroSistema.CATEGORIA_CHOICES]
                    if categoria not in valid_cats:
                        raise ValueError("Categoría inválida.")
                    if clave_nueva != p.clave and ParametroSistema.objects.filter(clave=clave_nueva).exists():
                        raise ValueError(
                            f"Ya existe un parámetro con clave «{clave_nueva}».")
                except Exception as exc:
                    messages.error(request, str(exc))
                    return redirect(f"/panel/gobierno/parametros/?modo=editar&id={param_id}")
                prev = {"clave": p.clave, "valor": p.valor,
                        "categoria": p.categoria, "activo": p.activo}
                p.clave = clave_nueva
                p.valor = valor
                p.categoria = categoria
                p.activo = activo
                p.save()
                log_event(request, accion="GOBIERNO::PARAMETRO_EDITAR",
                          entidad="ParametroSistema", entidad_id=p.pk,
                          resultado="ok",
                          detalle={"antes": prev, "despues": {"clave": clave_nueva, "valor": valor}})
                messages.success(
                    request, f"Parámetro «{clave_nueva}» actualizado.")
                return redirect("ui:gobierno_parametros")

            # ─── Catálogos maestros ───────────────────────────────────────
            if section == "catalogos":
                _cat_op = (request.POST.get("operation") or "").strip().lower()
                _cat_op_map = {
                    "create_curso": "cursos", "toggle_curso": "cursos",
                    "create_aula": "aulas", "toggle_aula": "aulas",
                    "create_docente": "docentes", "toggle_docente": "docentes",
                    "create_concepto": "conceptos", "toggle_concepto": "conceptos",
                }
                _handle_catalogos_maestros(request)
                _cat = _cat_op_map.get(_cat_op, "")
                _suffix = f"&cat={_cat}" if _cat else ""
                return redirect(f"/panel/gobierno/parametros/?modo=catalogos{_suffix}")

            messages.error(request, "Sección de parámetros inválida.")
            return redirect("ui:gobierno_parametros")

        if section == "smtp":
            _handle_smtp_parametros(request, spec, operation)
            return redirect("/panel/gobierno/parametros/?modo=smtp")

        if section == "pasarela":
            _handle_pasarela_parametros(request, spec, operation)
            return redirect("/panel/gobierno/parametros/?modo=pasarela")

        updates = {}
        try:
            for key in spec["campos"]:
                raw = request.POST.get(key)
                if key.endswith("_enabled"):
                    value = "1" if raw in {"on", "1", "true", "TRUE"} else "0"
                else:
                    value = (raw or "").strip()

                if section == "institucion" and key == "institucion_nombre":
                    value = validate_required_text(value, "Nombre institución")
                if section == "periodo" and key == "periodo_activo":
                    value = validate_periodo_value(value)

                ParametroSistema.objects.update_or_create(
                    clave=key,
                    defaults={
                        "categoria": spec["categoria"],
                        "valor": value,
                        "activo": True,
                    },
                )
                updates[key] = value
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect(f"/panel/gobierno/parametros/?modo={spec['modo']}")

        log_event(
            request,
            accion=spec["accion"],
            entidad="ParametroSistema",
            entidad_id=section,
            resultado="ok",
            detalle=updates,
        )
        messages.success(
            request, f"Configuración de {spec['label']} actualizada.")
        return redirect(f"/panel/gobierno/parametros/?modo={spec['modo']}")

    # ─── GET ─────────────────────────────────────────────────────────────────
    modo = request.GET.get("modo", "listado")
    editar_id = request.GET.get("id")
    pagina = request.GET.get("page", 1)

    all_params = ParametroSistema.objects.all()
    paginator = Paginator(all_params, 3)
    page_obj = paginator.get_page(pagina)

    param_editar = None
    if modo == "editar" and editar_id:
        param_editar = get_object_or_404(ParametroSistema, pk=editar_id)

    # ─ Sub-paginación de catálogos maestros
    cat = request.GET.get("cat", "").strip().lower()
    cat_page_num = request.GET.get("cat_page", 1)
    cat_page_obj = None
    cat_counts = {}
    if modo == "catalogos":
        cat_counts = {
            "cursos": Curso.objects.count(),
            "aulas": Aula.objects.count(),
            "docentes": Docente.objects.count(),
            "conceptos": Concepto.objects.count(),
        }
        _cat_qs_map = {
            "cursos": Curso.objects.order_by("nombre"),
            "aulas": Aula.objects.order_by("clave"),
            "docentes": Docente.objects.order_by(
                "apellido_paterno", "apellido_materno", "nombres"),
            "conceptos": Concepto.objects.order_by("nombre"),
        }
        if cat in _cat_qs_map:
            cat_page_obj = Paginator(
                _cat_qs_map[cat], 3).get_page(cat_page_num)

    ctx = _build_parametros_context()
    ctx.update({
        "modo": modo,
        "page_obj": page_obj,
        "param_editar": param_editar,
        "categoria_choices": ParametroSistema.CATEGORIA_CHOICES,
        "active": "gobierno_parametros",
        "cat": cat,
        "cat_page_obj": cat_page_obj,
        "cat_counts": cat_counts,
    })
    return render(request, "ui/gobierno_parametros.html", ctx)


def _build_parametros_context():
    return {
        "values": _load_parametros_values(),
        "catalogos": _load_catalogos_values(),
    }


def _load_catalogos_values():
    return {
        "cursos": list(Curso.objects.order_by("nombre")[:100]),
        "aulas": list(Aula.objects.order_by("clave")[:100]),
        "docentes": list(Docente.objects.order_by("apellido_paterno", "apellido_materno", "nombres")[:100]),
        "conceptos": list(Concepto.objects.order_by("nombre")[:120]),
    }


def _to_positive_int(raw, default_value=0):
    try:
        value = int((raw or "").strip())
    except (TypeError, ValueError, AttributeError):
        return default_value
    return value if value >= 0 else default_value


def _to_decimal_str(raw, default_value="0.00"):
    text = (raw or "").strip()
    if not text:
        return default_value
    try:
        return f"{Decimal(text):.2f}"
    except Exception:
        return default_value


def _to_bool_flag(raw):
    return "1" if (raw or "").strip().lower() in {"1", "on", "true"} else "0"


def _handle_catalogos_maestros(request):
    operation = (request.POST.get("operation") or "").strip().lower()

    if operation == "create_curso":
        codigo = (request.POST.get("curso_codigo") or "").strip().upper()
        nombre = (request.POST.get("curso_nombre") or "").strip()
        descripcion = (request.POST.get("curso_descripcion") or "").strip()
        activo = _to_bool_flag(request.POST.get("curso_activo")) == "1"
        try:
            codigo = validate_required_text(codigo, "Código curso")
            codigo = validate_auth_code(codigo, "Código curso").upper()
            nombre = validate_text_general(
                nombre,
                "Nombre curso",
                min_length=2,
                max_length=120,
            )
            descripcion = validate_text_general(
                descripcion,
                "Descripción curso",
                allow_blank=True,
                min_length=0,
                max_length=250,
            )
        except Exception as exc:
            messages.error(request, str(exc))
            return
        curso, created = Curso.objects.update_or_create(
            codigo=codigo,
            defaults={
                "nombre": nombre,
                "descripcion": descripcion,
                "activo": activo,
            },
        )
        log_event(
            request,
            accion="GOBIERNO::CATALOGOS_MAESTROS_CURSO_UPSERT",
            entidad="Curso",
            entidad_id=curso.id,
            resultado="ok",
            detalle={"codigo": codigo, "created": created, "activo": activo},
        )
        messages.success(request, "Catálogo académico (curso) actualizado.")
        return

    if operation == "toggle_curso":
        curso_id = _to_positive_int(request.POST.get("curso_id"))
        curso = Curso.objects.filter(pk=curso_id).first()
        if not curso:
            messages.error(request, "Curso no encontrado.")
            return
        curso.activo = not curso.activo
        curso.save(update_fields=["activo"])
        log_event(
            request,
            accion="GOBIERNO::CATALOGOS_MAESTROS_CURSO_TOGGLE",
            entidad="Curso",
            entidad_id=curso.id,
            resultado="ok",
            detalle={"activo": curso.activo},
        )
        messages.success(request, "Estado de curso actualizado.")
        return

    if operation == "create_aula":
        clave = (request.POST.get("aula_clave") or "").strip().upper()
        nombre = (request.POST.get("aula_nombre") or "").strip()
        capacidad = _to_positive_int(request.POST.get("aula_capacidad"), 0)
        activa = _to_bool_flag(request.POST.get("aula_activa")) == "1"
        try:
            clave = validate_required_text(clave, "Clave aula")
            clave = validate_auth_code(clave, "Clave aula").upper()
            nombre = validate_text_general(
                nombre,
                "Nombre aula",
                min_length=2,
                max_length=120,
            )
        except Exception as exc:
            messages.error(request, str(exc))
            return
        aula, created = Aula.objects.update_or_create(
            clave=clave,
            defaults={
                "nombre": nombre,
                "capacidad": capacidad,
                "activa": activa,
            },
        )
        log_event(
            request,
            accion="GOBIERNO::CATALOGOS_MAESTROS_AULA_UPSERT",
            entidad="Aula",
            entidad_id=aula.id,
            resultado="ok",
            detalle={"clave": clave, "created": created, "activa": activa},
        )
        messages.success(request, "Catálogo académico (aula) actualizado.")
        return

    if operation == "toggle_aula":
        aula_id = _to_positive_int(request.POST.get("aula_id"))
        aula = Aula.objects.filter(pk=aula_id).first()
        if not aula:
            messages.error(request, "Aula no encontrada.")
            return
        aula.activa = not aula.activa
        aula.save(update_fields=["activa"])
        log_event(
            request,
            accion="GOBIERNO::CATALOGOS_MAESTROS_AULA_TOGGLE",
            entidad="Aula",
            entidad_id=aula.id,
            resultado="ok",
            detalle={"activa": aula.activa},
        )
        messages.success(request, "Estado de aula actualizado.")
        return

    if operation == "create_docente":
        nombres = (request.POST.get("docente_nombres") or "").strip()
        ap_pat = (request.POST.get("docente_apellido_paterno") or "").strip()
        ap_mat = (request.POST.get("docente_apellido_materno")
                  or "").strip() or "NO CAPTURADO"
        correo = (request.POST.get("docente_correo") or "").strip().lower()
        telefono = (request.POST.get("docente_telefono") or "").strip()
        activo = _to_bool_flag(request.POST.get("docente_activo")) == "1"
        try:
            nombres = validate_human_name(nombres, "Nombres")
            ap_pat = validate_human_name(ap_pat, "Apellido paterno")
            ap_mat = validate_human_name(
                ap_mat, "Apellido materno", allow_blank=True) or "NO CAPTURADO"
            correo = validate_email_value(correo, "Correo")
            telefono = validate_phone(telefono, "Teléfono", allow_blank=True)
        except Exception as exc:
            messages.error(request, str(exc))
            return
        docente, created = Docente.objects.update_or_create(
            correo=correo,
            defaults={
                "nombres": nombres,
                "apellido_paterno": ap_pat,
                "apellido_materno": ap_mat,
                "telefono": telefono,
                "activo": activo,
            },
        )
        log_event(
            request,
            accion="GOBIERNO::CATALOGOS_MAESTROS_DOCENTE_UPSERT",
            entidad="Docente",
            entidad_id=docente.id,
            resultado="ok",
            detalle={"correo": correo, "created": created, "activo": activo},
        )
        messages.success(request, "Catálogo académico (docente) actualizado.")
        return

    if operation == "toggle_docente":
        docente_id = _to_positive_int(request.POST.get("docente_id"))
        docente = Docente.objects.filter(pk=docente_id).first()
        if not docente:
            messages.error(request, "Docente no encontrado.")
            return
        docente.activo = not docente.activo
        docente.save(update_fields=["activo"])
        log_event(
            request,
            accion="GOBIERNO::CATALOGOS_MAESTROS_DOCENTE_TOGGLE",
            entidad="Docente",
            entidad_id=docente.id,
            resultado="ok",
            detalle={"activo": docente.activo},
        )
        messages.success(request, "Estado de docente actualizado.")
        return

    if operation == "create_concepto":
        nombre = (request.POST.get("concepto_nombre") or "").strip()
        precio = _to_decimal_str(request.POST.get("concepto_precio"), "0.00")
        activo = _to_bool_flag(request.POST.get("concepto_activo")) == "1"
        try:
            nombre = validate_text_general(
                nombre,
                "Concepto",
                min_length=2,
                max_length=120,
            )
            if Decimal(precio) <= 0:
                raise ValueError("Precio inválido. Debe ser mayor a 0.")
        except Exception as exc:
            messages.error(request, str(exc))
            return
        concepto, created = Concepto.objects.update_or_create(
            nombre=nombre,
            defaults={
                "precio": precio,
                "activo": activo,
            },
        )
        log_event(
            request,
            accion="GOBIERNO::CATALOGOS_MAESTROS_CONCEPTO_UPSERT",
            entidad="Concepto",
            entidad_id=concepto.id,
            resultado="ok",
            detalle={"nombre": nombre, "created": created,
                     "activo": activo, "precio": precio},
        )
        messages.success(request, "Catálogo comercial (concepto) actualizado.")
        return

    if operation == "toggle_concepto":
        concepto_id = _to_positive_int(request.POST.get("concepto_id"))
        concepto = Concepto.objects.filter(pk=concepto_id).first()
        if not concepto:
            messages.error(request, "Concepto no encontrado.")
            return
        concepto.activo = not concepto.activo
        concepto.save(update_fields=["activo"])
        log_event(
            request,
            accion="GOBIERNO::CATALOGOS_MAESTROS_CONCEPTO_TOGGLE",
            entidad="Concepto",
            entidad_id=concepto.id,
            resultado="ok",
            detalle={"activo": concepto.activo},
        )
        messages.success(request, "Estado de concepto actualizado.")
        return

    messages.error(request, "Operación de catálogos inválida.")


def _handle_smtp_parametros(request, spec, operation):
    updates = {
        "smtp_host": (request.POST.get("smtp_host") or "").strip(),
        "smtp_port": (request.POST.get("smtp_port") or "").strip(),
        "smtp_user": (request.POST.get("smtp_user") or "").strip(),
        "smtp_from": (request.POST.get("smtp_from") or "").strip(),
        "smtp_password": (request.POST.get("smtp_password") or "").strip(),
        "smtp_enabled": "1" if (request.POST.get("smtp_enabled") or "") in {"on", "1", "true", "TRUE"} else "0",
    }

    try:
        updates["smtp_host"] = validate_text_general(
            updates["smtp_host"],
            "Host SMTP",
            min_length=2,
            max_length=120,
        )
        updates["smtp_port"] = validate_required_text(
            updates["smtp_port"], "Puerto SMTP")
        int(updates["smtp_port"])
        updates["smtp_user"] = validate_text_general(
            updates["smtp_user"],
            "Usuario SMTP",
            allow_blank=True,
            min_length=0,
            max_length=120,
        )
        updates["smtp_from"] = validate_email_value(
            updates["smtp_from"], "Remitente SMTP")
    except Exception as exc:
        messages.error(request, str(exc))
        return
    fingerprint = _integration_fingerprint(
        {
            "smtp_host": updates["smtp_host"],
            "smtp_port": updates["smtp_port"],
            "smtp_user": updates["smtp_user"],
            "smtp_from": updates["smtp_from"],
            "smtp_password": updates["smtp_password"],
        }
    )

    if operation == "rotate":
        version = _next_rotation_version("smtp_rotation_version")
        rotated_at = timezone.now().isoformat()
        updates["smtp_password"] = f"smtp_{secrets.token_urlsafe(18)}"
        updates["smtp_enabled"] = "0"
        updates["smtp_rotation_version"] = str(version)
        updates["smtp_rotated_at"] = rotated_at
        updates["smtp_test_status"] = "pendiente"
        updates["smtp_test_message"] = "Rotacion de credenciales aplicada. Ejecuta una nueva prueba SMTP."
        updates["smtp_test_fingerprint"] = ""
        updates["smtp_tested_at"] = ""

        _persist_param_updates(spec["categoria"], updates)
        log_event(
            request,
            accion="GOBIERNO::PARAMETROS_SMTP_ROTATE",
            entidad="ParametroSistema",
            entidad_id="smtp",
            resultado="ok",
            detalle={
                "smtp_host": updates["smtp_host"],
                "smtp_user": updates["smtp_user"],
                "rotation_version": version,
                "rotated_at": rotated_at,
            },
        )
        messages.success(
            request, f"Credenciales SMTP rotadas (version {version}).")
        return

    if operation == "test":
        ok, message = _validate_smtp_config(updates)
        _save_integration_test_result(
            categoria=ParametroSistema.CATEGORIA_SMTP,
            prefix="smtp",
            ok=ok,
            message=message,
            fingerprint=fingerprint,
        )
        log_event(
            request,
            accion="GOBIERNO::PARAMETROS_SMTP_TEST",
            entidad="ParametroSistema",
            entidad_id="smtp",
            resultado="ok" if ok else "error",
            detalle={
                "smtp_host": updates["smtp_host"],
                "smtp_port": updates["smtp_port"],
                "message": message,
            },
        )
        if ok:
            messages.success(
                request, "Prueba SMTP exitosa. Ya puedes habilitar la integración.")
        else:
            messages.error(request, f"Prueba SMTP fallida: {message}")
        return

    if updates["smtp_enabled"] == "1" and not _integration_can_enable("smtp", fingerprint):
        updates["smtp_enabled"] = "0"
        log_event(
            request,
            accion="GOBIERNO::PARAMETROS_SMTP_ENABLE_DENIED",
            entidad="ParametroSistema",
            entidad_id="smtp",
            resultado="denied",
            detalle={
                "reason": "test_required",
                "smtp_host": updates["smtp_host"],
                "smtp_port": updates["smtp_port"],
            },
        )
        messages.error(
            request, "Debes ejecutar una prueba SMTP exitosa con esta configuración antes de habilitar.")

    _persist_param_updates(spec["categoria"], updates)
    log_event(
        request,
        accion=spec["accion"],
        entidad="ParametroSistema",
        entidad_id="smtp",
        resultado="ok",
        detalle=updates,
    )
    messages.success(request, "Configuración de SMTP actualizada.")


def _handle_pasarela_parametros(request, spec, operation):
    updates = {
        "pasarela_proveedor": (request.POST.get("pasarela_proveedor") or "").strip(),
        "pasarela_public_key": (request.POST.get("pasarela_public_key") or "").strip(),
        "pasarela_secret_key": (request.POST.get("pasarela_secret_key") or "").strip(),
        "pasarela_enabled": "1" if (request.POST.get("pasarela_enabled") or "") in {"on", "1", "true", "TRUE"} else "0",
    }

    try:
        updates["pasarela_proveedor"] = validate_text_general(
            updates["pasarela_proveedor"],
            "Proveedor de pasarela",
            min_length=2,
            max_length=40,
        )
        updates["pasarela_public_key"] = validate_text_general(
            updates["pasarela_public_key"],
            "Public key",
            min_length=8,
            max_length=120,
        )
        updates["pasarela_secret_key"] = validate_text_general(
            updates["pasarela_secret_key"],
            "Secret key",
            allow_blank=True,
            min_length=0,
            max_length=120,
        )
    except Exception as exc:
        messages.error(request, str(exc))
        return
    fingerprint = _integration_fingerprint(
        {
            "pasarela_proveedor": updates["pasarela_proveedor"],
            "pasarela_public_key": updates["pasarela_public_key"],
            "pasarela_secret_key": updates["pasarela_secret_key"],
        }
    )

    if operation == "rotate":
        version = _next_rotation_version("pasarela_rotation_version")
        rotated_at = timezone.now().isoformat()
        updates["pasarela_secret_key"] = f"sk_rot_{secrets.token_urlsafe(18)}"
        updates["pasarela_enabled"] = "0"
        updates["pasarela_rotation_version"] = str(version)
        updates["pasarela_rotated_at"] = rotated_at
        updates["pasarela_test_status"] = "pendiente"
        updates["pasarela_test_message"] = "Rotacion de credenciales aplicada. Ejecuta una nueva prueba de pasarela."
        updates["pasarela_test_fingerprint"] = ""
        updates["pasarela_tested_at"] = ""

        _persist_param_updates(spec["categoria"], updates)
        log_event(
            request,
            accion="GOBIERNO::PARAMETROS_PASARELA_ROTATE",
            entidad="ParametroSistema",
            entidad_id="pasarela",
            resultado="ok",
            detalle={
                "pasarela_proveedor": updates["pasarela_proveedor"],
                "rotation_version": version,
                "rotated_at": rotated_at,
            },
        )
        messages.success(
            request, f"Credenciales de pasarela rotadas (version {version}).")
        return

    if operation == "test":
        ok, message = _validate_pasarela_config(updates)
        _save_integration_test_result(
            categoria=ParametroSistema.CATEGORIA_PASARELA,
            prefix="pasarela",
            ok=ok,
            message=message,
            fingerprint=fingerprint,
        )
        log_event(
            request,
            accion="GOBIERNO::PARAMETROS_PASARELA_TEST",
            entidad="ParametroSistema",
            entidad_id="pasarela",
            resultado="ok" if ok else "error",
            detalle={
                "pasarela_proveedor": updates["pasarela_proveedor"],
                "message": message,
            },
        )
        if ok:
            messages.success(
                request, "Prueba de pasarela exitosa. Ya puedes habilitar la integración.")
        else:
            messages.error(request, f"Prueba de pasarela fallida: {message}")
        return

    if updates["pasarela_enabled"] == "1" and not _integration_can_enable("pasarela", fingerprint):
        updates["pasarela_enabled"] = "0"
        log_event(
            request,
            accion="GOBIERNO::PARAMETROS_PASARELA_ENABLE_DENIED",
            entidad="ParametroSistema",
            entidad_id="pasarela",
            resultado="denied",
            detalle={
                "reason": "test_required",
                "pasarela_proveedor": updates["pasarela_proveedor"],
            },
        )
        messages.error(
            request, "Debes ejecutar una prueba de pasarela exitosa con esta configuración antes de habilitar.")

    _persist_param_updates(spec["categoria"], updates)
    log_event(
        request,
        accion=spec["accion"],
        entidad="ParametroSistema",
        entidad_id="pasarela",
        resultado="ok",
        detalle=updates,
    )
    messages.success(request, "Configuración de pasarela actualizada.")


def _persist_param_updates(categoria, updates):
    for key, value in updates.items():
        ParametroSistema.objects.update_or_create(
            clave=key,
            defaults={
                "categoria": categoria,
                "valor": value,
                "activo": True,
            },
        )


def _save_integration_test_result(categoria, prefix, ok, message, fingerprint):
    now_iso = timezone.now().isoformat()
    values = {
        f"{prefix}_test_status": "ok" if ok else "error",
        f"{prefix}_test_message": message,
        f"{prefix}_test_fingerprint": fingerprint,
        f"{prefix}_tested_at": now_iso,
    }
    _persist_param_updates(categoria, values)


def _integration_can_enable(prefix, fingerprint):
    values = {row.clave: row.valor for row in ParametroSistema.objects.filter(
        clave__startswith=f"{prefix}_test_")}
    return values.get(f"{prefix}_test_status") == "ok" and values.get(f"{prefix}_test_fingerprint") == fingerprint


def _integration_fingerprint(data):
    raw = json.dumps(data, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _next_rotation_version(param_key):
    value = ParametroSistema.objects.filter(
        clave=param_key).values_list("valor", flat=True).first() or "0"
    try:
        current = int(value)
    except (TypeError, ValueError):
        current = 0
    return current + 1


def _validate_smtp_config(updates):
    host = updates.get("smtp_host", "")
    port_raw = updates.get("smtp_port", "")
    sender = updates.get("smtp_from", "")
    if not host or " " in host:
        return False, "Host SMTP inválido."
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        return False, "Puerto SMTP inválido."
    if port < 1 or port > 65535:
        return False, "Puerto SMTP fuera de rango."
    try:
        validate_email_value(sender, "Remitente SMTP")
    except Exception as exc:
        return False, str(exc)
    # Intento de conexión real al servidor SMTP (timeout corto para no bloquear)
    try:
        with smtplib.SMTP(host, port, timeout=5) as conn:
            conn.noop()
    except Exception as exc:
        return False, f"Sin conexión al servidor SMTP ({host}:{port}): {exc}"
    return True, f"Conexión SMTP verificada con {host}:{port}."


def _validate_pasarela_config(updates):
    proveedor = updates.get("pasarela_proveedor", "")
    public_key = updates.get("pasarela_public_key", "")
    if not proveedor:
        return False, "Proveedor de pasarela requerido."
    if not public_key or len(public_key) < 8:
        return False, "Public key inválida."
    if not public_key.startswith("pk_"):
        return False, "Public key debe iniciar con pk_."
    return True, "Credenciales de pasarela validadas en modo simulación."


def _load_parametros_values():
    values = {row.clave: row.valor for row in ParametroSistema.objects.all()}
    return {
        "institucion_nombre": values.get("institucion_nombre", ""),
        "institucion_rfc": values.get("institucion_rfc", ""),
        "institucion_direccion": values.get("institucion_direccion", ""),
        "periodo_activo": values.get("periodo_activo", ""),
        "periodo_inicio": values.get("periodo_inicio", ""),
        "periodo_fin": values.get("periodo_fin", ""),
        "smtp_host": values.get("smtp_host", ""),
        "smtp_port": values.get("smtp_port", ""),
        "smtp_user": values.get("smtp_user", ""),
        "smtp_from": values.get("smtp_from", ""),
        "smtp_password": values.get("smtp_password", ""),
        "smtp_enabled": values.get("smtp_enabled", "0"),
        "smtp_rotation_version": values.get("smtp_rotation_version", "0"),
        "smtp_rotated_at": values.get("smtp_rotated_at", ""),
        "smtp_test_status": values.get("smtp_test_status", "pendiente"),
        "smtp_test_message": values.get("smtp_test_message", "Sin pruebas registradas."),
        "smtp_tested_at": values.get("smtp_tested_at", ""),
        "pasarela_proveedor": values.get("pasarela_proveedor", ""),
        "pasarela_public_key": values.get("pasarela_public_key", ""),
        "pasarela_secret_key": values.get("pasarela_secret_key", ""),
        "pasarela_enabled": values.get("pasarela_enabled", "0"),
        "pasarela_rotation_version": values.get("pasarela_rotation_version", "0"),
        "pasarela_rotated_at": values.get("pasarela_rotated_at", ""),
        "pasarela_test_status": values.get("pasarela_test_status", "pendiente"),
        "pasarela_test_message": values.get("pasarela_test_message", "Sin pruebas registradas."),
        "pasarela_tested_at": values.get("pasarela_tested_at", ""),
    }


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def gobierno_respaldos(request):
    if request.method == "POST":
        accion = (request.POST.get("accion") or "").strip().lower()
        if accion == "generar":
            notas = (request.POST.get("notas") or "").strip()
            try:
                notas = validate_text_general(
                    notas,
                    "Notas",
                    allow_blank=True,
                    min_length=0,
                    max_length=400,
                )
            except Exception as exc:
                messages.error(request, str(exc))
                return redirect("/panel/gobierno/respaldos/")
            payload = _build_respaldo_payload()
            payload_raw = json.dumps(
                payload, sort_keys=True, ensure_ascii=True)
            checksum = hashlib.sha256(payload_raw.encode("utf-8")).hexdigest()
            nombre = f"backup-{timezone.now().strftime('%Y%m%d-%H%M%S')}"

            respaldo = RespaldoSistema.objects.create(
                nombre=nombre,
                estado=RespaldoSistema.ESTADO_GENERADO,
                checksum=checksum,
                payload=payload,
                notas=notas,
                generado_por=request.user,
            )
            log_event(
                request,
                accion="GOBIERNO::RESPALDO_GENERAR",
                entidad="RespaldoSistema",
                entidad_id=respaldo.pk,
                resultado="ok",
                detalle={
                    "nombre": respaldo.nombre,
                    "checksum": respaldo.checksum,
                    "parametros": len(payload.get("parametros", [])),
                    "eventos": payload.get("auditoria", {}).get("total_eventos", 0),
                },
            )
            messages.success(request, f"Respaldo generado: {respaldo.nombre}")

        elif accion == "restaurar":
            respaldo_id = (request.POST.get("respaldo_id") or "").strip()
            confirmacion = (request.POST.get(
                "confirmar") or "").strip().upper()
            if confirmacion != "SI":
                messages.error(
                    request, "Confirma la restauración escribiendo SI.")
            else:
                respaldo = RespaldoSistema.objects.filter(
                    pk=respaldo_id).first()
                if not respaldo:
                    messages.error(request, "Respaldo no encontrado.")
                else:
                    with transaction.atomic():
                        for item in respaldo.payload.get("parametros", []):
                            ParametroSistema.objects.update_or_create(
                                clave=item.get("clave", ""),
                                defaults={
                                    "categoria": item.get("categoria") or ParametroSistema.CATEGORIA_INSTITUCION,
                                    "valor": item.get("valor", ""),
                                    "activo": bool(item.get("activo", True)),
                                },
                            )
                        respaldo.estado = RespaldoSistema.ESTADO_RESTAURADO
                        respaldo.restaurado_en = timezone.now()
                        respaldo.save(
                            update_fields=["estado", "restaurado_en"])

                    log_event(
                        request,
                        accion="GOBIERNO::RESPALDO_RESTAURAR",
                        entidad="RespaldoSistema",
                        entidad_id=respaldo.pk,
                        resultado="ok",
                        detalle={
                            "nombre": respaldo.nombre,
                            "checksum": respaldo.checksum,
                            "parametros_restaurados": len(respaldo.payload.get("parametros", [])),
                        },
                    )
                    messages.success(
                        request, f"Respaldo restaurado: {respaldo.nombre}")
        else:
            messages.error(request, "Acción de respaldo inválida.")
        return redirect("ui:gobierno_respaldos")

    modo = request.GET.get("modo", "historial")
    pagina = request.GET.get("page", 1)
    respaldos_qs = RespaldoSistema.objects.select_related(
        "generado_por").order_by("-generado_en")
    respaldos_paginator = Paginator(respaldos_qs, 3)
    respaldos_page = respaldos_paginator.get_page(pagina)
    return render(
        request,
        "ui/gobierno_respaldos.html",
        {
            "modo": modo,
            "respaldos_page": respaldos_page,
            "auditoria_total": EventoAuditoria.objects.count(),
            "parametros_total": ParametroSistema.objects.count(),
            "active": "gobierno_respaldos",
        },
    )


def _build_respaldo_payload():
    parametros = list(
        ParametroSistema.objects.order_by("categoria", "clave").values(
            "categoria",
            "clave",
            "valor",
            "activo",
        )
    )
    return {
        "generado_en": timezone.now().isoformat(),
        "parametros": parametros,
        "auditoria": {
            "total_eventos": EventoAuditoria.objects.count(),
        },
    }


# ── Submódulo Usuarios ────────────────────────────────────────────────────────

@login_required(login_url="/acceso/")
@role_required("Superusuario")
def gobierno_usuarios_lista(request):
    User = get_user_model()
    qs = User.objects.order_by("username")
    paginator = Paginator(qs, 3)
    page_obj = paginator.get_page(request.GET.get("p", 1))
    return render(request, "ui/gobierno_usuarios_lista.html", {"page_obj": page_obj})


@login_required(login_url="/acceso/")
@role_required("Superusuario")
def gobierno_usuarios_nuevo(request):
    from apps.accounts.forms import UsuarioCreateFormUI
    from apps.accounts.models import Rol, UsuarioRol
    from apps.accounts.services.username_generator import (
        generate_institutional_username,
        get_institutional_prefix,
    )

    roles = Rol.objects.filter(activo=True).order_by("nombre")

    if request.method == "POST":
        form = UsuarioCreateFormUI(request.POST)
        rol_id = request.POST.get("rol_inicial", "").strip()
        matricula = request.POST.get("matricula_alumno", "").strip()

        # Validar rol seleccionado
        rol = None
        rol_error = None
        if rol_id:
            try:
                rol = Rol.objects.get(pk=rol_id, activo=True)
            except Rol.DoesNotExist:
                rol_error = "El rol seleccionado no es válido."
        else:
            rol_error = "Debes seleccionar un rol inicial."

        if form.is_valid() and rol and not rol_error:
            # Determinar username según tipo de rol
            prefix = get_institutional_prefix(rol.codigo)
            username = None

            if prefix:
                # Roles con prefijo institucional: auto-generar
                username = generate_institutional_username(rol.codigo)
            elif rol.codigo == "ALUMNO":
                # Username = matrícula del alumno (obligatorio)
                if not matricula:
                    form.add_error(
                        None, "La matrícula es obligatoria para el rol Alumno.")
                else:
                    from django.contrib.auth import get_user_model as _gum
                    if _gum().objects.filter(username=matricula).exists():
                        form.add_error(
                            None,
                            f"Ya existe un usuario con la matrícula '{matricula}'.",
                        )
                    else:
                        username = matricula
            else:
                # Otro rol personalizado: derivar del correo (fallback único)
                email = form.cleaned_data.get("email", "")
                base = (email.split("@")[0] if email else "usuario")[:30]
                from django.contrib.auth import get_user_model as _gum
                _User = _gum()
                candidate = base
                counter = 1
                while _User.objects.filter(username=candidate).exists():
                    candidate = f"{base}{counter}"
                    counter += 1
                username = candidate

            # Si hubo errores (form.add_error), re-renderizar
            if form.errors or username is None:
                return render(
                    request,
                    "ui/gobierno_usuarios_form.html",
                    {
                        "form": form,
                        "modo": "alta",
                        "roles": roles,
                        "rol_error": rol_error,
                        "rol_id_sel": rol_id,
                        "matricula": matricula,
                    },
                )

            with transaction.atomic():
                user = form.save(commit=False)
                user.username = username
                user.save()
                form.save_m2m()
                UsuarioRol.objects.get_or_create(
                    usuario=user, defaults={"rol": rol})

            log_event(
                request,
                accion="GOBIERNO::USUARIO_ALTA",
                entidad="User",
                entidad_id=str(user.pk),
                resultado="ok",
                detalle={"username": user.username, "rol": rol.codigo},
            )
            messages.success(
                request, f"Usuario '{user.username}' creado correctamente."
            )
            return redirect("/panel/gobierno/usuarios/")
    else:
        form = UsuarioCreateFormUI()
        rol_id = ""
        matricula = ""
        rol_error = None

    return render(
        request,
        "ui/gobierno_usuarios_form.html",
        {
            "form": form,
            "modo": "alta",
            "roles": roles,
            "rol_error": rol_error,
            "rol_id_sel": rol_id,
            "matricula": matricula if request.method == "POST" else "",
        },
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario")
def gobierno_usuarios_editar(request, pk):
    from apps.accounts.forms import UsuarioEditForm
    User = get_user_model()
    usuario = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = UsuarioEditForm(request.POST, instance=usuario)
        if form.is_valid():
            with transaction.atomic():
                form.save()
            log_event(
                request,
                accion="GOBIERNO::USUARIO_EDITAR",
                entidad="User",
                entidad_id=str(pk),
                resultado="ok",
                detalle={"username": usuario.username},
            )
            messages.success(
                request, f"Usuario '{usuario.username}' actualizado.")
            return redirect("/panel/gobierno/usuarios/")
    else:
        form = UsuarioEditForm(instance=usuario)
    return render(
        request,
        "ui/gobierno_usuarios_form.html",
        {"form": form, "modo": "edicion", "usuario": usuario},
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario")
def gobierno_usuarios_estado(request, pk):
    if request.method != "POST":
        return redirect("/panel/gobierno/usuarios/")
    User = get_user_model()
    usuario = get_object_or_404(User, pk=pk)
    nuevo_estado = not usuario.is_active
    usuario.is_active = nuevo_estado
    usuario.save(update_fields=["is_active"])
    accion_str = "activado" if nuevo_estado else "desactivado"
    log_event(
        request,
        accion="GOBIERNO::USUARIO_ESTADO",
        entidad="User",
        entidad_id=str(pk),
        resultado="ok",
        detalle={"username": usuario.username, "is_active": nuevo_estado},
    )
    messages.success(request, f"Usuario '{usuario.username}' {accion_str}.")
    return redirect("/panel/gobierno/usuarios/")


# ── Submódulo Roles ───────────────────────────────────────────────────────────

@login_required(login_url="/acceso/")
@role_required("Superusuario")
def gobierno_roles_lista(request):
    from apps.accounts.models import UsuarioRol
    qs = UsuarioRol.objects.select_related("usuario", "rol").order_by(
        "rol__nombre", "usuario__username"
    )
    paginator = Paginator(qs, 3)
    page_obj = paginator.get_page(request.GET.get("p", 1))
    return render(request, "ui/gobierno_roles_lista.html", {"page_obj": page_obj})


@login_required(login_url="/acceso/")
@role_required("Superusuario")
def gobierno_roles_asignar(request):
    from apps.accounts.models import UsuarioRol
    User = get_user_model()
    roles = Rol.objects.order_by("nombre")
    usuarios = User.objects.filter(is_active=True).order_by("username")

    if request.method == "POST":
        usuario_id = (request.POST.get("usuario_id") or "").strip()
        rol_id = (request.POST.get("rol_id") or "").strip()

        if not usuario_id or not rol_id:
            messages.error(request, "Selecciona usuario y rol.")
            return render(request, "ui/gobierno_roles_form.html",
                          {"roles": roles, "usuarios": usuarios})

        usuario = get_object_or_404(User, pk=usuario_id)
        rol = get_object_or_404(Rol, pk=rol_id)

        _, created = UsuarioRol.objects.get_or_create(usuario=usuario, rol=rol)
        if not created:
            messages.warning(request,
                             f"'{usuario.username}' ya tiene el rol '{rol.nombre}'.")
            return render(request, "ui/gobierno_roles_form.html",
                          {"roles": roles, "usuarios": usuarios})

        log_event(
            request,
            accion="GOBIERNO::ROL_ASIGNAR",
            entidad="UsuarioRol",
            entidad_id=str(usuario.pk),
            resultado="ok",
            detalle={"username": usuario.username, "rol": rol.nombre},
        )
        messages.success(request,
                         f"Rol '{rol.nombre}' asignado a '{usuario.username}'.")
        return redirect("/panel/gobierno/roles/")

    return render(request, "ui/gobierno_roles_form.html",
                  {"roles": roles, "usuarios": usuarios})


@login_required(login_url="/acceso/")
@role_required("Superusuario")
def gobierno_roles_retirar(request, pk):
    if request.method != "POST":
        return redirect("/panel/gobierno/roles/")
    from apps.accounts.models import UsuarioRol
    asignacion = get_object_or_404(UsuarioRol, pk=pk)
    username = asignacion.usuario.username
    nombre_rol = asignacion.rol.nombre
    asignacion.delete()
    log_event(
        request,
        accion="GOBIERNO::ROL_RETIRAR",
        entidad="UsuarioRol",
        entidad_id=str(pk),
        resultado="ok",
        detalle={"username": username, "rol": nombre_rol},
    )
    messages.success(request,
                     f"Rol '{nombre_rol}' retirado de '{username}'.")
    return redirect("/panel/gobierno/roles/")
