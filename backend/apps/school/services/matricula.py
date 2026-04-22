"""
Servicio de generación de matrícula para el módulo Escolar.

Formato: CCENT-NNNN  (ej. CCENT-0001, CCENT-0042, CCENT-1000)
- El prefijo CCENT identifica al centro de enseñanza.
- El número es secuencial, cero-rellenado a 4 dígitos.
- Es seguro ante concurrencia: usa select_for_update dentro de una transacción.
"""

import re

from django.db import transaction

_PREFIX = "CCENT-"
_CCENT_RE = re.compile(r"^CCENT-(\d+)$")


def generate_matricula() -> str:
    """
    Devuelve la siguiente matrícula CCENT-NNNN disponible.

    Adquiere un lock optimista sobre todas las filas CCENT existentes para
    evitar colisiones en inserciones concurrentes.
    Debe llamarse dentro de la misma transacción que el INSERT del alumno
    (o bien Alumno.save() lo garantiza al envolver en atomic).
    """
    # Import local para evitar dependencia circular en módulo de modelos.
    from apps.school.models import Alumno

    with transaction.atomic():
        matriculas = list(
            Alumno.objects
            .filter(matricula__startswith=_PREFIX)
            .select_for_update()
            .values_list("matricula", flat=True)
        )

        max_n = 0
        for valor in matriculas:
            m = _CCENT_RE.match(valor)
            if m:
                max_n = max(max_n, int(m.group(1)))

        return f"{_PREFIX}{max_n + 1:04d}"


def es_matricula_ccent(valor: str) -> bool:
    """Retorna True si el valor ya tiene formato CCENT-NNNN."""
    return bool(_CCENT_RE.match(valor or ""))
