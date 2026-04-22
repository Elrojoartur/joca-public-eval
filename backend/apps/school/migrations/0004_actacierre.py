from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0003_alumno_curp_alumno_rfc"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActaCierre",
            fields=[
                ("id", models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name="ID")),
                ("periodo", models.CharField(db_index=True, max_length=32)),
                ("cerrada_en", models.DateTimeField(
                    db_index=True, default=django.utils.timezone.now)),
                ("motivo", models.TextField(blank=True)),
                (
                    "cerrada_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "grupo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="actas_cierre",
                        to="school.grupo",
                    ),
                ),
            ],
            options={
                "verbose_name": "Acta de cierre",
                "verbose_name_plural": "Actas de cierre",
                "ordering": ["-cerrada_en"],
            },
        ),
        migrations.AddConstraint(
            model_name="actacierre",
            constraint=models.UniqueConstraint(
                fields=("grupo", "periodo"), name="uq_actacierre_grupo_periodo"
            ),
        ),
    ]
