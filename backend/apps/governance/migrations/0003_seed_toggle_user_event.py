from django.db import migrations


DEMO_ACTION = "USER_TOGGLE_ACTIVE_DEMO"


def create_demo_toggle(apps, schema_editor):
    EventoAuditoria = apps.get_model("governance", "EventoAuditoria")
    if EventoAuditoria.objects.filter(accion=DEMO_ACTION).exists():
        return
    EventoAuditoria.objects.create(
        actor=None,
        ip="127.0.0.1",
        accion=DEMO_ACTION,
        entidad="User",
        entidad_id="demo-user",
        resultado="OK",
        detalle={
            "motivo": "Ejemplo de cambio de estado (toggle activo)",
            "antes": "activo",
            "despues": "inactivo",
        },
    )


def remove_demo_toggle(apps, schema_editor):
    EventoAuditoria = apps.get_model("governance", "EventoAuditoria")
    EventoAuditoria.objects.filter(
        accion=DEMO_ACTION, entidad_id="demo-user"
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("governance", "0002_seed_demo_event"),
    ]

    operations = [
        migrations.RunPython(create_demo_toggle, remove_demo_toggle),
    ]
