"""
apps/authn/decorators.py
========================
Rate limiting basado en Django cache (sin dependencias externas).

Uso:
    from apps.authn.decorators import rate_limit

    @rate_limit("contacto_post", max_calls=5, period_seconds=300)
    def mi_vista(request):
        ...

Notas de producción:
- Con el cache por defecto (LocMemCache) el estado NO se comparte entre
  workers Gunicorn. Para producción multi-worker considera configurar
  django-redis o memcached en settings.CACHES. Para un proyecto de un
  solo worker (típico en VPS estudiantil) LocMemCache es suficiente.
- No registra secretos: solo IP y prefijo de clave.

Confianza de X-Forwarded-For:
- En dev (SECURE_PROXY_SSL_HEADER no configurado) se usa REMOTE_ADDR.
- En producción detrás de Nginx (SECURE_PROXY_SSL_HEADER activo) se usa
  el primer valor de X-Forwarded-For.
  IMPORTANTE: el bloque Nginx debe usar
      proxy_set_header X-Forwarded-For $remote_addr;
  (no $proxy_add_x_forwarded_for) para evitar que un cliente inyecte
  IPs falsas y evada el rate limiting.
"""
from __future__ import annotations

import logging
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

_logger = logging.getLogger("bitacora")


def _extract_ip(request) -> str:
    """
    Extrae la IP real del cliente.

    - Si la app está detrás de un proxy de confianza (SECURE_PROXY_SSL_HEADER
      configurado en settings) usa el primer valor de X-Forwarded-For, que
      debe ser sobreescrito por Nginx con el IP real del cliente.
    - De lo contrario usa REMOTE_ADDR directamente para evitar spoofing.
    """
    behind_proxy = bool(getattr(settings, "SECURE_PROXY_SSL_HEADER", None))
    if behind_proxy:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or "anon"


def rate_limit(key_prefix: str, max_calls: int, period_seconds: int):
    """
    Limita a ``max_calls`` peticiones por IP en una ventana de ``period_seconds``.

    Responde con HTTP 429 cuando se supera el límite.
    La ventana se reinicia automáticamente al expirar la clave en cache.

    Args:
        key_prefix:      Identificador único de la ruta/acción.
        max_calls:       Máximo de llamadas permitidas en la ventana.
        period_seconds:  Duración de la ventana en segundos.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            ip = _extract_ip(request)
            cache_key = f"rl:{key_prefix}:{ip}"

            # cache.add() solo escribe si la clave no existe → inicia ventana
            cache.add(cache_key, 0, period_seconds)
            try:
                count = cache.incr(cache_key)
            except ValueError:
                # Clave desapareció entre add() e incr() (race extremo); reiniciar
                cache.set(cache_key, 1, period_seconds)
                count = 1

            if count > max_calls:
                _logger.warning(
                    "[RATE_LIMIT] bloqueado key=%s ip=%s count=%d",
                    key_prefix, ip, count,
                )
                return HttpResponse(
                    "Demasiadas solicitudes. Intenta más tarde.",
                    status=429,
                    content_type="text/plain; charset=utf-8",
                )

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
