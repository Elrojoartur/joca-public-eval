import json
import logging
import random
import os
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import render
from apps.authn.decorators import rate_limit
from .forms import ContactForm
from .models import MensajeContacto
from apps.school.models import Grupo, GrupoHorario

bitacora_logger = logging.getLogger("bitacora")
if not bitacora_logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    bitacora_logger.addHandler(handler)
bitacora_logger.setLevel(logging.INFO)
bitacora_logger.propagate = False
SECURITY_ANSWER_KEY = "portal_contact_security_answer"
SECURITY_PROMPT_KEY = "portal_contact_security_prompt"

CATALOG_CURSOS_PATH = Path(__file__).resolve(
).parent.parent / "ui" / "catalogs" / "cursos.json"
CATALOG_AVISOS_PATH = Path(__file__).resolve(
).parent.parent / "ui" / "catalogs" / "avisos.json"
CATALOG_FAQS_PATH = Path(__file__).resolve(
).parent.parent / "ui" / "catalogs" / "faqs.json"


def portal_grupos(request):
    grupos = _load_groups_public_summary(limit=None)
    paginator = Paginator(grupos, 8)
    grupos_page = paginator.get_page(request.GET.get("page"))
    return render(request, "ui/portal_grupos.html", {"grupos_page": grupos_page})


def portal_avisos(request):
    avisos = load_avisos_catalog()
    paginator = Paginator(avisos, 8)
    avisos_page = paginator.get_page(request.GET.get("page"))
    return render(request, "ui/portal_avisos.html", {"avisos_page": avisos_page})


def portal_faqs(request):
    faqs = load_faqs_catalog()
    paginator = Paginator(faqs, 8)
    faqs_page = paginator.get_page(request.GET.get("page"))
    return render(request, "ui/portal_faqs.html", {"faqs_page": faqs_page})


# 5 envíos por IP en 5 minutos: permite navegar la página (GET) y enviar al menos
# una o dos veces sin bloquearse, mientras limita envíos automatizados masivos.
@rate_limit("portal_contacto", max_calls=5, period_seconds=300)
def portal_contacto(request):
    # Precarga desde "Pedir información" en portal de grupos
    ref = request.GET.get("ref", "")
    grupo_id = request.GET.get("grupo", "")
    curso_nombre = request.GET.get("curso", "")
    horario_str = request.GET.get("horario", "")
    grupo_ref = None
    if ref == "grupo" and grupo_id:
        grupo_ref = {
            "id": grupo_id,
            "curso": curso_nombre,
            "horario": horario_str,
        }

    asunto_inicial = ""
    if grupo_ref:
        asunto_inicial = f"Información sobre {curso_nombre} (Grupo {grupo_id})" if curso_nombre else f"Información sobre Grupo {grupo_id}"

    initial_data = {"asunto": asunto_inicial} if asunto_inicial else {}
    contact_form = ContactForm(request.POST or None, initial=initial_data)
    security_question = get_security_question(request)
    contact_info = {
        "telefono": getattr(settings, "PORTAL_CONTACT_PHONE", "2755299"),
        "whatsapp": getattr(settings, "PORTAL_CONTACT_WHATSAPP", "4431722172"),
        "correo": getattr(settings, "PORTAL_CONTACT_EMAIL", "ccent_2012@hotmail.com"),
        "horario": getattr(settings, "PORTAL_CONTACT_SCHEDULE", "Lunes a Viernes de 09:00 a 18:00"),
        "direccion": getattr(
            settings,
            "PORTAL_CONTACT_ADDRESS",
            "C. Juan Guillermo Villasana 131, Jardines de Guadalupe, 58140 Morelia, Michoacan.",
        ),
    }

    if request.method == "POST":
        if contact_form.is_valid():
            expected = str(request.session.get(
                SECURITY_ANSWER_KEY, "")).strip()
            provided = str(contact_form.cleaned_data.get(
                "security_answer", "")).strip()

            if not expected or provided != expected:
                contact_form.add_error(
                    "security_answer", "Respuesta incorrecta, intenta de nuevo."
                )
                messages.warning(
                    request,
                    "Casi: responde bien la pregunta de seguridad para enviar el mensaje.",
                )
                security_question = build_security_challenge(request)
            else:
                registrar_bitacora_contacto(contact_form.cleaned_data, request)
                enviar_correo_contacto(contact_form.cleaned_data)
                # Guardar mensaje en BD
                ip_origen = request.META.get("REMOTE_ADDR", "")
                MensajeContacto.objects.create(
                    nombre=contact_form.cleaned_data.get("nombre"),
                    email=contact_form.cleaned_data.get("email"),
                    telefono=contact_form.cleaned_data.get("telefono") or "",
                    asunto=contact_form.cleaned_data.get(
                        "asunto") or "Contacto",
                    mensaje=contact_form.cleaned_data.get("mensaje"),
                    ip_origen=ip_origen if ip_origen else None,
                )
                messages.success(
                    request,
                    "Listo. Recibimos tu mensaje y te contactaremos pronto.",
                )
                contact_form = ContactForm()
                security_question = build_security_challenge(request)
        else:
            messages.error(
                request, "Revisa los campos obligatorios antes de enviar.")

    return render(
        request,
        "ui/portal_contacto.html",
        {
            "contact_form": contact_form,
            "security_question": security_question,
            "contact_info": contact_info,
            "grupo_ref": grupo_ref,
        },
    )


def _load_groups_public_summary(limit=8):
    grupos_qs = (
        Grupo.objects.select_related("curso_ref", "periodo_ref")
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
            inscripciones_activas=Count(
                "inscripciones",
                filter=Q(inscripciones__estado="activa"),
            )
        )
        .order_by("periodo_ref__codigo", "curso_ref__codigo", "turno", "id")
    )
    if limit:
        grupos_qs = grupos_qs[:limit]

    grupos = []
    for g in grupos_qs:
        disponibles = max(
            int(g.cupo) - int(getattr(g, "inscripciones_activas", 0)), 0)
        horarios_list = getattr(g, "horarios_activos", [])
        horario_str = "  /  ".join(
            f"{h.get_dia_display()} {h.hora_inicio.strftime('%H:%M')}-{h.hora_fin.strftime('%H:%M')}"
            for h in horarios_list
        ) or "Horario por definir"
        if disponibles == 0:
            disponibilidad = "lleno"
        elif disponibles <= 3:
            disponibilidad = "ultimos"
        else:
            disponibilidad = "abierto"
        grupos.append(
            {
                "id": g.id,
                "curso": g.curso_ref.nombre if g.curso_ref_id else "",
                "curso_codigo": g.curso_ref.codigo if g.curso_ref_id else "",
                "periodo": g.periodo_ref.codigo if g.periodo_ref_id else "",
                "tipo_horario": g.get_tipo_horario_display(),
                "turno": g.get_turno_display(),
                "cupo": int(g.cupo),
                "inscripciones_activas": int(getattr(g, "inscripciones_activas", 0)),
                "cupo_disponible": disponibles,
                "horario": horario_str,
                "disponibilidad": disponibilidad,
            }
        )
    return grupos


def load_cursos():
    p = Path(__file__).resolve().parent.parent / \
        "ui" / "catalogs" / "cursos.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_cursos_catalog():
    try:
        data = load_cursos()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return list(data.values())
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return []


def load_json_list(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_avisos_catalog():
    avisos = load_json_list(CATALOG_AVISOS_PATH)
    hoy = date.today()
    vigentes = []

    def parse_iso(value):
        if not value:
            return None
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            return None

    for aviso in avisos:
        if aviso.get("vigente") is False:
            continue

        fecha_inicio = parse_iso(
            aviso.get("fecha_inicio") or aviso.get("fecha"))
        fecha_fin = parse_iso(aviso.get("fecha_fin"))

        if fecha_inicio and fecha_inicio > hoy:
            continue
        if fecha_fin and fecha_fin < hoy:
            continue

        vigentes.append(aviso)

    # Ordenar desc por fecha de publicación/inicio para mostrar primero lo más reciente.
    return sorted(
        vigentes,
        key=lambda a: a.get("fecha_inicio") or a.get("fecha") or "",
        reverse=True,
    )


def load_faqs_catalog():
    faqs = load_json_list(CATALOG_FAQS_PATH)
    # Filtrar activas
    return [f for f in faqs if f.get("activa")]


def find_curso_by_slug(slug: str):
    for c in load_cursos_catalog():
        # Usamos "id" como slug por consistencia con catálogo actual
        if str(c.get("id")) == slug:
            return c
    return None


def build_security_challenge(request):
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    prompt = f"{a} + {b}"
    request.session[SECURITY_ANSWER_KEY] = str(a + b)
    request.session[SECURITY_PROMPT_KEY] = prompt
    request.session.modified = True
    return prompt


def get_security_question(request):
    return request.session.get(SECURITY_PROMPT_KEY) or build_security_challenge(request)


def registrar_bitacora_contacto(data, request):
    payload = {
        "modulo": "PORTAL",
        "tipo": "CONTACTO",
        "nombre": data.get("nombre"),
        "email": data.get("email"),
        "telefono": data.get("telefono"),
        "asunto": data.get("asunto"),
        "ip": request.META.get("REMOTE_ADDR"),
    }
    bitacora_logger.info("[PORTAL][CONTACTO] %s", payload)


def enviar_correo_contacto(data):
    """Envía dos correos tras un mensaje de contacto válido:

    1) Notificación interna al correo institucional (CONTACT_EMAIL).
    2) Acuse de recibo al remitente del formulario.

    Usa fail_silently=False en cada send_mail para que los errores SMTP
    queden registrados en la bitácora en lugar de perderse silenciosamente.
    Cada envío es independiente: un fallo en el acuse no bloquea la
    notificación interna y viceversa.
    """
    asunto_raw = data.get("asunto") or "Mensaje desde el portal"
    nombre = data.get("nombre", "")
    email_remitente = data.get("email", "")
    telefono = data.get("telefono") or "No proporcionado"
    mensaje = data.get("mensaje", "")

    site_name = getattr(settings, "SITE_NAME", "CCENT")
    noreply = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@joca.local")
    correo_institucional = getattr(settings, "CONTACT_EMAIL", noreply)

    cuerpo_institucional = (
        f"Nombre: {nombre}\n"
        f"Correo: {email_remitente}\n"
        f"Teléfono: {telefono}\n"
        f"Asunto: {asunto_raw}\n\n"
        f"Mensaje:\n{mensaje}"
    )
    cuerpo_acuse = (
        f"Hola {nombre},\n\n"
        f"Recibimos tu mensaje en {site_name} con el asunto \u00ab{asunto_raw}\u00bb.\n"
        f"Nos pondremos en contacto contigo a la brevedad.\n\n"
        f"Este es un correo automático, por favor no respondas a este mensaje."
    )

    # ── 1. Notificación al correo institucional ─────────────────────────────────────
    try:
        send_mail(
            subject=f"[{site_name}] {asunto_raw}",
            message=cuerpo_institucional,
            from_email=noreply,
            recipient_list=[correo_institucional],
            fail_silently=False,
        )
        bitacora_logger.info(
            "[PORTAL][CONTACTO][EMAIL] Notificación interna enviada a %s",
            correo_institucional,
        )
    except Exception as exc:
        bitacora_logger.error(
            "[PORTAL][CONTACTO][EMAIL] Error al enviar notificación interna a %s: %s",
            correo_institucional,
            exc,
        )

    # ── 2. Acuse de recibo al remitente ─────────────────────────────────────────
    if not email_remitente:
        return
    try:
        send_mail(
            subject=f"[{site_name}] Recibimos tu mensaje",
            message=cuerpo_acuse,
            from_email=noreply,
            recipient_list=[email_remitente],
            fail_silently=False,
        )
        bitacora_logger.info(
            "[PORTAL][CONTACTO][EMAIL] Acuse de recibo enviado a %s",
            email_remitente,
        )
    except Exception as exc:
        bitacora_logger.error(
            "[PORTAL][CONTACTO][EMAIL] Error al enviar acuse a %s: %s",
            email_remitente,
            exc,
        )


def portal_home(request):
    raw_cursos = load_cursos_catalog()
    cursos = []
    for c in raw_cursos:
        cursos.append(
            {
                **c,
                "categoria": c.get("categoria") or "General",
                "modalidad": c.get("modalidad") or "Presencial",
                "fecha_inicio": c.get("fecha_inicio") or "",
            }
        )

    categoria = (request.GET.get("categoria") or "").strip()
    modalidad = (request.GET.get("modalidad") or "").strip()
    fecha = (request.GET.get("fecha") or "").strip()

    if categoria:
        cursos = [c for c in cursos if str(
            c.get("categoria", "")).strip() == categoria]
    if modalidad:
        cursos = [c for c in cursos if str(
            c.get("modalidad", "")).strip() == modalidad]
    if fecha:
        cursos = [c for c in cursos if str(
            c.get("fecha_inicio", "")).strip() == fecha]

    categorias = sorted({str(c.get("categoria", "")).strip()
                        for c in raw_cursos if c.get("categoria")})
    modalidades = sorted({str(c.get("modalidad", "")).strip()
                         for c in raw_cursos if c.get("modalidad")})
    fechas = sorted({str(c.get("fecha_inicio", "")).strip()
                    for c in raw_cursos if c.get("fecha_inicio")})

    paginator = Paginator(cursos, 50)
    cursos_page = paginator.get_page(request.GET.get("page"))
    avisos = load_avisos_catalog()
    faqs = load_faqs_catalog()
    grupos_resumen = _load_groups_public_summary(limit=8)
    grupos_con_cupo = sum(
        1 for g in grupos_resumen if g["cupo_disponible"] > 0)

    return render(
        request,
        "ui/portal.html",
        {
            "cursos": cursos,
            "cursos_page": cursos_page,
            "categorias": categorias,
            "modalidades": modalidades,
            "fechas": fechas,
            "selected_categoria": categoria,
            "selected_modalidad": modalidad,
            "selected_fecha": fecha,
            "grupos": grupos_resumen,
            "grupos_con_cupo": grupos_con_cupo,
            "avisos": avisos,
            "faqs": faqs,
            "hoy": date.today().strftime("%d/%m/%Y"),
            "mision": getattr(settings, "PORTAL_MISION", ""),
            "vision": getattr(settings, "PORTAL_VISION", ""),
            "contacto_telefono": getattr(settings, "PORTAL_CONTACT_PHONE", "2755299"),
            "contacto_whatsapp": getattr(settings, "PORTAL_CONTACT_WHATSAPP", "4431722172"),
            "contacto_correo": getattr(settings, "PORTAL_CONTACT_EMAIL", "ccent_2012@hotmail.com"),
            "contacto_direccion": getattr(
                settings,
                "PORTAL_CONTACT_ADDRESS",
                "C. Juan Guillermo Villasana 131, Jardines de Guadalupe, 58140 Morelia, Michoacán.",
            ),
        },
    )


def portal_mision_vision(request):
    return render(
        request,
        "ui/portal_mision_vision.html",
        {
            "mision": getattr(settings, "PORTAL_MISION", ""),
            "vision": getattr(settings, "PORTAL_VISION", ""),
        },
    )


def curso_detalle(request, slug: str):
    curso = find_curso_by_slug(slug)
    if not curso:
        raise Http404("Curso no encontrado")

    # Defaults para campos adicionales solicitados
    enriched = {
        "slug": slug,
        "nombre": curso.get("nombre", "Curso"),
        "descripcion": curso.get("descripcion", "Descripción próximamente."),
        "imagen": curso.get("imagen", "ui/brand/logo.svg"),
        "categoria": curso.get("categoria", "Capacitación"),
        "modalidad": curso.get("modalidad", "Presencial"),
        "fecha_inicio": curso.get("fecha_inicio", "Próximo inicio"),
        "duracion": curso.get("duracion", "Duración a confirmar"),
        "costo": curso.get("costo", "Consulta costos"),
    }

    return render(
        request,
        "ui/curso_detalle.html",
        {"curso": enriched},
    )


def historias(request):
    # docs/historias_28.json dentro del contenedor (BASE_DIR suele ser /app)
    ruta = os.path.join(settings.BASE_DIR, "docs", "historias_28.json")
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            historias = json.load(f)
    except FileNotFoundError:
        historias = []

    return render(request, "public_portal/historias.html", {
        "historias": historias,
        "vps_base": request.build_absolute_uri("/").rstrip("/"),
    })
