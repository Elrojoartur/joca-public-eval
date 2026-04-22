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


def forwards(apps, schema_editor):
    Grupo = apps.get_model("school", "Grupo")
    for idx, _course in enumerate(COURSES, start=1):
        for modalidad_code, horario in MODALIDADES:
            horario_tag = horario.replace(":", "")
            new_period = f"{PERIODO_BASE}-C{idx:02d}-{modalidad_code}-{horario_tag}"
            if not Grupo.objects.filter(periodo=new_period).exists():
                Grupo.objects.create(periodo=new_period, cupo=20, estado=1)
            old_period = f"{PERIODO_BASE}-C{idx:02d}-{modalidad_code}"
            Grupo.objects.filter(periodo=old_period).delete()


def backwards(apps, schema_editor):
    Grupo = apps.get_model("school", "Grupo")
    for idx, _course in enumerate(COURSES, start=1):
        for modalidad_code, horario in MODALIDADES:
            horario_tag = horario.replace(":", "")
            new_period = f"{PERIODO_BASE}-C{idx:02d}-{modalidad_code}-{horario_tag}"
            Grupo.objects.filter(periodo=new_period).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0005_seed_grupos_modalidad"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
