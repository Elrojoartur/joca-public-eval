from __future__ import annotations

from django.conf import settings

from apps.governance.models import ParametroSistema


def _get_param_value(key: str):
    row = ParametroSistema.objects.filter(clave=key, activo=True).first()
    return row.valor if row else None


def get_security_int(key: str, default: int, min_value: int = 1, max_value: int = 86400) -> int:
    raw = _get_param_value(key)
    try:
        value = int(raw) if raw not in (None, "") else int(default)
    except (TypeError, ValueError):
        value = int(default)
    value = max(min_value, value)
    value = min(max_value, value)
    return value


def get_security_bool(key: str, default: bool) -> bool:
    raw = _get_param_value(key)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "on", "yes", "si"}


def get_password_min_length() -> int:
    default = int(getattr(settings, "PASSWORD_MIN_LENGTH", 6) or 6)
    return get_security_int("security_password_min_length", default=default, min_value=6, max_value=64)


def get_max_attempts() -> int:
    default = int(getattr(settings, "ACCESS_MAX_ATTEMPTS", 3) or 3)
    return get_security_int("security_max_attempts", default=default, min_value=1, max_value=20)


def get_attempt_window_seconds() -> int:
    default = int(
        getattr(settings, "ACCESS_ATTEMPT_WINDOW_SECONDS", 900) or 900)
    return get_security_int("security_attempt_window_seconds", default=default, min_value=60, max_value=86400)


def get_lockout_seconds() -> int:
    default = int(getattr(settings, "ACCESS_LOCKOUT_SECONDS", 900) or 900)
    return get_security_int("security_lockout_seconds", default=default, min_value=60, max_value=86400)


def get_idle_timeout_seconds() -> int:
    default = int(getattr(settings, "ACCESS_IDLE_TIMEOUT_SECONDS", 900) or 900)
    return get_security_int("security_idle_timeout_seconds", default=default, min_value=1, max_value=86400)


def get_captcha_enabled() -> bool:
    default = bool(getattr(settings, "RECAPTCHA_ENABLED", False))
    return get_security_bool("security_captcha_enabled", default=default)
