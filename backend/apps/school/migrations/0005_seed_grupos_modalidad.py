from django.db import migrations

COURSES = [
    "Electrónica básica",
    "Diagnóstico en inyección electrónica",
    "Robótica",
    "Reparación de ECUs",
    "Programación automotriz",
    "Reparación de audio y video",
]

MODALIDADES = [
    ("SAB", "09:00-14:00"),
    ("SEM", "19:00-21:00"),
]

PERIODO_BASE = "2026A"


def seed_groups(apps, schema_editor):
    Grupo = apps.get_model("school", "Grupo")
    for idx, course in enumerate(COURSES, start=1):
        for modalidad_code, horario in MODALIDADES:
            horario_tag = horario.replace(":", "")
            periodo_txt = f"{PERIODO_BASE}-C{idx:02d}-{modalidad_code}-{horario_tag}"
            exists = Grupo.objects.filter(periodo=periodo_txt).exists()
            if exists:
                continue
            Grupo.objects.create(
                periodo=periodo_txt,
                cupo=20,
                estado=1,
            )


def unseed_groups(apps, schema_editor):
    Grupo = apps.get_model("school", "Grupo")
    for idx, course in enumerate(COURSES, start=1):
        for modalidad_code, horario in MODALIDADES:
            horario_tag = horario.replace(":", "")
            periodo_txt = f"{PERIODO_BASE}-C{idx:02d}-{modalidad_code}-{horario_tag}"
            Grupo.objects.filter(periodo=periodo_txt).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0004_actacierre"),
    ]

    operations = [
        migrations.RunPython(seed_groups, unseed_groups),
    ]
