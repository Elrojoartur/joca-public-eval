# Generated 2026-04-06
#
# Renumera todas las matrículas existentes al formato CCENT-NNNN.
# Las filas se ordenan por id_alumno (llave primaria) para garantizar
# asignación determinista: el alumno con id más bajo recibe CCENT-0001.
#
# La migración es atómica: si algún paso falla, la BD queda intacta.

import re

from django.db import migrations

_CCENT_RE = re.compile(r"^CCENT-(\d+)$")
_PREFIX = "CCENT-"


def _forward_renumerar(apps, schema_editor):
    Alumno = apps.get_model("school", "Alumno")

    alumnos = list(Alumno.objects.order_by(
        "id_alumno").only("id_alumno", "matricula"))
    if not alumnos:
        return

    # Construye el mapa nuevo con un contador limpio.
    updates = []
    for i, alumno in enumerate(alumnos, start=1):
        nueva = f"{_PREFIX}{i:04d}"
        if alumno.matricula != nueva:
            alumno.matricula = nueva
            updates.append(alumno)

    if updates:
        Alumno.objects.bulk_update(updates, ["matricula"])


def _reverse_renumerar(apps, schema_editor):
    # No es posible recuperar los valores originales sin almacenarlos;
    # el reverse deja las matrículas CCENT-NNNN tal cual.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0020_alumnodomicilio"),
    ]

    operations = [
        migrations.RunPython(
            _forward_renumerar,
            _reverse_renumerar,
        ),
    ]
