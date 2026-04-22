"""Servicio de generación de usernames institucionales.

Genera identificadores de acceso según el rol asignado:
  SUPERUSUARIO              → CCENTSP-NNN
  DIRECTOR_ESCOLAR          → CCENTDE-NNN
  ADMINISTRATIVO_COMERCIAL  → CCENTADC-NNN
  ALUMNO                    → matrícula (gestionada externamente)

No requiere modificaciones de esquema de base de datos.
"""

import re

from django.contrib.auth import get_user_model

# Mapa de código de rol → prefijo institucional
_PREFIXES: dict[str, str] = {
    "SUPERUSUARIO": "CCENTSP",
    "DIRECTOR_ESCOLAR": "CCENTDE",
    "ADMINISTRATIVO_COMERCIAL": "CCENTADC",
}


def get_institutional_prefix(rol_codigo: str) -> str | None:
    """Retorna el prefijo institucional para un código de rol, o ``None`` si no aplica."""
    return _PREFIXES.get(rol_codigo)


def generate_institutional_username(rol_codigo: str) -> str:
    """Genera el siguiente username institucional disponible para el rol dado.

    Ejemplo: la primera vez con DIRECTOR_ESCOLAR retorna ``CCENTDE-001``;
    si ya existe ``CCENTDE-001`` y ``CCENTDE-002``, retorna ``CCENTDE-003``.

    Raises:
        ValueError: Si el código de rol no tiene prefijo institucional definido.
    """
    prefix = _PREFIXES.get(rol_codigo)
    if not prefix:
        raise ValueError(
            f"No hay prefijo institucional para el rol: {rol_codigo!r}"
        )

    User = get_user_model()
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    max_num = 0

    for uname in (
        User.objects.filter(username__startswith=prefix + "-")
        .values_list("username", flat=True)
    ):
        m = pattern.match(uname)
        if m:
            max_num = max(max_num, int(m.group(1)))

    return f"{prefix}-{max_num + 1:03d}"
