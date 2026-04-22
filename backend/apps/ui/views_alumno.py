# apps/ui/views_alumno.py
from __future__ import annotations
import re
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse
from apps.ui.views import role_required
from apps.school.models import Alumno, Inscripcion, Calificacion
from io import BytesIO


def _get_alumno_for_user(request):
    """
    Devuelve el Alumno asociado al usuario logueado.
    Superusuario puede “ver como alumno” pasando ?alumno=<pk>
    """
    if request.user.is_superuser:
        pk = request.GET.get("alumno")
        if pk:
            return Alumno.objects.filter(pk=pk).first()

    # Intentos comunes de vinculación (según cómo esté tu modelo)
    # 1) OneToOne/ForeignKey desde Alumno hacia User (campo usuario/user)
    for field_name in ("usuario", "user"):
        try:
            return Alumno.objects.filter(**{field_name: request.user}).first()
        except Exception:
            pass

    # 2) Match por email/username vs matrícula/curp (si aplica)
    try:
        if request.user.email:
            a = Alumno.objects.filter(correo=request.user.email).first()
            if a:
                return a
    except Exception:
        pass

    try:
        a = Alumno.objects.filter(matricula=request.user.username).first()
        if a:
            return a
    except Exception:
        pass

    try:
        a = Alumno.objects.filter(curp=request.user.username).first()
        if a:
            return a
    except Exception:
        pass

    return None


@login_required(login_url="/acceso/")
@role_required("Alumno", "Superusuario")
def alumno_home(request):
    alumno = _get_alumno_for_user(request)
    if not alumno:
        return render(request, "ui/alumno/home.html", {"alumno": None})

    cards = [
        {"title": "Mis calificaciones", "desc": "Consulta por período y grupo",
            "href": "/panel/alumno/calificaciones/"},
        {"title": "Mis boletas",
            "desc": "Generar boleta por período (PDF)", "href": "/panel/alumno/boletas/"},
    ]
    return render(request, "ui/alumno/home.html", {"alumno": alumno, "cards": cards})


@login_required(login_url="/acceso/")
@role_required("Alumno", "Superusuario")
def alumno_calificaciones(request):
    alumno = _get_alumno_for_user(request)
    if not alumno:
        return render(request, "ui/alumno/calificaciones.html", {"alumno": None, "calificaciones": []})

    calificaciones = (
        Calificacion.objects
        .select_related("inscripcion", "inscripcion__grupo", "inscripcion__alumno")
        .filter(inscripcion__alumno=alumno)
        .order_by("-capturado_en")
    )

    return render(
        request,
        "ui/alumno/calificaciones.html",
        {"alumno": alumno, "calificaciones": calificaciones},
    )


@login_required(login_url="/acceso/")
@role_required("Alumno", "Superusuario")
def alumno_boletas(request):
    alumno = _get_alumno_for_user(request)
    if not alumno:
        return render(request, "ui/alumno/boletas.html", {"alumno": None, "periodos": []})

    periodos = (
        Inscripcion.objects
        .select_related("grupo")
        .filter(alumno=alumno)
        .values_list("grupo__periodo_ref__codigo", flat=True)
        .distinct()
        .order_by("-grupo__periodo_ref__codigo")
    )

    # Nota: usa alumno.pk (no alumno.id) porque tu PK parece llamarse distinto (ej. id_alumno)
    return render(
        request,
        "ui/alumno/boletas.html",
        {"alumno": alumno, "periodos": list(periodos)},
    )


PERIODO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@login_required(login_url="/acceso/")
@role_required("Alumno", "Superusuario")
def alumno_boleta_pdf(request):
    alumno = _get_alumno_for_user(request)
    if not alumno:
        return HttpResponse("Tu cuenta no está vinculada a un alumno.", status=400)

    periodo = (request.GET.get("periodo") or "").strip()
    if not PERIODO_RE.match(periodo):
        return HttpResponse("Periodo inválido. Usa YYYY-MM.", status=400)

    califs = (
        Calificacion.objects
        .select_related("inscripcion__grupo", "inscripcion__alumno")
        .filter(inscripcion__alumno=alumno, inscripcion__grupo__periodo_ref__codigo=periodo)
        .order_by("id")
    )

    # ---- PDF (ReportLab) ----
    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import cm
        from reportlab.lib import colors
    except Exception:
        return HttpResponse(
            "No se puede generar PDF: falta la dependencia 'reportlab'.",
            status=500
        )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title=f"Boleta {alumno.matricula} {periodo}",
    )

    styles = getSampleStyleSheet()
    story = []

    # Encabezado
    story.append(Paragraph("Boleta de calificaciones", styles["Title"]))
    story.append(Spacer(1, 8))

    # Datos alumno (ajusta si quieres más campos)
    alumno_nombre = getattr(alumno, "nombre", "") or ""
    alumno_matricula = getattr(alumno, "matricula", "") or ""
    story.append(
        Paragraph(f"<b>Alumno:</b> {alumno_nombre}", styles["Normal"]))
    story.append(
        Paragraph(f"<b>Matrícula:</b> {alumno_matricula}", styles["Normal"]))
    story.append(Paragraph(f"<b>Período:</b> {periodo}", styles["Normal"]))
    story.append(Spacer(1, 10))

    # Tabla
    data = [["Grupo", "Calificación", "Capturado"]]

    valores = []
    for c in califs:
        grupo_txt = str(c.inscripcion.grupo)  # usa __str__ del grupo
        valor_txt = str(getattr(c, "valor", ""))
        capturado = getattr(c, "capturado_en", None)
        capturado_txt = capturado.strftime(
            "%d/%m/%Y %H:%M") if capturado else ""

        data.append([grupo_txt, valor_txt, capturado_txt])

        # Promedio (si el valor es numérico)
        try:
            valores.append(float(c.valor))
        except Exception:
            pass

    if len(data) == 1:
        data.append(["(Sin registros en este período)", "", ""])

    tabla = Table(data, colWidths=[9*cm, 3*cm, 4*cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.whitesmoke, colors.white]),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(tabla)
    story.append(Spacer(1, 10))

    # Resumen
    if valores:
        prom = sum(valores) / len(valores)
        story.append(
            Paragraph(f"<b>Total de calificaciones:</b> {len(valores)}", styles["Normal"]))
        story.append(
            Paragraph(f"<b>Promedio:</b> {prom:.2f}", styles["Normal"]))
    else:
        story.append(
            Paragraph("<b>Total de calificaciones:</b> 0", styles["Normal"]))

    doc.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="boleta_{alumno.matricula}_{periodo}.pdf"'
    return resp
