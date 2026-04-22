from __future__ import annotations

import json
import random
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.core.cache import cache
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from apps.governance.services.audit import log_event
from apps.governance.services.security_policy import (
    get_attempt_window_seconds,
    get_captcha_enabled,
    get_max_attempts,
)
from apps.ui.input_validation import validate_required_text
from apps.authn.decorators import rate_limit


# Keys de sesión (coinciden con lo que ya rastreaste en templates)
SESSION_Q = "login_verif_question"
SESSION_A = "login_verif_answer"


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _recaptcha_active() -> bool:
    return bool(
        get_captcha_enabled()
        and getattr(settings, "RECAPTCHA_SITE_KEY", "")
        and getattr(settings, "RECAPTCHA_SECRET_KEY", "")
    )


def _recaptcha_mode() -> str:
    return str(getattr(settings, "RECAPTCHA_MODE", "v3") or "v3").strip().lower()


def _attempt_cache_key(username: str) -> str:
    return f"auth:login_attempts:{(username or '').lower()}"


def _failed_attempts(username: str) -> int:
    return int(cache.get(_attempt_cache_key(username), 0))


def _mark_failed_attempt(username: str) -> int:
    key = _attempt_cache_key(username)
    attempts = int(cache.get(key, 0)) + 1
    cache.set(key, attempts, timeout=get_attempt_window_seconds())
    return attempts


def _clear_attempts(username: str) -> None:
    cache.delete(_attempt_cache_key(username))


def _max_failed_attempts() -> int:
    return get_max_attempts()


def _is_locked_out(username: str) -> bool:
    return _failed_attempts(username) >= _max_failed_attempts()


def _captcha_required(username: str, ip: str) -> bool:
    # CAPTCHA nivel 2+: se solicita desde el inicio si esta habilitado.
    return _recaptcha_active()


def _verify_recaptcha(token: str, remote_ip: str) -> bool:
    if not _recaptcha_active():
        return True
    if not token:
        return False

    payload = urlencode(
        {
            "secret": settings.RECAPTCHA_SECRET_KEY,
            "response": token,
            "remoteip": remote_ip,
        }
    ).encode("utf-8")

    try:
        with urlopen(
            "https://www.google.com/recaptcha/api/siteverify",
            data=payload,
            timeout=5,
        ) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if not bool(result.get("success", False)):
                return False

            # v3 invisible: validar score y action.
            if _recaptcha_mode() == "v3":
                score = float(result.get("score", 0.0) or 0.0)
                action = str(result.get("action", "") or "").strip().lower()
                min_score = float(
                    getattr(settings, "RECAPTCHA_SCORE_THRESHOLD", 0.5))
                return action == "login" and score >= min_score

            # v2 checkbox/invisible: success=true es suficiente.
            return True
    except Exception:
        return False


def _set_verification(request) -> str:
    """
    Genera la verificación (tipo CAPTCHA) y la guarda en sesión:
    - login_verif_question: texto visible
    - login_verif_answer: respuesta esperada
    """
    a = random.randint(2, 9)
    b = random.randint(2, 9)
    question = f"¿Cuánto es {a} + {b}?"
    request.session[SESSION_Q] = question
    request.session[SESSION_A] = str(a + b)
    return question


def _get_or_set_verification(request) -> str:
    q = request.session.get(SESSION_Q)
    a = request.session.get(SESSION_A)
    if not q or not a:
        q = _set_verification(request)
    return q


# 20 peticiones por IP en 60 segundos: generoso para un usuario normal,
# bloquea ataques de fuerza bruta automatizados.
@rate_limit("acceso", max_calls=20, period_seconds=60)
@require_http_methods(["GET", "POST"])
def acceso(request):
    _raw_next = request.POST.get("next") or request.GET.get("next") or ""
    if _raw_next and url_has_allowed_host_and_scheme(
        _raw_next,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = _raw_next
    else:
        next_url = "/panel/"
    username = (request.POST.get("username")
                or request.GET.get("username") or "").strip()
    ip = _client_ip(request)
    show_recaptcha = _captcha_required(username, ip)
    recaptcha_enabled = _recaptcha_active()

    if request.method == "GET":
        pregunta = _get_or_set_verification(request)
        return render(
            request,
            "registration/login.html",
            {
                "next": next_url,
                "username": username,
                "verif_pregunta": pregunta,
                "show_recaptcha": show_recaptcha,
                "recaptcha_enabled": recaptcha_enabled,
                "recaptcha_site_key": getattr(settings, "RECAPTCHA_SITE_KEY", ""),
                "recaptcha_mode": _recaptcha_mode(),
            },
        )

    # POST
    password = request.POST.get("password") or ""
    verif = (request.POST.get("verificacion") or "").strip()
    hp = (request.POST.get("hp") or "").strip()  # honeypot invisible
    recaptcha_token = (request.POST.get("g-recaptcha-response") or "").strip()

    try:
        username = validate_required_text(username, "Usuario")
    except Exception as exc:
        messages.error(request, str(exc))
        pregunta = _set_verification(request)
        return render(
            request,
            "registration/login.html",
            {
                "form_errors": str(exc),
                "next": next_url,
                "username": "",
                "verif_pregunta": pregunta,
                "show_recaptcha": _captcha_required("", ip),
                "recaptcha_enabled": recaptcha_enabled,
                "recaptcha_site_key": getattr(settings, "RECAPTCHA_SITE_KEY", ""),
                "recaptcha_mode": _recaptcha_mode(),
            },
        )

    if _is_locked_out(username):
        log_event(
            request,
            accion="AUTH::LOGIN_BLOCKED",
            entidad="Sesion",
            entidad_id=username or None,
            resultado="denied",
            detalle={"username": username, "ip": ip, "reason": "lockout"},
        )
        pregunta = _set_verification(request)
        return render(
            request,
            "registration/login.html",
            {
                "form_errors": "Por seguridad, intenta de nuevo en unos minutos.",
                "next": next_url,
                "username": username,
                "verif_pregunta": pregunta,
                "show_recaptcha": _captcha_required(username, ip),
                "recaptcha_enabled": recaptcha_enabled,
                "recaptcha_site_key": getattr(settings, "RECAPTCHA_SITE_KEY", ""),
                "recaptcha_mode": _recaptcha_mode(),
            },
        )

    if _captcha_required(username, ip):
        if not _verify_recaptcha(recaptcha_token, ip):
            pregunta = _set_verification(request)
            return render(
                request,
                "registration/login.html",
                {
                    "form_errors": "Debes validar el CAPTCHA para continuar.",
                    "next": next_url,
                    "username": username,
                    "verif_pregunta": pregunta,
                    "show_recaptcha": True,
                    "recaptcha_enabled": recaptcha_enabled,
                    "recaptcha_site_key": getattr(settings, "RECAPTCHA_SITE_KEY", ""),
                    "recaptcha_mode": _recaptcha_mode(),
                },
            )

    # Honeypot (si trae valor, aborta)
    if hp:
        _mark_failed_attempt(username)
        pregunta = _set_verification(request)
        return render(
            request,
            "registration/login.html",
            {
                "form_errors": "No se pudo validar el acceso. Intenta de nuevo.",
                "next": next_url,
                "username": username,
                "verif_pregunta": pregunta,
                "show_recaptcha": _captcha_required(username, ip),
                "recaptcha_enabled": recaptcha_enabled,
                "recaptcha_site_key": getattr(settings, "RECAPTCHA_SITE_KEY", ""),
                "recaptcha_mode": _recaptcha_mode(),
            },
        )

    expected = request.session.get(SESSION_A)

    # Validación de verificación
    if not expected or verif != expected:
        _mark_failed_attempt(username)
        # regenerar para evitar reintentos automáticos
        pregunta = _set_verification(request)
        return render(
            request,
            "registration/login.html",
            {
                "form_errors": "Verificación de seguridad incorrecta.",
                "next": next_url,
                "username": username,
                "verif_pregunta": pregunta,
                "show_recaptcha": _captcha_required(username, ip),
                "recaptcha_enabled": recaptcha_enabled,
                "recaptcha_site_key": getattr(settings, "RECAPTCHA_SITE_KEY", ""),
                "recaptcha_mode": _recaptcha_mode(),
            },
        )

    # Resolución por correo electrónico: si el campo contiene "@" se busca
    # el usuario activo con ese correo y se usa su username para autenticar.
    if "@" in username:
        _User = get_user_model()
        _u = _User.objects.filter(
            email__iexact=username, is_active=True).first()
        if _u:
            username = _u.username

    # Auth
    user = authenticate(request, username=username, password=password)
    if user is None:
        _mark_failed_attempt(username)
        log_event(
            request,
            accion="AUTH::LOGIN_FAIL",
            entidad="Sesion",
            entidad_id=username or None,
            resultado="error",
            detalle={"username": username, "ip": ip,
                     "reason": "invalid_credentials"},
        )
        pregunta = _set_verification(request)
        return render(
            request,
            "registration/login.html",
            {
                "form_errors": "Usuario o contraseña incorrectos.",
                "next": next_url,
                "username": username,
                "verif_pregunta": pregunta,
                "show_recaptcha": _captcha_required(username, ip),
                "recaptcha_enabled": recaptcha_enabled,
                "recaptcha_site_key": getattr(settings, "RECAPTCHA_SITE_KEY", ""),
                "recaptcha_mode": _recaptcha_mode(),
            },
        )

    # OK login
    _clear_attempts(username)
    login(request, user)
    request.session.pop(SESSION_Q, None)
    request.session.pop(SESSION_A, None)
    log_event(
        request,
        accion="AUTH::LOGIN",
        entidad="Sesion",
        entidad_id=str(user.pk),
        resultado="ok",
        detalle={"username": user.get_username()},
    )
    return redirect(next_url)
