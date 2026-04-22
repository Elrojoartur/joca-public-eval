from django.db import migrations


DEMO_ACTION = "DEMO_BITACORA_INICIAL"


def create_demo_event(apps, schema_editor):
    EventoAuditoria = apps.get_model("governance", "EventoAuditoria")
    if EventoAuditoria.objects.filter(accion=DEMO_ACTION).exists():
        return
    EventoAuditoria.objects.create(
        actor=None,
        ip="127.0.0.1",
        accion=DEMO_ACTION,
        entidad="Sistema",
        entidad_id="demo",
        resultado="OK",
        detalle={"nota": "Evento de ejemplo para mostrar la bitácora en /admin/"},
    )


def remove_demo_event(apps, schema_editor):
    EventoAuditoria = apps.get_model("governance", "EventoAuditoria")
    EventoAuditoria.objects.filter(
        accion=DEMO_ACTION, entidad_id="demo").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("governance", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_demo_event, remove_demo_event),
    ]
