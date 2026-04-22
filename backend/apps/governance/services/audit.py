import logging

from apps.governance.models import EventoAuditoria


def get_client_ip(request):
    if not request:
        return ""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or ""


def log_event(request, accion, entidad, entidad_id=None, resultado="ok", detalle=None):
    actor = request.user if request and getattr(
        request, "user", None) and request.user.is_authenticated else None
    try:
        EventoAuditoria.objects.create(
            actor=actor,
            ip=get_client_ip(request),
            accion=accion,
            entidad=entidad,
            entidad_id=str(entidad_id) if entidad_id is not None else None,
            resultado=resultado,
            detalle=detalle or {},
        )
    except Exception:  # pragma: no cover - fallback de auditoria
        logging.getLogger("bitacora").info("[AUDIT][%s] %s", accion, detalle)
