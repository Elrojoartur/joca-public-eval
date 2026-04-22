from django.db import migrations, models


def forwards(apps, schema_editor):
    OrdenPOS = apps.get_model("sales", "OrdenPOS")

    for orden in OrdenPOS.objects.select_related("inscripcion__grupo__periodo_ref").all().iterator():
        if orden.periodo_ref_id:
            continue
        periodo_id = None
        if orden.inscripcion_id and orden.inscripcion.grupo_id and orden.inscripcion.grupo.periodo_ref_id:
            periodo_id = orden.inscripcion.grupo.periodo_ref_id
        if periodo_id:
            orden.periodo_ref_id = periodo_id
            orden.save(update_fields=["periodo_ref"])


def backwards(apps, schema_editor):
    OrdenPOS = apps.get_model("sales", "OrdenPOS")

    for orden in OrdenPOS.objects.select_related("periodo_ref").all().iterator():
        periodo = orden.periodo_ref.codigo if orden.periodo_ref_id else ""
        OrdenPOS.objects.filter(pk=orden.pk).update(periodo=periodo)


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0015_normalize_grupo_acta_3fn"),
        ("sales", "0003_cortecaja"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordenpos",
            name="periodo_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="ordenes_pos",
                to="school.periodo",
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveConstraint(
            model_name="ordenpos",
            name="uq_orden_inscripcion_periodo",
        ),
        migrations.AddConstraint(
            model_name="ordenpos",
            constraint=models.UniqueConstraint(
                fields=("inscripcion", "periodo_ref"),
                name="uq_orden_inscripcion_periodoref",
            ),
        ),
        migrations.RemoveField(
            model_name="ordenpos",
            name="periodo",
        ),
        migrations.AlterField(
            model_name="ordenpos",
            name="periodo_ref",
            field=models.ForeignKey(
                on_delete=models.PROTECT,
                related_name="ordenes_pos",
                to="school.periodo",
            ),
        ),
    ]
