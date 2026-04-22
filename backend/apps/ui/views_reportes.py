# apps/ui/views_reportes.py
from __future__ import annotations
from functools import wraps
from decimal import Decimal
import csv
import hashlib
from io import BytesIO, StringIO

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.shortcuts import render
from django.db.models import Avg, Case, Count, DecimalField, ExpressionWrapper, F, Q, Sum, When
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from apps.accounts.models import UsuarioRol
from apps.authn.decorators import rate_limit
from apps.governance.services.audit import log_event
from apps.governance.models import ParametroSistema
from apps.school.models import Alumno, Grupo, Inscripcion, Calificacion, ActaCierre
from django.core.mail import EmailMessage
from apps.ui.input_validation import (
    sanitize_csv_cell,
    validate_choice,
    validate_email_value,
    validate_hhmm,
    validate_int_range,
    validate_required_text,
)

try:
    from apps.sales.models import Concepto, OrdenItem, OrdenPOS, Pago, Ticket, AlertaStock, Existencia, CorteCaja
except Exception:  # pragma: no cover
    Concepto = None
    OrdenItem = None
    OrdenPOS = None
    Pago = None
    Ticket = None
    AlertaStock = None
    Existencia = None
    CorteCaja = None


def _rol_codigo(user):
    if not user.is_authenticated:
        return None
    ur = UsuarioRol.objects.select_related("rol").filter(usuario=user).first()
    return ur.rol.codigo if ur and ur.rol else None


def _parse_periodo(periodo: str) -> tuple[int | None, int | None]:
    try:
        year_text, month_text = periodo.split("-", 1)
        year = int(year_text)
        month = int(month_text)
        if month < 1 or month > 12:
            return None, None
        return year, month
    except Exception:
        return None, None


def _parse_decimal_or_none(raw_value):
    text = (raw_value or "").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def _orden_total_expr(prefix="items__"):
    return ExpressionWrapper(
        F(f"{prefix}cantidad") * F(f"{prefix}precio_unit"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


def _aggregate_ordenes_monto(queryset):
    if queryset is None:
        return Decimal("0.00")
    return queryset.aggregate(total=Sum(_orden_total_expr())).get("total") or Decimal("0.00")


def _load_report_schedule_values():
    defaults = {
        "reportes_envio_activo": "0",
        "reportes_envio_frecuencia": "diario",
        "reportes_envio_hora": "08:00",
        "reportes_envio_dia_semana": "1",
        "reportes_envio_dia_mes": "1",
        "reportes_envio_reporte": "ejecutivo",
        "reportes_envio_formato": "pdf",
        "reportes_envio_destinatarios": "",
        "reportes_envio_ultimo": "",
    }
    for item in ParametroSistema.objects.filter(categoria=ParametroSistema.CATEGORIA_REPORTES):
        defaults[item.clave] = item.valor
    return defaults


def _save_report_schedule_values(values):
    for key, value in values.items():
        ParametroSistema.objects.update_or_create(
            clave=key,
            defaults={
                "categoria": ParametroSistema.CATEGORIA_REPORTES,
                "valor": value,
                "activo": True,
            },
        )


def _parse_email_list(raw_text):
    emails = []
    for token in (raw_text or "").replace(";", ",").split(","):
        candidate = token.strip()
        if not candidate:
            continue
        try:
            candidate = validate_email_value(candidate, "Correo destinatario")
        except Exception:
            continue
        emails.append(candidate)
    return list(dict.fromkeys(emails))


def _dashboard_view_catalog():
    return [
        {
            "key": "ejecutivo",
            "title": "Tablero ejecutivo",
            "desc": "KPIs generales del sistema",
            "href": "/panel/reportes/ejecutivo/",
        },
        {
            "key": "academico",
            "title": "Reporte académico",
            "desc": "Alumnos, grupos, inscripciones, calificaciones",
            "href": "/panel/reportes/academico/",
        },
        {
            "key": "comercial",
            "title": "Reporte comercial",
            "desc": "Conceptos, órdenes POS, pagos",
            "href": "/panel/reportes/comercial/",
        },
        {
            "key": "hu012_adeudos",
            "title": "Adeudos HU012",
            "desc": "Consulta rápida de adeudos HU012",
            "href": "/panel/reportes/hu012-adeudos/",
        },
        {
            "key": "programacion",
            "title": "Programación de envío",
            "desc": "Configurar envío periódico por correo",
            "href": "/panel/reportes/programacion/",
        },
        {
            "key": "alertas",
            "title": "Alertas y pendientes",
            "desc": "Alertas de inventario y órdenes abiertas",
            "href": "/panel/reportes/alertas/",
        },
    ]


def _dashboard_favorites_param_key(user):
    return f"reportes_tablero_favoritos_u{user.id}"


def _load_dashboard_favorites(user):
    if not user or not user.is_authenticated:
        return []
    allowed = {item["key"] for item in _dashboard_view_catalog()}
    param = ParametroSistema.objects.filter(
        categoria=ParametroSistema.CATEGORIA_REPORTES,
        clave=_dashboard_favorites_param_key(user),
    ).first()
    if not param or not param.valor:
        return []
    selected = []
    for token in param.valor.split(","):
        candidate = (token or "").strip().lower()
        if candidate and candidate in allowed and candidate not in selected:
            selected.append(candidate)
    return selected


def _save_dashboard_favorites(user, selected_keys):
    clean = []
    allowed = {item["key"] for item in _dashboard_view_catalog()}
    for token in selected_keys:
        candidate = (token or "").strip().lower()
        if candidate and candidate in allowed and candidate not in clean:
            clean.append(candidate)

    ParametroSistema.objects.update_or_create(
        categoria=ParametroSistema.CATEGORIA_REPORTES,
        clave=_dashboard_favorites_param_key(user),
        defaults={
            "valor": ",".join(clean),
            "activo": True,
        },
    )
    return clean


def _build_ejecutivo_csv_bytes(kpi_cards):
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(["indicador", "valor", "meta"])
    for card in kpi_cards:
        writer.writerow([
            sanitize_csv_cell(card.get("label", "")),
            sanitize_csv_cell(card.get("value", "")),
            sanitize_csv_cell(card.get("meta", "")),
        ])
    content = stream.getvalue()
    stream.close()
    return content.encode("utf-8")


def _build_ejecutivo_pdf_bytes(kpi_cards):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(40, y, "Reporte ejecutivo")
    y -= 18
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, y, f"Generado: {timezone.now().isoformat()}")
    y -= 16
    pdf.setFont("Helvetica", 9)
    for card in kpi_cards:
        meta = card.get("meta") or ""
        line = f"{card.get('label', '')}: {card.get('value', '')} {meta}".strip()
        pdf.drawString(40, y, line[:120])
        y -= 12
        if y < 70:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 9)
    pdf.save()
    content = buffer.getvalue()
    buffer.close()
    return content


def _build_reporte_ejecutivo_payload():
    today = timezone.localdate()
    matricula_activa = Inscripcion.objects.filter(
        estado=Inscripcion.ESTADO_ACTIVA).count()

    ventas_hoy_qs = Pago.objects.filter(fecha_pago__date=today) if Pago else []
    ventas_hoy_total = ventas_hoy_qs.aggregate(
        total=Sum("monto")).get("total") if Pago else Decimal("0")
    ventas_hoy_total = ventas_hoy_total or Decimal("0")
    ventas_hoy_count = ventas_hoy_qs.count() if Pago else 0

    morosidad_ordenes = 0
    morosidad_monto = Decimal("0")
    if OrdenPOS:
        candidatos = OrdenPOS.objects.exclude(
            estado=OrdenPOS.ESTADO_CANCELADA).exclude(estado=OrdenPOS.ESTADO_PAGADA)
        for orden in candidatos:
            pagado = orden.pagos.aggregate(
                total=Sum("monto")).get("total") or Decimal("0")
            deuda = (Decimal(orden.total_calculado) or Decimal("0")) - pagado
            if deuda > 0:
                morosidad_ordenes += 1
                morosidad_monto += deuda

    alertas_activas = AlertaStock.objects.filter(
        activa=True).count() if AlertaStock else 0
    alertas_por_existencia = 0
    if Existencia:
        alertas_por_existencia = Existencia.objects.filter(
            inventario_habilitado=True,
            stock_actual__lte=F("stock_minimo"),
        ).count()

    return [
        {"key": "matricula_activa", "label": "Matricula activa",
            "value": matricula_activa},
        {"key": "ventas_dia", "label": "Ventas del dia",
            "value": f"${ventas_hoy_total:.2f}", "meta": f"{ventas_hoy_count} pagos"},
        {"key": "morosidad", "label": "Morosidad", "value": f"${morosidad_monto:.2f}",
            "meta": f"{morosidad_ordenes} ordenes con adeudo"},
        {"key": "alertas_inventario", "label": "Alertas de inventario",
            "value": alertas_activas + alertas_por_existencia},
    ]


def _build_scheduled_report_content(report_key, export_format):
    if report_key == "academico":
        inscripciones_por_periodo = list(
            Inscripcion.objects.values(periodo=F("grupo__periodo_ref__codigo"))
            .annotate(
                total=Count("id"),
                activas=Count("id", filter=Q(
                    estado=Inscripcion.ESTADO_ACTIVA)),
                bajas=Count("id", filter=Q(estado=Inscripcion.ESTADO_BAJA)),
                finalizadas=Count("id", filter=Q(
                    estado=Inscripcion.ESTADO_FINALIZADA)),
            )
            .order_by("-periodo")
        )
        calificaciones = Calificacion.objects.select_related(
            "inscripcion__alumno", "inscripcion__grupo").order_by("-id")[:200]
        calif_stats = Calificacion.objects.aggregate(promedio=Avg("valor"))
        calif_promedio = calif_stats.get("promedio")
        kpi = {
            "inscripciones": Inscripcion.objects.count(),
            "calificaciones": Calificacion.objects.count(),
            "calif_promedio": f"{calif_promedio:.2f}" if calif_promedio is not None else "N/A",
        }
        if export_format == "csv":
            return _build_academico_csv_bytes(inscripciones_por_periodo, calificaciones)
        return _build_academico_pdf_bytes(kpi, inscripciones_por_periodo, calificaciones)

    if report_key == "comercial":
        ventas_por_periodo = []
        if OrdenPOS:
            ventas_por_periodo = list(
                OrdenPOS.objects.exclude(estado=OrdenPOS.ESTADO_CANCELADA)
                .values(periodo=F("inscripcion__grupo__periodo_ref__codigo"))
                .annotate(
                    total_ordenes=Count("id", distinct=True),
                    monto_ordenes=Sum(_orden_total_expr()),
                    pagadas=Count("id", filter=Q(
                        estado=OrdenPOS.ESTADO_PAGADA)),
                    pendientes=Count("id", filter=Q(
                        estado__in=[OrdenPOS.ESTADO_PENDIENTE, OrdenPOS.ESTADO_PARCIAL])),
                )
                .order_by("-periodo")
            )
        cortes_caja = CorteCaja.objects.order_by(
            "-fecha_operacion", "-cerrado_en")[:200] if CorteCaja else []
        monto_ventas = _aggregate_ordenes_monto(
            OrdenPOS.objects.exclude(estado=OrdenPOS.ESTADO_CANCELADA)
        ) if OrdenPOS else Decimal("0")
        monto_pagos = Pago.objects.aggregate(total=Sum("monto")).get(
            "total") if Pago else Decimal("0")
        # Inscripciones como venta
        _sched_insc = []
        if OrdenPOS and OrdenItem:
            _concepto_expr = ExpressionWrapper(
                F("cantidad") * F("precio_unit"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
            for _row in (
                OrdenItem.objects
                .filter(
                    orden__estado__in=[
                        OrdenPOS.ESTADO_PENDIENTE, OrdenPOS.ESTADO_PARCIAL, OrdenPOS.ESTADO_PAGADA],
                    concepto__nombre__in=[
                        "Inscripcion escolar", "IVA inscripcion 16%"],
                )
                .values(periodo=F("orden__inscripcion__grupo__periodo_ref__codigo"))
                .annotate(
                    total_inscripciones=Count("orden_id", distinct=True),
                    monto_base=Sum(Case(When(concepto__nombre="Inscripcion escolar", then=_concepto_expr), default=Decimal(
                        "0"), output_field=DecimalField(max_digits=12, decimal_places=2))),
                    monto_iva=Sum(Case(When(concepto__nombre="IVA inscripcion 16%", then=_concepto_expr), default=Decimal(
                        "0"), output_field=DecimalField(max_digits=12, decimal_places=2))),
                )
                .order_by("-periodo")
            ):
                _b = _row["monto_base"] or Decimal("0")
                _v = _row["monto_iva"] or Decimal("0")
                _sched_insc.append(
                    {"periodo": _row["periodo"], "total_inscripciones": _row["total_inscripciones"], "monto_base": _b, "monto_iva": _v, "total": _b + _v})
        kpi = {
            "ordenes_pos": OrdenPOS.objects.count() if OrdenPOS else 0,
            "pagos": Pago.objects.count() if Pago else 0,
            "ventas_periodo_total": f"{(monto_ventas or Decimal('0')):.2f}",
        }
        if export_format == "csv":
            return _build_comercial_csv_bytes(ventas_por_periodo, cortes_caja, _sched_insc)
        return _build_comercial_pdf_bytes(kpi, ventas_por_periodo, cortes_caja, _sched_insc)

    kpi_cards = _build_reporte_ejecutivo_payload()
    if export_format == "csv":
        return _build_ejecutivo_csv_bytes(kpi_cards)
    return _build_ejecutivo_pdf_bytes(kpi_cards)


def _schedule_is_due(values, now_dt):
    if values.get("reportes_envio_activo") != "1":
        return False

    frecuencia = values.get("reportes_envio_frecuencia") or "diario"
    hora = values.get("reportes_envio_hora") or "08:00"
    dia_semana = values.get("reportes_envio_dia_semana") or "1"
    dia_mes = values.get("reportes_envio_dia_mes") or "1"
    last_sent = values.get("reportes_envio_ultimo") or ""

    try:
        hh, mm = hora.split(":", 1)
        hh_int, mm_int = int(hh), int(mm)
    except Exception:
        hh_int, mm_int = 8, 0

    scheduled_today = now_dt.replace(
        hour=hh_int, minute=mm_int, second=0, microsecond=0)
    if now_dt < scheduled_today:
        return False

    if frecuencia == "semanal":
        if str(now_dt.weekday()) != str(dia_semana):
            return False
    elif frecuencia == "mensual":
        if str(now_dt.day) != str(dia_mes):
            return False

    if not last_sent:
        return True
    try:
        last_dt = timezone.datetime.fromisoformat(last_sent)
        if timezone.is_naive(last_dt):
            last_dt = timezone.make_aware(
                last_dt, timezone.get_current_timezone())
    except Exception:
        return True

    if frecuencia == "diario":
        return last_dt.date() < now_dt.date()
    if frecuencia == "semanal":
        return (now_dt.date() - last_dt.date()).days >= 7
    return (now_dt.year, now_dt.month) != (last_dt.year, last_dt.month)


def ejecutar_envio_periodico_reportes(force=False, actor=None):
    values = _load_report_schedule_values()
    now_dt = timezone.localtime(timezone.now())
    if not force and not _schedule_is_due(values, now_dt):
        return {"status": "skipped", "reason": "not_due_or_disabled"}

    recipients = _parse_email_list(values.get("reportes_envio_destinatarios"))
    if not recipients:
        log_event(
            None,
            accion="REPORTES::ENVIO_PERIODICO",
            entidad="ReporteProgramado",
            entidad_id=values.get("reportes_envio_reporte") or "ejecutivo",
            resultado="error",
            detalle={"reason": "no_recipients"},
        )
        return {"status": "error", "reason": "no_recipients"}

    report_key = values.get("reportes_envio_reporte") or "ejecutivo"
    if report_key not in {"ejecutivo", "academico", "comercial"}:
        report_key = "ejecutivo"

    export_format = values.get("reportes_envio_formato") or "pdf"
    if export_format not in {"csv", "pdf"}:
        export_format = "pdf"

    content_bytes = _build_scheduled_report_content(report_key, export_format)
    response, digest, filename = _render_export_response(
        content_bytes, export_format, f"reporte_{report_key}_programado")

    email = EmailMessage(
        subject=f"Reporte programado: {report_key}",
        body=f"Se adjunta reporte {report_key} en formato {export_format}.",
        to=recipients,
    )
    mime_type = "text/csv" if export_format == "csv" else "application/pdf"
    email.attach(filename, content_bytes, mime_type)
    email.send(fail_silently=False)

    _save_report_schedule_values({"reportes_envio_ultimo": now_dt.isoformat()})
    log_event(
        None,
        accion="REPORTES::ENVIO_PERIODICO",
        entidad="ReporteProgramado",
        entidad_id=report_key,
        resultado="ok",
        detalle={
            "format": export_format,
            "sha256": digest,
            "filename": filename,
            "recipients": recipients,
            "force": bool(force),
        },
    )
    return {
        "status": "ok",
        "report": report_key,
        "format": export_format,
        "filename": filename,
        "sha256": digest,
        "recipients": recipients,
    }


def _render_export_response(content_bytes, export_format, filename_prefix):
    timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    digest = hashlib.sha256(content_bytes).hexdigest()
    extension = "csv" if export_format == "csv" else "pdf"
    filename = f"{filename_prefix}_{timestamp}_{digest[:12]}.{extension}"
    content_type = "text/csv; charset=utf-8" if export_format == "csv" else "application/pdf"

    response = HttpResponse(content_bytes, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Export-SHA256"] = digest
    return response, digest, filename


def _build_academico_csv_bytes(inscripciones_por_periodo, calificaciones):
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(["seccion", "periodo", "total",
                    "activas", "bajas", "finalizadas"])
    for row in inscripciones_por_periodo:
        writer.writerow([
            sanitize_csv_cell("inscripciones"),
            sanitize_csv_cell(row["periodo"]),
            sanitize_csv_cell(row["total"]),
            sanitize_csv_cell(row["activas"]),
            sanitize_csv_cell(row["bajas"]),
            sanitize_csv_cell(row["finalizadas"]),
        ])

    writer.writerow([])
    writer.writerow(["seccion", "periodo", "alumno", "grupo", "valor"])
    for c in calificaciones:
        writer.writerow([
            sanitize_csv_cell("calificaciones"),
            sanitize_csv_cell(c.inscripcion.grupo.periodo),
            sanitize_csv_cell(str(c.inscripcion.alumno)),
            sanitize_csv_cell(str(c.inscripcion.grupo)),
            sanitize_csv_cell(str(c.valor)),
        ])

    content = stream.getvalue()
    stream.close()
    return content.encode("utf-8")


def _build_academico_pdf_bytes(kpi, inscripciones_por_periodo, calificaciones):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(40, y, "Reporte academico")
    y -= 18
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, y, f"Generado: {timezone.now().isoformat()}")
    y -= 14
    pdf.drawString(
        40, y, f"Inscripciones: {kpi['inscripciones']} | Calificaciones: {kpi['calificaciones']} | Promedio: {kpi['calif_promedio']}")
    y -= 18

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Inscripciones por periodo")
    y -= 14
    pdf.setFont("Helvetica", 8)
    for row in inscripciones_por_periodo[:150]:
        line = f"{row['periodo']}: total={row['total']} activas={row['activas']} bajas={row['bajas']} finalizadas={row['finalizadas']}"
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
    pdf.drawString(40, y, "Calificaciones")
    y -= 14
    pdf.setFont("Helvetica", 8)
    for c in list(calificaciones)[:200]:
        line = f"{c.inscripcion.grupo.periodo} | {c.inscripcion.alumno} | {c.inscripcion.grupo} | {c.valor}"
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


def _build_comercial_csv_bytes(ventas_por_periodo, cortes_caja, inscripciones_ventas=None):
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(["seccion", "periodo", "total_ordenes",
                    "monto_ordenes", "pagadas", "pendientes"])
    for row in ventas_por_periodo:
        writer.writerow([
            sanitize_csv_cell("ventas"),
            sanitize_csv_cell(row["periodo"]),
            sanitize_csv_cell(row["total_ordenes"]),
            sanitize_csv_cell(row["monto_ordenes"] or Decimal("0.00")),
            sanitize_csv_cell(row["pagadas"]),
            sanitize_csv_cell(row["pendientes"]),
        ])

    writer.writerow([])
    writer.writerow(["seccion", "fecha_operacion", "total_ordenes",
                    "monto_ordenes", "total_pagos", "monto_pagos", "notas"])
    for c in cortes_caja:
        resumen = CorteCaja.resumen_calculado(c.fecha_operacion)
        writer.writerow([
            sanitize_csv_cell("cortes"),
            sanitize_csv_cell(c.fecha_operacion.isoformat()),
            sanitize_csv_cell(c.total_ordenes),
            sanitize_csv_cell(resumen["monto_ordenes"]),
            sanitize_csv_cell(c.total_pagos),
            sanitize_csv_cell(resumen["monto_pagos"]),
            sanitize_csv_cell(c.notas or ""),
        ])

    if inscripciones_ventas:
        writer.writerow([])
        writer.writerow(["seccion", "periodo", "total_inscripciones",
                         "monto_base", "monto_iva", "total"])
        for row in inscripciones_ventas:
            writer.writerow([
                sanitize_csv_cell("inscripciones"),
                sanitize_csv_cell(row["periodo"]),
                sanitize_csv_cell(row["total_inscripciones"]),
                sanitize_csv_cell(row["monto_base"]),
                sanitize_csv_cell(row["monto_iva"]),
                sanitize_csv_cell(row["total"]),
            ])

    content = stream.getvalue()
    stream.close()
    return content.encode("utf-8")


def _build_comercial_pdf_bytes(kpi, ventas_por_periodo, cortes_caja, inscripciones_ventas=None):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(40, y, "Reporte comercial")
    y -= 18
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, y, f"Generado: {timezone.now().isoformat()}")
    y -= 14
    pdf.drawString(
        40, y, f"Ordenes: {kpi['ordenes_pos']} | Pagos: {kpi['pagos']} | Ventas: {kpi['ventas_periodo_total']}")
    y -= 18

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Ventas por periodo")
    y -= 14
    pdf.setFont("Helvetica", 8)
    for row in ventas_por_periodo[:150]:
        line = f"{row['periodo']}: ordenes={row['total_ordenes']} monto={row['monto_ordenes'] or Decimal('0.00')} pagadas={row['pagadas']} pendientes={row['pendientes']}"
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
    pdf.drawString(40, y, "Cortes de caja")
    y -= 14
    pdf.setFont("Helvetica", 8)
    for c in list(cortes_caja)[:180]:
        resumen = CorteCaja.resumen_calculado(c.fecha_operacion)
        line = f"{c.fecha_operacion} ordenes={c.total_ordenes} monto_ordenes={resumen['monto_ordenes']} pagos={c.total_pagos} monto_pagos={resumen['monto_pagos']}"
        pdf.drawString(40, y, line[:120])
        y -= 11
        if y < 70:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 8)

    if inscripciones_ventas:
        y -= 6
        if y < 90:
            pdf.showPage()
            y = height - 50
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(40, y, "Inscripciones (base / IVA / total)")
        y -= 14
        pdf.setFont("Helvetica", 8)
        for row in inscripciones_ventas[:150]:
            line = (
                f"{row['periodo']}: inscripciones={row['total_inscripciones']} "
                f"base=${row['monto_base']:.2f} iva=${row['monto_iva']:.2f} "
                f"total=${row['total']:.2f}"
            )
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


def _build_hu012_adeudos_csv_bytes(ordenes):
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow([
        "orden_id",
        "alumno",
        "matricula",
        "periodo",
        "estado",
        "total_orden",
        "pagado",
        "adeudo",
    ])

    for orden in ordenes:
        writer.writerow([
            sanitize_csv_cell(orden.id),
            sanitize_csv_cell(str(orden.inscripcion.alumno)),
            sanitize_csv_cell(orden.inscripcion.alumno.matricula),
            sanitize_csv_cell(orden.inscripcion.grupo.periodo_ref.codigo),
            sanitize_csv_cell(orden.estado),
            sanitize_csv_cell(orden.total_orden),
            sanitize_csv_cell(orden.pagado),
            sanitize_csv_cell(orden.adeudo),
        ])

    content = stream.getvalue()
    stream.close()
    return content.encode("utf-8")


def role_required_codes(*allowed_codes):
    def deco(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            code = _rol_codigo(request.user)
            if code in allowed_codes:
                return view_func(request, *args, **kwargs)

            return render(
                request,
                "ui/forbidden.html",
                {"role": code or "Usuario",
                    "allowed": ", ".join(allowed_codes)},
                status=403,
            )
        return _wrapped
    return deco


@login_required(login_url="/acceso/")
@role_required_codes("SUPERUSUARIO", "DIRECTOR_ESCOLAR", "ADMINISTRATIVO_COMERCIAL")
def reportes_home(request):
    if request.method == "POST":
        selected = request.POST.getlist("favorite_views")
        allowed_views = {card["key"] for card in _dashboard_view_catalog()}
        selected = [item for item in selected if item in allowed_views]
        saved = _save_dashboard_favorites(request.user, selected)
        log_event(
            request,
            accion="REPORTES::FAVORITOS_TABLERO_UPDATE",
            entidad="ParametroSistema",
            entidad_id=_dashboard_favorites_param_key(request.user),
            resultado="ok",
            detalle={"favorite_views": saved},
        )
        messages.success(request, "Vistas favoritas actualizadas.")

    cards = _dashboard_view_catalog()
    favorite_keys = set(_load_dashboard_favorites(request.user))
    for card in cards:
        card["is_favorite"] = card["key"] in favorite_keys

    favorite_cards = [card for card in cards if card["is_favorite"]]
    return render(
        request,
        "ui/reportes/home.html",
        {
            "cards": cards,
            "favorite_cards": favorite_cards,
        },
    )


@login_required(login_url="/acceso/")
@role_required_codes("SUPERUSUARIO", "DIRECTOR_ESCOLAR", "ADMINISTRATIVO_COMERCIAL")
def reporte_programacion(request):
    if request.method == "POST":
        operation = (request.POST.get("operation") or "save").strip().lower()
        try:
            operation = validate_choice(
                operation, {"save", "send_now"}, "Operación")
        except Exception as exc:
            messages.error(request, str(exc))
            return render(request, "ui/reportes/programacion.html", {"values": _load_report_schedule_values()})
        if operation == "send_now":
            result = ejecutar_envio_periodico_reportes(
                force=True, actor=request.user)
            if result.get("status") == "ok":
                messages.success(request, "Envío ejecutado correctamente.")
            else:
                messages.error(
                    request, f"No fue posible enviar: {result.get('reason', 'error')}")
        else:
            values = {
                "reportes_envio_activo": "1" if request.POST.get("reportes_envio_activo") in {"on", "1", "true", "TRUE"} else "0",
                "reportes_envio_frecuencia": (request.POST.get("reportes_envio_frecuencia") or "diario").strip().lower(),
                "reportes_envio_hora": (request.POST.get("reportes_envio_hora") or "08:00").strip(),
                "reportes_envio_dia_semana": (request.POST.get("reportes_envio_dia_semana") or "1").strip(),
                "reportes_envio_dia_mes": (request.POST.get("reportes_envio_dia_mes") or "1").strip(),
                "reportes_envio_reporte": (request.POST.get("reportes_envio_reporte") or "ejecutivo").strip().lower(),
                "reportes_envio_formato": (request.POST.get("reportes_envio_formato") or "pdf").strip().lower(),
                "reportes_envio_destinatarios": (request.POST.get("reportes_envio_destinatarios") or "").strip(),
            }

            try:
                values["reportes_envio_frecuencia"] = validate_choice(
                    values["reportes_envio_frecuencia"],
                    {"diario", "semanal", "mensual"},
                    "Frecuencia",
                )
                values["reportes_envio_reporte"] = validate_choice(
                    values["reportes_envio_reporte"],
                    {"ejecutivo", "academico", "comercial"},
                    "Tipo de reporte",
                )
                values["reportes_envio_formato"] = validate_choice(
                    values["reportes_envio_formato"],
                    {"csv", "pdf"},
                    "Formato",
                )
                values["reportes_envio_hora"] = validate_hhmm(
                    values["reportes_envio_hora"],
                    "Hora programada",
                )
                values["reportes_envio_dia_semana"] = validate_int_range(
                    values["reportes_envio_dia_semana"],
                    0,
                    6,
                    "Día de semana",
                )
                values["reportes_envio_dia_mes"] = validate_int_range(
                    values["reportes_envio_dia_mes"],
                    1,
                    31,
                    "Día del mes",
                )
                if values["reportes_envio_activo"] == "1":
                    validate_required_text(
                        values["reportes_envio_destinatarios"],
                        "Destinatarios",
                    )
                    recipients = _parse_email_list(
                        values["reportes_envio_destinatarios"])
                    if not recipients:
                        raise ValueError(
                            "Destinatarios inválidos. Captura al menos un correo válido.")
                    values["reportes_envio_destinatarios"] = ", ".join(
                        recipients)
            except Exception as exc:
                messages.error(request, str(exc))
                return render(request, "ui/reportes/programacion.html", {"values": _load_report_schedule_values()})

            _save_report_schedule_values(values)
            log_event(
                request,
                accion="REPORTES::PROGRAMACION_UPDATE",
                entidad="ParametroSistema",
                entidad_id="reportes_programados",
                resultado="ok",
                detalle=values,
            )
            messages.success(request, "Programación de reportes actualizada.")

    values = _load_report_schedule_values()
    return render(request, "ui/reportes/programacion.html", {"values": values})


@rate_limit("export_ejecutivo", max_calls=30, period_seconds=300)
@login_required(login_url="/acceso/")
@role_required_codes("SUPERUSUARIO", "DIRECTOR_ESCOLAR", "ADMINISTRATIVO_COMERCIAL")
def reporte_ejecutivo(request):
    today = timezone.localdate()

    matricula_activa = Inscripcion.objects.filter(
        estado=Inscripcion.ESTADO_ACTIVA).count()

    ventas_hoy_qs = Pago.objects.filter(fecha_pago__date=today) if Pago else []
    ventas_hoy_total = ventas_hoy_qs.aggregate(
        total=Sum("monto")).get("total") if Pago else Decimal("0")
    ventas_hoy_total = ventas_hoy_total or Decimal("0")
    ventas_hoy_count = ventas_hoy_qs.count() if Pago else 0

    morosidad_ordenes = 0
    morosidad_monto = Decimal("0")
    if OrdenPOS:
        candidatos = OrdenPOS.objects.exclude(estado=OrdenPOS.ESTADO_CANCELADA).exclude(
            estado=OrdenPOS.ESTADO_PAGADA
        )
        for orden in candidatos:
            pagado = orden.pagos.aggregate(
                total=Sum("monto")).get("total") or Decimal("0")
            deuda = (Decimal(orden.total_calculado) or Decimal("0")) - pagado
            if deuda > 0:
                morosidad_ordenes += 1
                morosidad_monto += deuda

    alertas_activas = AlertaStock.objects.filter(
        activa=True).count() if AlertaStock else 0
    alertas_por_existencia = 0
    if Existencia:
        alertas_por_existencia = Existencia.objects.filter(
            inventario_habilitado=True,
            stock_actual__lte=F("stock_minimo"),
        ).count()

    kpi = {
        "matricula_activa": matricula_activa,
        "ventas_dia": f"{ventas_hoy_total:.2f}",
        "morosidad": f"{morosidad_monto:.2f}",
        "alertas_inventario": alertas_activas + alertas_por_existencia,
        "alumnos": Alumno.objects.count(),
        "grupos": Grupo.objects.count(),
        "inscripciones": Inscripcion.objects.count(),
        "calificaciones": Calificacion.objects.count(),
        "actas_cerradas": ActaCierre.objects.count(),
        "conceptos": Concepto.objects.count() if Concepto else 0,
        "ordenes_pos": OrdenPOS.objects.count() if OrdenPOS else 0,
        "pagos": Pago.objects.count() if Pago else 0,
        "tickets": Ticket.objects.count() if Ticket else 0,
    }

    ult_calif = Calificacion.objects.select_related(
        "inscripcion__alumno", "inscripcion__grupo"
    ).order_by("-id")[:10]

    ult_ordenes = OrdenPOS.objects.order_by("-id")[:10] if OrdenPOS else []
    ult_pagos = Pago.objects.order_by("-id")[:10] if Pago else []

    kpi_cards = [
        {"key": "matricula_activa", "label": "Matricula activa",
            "value": matricula_activa},
        {"key": "ventas_dia", "label": "Ventas del dia",
            "value": f"${ventas_hoy_total:.2f}", "meta": f"{ventas_hoy_count} pagos"},
        {"key": "morosidad", "label": "Morosidad", "value": f"${morosidad_monto:.2f}",
            "meta": f"{morosidad_ordenes} ordenes con adeudo"},
        {"key": "alertas_inventario", "label": "Alertas de inventario",
            "value": alertas_activas + alertas_por_existencia},
    ]

    return render(
        request,
        "ui/reportes/ejecutivo.html",
        {
            "kpi": kpi,
            "kpi_cards": kpi_cards,
            "ult_calif": ult_calif,
            "ult_ordenes": ult_ordenes,
            "ult_pagos": ult_pagos,
            "active": "reporte_ejecutivo",
        },
    )


@rate_limit("export_academico", max_calls=30, period_seconds=300)
@login_required(login_url="/acceso/")
@role_required_codes("SUPERUSUARIO", "DIRECTOR_ESCOLAR")
def reporte_academico(request):
    periodo_activo = (request.GET.get("periodo") or "").strip()
    estado_inscripcion = (request.GET.get("estado") or "").strip().lower()
    calif_desde = _parse_decimal_or_none(request.GET.get("calif_desde"))
    calif_hasta = _parse_decimal_or_none(request.GET.get("calif_hasta"))
    export_format = (request.GET.get("export") or "").strip().lower()
    vista = (request.GET.get("vista") or "por_periodo").strip().lower()
    if vista not in {"por_periodo", "inscripciones", "calificaciones"}:
        vista = "por_periodo"
    page_num = request.GET.get("page", 1)

    periodos_disponibles = list(
        Grupo.objects.order_by(
            "-periodo_ref__codigo").values_list("periodo_ref__codigo", flat=True).distinct()
    )

    inscripciones_base = Inscripcion.objects.select_related(
        "alumno", "grupo", "grupo__periodo_ref"
    )
    calificaciones_base = Calificacion.objects.select_related(
        "inscripcion__alumno", "inscripcion__grupo", "inscripcion__grupo__periodo_ref"
    )

    if periodo_activo:
        inscripciones_base = inscripciones_base.filter(
            grupo__periodo_ref__codigo=periodo_activo)
        calificaciones_base = calificaciones_base.filter(
            inscripcion__grupo__periodo_ref__codigo=periodo_activo)

    estados_validos = {
        Inscripcion.ESTADO_ACTIVA,
        Inscripcion.ESTADO_BAJA,
        Inscripcion.ESTADO_FINALIZADA,
    }
    if estado_inscripcion in estados_validos:
        inscripciones_base = inscripciones_base.filter(
            estado=estado_inscripcion)
        calificaciones_base = calificaciones_base.filter(
            inscripcion__estado=estado_inscripcion)
    else:
        estado_inscripcion = ""

    if calif_desde is not None:
        calificaciones_base = calificaciones_base.filter(
            valor__gte=calif_desde)
    if calif_hasta is not None:
        calificaciones_base = calificaciones_base.filter(
            valor__lte=calif_hasta)

    inscripciones_por_periodo = list(
        Inscripcion.objects.values(periodo=F("grupo__periodo_ref__codigo"))
        .annotate(
            total=Count("id"),
            activas=Count("id", filter=Q(estado=Inscripcion.ESTADO_ACTIVA)),
            bajas=Count("id", filter=Q(estado=Inscripcion.ESTADO_BAJA)),
            finalizadas=Count(
                "id", filter=Q(estado=Inscripcion.ESTADO_FINALIZADA)),
        )
        .order_by("-periodo")
    )

    calif_stats = calificaciones_base.aggregate(promedio=Avg("valor"))
    calif_promedio = calif_stats.get("promedio")

    inscripciones_por_estado = list(
        inscripciones_base.values("estado")
        .annotate(total=Count("id"))
        .order_by("estado")
    )

    calificaciones_rows = list(calificaciones_base.order_by("-id"))
    segmentos_calificacion = {
        "alto_9_10": 0,
        "medio_8_89": 0,
        "bajo_menor_8": 0,
    }
    for calif in calificaciones_rows:
        if calif.valor is None:
            continue
        if calif.valor >= Decimal("9.00"):
            segmentos_calificacion["alto_9_10"] += 1
        elif calif.valor >= Decimal("8.00"):
            segmentos_calificacion["medio_8_89"] += 1
        else:
            segmentos_calificacion["bajo_menor_8"] += 1

    # Para export se usan las listas completas (legacy)
    calificaciones_export = calificaciones_rows[:50]

    kpi = {
        "inscripciones": inscripciones_base.count(),
        "calificaciones": calificaciones_base.count(),
        "alumnos": Alumno.objects.count(),
        "grupos": Grupo.objects.count(),
        "actas_cerradas": ActaCierre.objects.count(),
        "calif_promedio": f"{calif_promedio:.2f}" if calif_promedio is not None else "N/A",
    }

    if export_format in {"csv", "pdf"}:
        kpi_export = {
            "alumnos": Alumno.objects.count(),
            "grupos": Grupo.objects.count(),
            "inscripciones": inscripciones_base.count(),
            "calificaciones": calificaciones_base.count(),
            "actas_cerradas": ActaCierre.objects.count(),
            "calif_promedio": f"{calif_promedio:.2f}" if calif_promedio is not None else "N/A",
        }
        if export_format == "csv":
            content_bytes = _build_academico_csv_bytes(
                inscripciones_por_periodo, calificaciones_export)
        else:
            content_bytes = _build_academico_pdf_bytes(
                kpi_export, inscripciones_por_periodo, calificaciones_export)

        response, digest, filename = _render_export_response(
            content_bytes, export_format, "reporte_academico")
        log_event(
            request,
            accion="REPORTES::ACADEMICO_EXPORT",
            entidad="ReporteAcademico",
            entidad_id=periodo_activo or "all",
            resultado="ok",
            detalle={
                "format": export_format,
                "sha256": digest,
                "filename": filename,
                "periodo": periodo_activo or "all",
                "estado": estado_inscripcion or "all",
                "calif_desde": str(calif_desde) if calif_desde is not None else "",
                "calif_hasta": str(calif_hasta) if calif_hasta is not None else "",
                "inscripciones": kpi_export["inscripciones"],
                "calificaciones": kpi_export["calificaciones"],
            },
        )
        return response

    # Paginación por vista activa
    if vista == "inscripciones":
        page_obj = Paginator(inscripciones_base.order_by(
            "-id"), 3).get_page(page_num)
    elif vista == "calificaciones":
        page_obj = Paginator(calificaciones_rows, 3).get_page(page_num)
    else:  # por_periodo
        page_obj = Paginator(inscripciones_por_periodo, 3).get_page(page_num)

    # Query string de filtros para enlaces de paginación y vista
    _filtros = []
    if periodo_activo:
        _filtros.append(f"periodo={periodo_activo}")
    if estado_inscripcion:
        _filtros.append(f"estado={estado_inscripcion}")
    if calif_desde is not None:
        _filtros.append(f"calif_desde={calif_desde}")
    if calif_hasta is not None:
        _filtros.append(f"calif_hasta={calif_hasta}")
    filtros_qs = "&".join(_filtros)

    return render(
        request,
        "ui/reportes/academico.html",
        {
            "kpi": kpi,
            "calificaciones": calificaciones_rows,
            "inscripciones_por_periodo": inscripciones_por_periodo,
            "vista": vista,
            "page_obj": page_obj,
            "periodo_activo": periodo_activo,
            "estado_activo": estado_inscripcion,
            "calif_desde": str(calif_desde) if calif_desde is not None else "",
            "calif_hasta": str(calif_hasta) if calif_hasta is not None else "",
            "periodos_disponibles": periodos_disponibles,
            "inscripciones_por_estado": inscripciones_por_estado,
            "segmentos_calificacion": segmentos_calificacion,
            "calif_promedio": f"{calif_promedio:.2f}" if calif_promedio is not None else "N/A",
            "filtros_qs": filtros_qs,
            "active": "reporte_academico",
        },
    )


@rate_limit("export_comercial", max_calls=30, period_seconds=300)
@login_required(login_url="/acceso/")
@role_required_codes("SUPERUSUARIO", "ADMINISTRATIVO_COMERCIAL")
def reporte_comercial(request):
    periodo_activo = (request.GET.get("periodo") or "").strip()
    estado_orden = (request.GET.get("estado") or "").strip().lower()
    metodo_pago = (request.GET.get("metodo") or "").strip().upper()
    export_format = (request.GET.get("export") or "").strip().lower()

    periodos_disponibles = list(
        OrdenPOS.objects.order_by(
            "-inscripcion__grupo__periodo_ref__codigo").values_list("inscripcion__grupo__periodo_ref__codigo", flat=True).distinct()
    ) if OrdenPOS else []

    if periodo_activo and periodo_activo not in periodos_disponibles:
        periodo_activo = ""

    estados_validos = {
        OrdenPOS.ESTADO_PENDIENTE,
        OrdenPOS.ESTADO_PARCIAL,
        OrdenPOS.ESTADO_PAGADA,
        OrdenPOS.ESTADO_CANCELADA,
    } if OrdenPOS else set()
    if estado_orden not in estados_validos:
        estado_orden = ""

    ordenes_base = OrdenPOS.objects.all() if OrdenPOS else None
    pagos_base = Pago.objects.select_related("orden") if Pago else None
    cortes_base = CorteCaja.objects.all() if CorteCaja else None

    if periodo_activo:
        if ordenes_base is not None:
            ordenes_base = ordenes_base.filter(
                inscripcion__grupo__periodo_ref__codigo=periodo_activo)
        if pagos_base is not None:
            pagos_base = pagos_base.filter(
                orden__inscripcion__grupo__periodo_ref__codigo=periodo_activo)
        if cortes_base is not None:
            year, month = _parse_periodo(periodo_activo)
            if year and month:
                cortes_base = cortes_base.filter(
                    fecha_operacion__year=year,
                    fecha_operacion__month=month,
                )

    if estado_orden and ordenes_base is not None:
        ordenes_base = ordenes_base.filter(estado=estado_orden)
        if pagos_base is not None:
            pagos_base = pagos_base.filter(orden__estado=estado_orden)

    metodos_disponibles = list(
        Pago.objects.order_by("metodo").values_list(
            "metodo", flat=True).distinct()
    ) if Pago else []
    if metodo_pago and metodo_pago not in metodos_disponibles:
        metodo_pago = ""

    if metodo_pago:
        if pagos_base is not None:
            pagos_base = pagos_base.filter(metodo=metodo_pago)
        if ordenes_base is not None:
            ordenes_base = ordenes_base.filter(
                pagos__metodo=metodo_pago).distinct()

    ventas_por_periodo = []
    if ordenes_base is not None:
        ventas_por_periodo = list(
            ordenes_base.exclude(estado=OrdenPOS.ESTADO_CANCELADA)
            .values(periodo=F("inscripcion__grupo__periodo_ref__codigo"))
            .annotate(
                total_ordenes=Count("id", distinct=True),
                monto_ordenes=Sum(_orden_total_expr()),
                pagadas=Count("id", filter=Q(estado=OrdenPOS.ESTADO_PAGADA)),
                pendientes=Count(
                    "id",
                    filter=Q(
                        estado__in=[OrdenPOS.ESTADO_PENDIENTE, OrdenPOS.ESTADO_PARCIAL]),
                ),
            )
            .order_by("-periodo")
        )

    ordenes_por_estado = []
    if ordenes_base is not None:
        ordenes_por_estado = list(
            ordenes_base.values("estado")
            .annotate(total=Count("id", distinct=True), monto=Sum(_orden_total_expr()))
            .order_by("estado")
        )

    pagos_por_metodo = []
    if pagos_base is not None:
        pagos_por_metodo = list(
            pagos_base.values("metodo")
            .annotate(total=Count("id"), monto=Sum("monto"))
            .order_by("metodo")
        )

    monto_ventas = (
        _aggregate_ordenes_monto(ordenes_base.exclude(
            estado=OrdenPOS.ESTADO_CANCELADA))
        if ordenes_base is not None
        else Decimal("0")
    )
    monto_pagos = (
        pagos_base.aggregate(total=Sum("monto")).get("total")
        if pagos_base is not None
        else Decimal("0")
    )
    monto_ventas = monto_ventas or Decimal("0")
    monto_pagos = monto_pagos or Decimal("0")

    # ──────────────────────────────────────────────────
    # Inscripciones como venta: base $1 000 + IVA 16% $160
    # ──────────────────────────────────────────────────
    inscripciones_ventas = []
    insc_base_total = Decimal("0")
    insc_iva_total = Decimal("0")
    if OrdenPOS and OrdenItem and ordenes_base is not None:
        _concepto_expr = ExpressionWrapper(
            F("cantidad") * F("precio_unit"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        _items_qs = (
            OrdenItem.objects
            .filter(
                orden__in=ordenes_base,
                concepto__nombre__in=[
                    "Inscripcion escolar", "IVA inscripcion 16%"],
            )
            .values(periodo=F("orden__inscripcion__grupo__periodo_ref__codigo"))
            .annotate(
                total_inscripciones=Count("orden_id", distinct=True),
                monto_base=Sum(
                    Case(
                        When(
                            concepto__nombre="Inscripcion escolar",
                            then=_concepto_expr,
                        ),
                        default=Decimal("0"),
                        output_field=DecimalField(
                            max_digits=12, decimal_places=2),
                    )
                ),
                monto_iva=Sum(
                    Case(
                        When(
                            concepto__nombre="IVA inscripcion 16%",
                            then=_concepto_expr,
                        ),
                        default=Decimal("0"),
                        output_field=DecimalField(
                            max_digits=12, decimal_places=2),
                    )
                ),
            )
            .order_by("-periodo")
        )
        for _row in _items_qs:
            _base = _row["monto_base"] or Decimal("0")
            _iva = _row["monto_iva"] or Decimal("0")
            inscripciones_ventas.append({
                "periodo": _row["periodo"],
                "total_inscripciones": _row["total_inscripciones"],
                "monto_base": _base,
                "monto_iva": _iva,
                "total": _base + _iva,
            })
            insc_base_total += _base
            insc_iva_total += _iva
    insc_total = insc_base_total + insc_iva_total

    kpi = {
        "conceptos": Concepto.objects.count() if Concepto else 0,
        "ordenes_pos": ordenes_base.count() if ordenes_base is not None else 0,
        "pagos": pagos_base.count() if pagos_base is not None else 0,
        "tickets": Ticket.objects.count() if Ticket else 0,
        "ventas_periodo_total": f"{monto_ventas:.2f}",
        "pagos_periodo_total": f"{monto_pagos:.2f}",
        "cortes_periodo": cortes_base.count() if cortes_base is not None else 0,
        "inscripciones_base": f"{insc_base_total:.2f}",
        "inscripciones_iva": f"{insc_iva_total:.2f}",
        "inscripciones_total": f"{insc_total:.2f}",
    }

    # ──────────────────────────────────────────────────
    # Export (usa listas completas, no paginadas)
    # ──────────────────────────────────────────────────
    if export_format in {"csv", "pdf"}:
        cortes_export = (
            list(cortes_base.order_by("-fecha_operacion")[:30])
            if cortes_base is not None
            else []
        )
        for _c in cortes_export:
            _r = CorteCaja.resumen_calculado(_c.fecha_operacion)
            _c.monto_ordenes_calc = _r["monto_ordenes"]
            _c.monto_pagos_calc = _r["monto_pagos"]

        if export_format == "csv":
            content_bytes = _build_comercial_csv_bytes(
                ventas_por_periodo, cortes_export, inscripciones_ventas)
        else:
            content_bytes = _build_comercial_pdf_bytes(
                kpi, ventas_por_periodo, cortes_export, inscripciones_ventas)

        response, digest, filename = _render_export_response(
            content_bytes, export_format, "reporte_comercial")
        log_event(
            request,
            accion="REPORTES::COMERCIAL_EXPORT",
            entidad="ReporteComercial",
            entidad_id=periodo_activo or "all",
            resultado="ok",
            detalle={
                "format": export_format,
                "sha256": digest,
                "filename": filename,
                "periodo": periodo_activo or "all",
                "estado": estado_orden or "all",
                "metodo": metodo_pago or "all",
                "ordenes": kpi["ordenes_pos"],
                "pagos": kpi["pagos"],
                "cortes": kpi["cortes_periodo"],
            },
        )
        return response

    # ──────────────────────────────────────────────────
    # Vista + paginación
    # ──────────────────────────────────────────────────
    vista = (request.GET.get("vista") or "por_periodo").strip().lower()
    if vista not in {"por_periodo", "ordenes", "pagos", "cortes"}:
        vista = "por_periodo"
    page_num = request.GET.get("page", 1)

    _filtros = []
    if periodo_activo:
        _filtros.append(f"periodo={periodo_activo}")
    if estado_orden:
        _filtros.append(f"estado={estado_orden}")
    if metodo_pago:
        _filtros.append(f"metodo={metodo_pago}")
    filtros_qs = "&".join(_filtros)

    if vista == "ordenes":
        _qs = ordenes_base.order_by(
            "-fecha_emision") if ordenes_base is not None else []
        page_obj = Paginator(_qs, 3).get_page(page_num)
    elif vista == "pagos":
        _qs = pagos_base.order_by(
            "-fecha_pago") if pagos_base is not None else []
        page_obj = Paginator(_qs, 3).get_page(page_num)
    elif vista == "cortes":
        _cortes_list = (
            list(cortes_base.order_by("-fecha_operacion"))
            if cortes_base is not None
            else []
        )
        for _c in _cortes_list:
            _r = CorteCaja.resumen_calculado(_c.fecha_operacion)
            _c.monto_ordenes_calc = _r["monto_ordenes"]
            _c.monto_pagos_calc = _r["monto_pagos"]
        page_obj = Paginator(_cortes_list, 3).get_page(page_num)
    else:  # por_periodo
        page_obj = Paginator(ventas_por_periodo, 3).get_page(page_num)

    return render(
        request,
        "ui/reportes/comercial.html",
        {
            "kpi": kpi,
            "ordenes": ordenes_base,
            "pagos": pagos_base,
            "ventas_por_periodo": ventas_por_periodo,
            "cortes_caja": cortes_base,
            "vista": vista,
            "page_obj": page_obj,
            "filtros_qs": filtros_qs,
            "periodo_activo": periodo_activo,
            "estado_activo": estado_orden,
            "metodo_activo": metodo_pago,
            "periodos_disponibles": periodos_disponibles,
            "metodos_disponibles": metodos_disponibles,
            "ordenes_por_estado": ordenes_por_estado,
            "pagos_por_metodo": pagos_por_metodo,
            "inscripciones_ventas": inscripciones_ventas,
            "active": "reporte_comercial",
        },
    )


@rate_limit("export_adeudos", max_calls=30, period_seconds=300)
@login_required(login_url="/acceso/")
@role_required_codes("SUPERUSUARIO", "ADMINISTRATIVO_COMERCIAL")
def reporte_hu012_adeudos(request):
    periodo_activo = (request.GET.get("periodo") or "").strip()
    export_format = (request.GET.get("export") or "").strip().lower()
    ordenes_hu012 = []
    total_adeudo = Decimal("0.00")
    total_ordenes = 0
    periodos_disponibles = []

    if OrdenPOS:
        base_qs = (
            OrdenPOS.objects
            .select_related("inscripcion__alumno", "inscripcion__grupo__periodo_ref")
            .exclude(estado=OrdenPOS.ESTADO_CANCELADA)
            .filter(
                Q(inscripcion__alumno__matricula__icontains="HU012") |
                Q(inscripcion__alumno__correo__icontains="hu012")
            )
            .order_by("-fecha_emision")
        )

        periodos_disponibles = list(
            base_qs.values_list(
                "inscripcion__grupo__periodo_ref__codigo", flat=True)
            .distinct()
            .order_by("-inscripcion__grupo__periodo_ref__codigo")
        )

        if periodo_activo and periodo_activo in periodos_disponibles:
            base_qs = base_qs.filter(
                inscripcion__grupo__periodo_ref__codigo=periodo_activo
            )
        else:
            periodo_activo = ""

        for orden in base_qs:
            total_orden = Decimal(orden.total_calculado or Decimal("0.00"))
            pagado = orden.pagos.aggregate(
                total=Sum("monto")).get("total") or Decimal("0.00")
            adeudo = total_orden - Decimal(pagado)
            if adeudo > 0:
                total_ordenes += 1
                total_adeudo += adeudo
                orden.adeudo = adeudo
                orden.pagado = pagado
                orden.total_orden = total_orden
                ordenes_hu012.append(orden)

    if export_format == "csv":
        content_bytes = _build_hu012_adeudos_csv_bytes(ordenes_hu012)
        response, digest, filename = _render_export_response(
            content_bytes,
            "csv",
            "reporte_hu012_adeudos",
        )
        log_event(
            request,
            accion="REPORTES::HU012_ADEUDOS_EXPORT",
            entidad="ReporteHu012Adeudos",
            entidad_id=periodo_activo or "all",
            resultado="ok",
            detalle={
                "format": "csv",
                "sha256": digest,
                "filename": filename,
                "periodo": periodo_activo or "all",
                "ordenes": total_ordenes,
                "adeudo_total": f"{total_adeudo:.2f}",
            },
        )
        return response

    return render(
        request,
        "ui/reportes/hu012_adeudos.html",
        {
            "ordenes": ordenes_hu012,
            "total_adeudo": total_adeudo,
            "total_ordenes": total_ordenes,
            "periodos_disponibles": periodos_disponibles,
            "periodo_activo": periodo_activo,
        },
    )


@login_required(login_url="/acceso/")
@role_required_codes("SUPERUSUARIO", "DIRECTOR_ESCOLAR", "ADMINISTRATIVO_COMERCIAL")
def reporte_alertas(request):
    """Vista de alertas y pendientes operativos (solo lectura)."""
    vista = (request.GET.get("vista") or "alertas_stock").strip().lower()
    if vista not in {"alertas_stock", "ordenes_abiertas"}:
        vista = "alertas_stock"
    page_num = request.GET.get("page", 1)

    # ── KPIs ────────────────────────────────────────────────────────────────
    total_alertas_stock = (
        AlertaStock.objects.filter(activa=True).count()
        if AlertaStock else 0
    )
    total_bajo_minimo = (
        Existencia.objects.filter(
            inventario_habilitado=True,
            stock_actual__lte=F("stock_minimo"),
        ).count()
        if Existencia else 0
    )
    total_ordenes_abiertas = (
        OrdenPOS.objects.filter(
            estado__in=[OrdenPOS.ESTADO_PENDIENTE, OrdenPOS.ESTADO_PARCIAL]
        ).count()
        if OrdenPOS else 0
    )

    kpi = {
        "Alertas de stock activas": total_alertas_stock,
        "Conceptos bajo mínimo": total_bajo_minimo,
        "Órdenes abiertas": total_ordenes_abiertas,
    }

    # ── Paginación por vista ─────────────────────────────────────────────────
    if vista == "ordenes_abiertas":
        _qs = (
            OrdenPOS.objects.filter(
                estado__in=[OrdenPOS.ESTADO_PENDIENTE, OrdenPOS.ESTADO_PARCIAL]
            ).select_related(
                "inscripcion__alumno",
                "inscripcion__grupo",
                "inscripcion__grupo__periodo_ref",
            ).order_by("-fecha_emision")
            if OrdenPOS else []
        )
    else:  # alertas_stock
        _qs = (
            AlertaStock.objects.filter(activa=True).select_related(
                "existencia__concepto"
            ).order_by("-generado_en")
            if AlertaStock else []
        )

    page_obj = Paginator(_qs, 3).get_page(page_num)

    return render(
        request,
        "ui/reportes/alertas.html",
        {
            "kpi": kpi,
            "vista": vista,
            "page_obj": page_obj,
            "active": "reporte_alertas",
        },
    )
