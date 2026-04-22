import csv
import io
import logging
from typing import Dict

from django.contrib import admin, messages
from django.http import HttpResponse

from apps.accounts.admin import get_client_ip, log_event
from apps.governance.models import EventoAuditoria

logger = logging.getLogger("bitacora")


@admin.register(EventoAuditoria)
class EventoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("creado_en", "actor", "ip", "accion",
                    "entidad", "entidad_id", "resultado")
    search_fields = ("actor__email", "actor__username", "entidad", "detalle")
    list_filter = ("accion", "entidad", "resultado")
    date_hierarchy = "creado_en"
    ordering = ("-creado_en",)
    list_per_page = 50
    actions = ["exportar_csv", "exportar_pdf"]

    def _audit_export(self, request, formato: str, count: int):
        log_event(
            request,
            "EXPORTA_BITACORA",
            "EventoAuditoria",
            "*",
            "OK",
            {"formato": formato, "registros": count},
        )

    def exportar_csv(self, request, queryset):
        headers = ["creado_en", "actor", "ip", "accion",
                   "entidad", "entidad_id", "resultado"]
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        for e in queryset:
            writer.writerow(
                [
                    e.creado_en,
                    getattr(e.actor, "username", ""),
                    e.ip,
                    e.accion,
                    e.entidad,
                    e.entidad_id,
                    e.resultado,
                ]
            )

        resp = HttpResponse(buffer.getvalue(), content_type="text/csv")
        resp["Content-Disposition"] = "attachment; filename=bitacora.csv"
        self._audit_export(request, "csv", queryset.count())
        return resp

    exportar_csv.short_description = "Exportar CSV"

    def exportar_pdf(self, request, queryset):
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.pdfgen import canvas
        except Exception:  # pragma: no cover - fallback simple PDF
            return self._exportar_pdf_simple(request, queryset)

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        y = height - inch
        headers = ["Fecha", "Usuario", "IP",
                   "Accion", "Entidad", "ID", "Resultado"]
        p.setFont("Helvetica-Bold", 10)
        p.drawString(inch, y, "Bitácora de eventos")
        y -= 0.3 * inch
        p.setFont("Helvetica", 8)
        p.drawString(inch, y, " | ".join(headers))
        y -= 0.2 * inch
        for e in queryset:
            line = " | ".join(
                [
                    e.creado_en.strftime("%Y-%m-%d %H:%M"),
                    getattr(e.actor, "username", ""),
                    e.ip,
                    e.accion,
                    e.entidad,
                    e.entidad_id or "",
                    e.resultado,
                ]
            )
            p.drawString(inch, y, line[:180])
            y -= 0.18 * inch
            if y < inch:
                p.showPage()
                y = height - inch
        p.showPage()
        p.save()
        pdf = buffer.getvalue()
        buffer.close()

        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = "attachment; filename=bitacora.pdf"
        self._audit_export(request, "pdf", queryset.count())
        return resp

    exportar_pdf.short_description = "Exportar PDF"

    def _exportar_pdf_simple(self, request, queryset):
        # Fallback: genera PDF básico sin reportlab
        buffer = io.StringIO()
        buffer.write("Bitacora\n")
        for e in queryset:
            buffer.write(
                f"{e.creado_en} | {getattr(e.actor, 'username', '')} | {e.ip} | {e.accion} | {e.entidad} | {e.entidad_id or ''} | {e.resultado}\n"
            )
        resp = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        resp["Content-Disposition"] = "attachment; filename=bitacora.pdf"
        self._audit_export(request, "pdf-simple", queryset.count())
        return resp
