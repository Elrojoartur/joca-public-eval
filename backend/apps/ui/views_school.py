import re
from io import BytesIO
from datetime import time
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models.deletion import RestrictedError
from django.db.models import Count, ExpressionWrapper, F, IntegerField, OuterRef, Prefetch, Q, Subquery
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from apps.school.models import (
    Alumno,
    Grupo,
    GrupoHorario,
    Inscripcion,
    Calificacion,
    ActaCierre,
    Curso,
    Periodo,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.services.audit import log_event
from apps.sales.models import OrdenPOS
from apps.sales.services.enrollment_sales import ensure_inscripcion_sale
from apps.ui.catalogs.cursos import load_cursos
from apps.ui.input_validation import validate_periodo_value, validate_text_general

from .forms import AlumnoForm, AlumnoDomicilioForm, InscripcionInicialForm, GrupoForm, CalificacionForm
from .views_core import (
    role_required,
    get_user_role,
    _is_director,
    registrar_auditoria,
    _parse_date,
    build_group_catalog,
)

PERIODO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _flash_form_errors(request, form):
    """Muestra cada error de validación del formulario como mensaje en pantalla."""
    for field, errors in form.errors.items():
        if field == "__all__":
            label = "Formulario"
        else:
            form_field = form.fields.get(field)
            label = form_field.label if form_field and form_field.label else field
        for err in errors:
            messages.error(request, f"{label}: {err}")


def sync_horarios(grupo, horarios):
    """
    Sincroniza horarios normalizados de un grupo.
    Estrategia simple: borra y recrea.
    """
    GrupoHorario.objects.filter(grupo=grupo).delete()
    for h in horarios:
        GrupoHorario.objects.create(
            grupo=grupo,
            dia=h["dia"],
            hora_inicio=h["hora_inicio"],
            hora_fin=h["hora_fin"],
            activo=True,
        )


def _render_boleta_pdf(alumno, periodo: str, inscripcion, calificacion):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 72

    def _hr(y_pos, margin=72):
        """Dibuja una línea separadora horizontal."""
        pdf.setStrokeColorRGB(0.8, 0.8, 0.8)
        pdf.setLineWidth(0.5)
        pdf.line(margin, y_pos, width - margin, y_pos)
        pdf.setStrokeColorRGB(0, 0, 0)
        return y_pos - 10

    # ── Encabezado institucional ──────────────────────────────────────────────
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(72, y, "CCENT Nikola Tesla")
    y -= 18
    pdf.setFont("Helvetica", 9)
    pdf.drawString(72, y, "Boleta de Calificaciones")
    y -= 20
    y = _hr(y)

    # ── Datos del alumno ──────────────────────────────────────────────────────
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(72, y, "Datos del alumno")
    y -= 16
    pdf.setFont("Helvetica", 10)

    nombre_completo = (alumno.nombre_completo or "").strip()

    pdf.drawString(72, y, f"Matrícula:        {alumno.matricula}")
    y -= 14
    pdf.drawString(72, y, f"Nombre completo:  {nombre_completo or '—'}")
    y -= 20
    y = _hr(y)

    # ── Datos académicos ──────────────────────────────────────────────────────
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(72, y, "Datos académicos")
    y -= 16
    pdf.setFont("Helvetica", 10)

    if inscripcion and getattr(inscripcion, "grupo", None):
        grupo = inscripcion.grupo
        curso = getattr(grupo, "curso_ref", None)
        periodo_obj = getattr(grupo, "periodo_ref", None)
        curso_txt = (
            f"{curso.codigo} – {curso.nombre}" if curso else "Sin curso registrado"
        )
        periodo_txt = periodo_obj.codigo if periodo_obj else periodo
        grupo_txt = f"Grupo {grupo.pk}"

        horarios_list = getattr(grupo, "horarios_activos", None)
        if horarios_list is None:
            horarios_list = list(
                grupo.horarios.filter(activo=True).order_by(
                    "dia", "hora_inicio")
            )
        if horarios_list:
            horario_txt = "  /  ".join(
                f"{h.get_dia_display()} {h.hora_inicio.strftime('%H:%M')}-{h.hora_fin.strftime('%H:%M')}"
                for h in horarios_list
            )
        else:
            horario_txt = "Horario por definir"
    else:
        curso_txt = "Sin curso registrado"
        periodo_txt = periodo
        grupo_txt = "Sin grupo asignado"
        horario_txt = "Horario por definir"

    pdf.drawString(72, y, f"Curso:            {curso_txt}")
    y -= 14
    pdf.drawString(72, y, f"Grupo:            {grupo_txt}")
    y -= 14
    pdf.drawString(72, y, f"Periodo:          {periodo_txt}")
    y -= 14
    pdf.drawString(72, y, f"Horario:          {horario_txt}")
    y -= 20
    y = _hr(y)

    # ── Calificación ──────────────────────────────────────────────────────────
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(72, y, "Calificación")
    y -= 16
    pdf.setFont("Helvetica", 10)

    if calificacion and calificacion.valor is not None:
        cal_txt = str(calificacion.valor)
        fecha_cap = (
            calificacion.capturado_en.strftime("%d/%m/%Y")
            if calificacion.capturado_en
            else "—"
        )
    else:
        cal_txt = "Sin calificación registrada"
        fecha_cap = "—"

    pdf.drawString(72, y, f"Calificación:     {cal_txt}")
    y -= 14
    pdf.drawString(72, y, f"Capturada:        {fecha_cap}")
    y -= 20
    y = _hr(y)

    # ── Fecha de emisión ──────────────────────────────────────────────────────
    pdf.setFont("Helvetica", 9)
    pdf.setFillColorRGB(0.5, 0.5, 0.5)
    fecha_emision = timezone.localdate().strftime("%d/%m/%Y")
    pdf.drawString(72, y, f"Fecha de emisión: {fecha_emision}")

    pdf.showPage()
    pdf.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = f"boleta_{alumno.matricula}_{periodo}.pdf".replace(" ", "_")
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def escolar(request):
    cards = [
        {
            "title": "Alumnos",
            "desc": "Altas y edición de alumnos.",
            "href": "/panel/escolar/alumnos/",
        },
        {
            "title": "Grupos",
            "desc": "Gestión de grupos y cupos.",
            "href": "/panel/escolar/grupos/",
        },
        {
            "title": "Inscripciones",
            "desc": "Asignación de alumnos a grupos.",
            "href": "/panel/escolar/inscripciones/",
        },
        {
            "title": "Calificaciones",
            "desc": "Registro de calificaciones.",
            "href": "/panel/escolar/calificaciones/",
        },
    ]

    # ── Indicadores operativos ────────────────────────────────────────────
    # Grupos con anotaciones en una sola query
    grupos_qs = (
        Grupo.objects
        .filter(estado=Grupo.ESTADO_ACTIVO)
        .annotate(
            inscritos_activos=Count(
                "inscripciones",
                filter=Q(inscripciones__estado=Inscripcion.ESTADO_ACTIVA),
                distinct=True,
            ),
            tiene_horario=Count(
                "horarios",
                filter=Q(horarios__activo=True),
                distinct=True,
            ),
            tiene_acta=Count(
                "actas_cierre",
                distinct=True,
            ),
        )
    )

    grupos_activos_total = grupos_qs.count()

    grupos_llenos = 0
    grupos_con_lugar = 0
    grupos_sin_horario = 0
    grupos_sin_acta = 0

    for g in grupos_qs.only("cupo").iterator():
        disponible = int(g.cupo) - int(g.inscritos_activos)
        if disponible <= 0:
            grupos_llenos += 1
        else:
            grupos_con_lugar += 1
        if g.tiene_horario == 0:
            grupos_sin_horario += 1
        if g.tiene_acta == 0:
            grupos_sin_acta += 1

    # Alumnos con inscripción activa (distintos)
    alumnos_inscritos = (
        Inscripcion.objects
        .filter(estado=Inscripcion.ESTADO_ACTIVA)
        .values("alumno_id")
        .distinct()
        .count()
    )

    # Inscripciones activas sin calificación
    insc_sin_calificacion = (
        Inscripcion.objects
        .filter(estado=Inscripcion.ESTADO_ACTIVA)
        .exclude(calificacion__isnull=False)
        .count()
    )

    # Grupos activos con alumnos pero sin acta de cierre
    grupos_pendientes_acta = grupos_sin_acta

    kpi = {
        "alumnos_inscritos": alumnos_inscritos,
        "grupos_activos": grupos_activos_total,
        "grupos_llenos": grupos_llenos,
        "grupos_con_lugar": grupos_con_lugar,
        "grupos_sin_horario": grupos_sin_horario,
        "grupos_pendientes_acta": grupos_pendientes_acta,
        "insc_sin_calificacion": insc_sin_calificacion,
    }

    return render(
        request,
        "ui/escolar.html",
        {"cards": cards, "kpi": kpi},
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def escolar_alumnos(request):
    debug_post = False

    modo = (request.GET.get("modo") or "form").strip().lower()
    if modo not in {"form", "lista"}:
        modo = "form"

    edit_id = request.GET.get("edit")
    is_edit = bool(edit_id)
    instance = Alumno.objects.filter(pk=edit_id).first() if is_edit else None

    filtro_texto = (request.GET.get("q") or "").strip()
    creado_desde = _parse_date(request.GET.get("desde"))
    creado_hasta = _parse_date(request.GET.get("hasta"))

    if request.method == "POST":
        debug_post = True

        if request.POST.get("delete_id"):
            alumno_id = request.POST.get("delete_id")
            try:
                deleted, _ = Alumno.objects.filter(pk=alumno_id).delete()
            except RestrictedError:
                messages.error(
                    request,
                    "No se puede eliminar el alumno porque tiene un domicilio registrado. "
                    "Edita el expediente y elimina el domicilio antes de borrar al alumno.",
                )
                return redirect("/panel/escolar/alumnos/?modo=lista")
            if deleted:
                registrar_auditoria(
                    request,
                    "ESCOLAR::ALUMNO_DELETE",
                    "Alumno",
                    alumno_id,
                    "ok",
                    {"alumno_id": alumno_id},
                )
                messages.success(request, "Alumno eliminado.")
            else:
                messages.error(request, "No se encontró el alumno a eliminar.")
            return redirect("/panel/escolar/alumnos/?modo=lista")

        if is_edit:
            instance = Alumno.objects.filter(pk=edit_id).first()
            domicilio_instance = getattr(
                instance, "domicilio", None) if instance else None
            form = AlumnoForm(request.POST, instance=instance)
            domicilio_form = AlumnoDomicilioForm(
                request.POST, instance=domicilio_instance)
        else:
            form = AlumnoForm(request.POST)
            domicilio_form = AlumnoDomicilioForm(request.POST)

        inscripcion_form = InscripcionInicialForm(request.POST)

        if form.is_valid() and domicilio_form.is_valid():
            if not inscripcion_form.is_valid():
                _flash_form_errors(request, inscripcion_form)
                modo = "form"
            else:
                try:
                    alumno = form.save_full_expediente(
                        domicilio_form, inscripcion_form)

                    # Generar orden de venta si se creó/actualizó una inscripción activa
                    insc_activa = Inscripcion.objects.filter(
                        alumno=alumno, estado=Inscripcion.ESTADO_ACTIVA
                    ).first()
                    if insc_activa:
                        ensure_inscripcion_sale(
                            insc_activa, requiere_factura=False)

                    accion = (
                        "ESCOLAR::ALUMNO_UPDATE" if is_edit else "ESCOLAR::ALUMNO_CREATE"
                    )
                    registrar_auditoria(
                        request,
                        accion,
                        "Alumno",
                        alumno.pk,
                        "ok",
                        {
                            "matricula": alumno.matricula,
                            "correo": alumno.correo,
                        },
                    )
                    if is_edit:
                        messages.success(
                            request, "Expediente de alumno actualizado.")
                        return redirect("/panel/escolar/alumnos/?modo=lista")
                    else:
                        messages.success(
                            request,
                            f"Alumno {alumno.matricula} creado correctamente. Puedes inscribirlo ahora.",
                        )
                        return redirect(
                            f"/panel/escolar/alumnos/?modo=lista&nuevo_alumno={alumno.pk}"
                        )
                except Exception as e:
                    messages.error(request, f"Error al guardar: {e}")
                    modo = "form"
        else:
            _flash_form_errors(request, form)
            _flash_form_errors(request, domicilio_form)
            modo = "form"
    else:
        domicilio_instance = getattr(
            instance, "domicilio", None) if instance else None
        form = AlumnoForm(instance=instance) if is_edit else AlumnoForm()
        domicilio_form = (
            AlumnoDomicilioForm(instance=domicilio_instance)
            if is_edit
            else AlumnoDomicilioForm()
        )
        _insc_grupo_id = None
        if is_edit and instance:
            _insc_activa = Inscripcion.objects.filter(
                alumno=instance, estado=Inscripcion.ESTADO_ACTIVA
            ).first()
            _insc_grupo_id = _insc_activa.grupo_id if _insc_activa else None
        inscripcion_form = InscripcionInicialForm(
            initial={"grupo": _insc_grupo_id}
        )

    grupos_activos = (
        Grupo.objects.filter(estado=Grupo.ESTADO_ACTIVO)
        .select_related("curso_ref", "periodo_ref")
        .prefetch_related(
            Prefetch(
                "horarios",
                queryset=GrupoHorario.objects.filter(
                    activo=True).order_by("dia", "hora_inicio"),
                to_attr="horarios_lista",
            )
        )
        .order_by("periodo_ref__codigo", "curso_ref__nombre")
    )

    # Determina el grupo pre-seleccionado para el template (int o None)
    _raw_grupo = (
        inscripcion_form.data.get("grupo")
        if inscripcion_form.is_bound
        else (inscripcion_form.initial.get("grupo") or None)
    )
    try:
        inscripcion_grupo_id = int(_raw_grupo) if _raw_grupo else None
    except (ValueError, TypeError):
        inscripcion_grupo_id = None

    alumnos_qs = Alumno.objects.prefetch_related(
        Prefetch(
            "inscripciones",
            queryset=(
                Inscripcion.objects
                .filter(estado=Inscripcion.ESTADO_ACTIVA)
                .select_related(
                    "grupo",
                    "grupo__curso_ref",
                    "grupo__periodo_ref",
                )
                .prefetch_related(
                    Prefetch(
                        "grupo__horarios",
                        queryset=GrupoHorario.objects.filter(
                            activo=True).order_by("dia", "hora_inicio"),
                        to_attr="horarios_activos",
                    )
                )
            ),
            to_attr="inscripciones_activas",
        )
    )

    if filtro_texto:
        alumnos_qs = alumnos_qs.filter(
            Q(matricula__icontains=filtro_texto)
            | Q(nombres__icontains=filtro_texto)
            | Q(apellido_paterno__icontains=filtro_texto)
            | Q(apellido_materno__icontains=filtro_texto)
            | Q(correo__icontains=filtro_texto)
        )

    alumnos_qs = alumnos_qs.order_by("matricula")

    paginator = Paginator(alumnos_qs, 2)
    page_number = request.GET.get("page")
    alumnos = paginator.get_page(page_number)

    nuevo_alumno_pk = (request.GET.get("nuevo_alumno") or "").strip()
    nuevo_alumno_obj = (
        Alumno.objects.filter(pk=nuevo_alumno_pk).first()
        if nuevo_alumno_pk
        else None
    )

    return render(
        request,
        "ui/escolar_alumnos.html",
        {
            "form": form,
            "domicilio_form": domicilio_form,
            "inscripcion_form": inscripcion_form,
            "grupos_activos": grupos_activos,
            "inscripcion_grupo_id": inscripcion_grupo_id,
            "alumnos": alumnos,
            "edit_id": edit_id if is_edit else None,
            "filtro_texto": filtro_texto,
            "creado_desde": creado_desde,
            "creado_hasta": creado_hasta,
            "debug_post": debug_post,
            "modo": "form" if is_edit else modo,
            "nuevo_alumno": nuevo_alumno_obj,
        },
    )


def horarios_default_por_tipo_turno(tipo_horario: str, turno: str):
    """
    Devuelve horarios en formato normalizado (para GrupoHorario):
    [{'dia': 'SAB', 'hora_inicio': time(...), 'hora_fin': time(...)}]
    """
    if tipo_horario == "SAB":
        return [
            {"dia": "SAB", "hora_inicio": time(9, 0), "hora_fin": time(14, 0)},
        ]

    if turno == "AM":
        return [
            {"dia": "LUN", "hora_inicio": time(9, 0), "hora_fin": time(11, 0)},
            {"dia": "MIE", "hora_inicio": time(9, 0), "hora_fin": time(11, 0)},
            {"dia": "VIE", "hora_inicio": time(9, 0), "hora_fin": time(11, 0)},
        ]

    return [
        {"dia": "LUN", "hora_inicio": time(19, 0), "hora_fin": time(21, 0)},
        {"dia": "MIE", "hora_inicio": time(19, 0), "hora_fin": time(21, 0)},
        {"dia": "VIE", "hora_inicio": time(19, 0), "hora_fin": time(21, 0)},
    ]


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def escolar_grupos_generar(request):
    if request.method != "POST":
        return redirect("/panel/escolar/grupos/")

    periodo = request.POST.get("periodo") or ""
    try:
        periodo = validate_periodo_value(periodo)
    except Exception as exc:
        messages.error(request, str(exc))
        return redirect("/panel/escolar/grupos/")

    cursos = load_cursos()
    created = 0
    for c in cursos:
        slug = c.get("slug") or c.get("id")
        if not slug:
            continue

        target_groups = [
            (Grupo.HORARIO_SEM, Grupo.TURNO_AM),
            (Grupo.HORARIO_SEM, Grupo.TURNO_PM),
            (Grupo.HORARIO_SAB, Grupo.TURNO_SAB),
        ]
        for tipo, turno in target_groups:
            horarios = horarios_default_por_tipo_turno(tipo, turno)
            curso_ref, _ = Curso.objects.get_or_create(
                codigo=slug,
                defaults={
                    "nombre": slug.replace("-", " ")[:120] or slug,
                    "activo": True,
                },
            )
            periodo_ref, _ = Periodo.objects.get_or_create(
                codigo=periodo,
                defaults=Periodo.defaults_for(periodo),
            )
            obj, was_created = Grupo.objects.get_or_create(
                curso_ref=curso_ref,
                periodo_ref=periodo_ref,
                tipo_horario=tipo,
                turno=turno,
                defaults={
                    "cupo": 20,
                    "estado": Grupo.ESTADO_ACTIVO,
                },
            )
            if not obj.horarios.exists():
                sync_horarios(obj, horarios)
            if was_created:
                created += 1

    registrar_auditoria(
        request,
        "ESCOLAR::GRUPO_GENERAR",
        "Grupo",
        None,
        "ok",
        {"periodo": periodo, "grupos_creados": created},
    )

    messages.success(
        request, f"Listo: se generaron {created} grupos para el periodo {periodo}."
    )
    return redirect("/panel/escolar/grupos/")


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def escolar_grupos(request):
    edit_id = request.GET.get("edit")
    instance = Grupo.objects.filter(pk=edit_id).first() if edit_id else None
    form = GrupoForm(instance=instance)

    qs = (
        Grupo.objects
        .select_related("curso_ref", "periodo_ref")
        .prefetch_related(
            Prefetch(
                "horarios",
                queryset=GrupoHorario.objects.filter(
                    activo=True).order_by("dia", "hora_inicio"),
                to_attr="horarios_lista",
            )
        )
        .annotate(
            inscritos=Count(
                "inscripciones",
                filter=Q(inscripciones__estado=Inscripcion.ESTADO_ACTIVA),
                distinct=True,
            )
        )
        .annotate(
            cupo_disponible=ExpressionWrapper(
                F("cupo") - F("inscritos"),
                output_field=IntegerField(),
            )
        )
    )
    periodo_filtro = (request.GET.get("periodo") or "").strip()
    estado_filtro = (request.GET.get("estado") or "").strip()
    turno_filtro = (request.GET.get("turno") or "").strip().upper()
    creado_desde = _parse_date(request.GET.get("desde"))
    creado_hasta = _parse_date(request.GET.get("hasta"))

    if periodo_filtro:
        qs = qs.filter(periodo_ref__codigo=periodo_filtro)
    if estado_filtro in ("0", "1"):
        qs = qs.filter(estado=int(estado_filtro))
    if turno_filtro in {Grupo.TURNO_AM, Grupo.TURNO_PM, Grupo.TURNO_SAB}:
        qs = qs.filter(turno=turno_filtro)
    if creado_desde:
        qs = qs.filter(creado_en__date__gte=creado_desde)
    if creado_hasta:
        qs = qs.filter(creado_en__date__lte=creado_hasta)

    periodos = list(
        Grupo.objects.order_by("periodo_ref__codigo")
        .values_list("periodo_ref__codigo", flat=True)
        .distinct()
    )

    if request.method == "POST":
        if request.POST.get("delete_id"):
            grupo_id = request.POST.get("delete_id")
            deleted, _ = Grupo.objects.filter(pk=grupo_id).delete()
            if deleted:
                registrar_auditoria(
                    request,
                    "ESCOLAR::GRUPO_DELETE",
                    "Grupo",
                    grupo_id,
                    "ok",
                    {"grupo_id": grupo_id},
                )
            messages.success(request, "Grupo eliminado.")
            return redirect("/panel/escolar/grupos/")

        form = GrupoForm(request.POST, instance=instance)
        if form.is_valid():
            old_tipo = instance.tipo_horario if instance else None
            old_turno = instance.turno if instance else None
            es_nuevo = instance is None
            grupo = form.save()
            accion = "ESCOLAR::GRUPO_UPDATE" if instance else "ESCOLAR::GRUPO_CREATE"
            registrar_auditoria(
                request,
                accion,
                "Grupo",
                grupo.pk,
                "ok",
                {
                    "periodo": grupo.periodo,
                    "cupo": grupo.cupo,
                    "estado": grupo.estado,
                    "tipo_horario": grupo.tipo_horario,
                    "turno": grupo.turno,
                },
            )

            if (
                (not grupo.horarios.exists())
                or (old_tipo != grupo.tipo_horario)
                or (old_turno != grupo.turno)
            ):
                horarios = horarios_default_por_tipo_turno(
                    grupo.tipo_horario, grupo.turno
                )
                sync_horarios(grupo, horarios)

            if es_nuevo:
                messages.success(
                    request,
                    "Grupo creado. Revisa o ajusta el horario asignado automáticamente.",
                )
                return redirect(f"/panel/escolar/grupos/?edit={grupo.pk}")
            else:
                messages.success(request, "Grupo actualizado correctamente.")
            return redirect("/panel/escolar/grupos/")
        _flash_form_errors(request, form)

    grupos_qs = qs.order_by("-creado_en")
    paginator = Paginator(grupos_qs, 2)
    page_number = request.GET.get("page")
    grupos = paginator.get_page(page_number)
    return render(
        request,
        "ui/escolar_grupos.html",
        {
            "form": form,
            "grupos": grupos,
            "edit_id": edit_id,
            "periodos": periodos,
            "periodo_filtro": periodo_filtro,
            "estado_filtro": estado_filtro,
            "turno_filtro": turno_filtro,
            "turno_choices": Grupo.TURNO_CHOICES,
            "creado_desde": creado_desde,
            "creado_hasta": creado_hasta,
        },
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def escolar_inscripciones(request):
    def _collect_filters():
        params = {}
        for key in ("periodo", "grupo_id", "estado", "desde", "hasta"):
            val = request.GET.get(key) or request.POST.get(key)
            if val:
                params[key] = val.strip()
        return params

    def _redirect_with_filters(extra=None):
        params = _collect_filters()
        if extra:
            params.update({k: v for k, v in (extra or {}).items() if v})
        query = urlencode(params)
        url = "/panel/escolar/inscripciones/"
        return redirect(f"{url}?{query}" if query else url)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()

        if action == "crear":
            alumno_id = request.POST.get(
                "alumno_id") or request.POST.get("alumno")
            grupo_id = (
                request.POST.get("grupo_id_crear")
                or request.POST.get("grupo_id")
                or request.POST.get("grupo")
            )
            requiere_factura = (request.POST.get(
                "requiere_factura") or "") == "on"

            alumno = Alumno.objects.filter(pk=alumno_id).first()
            grupo = Grupo.objects.filter(pk=grupo_id).first()

            if not alumno:
                messages.error(request, "Elige un alumno antes de inscribir.")
                return _redirect_with_filters()

            if not grupo:
                messages.error(request, "Selecciona un grupo válido.")
                return _redirect_with_filters()

            if grupo.estado != Grupo.ESTADO_ACTIVO:
                messages.error(
                    request,
                    "Ese grupo está inactivo; no se pueden agregar inscripciones.",
                )
                return _redirect_with_filters()

            activas_en_grupo = Inscripcion.objects.filter(
                grupo=grupo, estado=Inscripcion.ESTADO_ACTIVA
            ).count()
            if activas_en_grupo >= grupo.cupo:
                messages.error(
                    request, "El grupo ya está lleno, busca otro con cupo disponible."
                )
                return _redirect_with_filters()

            if Inscripcion.objects.filter(alumno=alumno, grupo=grupo).exists():
                messages.error(
                    request,
                    "Este alumno ya tenía una inscripción en ese grupo. Puedes reactivarla si estaba en baja.",
                )
                return _redirect_with_filters()

            try:
                insc = Inscripcion.objects.create(
                    alumno=alumno,
                    grupo=grupo,
                    estado=Inscripcion.ESTADO_ACTIVA,
                    fecha_inscripcion=timezone.now().date(),
                )
                venta = ensure_inscripcion_sale(
                    insc,
                    requiere_factura=requiere_factura,
                )
            except IntegrityError:
                messages.error(
                    request, "Ese alumno ya está apuntado en el grupo.")
                return _redirect_with_filters()

            registrar_auditoria(
                request,
                "ESCOLAR::INSCRIPCION_CREAR",
                "Inscripcion",
                insc.id,
                "ok",
                {
                    "alumno": alumno.pk,
                    "grupo": grupo.id,
                    "orden_venta_id": venta["orden_id"],
                    "inscripcion_total": str(venta["total"]),
                    "requiere_factura": venta["requiere_factura"],
                },
            )
            messages.success(
                request,
                f"Inscripción registrada para {alumno.nombres} en Grupo {grupo.id} ({grupo.periodo}). Venta generada: ${venta['total']:.2f} MXN.",
            )
            return redirect(f"/panel/escolar/alumnos/{alumno.pk}/expediente/")

        if action == "baja":
            insc_id = request.POST.get("id_inscripcion")
            insc = Inscripcion.objects.select_related("alumno", "grupo").filter(
                pk=insc_id
            ).first()

            if not insc:
                messages.info(request, "La inscripción ya no existe.")
                return _redirect_with_filters()

            if insc.estado == Inscripcion.ESTADO_BAJA:
                messages.info(
                    request, "Esa inscripción ya estaba dada de baja.")
                return _redirect_with_filters()

            insc.estado = Inscripcion.ESTADO_BAJA
            insc.save(update_fields=["estado"])

            # Cancelar la OrdenPOS asociada si existe y no está ya cancelada
            OrdenPOS.objects.filter(
                inscripcion=insc,
            ).exclude(
                estado=OrdenPOS.ESTADO_CANCELADA,
            ).update(estado=OrdenPOS.ESTADO_CANCELADA)

            registrar_auditoria(
                request,
                "ESCOLAR::INSCRIPCION_BAJA",
                "Inscripcion",
                insc.id,
                "ok",
                {"alumno": insc.alumno_id, "grupo": insc.grupo_id},
            )
            messages.info(
                request, "Inscripción en baja. Puedes reactivarla más adelante."
            )
            return _redirect_with_filters()

        if action == "reactivar":
            insc_id = request.POST.get("id_inscripcion")
            insc = Inscripcion.objects.select_related("alumno", "grupo").filter(
                pk=insc_id
            ).first()

            if not insc:
                messages.info(request, "La inscripción ya no existe.")
                return _redirect_with_filters()

            grupo = insc.grupo

            if grupo.estado != Grupo.ESTADO_ACTIVO:
                messages.error(
                    request, "El grupo está inactivo; no se puede reactivar aquí."
                )
                return _redirect_with_filters()

            activas_en_grupo = Inscripcion.objects.filter(
                grupo=grupo, estado=Inscripcion.ESTADO_ACTIVA
            ).exclude(pk=insc.id).count()
            if activas_en_grupo >= grupo.cupo:
                messages.error(
                    request,
                    "No hay lugares libres en el grupo para reactivar la inscripción.",
                )
                return _redirect_with_filters()

            insc.estado = Inscripcion.ESTADO_ACTIVA
            insc.save(update_fields=["estado"])

            registrar_auditoria(
                request,
                "ESCOLAR::INSCRIPCION_REACTIVAR",
                "Inscripcion",
                insc.id,
                "ok",
                {"alumno": insc.alumno_id, "grupo": insc.grupo_id},
            )
            messages.success(
                request,
                "Inscripción reactivada. El alumno vuelve a la lista del grupo.",
            )
            return _redirect_with_filters()

        if action == "editar":
            insc_id = request.POST.get("id_inscripcion")
            grupo_nuevo_id = request.POST.get("grupo_id_editar")

            insc = Inscripcion.objects.select_related("alumno", "grupo").filter(
                pk=insc_id
            ).first()
            if not insc:
                messages.error(request, "La inscripción a editar no existe.")
                return _redirect_with_filters()

            grupo_nuevo = Grupo.objects.filter(pk=grupo_nuevo_id).first()
            if not grupo_nuevo:
                messages.error(
                    request, "Selecciona un grupo válido para la edición."
                )
                return _redirect_with_filters()

            if grupo_nuevo.estado != Grupo.ESTADO_ACTIVO:
                messages.error(
                    request, "No puedes mover la inscripción a un grupo inactivo."
                )
                return _redirect_with_filters()

            if grupo_nuevo.pk == insc.grupo_id:
                messages.info(
                    request, "No hubo cambios: la inscripción ya está en ese grupo."
                )
                return _redirect_with_filters()

            if Inscripcion.objects.filter(
                alumno=insc.alumno,
                grupo=grupo_nuevo,
            ).exclude(pk=insc.pk).exists():
                messages.error(
                    request,
                    "Ese alumno ya tiene una inscripción en el grupo destino.",
                )
                return _redirect_with_filters()

            if insc.estado == Inscripcion.ESTADO_ACTIVA:
                activas_en_grupo = Inscripcion.objects.filter(
                    grupo=grupo_nuevo,
                    estado=Inscripcion.ESTADO_ACTIVA,
                ).count()
                if activas_en_grupo >= grupo_nuevo.cupo:
                    messages.error(
                        request,
                        "No hay cupo en el grupo destino para mover la inscripción activa.",
                    )
                    return _redirect_with_filters()

            grupo_anterior_id = insc.grupo_id
            insc.grupo = grupo_nuevo
            insc.save(update_fields=["grupo"])

            registrar_auditoria(
                request,
                "ESCOLAR::INSCRIPCION_EDITAR",
                "Inscripcion",
                insc.id,
                "ok",
                {
                    "alumno": insc.alumno_id,
                    "grupo_anterior": grupo_anterior_id,
                    "grupo_nuevo": grupo_nuevo.id,
                    "estado": insc.estado,
                },
            )
            messages.success(request, "Inscripción actualizada correctamente.")
            return _redirect_with_filters()

        messages.error(request, "Acción no reconocida para inscripciones.")
        return _redirect_with_filters()

    filtros = _collect_filters()
    periodo_filtro = filtros.get("periodo", "")
    grupo_filtro = filtros.get("grupo_id", "")
    estado_filtro = filtros.get("estado", "")
    fecha_desde = _parse_date(filtros.get("desde"))
    fecha_hasta = _parse_date(filtros.get("hasta"))

    inscripciones_qs = Inscripcion.objects.select_related(
        "alumno", "grupo", "grupo__curso_ref", "grupo__periodo_ref"
    ).prefetch_related(
        Prefetch(
            "grupo__horarios",
            queryset=GrupoHorario.objects.filter(
                activo=True).order_by("dia", "hora_inicio"),
            to_attr="horarios_activos",
        )
    )

    if periodo_filtro:
        inscripciones_qs = inscripciones_qs.filter(
            grupo__periodo_ref__codigo=periodo_filtro
        )
    if grupo_filtro:
        inscripciones_qs = inscripciones_qs.filter(grupo_id=grupo_filtro)
    if estado_filtro in {choice[0] for choice in Inscripcion.ESTADO_CHOICES}:
        inscripciones_qs = inscripciones_qs.filter(estado=estado_filtro)
    if fecha_desde:
        inscripciones_qs = inscripciones_qs.filter(
            fecha_inscripcion__gte=fecha_desde
        )
    if fecha_hasta:
        inscripciones_qs = inscripciones_qs.filter(
            fecha_inscripcion__lte=fecha_hasta
        )

    inscripciones = inscripciones_qs.order_by(
        "-fecha_inscripcion", "alumno__matricula"
    )

    periodos = list(
        Grupo.objects.order_by("periodo_ref__codigo")
        .values_list("periodo_ref__codigo", flat=True)
        .distinct()
    )
    grupos_filtro = Grupo.objects.select_related(
        "curso_ref", "periodo_ref").all()
    if periodo_filtro:
        grupos_filtro = grupos_filtro.filter(
            periodo_ref__codigo=periodo_filtro)
    grupos_filtro = grupos_filtro.order_by("periodo_ref__codigo", "id")

    grupos_creacion_qs = (
        Grupo.objects
        .select_related("curso_ref", "periodo_ref")
        .prefetch_related(
            Prefetch(
                "horarios",
                queryset=GrupoHorario.objects.filter(
                    activo=True).order_by("dia", "hora_inicio"),
                to_attr="horarios_activos",
            )
        )
        .filter(estado=Grupo.ESTADO_ACTIVO)
        .annotate(
            inscritos=Count(
                "inscripciones",
                filter=Q(inscripciones__estado=Inscripcion.ESTADO_ACTIVA),
                distinct=True,
            )
        )
        .order_by("periodo_ref__codigo", "id")
    )
    grupos_creacion = list(grupos_creacion_qs)
    for g in grupos_creacion:
        g.cupo_disponible = max(
            int(g.cupo) - int(getattr(g, "inscritos", 0)), 0)
    editing_inscripcion = None
    edit_inscripcion_id = (request.GET.get("edit_inscripcion") or "").strip()
    if edit_inscripcion_id:
        editing_inscripcion = Inscripcion.objects.select_related(
            "alumno", "grupo"
        ).filter(pk=edit_inscripcion_id).first()
    alumnos = (
        Alumno.objects
        .annotate(
            tiene_insc_activa=Count(
                "inscripciones",
                filter=Q(inscripciones__estado=Inscripcion.ESTADO_ACTIVA),
            )
        )
        .order_by("matricula", "nombres", "apellido_paterno", "apellido_materno")
    )

    return render(
        request,
        "ui/escolar_inscripciones.html",
        {
            "inscripciones": inscripciones,
            "periodos": periodos,
            "grupos_filtro": grupos_filtro,
            "grupos_creacion": grupos_creacion,
            "editing_inscripcion": editing_inscripcion,
            "alumnos": alumnos,
            "estado_choices": Inscripcion.ESTADO_CHOICES,
            "periodo_filtro": periodo_filtro,
            "grupo_filtro": grupo_filtro,
            "estado_filtro": estado_filtro,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
        },
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def escolar_calificaciones(request):
    edit_id = request.GET.get("edit")
    instance = (
        Calificacion.objects.filter(pk=edit_id)
        .select_related("inscripcion", "inscripcion__alumno", "inscripcion__grupo")
        .first()
        if edit_id
        else None
    )
    form = CalificacionForm(instance=instance, user=request.user)

    if request.method == "POST":
        if request.POST.get("delete_id"):
            cal = Calificacion.objects.select_related(
                "inscripcion", "inscripcion__grupo"
            ).filter(pk=request.POST.get("delete_id")).first()

            if not cal:
                messages.info(request, "La calificación ya no existe.")
                return redirect("/panel/escolar/calificaciones/")

            cierre = ActaCierre.objects.filter(
                grupo=cal.inscripcion.grupo).first()

            if cierre:
                if not request.user.is_superuser:
                    messages.error(
                        request,
                        "El acta de ese grupo ya está cerrada; no se puede borrar la calificación.",
                    )
                    return redirect("/panel/escolar/calificaciones/")

                if _is_director(request.user):
                    messages.info(
                        request,
                        "Si tienes permisos de superusuario, puedes eliminar la calificación usando la opción de 'Anular cierre de acta' al editar la calificación.",
                    )

                return redirect("/panel/escolar/calificaciones/")

            detalle = {
                "grupo": cal.inscripcion.grupo.id,
                "periodo": cal.inscripcion.grupo.periodo,
                "accion": "delete",
            }
            cal_id = cal.id
            cal.delete()
            messages.success(request, "Calificación eliminada.")

            if cierre and request.user.is_superuser:
                registrar_auditoria(
                    request,
                    "ESCOLAR::CIERRE_ACTA_OVERRIDE",
                    "Calificacion",
                    cal_id,
                    "ok",
                    detalle,
                )

            return redirect("/panel/escolar/calificaciones/")

        form = CalificacionForm(
            request.POST, instance=instance, user=request.user)
        if form.is_valid():
            cierre = getattr(form, "_acta_cierre", None)
            cal = form.save()
            messages.success(request, "Calificación guardada correctamente.")

            if cierre and request.user.is_superuser:
                registrar_auditoria(
                    request,
                    "ESCOLAR::CIERRE_ACTA_OVERRIDE",
                    "Calificacion",
                    cal.id,
                    "ok",
                    {
                        "grupo": cal.inscripcion.grupo.id,
                        "periodo": cal.inscripcion.grupo.periodo,
                        "accion": "save",
                    },
                )
            return redirect(
                f"/panel/escolar/calificaciones/?cal_ok={cal.pk}"
                f"&grupo={cal.inscripcion.grupo_id}"
            )
        messages.error(request, "Revisa los datos de la calificación.")
        _flash_form_errors(request, form)

    # ── Filtros ───────────────────────────────────────────────────────────
    periodo_filtro = (request.GET.get("periodo") or "").strip()
    grupo_filtro_id = (request.GET.get("grupo") or "").strip()
    fecha_desde = _parse_date(request.GET.get("desde"))
    fecha_hasta = _parse_date(request.GET.get("hasta"))

    # ── Calificaciones list ───────────────────────────────────────────────
    calificaciones = (
        Calificacion.objects.select_related(
            "inscripcion",
            "inscripcion__alumno",
            "inscripcion__grupo",
            "inscripcion__grupo__curso_ref",
            "inscripcion__grupo__periodo_ref",
        )
        .order_by("-capturado_en")
    )
    if periodo_filtro:
        calificaciones = calificaciones.filter(
            inscripcion__grupo__periodo_ref__codigo=periodo_filtro
        )
    if grupo_filtro_id:
        calificaciones = calificaciones.filter(
            inscripcion__grupo_id=grupo_filtro_id
        )
    if fecha_desde:
        calificaciones = calificaciones.filter(
            capturado_en__date__gte=fecha_desde
        )
    if fecha_hasta:
        calificaciones = calificaciones.filter(
            capturado_en__date__lte=fecha_hasta
        )

    # ── Selectores de filtro ──────────────────────────────────────────────
    periodos = list(
        Grupo.objects.order_by("periodo_ref__codigo")
        .values_list("periodo_ref__codigo", flat=True)
        .distinct()
    )
    grupos_list = (
        Grupo.objects
        .select_related("curso_ref", "periodo_ref")
        .order_by("periodo_ref__codigo", "curso_ref__nombre")
    )

    # ── Detalle del grupo seleccionado + alumnos inscritos ────────────────
    grupo_sel = None
    inscripciones_grupo = []
    if grupo_filtro_id:
        grupo_sel = (
            Grupo.objects
            .select_related("curso_ref", "periodo_ref")
            .prefetch_related(
                Prefetch(
                    "horarios",
                    queryset=GrupoHorario.objects.filter(
                        activo=True).order_by("dia", "hora_inicio"),
                    to_attr="horarios_activos",
                )
            )
            .filter(pk=grupo_filtro_id)
            .first()
        )
        if grupo_sel:
            cal_id_sq = (
                Calificacion.objects
                .filter(inscripcion=OuterRef("pk"))
                .values("id")[:1]
            )
            cal_valor_sq = (
                Calificacion.objects
                .filter(inscripcion=OuterRef("pk"))
                .values("valor")[:1]
            )
            inscripciones_grupo = list(
                Inscripcion.objects
                .filter(grupo=grupo_sel)
                .select_related("alumno")
                .annotate(
                    cal_id=Subquery(cal_id_sq),
                    cal_valor=Subquery(cal_valor_sq),
                )
                .order_by("alumno__matricula")
            )

    # Contexto para el banner post-guardar calificación
    cal_ok_pk = (request.GET.get("cal_ok") or "").strip()
    cal_ok_obj = None
    if cal_ok_pk:
        cal_ok_obj = (
            Calificacion.objects
            .select_related(
                "inscripcion__alumno",
                "inscripcion__grupo__periodo_ref",
            )
            .filter(pk=cal_ok_pk)
            .first()
        )

    return render(
        request,
        "ui/escolar_calificaciones.html",
        {
            "form": form,
            "calificaciones": calificaciones,
            "edit_id": edit_id,
            "periodos": periodos,
            "periodo_filtro": periodo_filtro,
            "grupos_list": grupos_list,
            "grupo_filtro_id": grupo_filtro_id,
            "grupo_sel": grupo_sel,
            "inscripciones_grupo": inscripciones_grupo,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "cal_ok": cal_ok_obj,
        },
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def cerrar_acta(request):
    grupo_id = request.GET.get("grupo") or request.POST.get("grupo")
    periodo = (request.GET.get("periodo")
               or request.POST.get("periodo") or "").strip()

    if not grupo_id:
        messages.error(request, "Indica el grupo para cerrar el acta.")
        return redirect("/panel/escolar/calificaciones/")

    grupo = Grupo.objects.filter(pk=grupo_id).first()
    if not grupo:
        messages.error(request, "No encontramos ese grupo.")
        return redirect("/panel/escolar/calificaciones/")

    if not periodo:
        periodo = grupo.periodo

    try:
        periodo = validate_periodo_value(periodo)
    except Exception as exc:
        messages.error(request, str(exc))
        return redirect("/panel/escolar/calificaciones/")

    acta = ActaCierre.objects.filter(grupo=grupo).first()

    if request.method == "POST":
        if acta:
            messages.info(
                request,
                "Este grupo ya tenía el acta cerrada para ese período.",
            )
            return redirect(f"/panel/escolar/calificaciones/?periodo={periodo}")

        motivo = (request.POST.get("motivo") or "").strip()
        try:
            motivo = validate_text_general(
                motivo,
                "Motivo",
                allow_blank=True,
                min_length=0,
                max_length=300,
            )
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect(f"/panel/escolar/calificaciones/?periodo={periodo}")

        acta = ActaCierre.objects.create(
            grupo=grupo,
            cerrada_por=request.user,
            motivo=motivo,
        )

        registrar_auditoria(
            request,
            "ESCOLAR::CIERRE_ACTA",
            "ActaCierre",
            acta.id,
            "ok",
            {"grupo": grupo.id, "periodo": periodo, "motivo": motivo},
        )

        messages.success(
            request,
            "Acta cerrada. Se congelan las calificaciones de este grupo y período.",
        )
        return redirect(f"/panel/escolar/calificaciones/?periodo={periodo}")

    return render(
        request,
        "ui/escolar_acta_cerrar.html",
        {"grupo": grupo, "periodo": periodo, "acta": acta},
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar", "Alumno")
def boleta_pdf(request):
    raw = (request.GET.get("alumno") or "").strip()
    m = re.search(r"\d+", raw)
    if not m:
        messages.error(request, "Parámetro alumno inválido.")
        return redirect("/panel/escolar/calificaciones/")

    alumno_id = int(m.group())
    periodo = (request.GET.get("periodo") or "").strip()

    if not alumno_id or not periodo:
        messages.error(
            request, "Indica alumno y período para generar la boleta.")
        return redirect("/panel/escolar/calificaciones/")

    if not PERIODO_RE.match(periodo):
        messages.error(request, "Período inválido. Usa formato YYYY-MM.")
        return redirect("/panel/escolar/calificaciones/")

    alumno = Alumno.objects.filter(pk=alumno_id).first()
    if not alumno:
        messages.error(request, "No encontramos al alumno indicado.")
        return redirect("/panel/escolar/calificaciones/")

    role = get_user_role(request.user)
    if role == "Alumno":
        user_email = (request.user.email or "").lower()
        alumno_email = (alumno.correo or "").lower()
        if not user_email or user_email != alumno_email:
            return render(
                request,
                "ui/forbidden.html",
                {"role": role, "allowed": "Superusuario, Director Escolar"},
                status=403,
            )

    inscripcion = (
        Inscripcion.objects
        .select_related("grupo", "grupo__curso_ref", "grupo__periodo_ref")
        .prefetch_related(
            Prefetch(
                "grupo__horarios",
                queryset=GrupoHorario.objects.filter(
                    activo=True).order_by("dia", "hora_inicio"),
                to_attr="horarios_activos",
            )
        )
        .filter(alumno=alumno, grupo__periodo_ref__codigo=periodo)
        .order_by("-fecha_inscripcion")
        .first()
    )

    if not inscripcion:
        messages.error(
            request, "El alumno no tiene inscripciones para ese período.")
        return redirect("/panel/escolar/calificaciones/")

    calificacion = Calificacion.objects.filter(inscripcion=inscripcion).first()
    return _render_boleta_pdf(alumno, periodo, inscripcion, calificacion)


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def escolar_expediente(request, alumno_id):
    alumno = Alumno.objects.filter(pk=alumno_id).first()
    if not alumno:
        messages.error(request, "No se encontró el alumno indicado.")
        return redirect("/panel/escolar/alumnos/?modo=lista")

    domicilio = getattr(alumno, "domicilio", None)

    inscripciones = (
        Inscripcion.objects
        .filter(alumno=alumno)
        .select_related(
            "grupo",
            "grupo__curso_ref",
            "grupo__periodo_ref",
        )
        .prefetch_related(
            Prefetch(
                "grupo__horarios",
                queryset=GrupoHorario.objects.filter(
                    activo=True).order_by("dia", "hora_inicio"),
                to_attr="horarios_activos",
            )
        )
        .order_by("-fecha_inscripcion")
    )

    inscripcion_activa = next(
        (i for i in inscripciones if i.estado == Inscripcion.ESTADO_ACTIVA),
        None,
    )

    calificacion_activa = None
    if inscripcion_activa:
        calificacion_activa = Calificacion.objects.filter(
            inscripcion=inscripcion_activa
        ).first()

    return render(
        request,
        "ui/escolar_expediente.html",
        {
            "alumno": alumno,
            "domicilio": domicilio,
            "inscripciones": inscripciones,
            "inscripcion_activa": inscripcion_activa,
            "calificacion_activa": calificacion_activa,
            "alumno_tiene_acceso": get_user_model().objects.filter(
                username=alumno.matricula
            ).exists() if alumno.matricula else False,
        },
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def escolar_generar_acceso(request, alumno_id):
    """Provisiona credenciales para un alumno: crea User(username=matricula),
    asigna rol ALUMNO y envía correo de establecimiento de contraseña."""
    if request.method != "POST":
        return redirect(f"/panel/escolar/alumnos/{alumno_id}/expediente/")

    alumno = Alumno.objects.filter(pk=alumno_id).first()
    if not alumno:
        messages.error(request, "No se encontró el alumno indicado.")
        return redirect("/panel/escolar/alumnos/?modo=lista")

    if not alumno.matricula:
        messages.error(
            request, "El alumno no tiene matrícula asignada. No se puede generar acceso.")
        return redirect(f"/panel/escolar/alumnos/{alumno_id}/expediente/")

    if not alumno.correo:
        messages.error(
            request, "El alumno no tiene correo electrónico registrado. No se puede generar acceso.")
        return redirect(f"/panel/escolar/alumnos/{alumno_id}/expediente/")

    User = get_user_model()
    if User.objects.filter(username=alumno.matricula).exists():
        messages.warning(
            request,
            f"El alumno ya tiene acceso con el usuario '{alumno.matricula}'.",
        )
        return redirect(f"/panel/escolar/alumnos/{alumno_id}/expediente/")

    if User.objects.filter(email__iexact=alumno.correo).exists():
        messages.error(
            request,
            f"El correo '{alumno.correo}' ya está registrado en otro usuario.",
        )
        return redirect(f"/panel/escolar/alumnos/{alumno_id}/expediente/")

    try:
        rol_alumno = Rol.objects.get(codigo="ALUMNO", activo=True)
    except Rol.DoesNotExist:
        messages.error(
            request, "El rol ALUMNO no está configurado en el sistema.")
        return redirect(f"/panel/escolar/alumnos/{alumno_id}/expediente/")

    user = User.objects.create_user(
        username=alumno.matricula,
        email=alumno.correo,
        is_active=True,
        password=None,
    )
    UsuarioRol.objects.get_or_create(
        usuario=user, defaults={"rol": rol_alumno})

    # Enviar correo de establecimiento de contraseña (reutiliza el flujo de recuperación)
    reset_form = PasswordResetForm({"email": alumno.correo})
    if reset_form.is_valid():
        reset_form.save(
            request=request,
            use_https=request.is_secure(),
            from_email=None,
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
        )

    log_event(
        request,
        accion="ESCOLAR::GENERAR_ACCESO",
        entidad="User",
        entidad_id=str(user.pk),
        resultado="ok",
        detalle={"username": user.username, "alumno_id": alumno_id},
    )
    messages.success(
        request,
        f"Acceso generado para '{alumno.matricula}'. Se envió un correo a {alumno.correo} para establecer contraseña.",
    )
    return redirect(f"/panel/escolar/alumnos/{alumno_id}/expediente/")


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar", "Alumno")
def escolar_boleta_alumno(request, alumno_id):
    alumno = Alumno.objects.filter(pk=alumno_id).first()
    if not alumno:
        messages.error(request, "No se encontró el alumno indicado.")
        return redirect("/panel/escolar/alumnos/?modo=lista")

    role = get_user_role(request.user)
    if role == "Alumno":
        user_email = (request.user.email or "").lower()
        alumno_email = (alumno.correo or "").lower()
        if not user_email or user_email != alumno_email:
            return render(
                request,
                "ui/forbidden.html",
                {"role": role, "allowed": "Superusuario, Director Escolar"},
                status=403,
            )

    inscripcion = (
        Inscripcion.objects
        .select_related("grupo", "grupo__curso_ref", "grupo__periodo_ref")
        .prefetch_related(
            Prefetch(
                "grupo__horarios",
                queryset=GrupoHorario.objects.filter(
                    activo=True).order_by("dia", "hora_inicio"),
                to_attr="horarios_activos",
            )
        )
        .filter(alumno=alumno)
        .order_by("-fecha_inscripcion")
        .first()
    )

    if not inscripcion:
        messages.error(
            request, "El alumno no tiene inscripciones registradas.")
        return redirect("/panel/escolar/alumnos/?modo=lista")

    periodo = (
        inscripcion.grupo.periodo_ref.codigo
        if getattr(inscripcion.grupo, "periodo_ref", None)
        else inscripcion.grupo.periodo
    )

    calificacion = Calificacion.objects.filter(inscripcion=inscripcion).first()

    return _render_boleta_pdf(alumno, periodo, inscripcion, calificacion)


def escolar_boleta_pdf(request):
    return boleta_pdf(request)
