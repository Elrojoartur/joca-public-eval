import logging
from typing import Tuple

from django.core.cache import cache
from django.utils import timezone
from apps.governance.services.security_policy import (
    get_attempt_window_seconds,
    get_lockout_seconds,
    get_max_attempts,
)

bitacora_logger = logging.getLogger("bitacora")


def get_client_ip(request) -> str:
    """Obtiene la IP real considerando X-Forwarded-For cuando existe."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        candidate = x_forwarded_for.split(",")[0].strip()
        if candidate:
            return candidate
    return request.META.get("REMOTE_ADDR") or ""


def lockout_key(username: str, ip: str) -> str:
    user_part = (username or "anon").strip().lower()
    ip_part = (ip or "noip").strip()
    return f"lockout:{user_part}:{ip_part}"


def _log_bitacora(tipo: str, data: dict):
    try:
        from apps.governance.models import Bitacora  # type: ignore
    except Exception:  # pragma: no cover - fallback a logger
        Bitacora = None

    if Bitacora:
        try:
            Bitacora.objects.create(modulo="ACCESO", tipo=tipo, detalle=data)
            return
        except Exception:  # pragma: no cover - fallback a logger
            pass

    bitacora_logger.info("[ACCESO][%s] %s", tipo, data)


def _load_state(key: str) -> dict:
    return cache.get(key, {"attempts": [], "locked_until": None})


def _save_state(key: str, state: dict):
    ttl = max(get_attempt_window_seconds(), get_lockout_seconds()) + 60
    cache.set(key, state, ttl)


def is_locked_out(username: str, ip: str) -> bool:
    key = lockout_key(username, ip)
    state = _load_state(key)
    locked_until = state.get("locked_until")
    now_ts = timezone.now().timestamp()

    if locked_until and locked_until > now_ts:
        return True

    # Limpia bloqueo expirado
    if locked_until and locked_until <= now_ts:
        state["locked_until"] = None
        _save_state(key, state)
    return False


def register_failed_attempt(username: str, ip: str) -> Tuple[int, bool]:
    now_ts = timezone.now().timestamp()
    key = lockout_key(username, ip)
    state = _load_state(key)
    attempts = [ts for ts in state.get(
        "attempts", []) if ts >= now_ts - get_attempt_window_seconds()]
    locked_until = state.get("locked_until")

    if locked_until and locked_until > now_ts:
        return len(attempts), True

    attempts.append(now_ts)
    locked = False

    if len(attempts) >= get_max_attempts():
        locked = True
        locked_until = now_ts + get_lockout_seconds()
        _log_bitacora("BLOQUEO", {"username": username,
                      "ip": ip, "intentos": len(attempts)})

    state = {
        "attempts": attempts,
        "locked_until": locked_until if locked else None,
    }
    _save_state(key, state)

    _log_bitacora(
        "LOGIN_FALLIDO",
        {"username": username, "ip": ip, "intentos": len(
            attempts), "bloqueado": locked},
    )

    return len(attempts), locked


def reset_attempts(username: str, ip: str):
    cache.delete(lockout_key(username, ip))


# Ejemplo de uso (vista de login basada en Django LoginView):
#
# from django.contrib import messages
# from django.contrib.auth.views import LoginView
# from apps.authn.services.lockout import (
#     get_client_ip, is_locked_out, register_failed_attempt, reset_attempts,
# )
#
# class PortalLoginView(LoginView):
#     template_name = "registration/login.html"
#
#     def post(self, request, *args, **kwargs):
#         username = request.POST.get("username", "")
#         ip = get_client_ip(request)
#
#         if is_locked_out(username, ip):
#             messages.error(request, "No pudimos iniciar sesión. Intenta más tarde.")
#             return self.form_invalid(self.get_form())
#
#         response = super().post(request, *args, **kwargs)
#
#         if response.status_code in (301, 302):
#             reset_attempts(username, ip)
#         else:
#             attempts, locked = register_failed_attempt(username, ip)
#             if locked:
#                 messages.error(request, "No pudimos iniciar sesión. Intenta más tarde.")
#         return response
