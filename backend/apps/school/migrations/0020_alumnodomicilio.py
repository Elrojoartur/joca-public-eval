# Generated 2026-04-06

import apps.school.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0019_grupo_turno_3grupos"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlumnoDomicilio",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "alumno",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="domicilio",
                        to="school.alumno",
                        verbose_name="alumno",
                    ),
                ),
                (
                    "calle",
                    models.CharField(
                        blank=True, default="", max_length=150, verbose_name="calle"
                    ),
                ),
                (
                    "numero",
                    models.CharField(
                        blank=True, default="", max_length=20, verbose_name="número"
                    ),
                ),
                (
                    "colonia",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=120,
                        verbose_name="colonia",
                    ),
                ),
                (
                    "codigo_postal",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=5,
                        validators=[
                            apps.school.validators.validate_codigo_postal],
                        verbose_name="código postal",
                    ),
                ),
                (
                    "estado",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=120,
                        verbose_name="estado",
                    ),
                ),
                (
                    "pais",
                    models.CharField(
                        default="México", max_length=120, verbose_name="país"
                    ),
                ),
                (
                    "actualizado_en",
                    models.DateTimeField(
                        auto_now=True, verbose_name="actualizado en"
                    ),
                ),
            ],
            options={
                "verbose_name": "Domicilio de alumno",
                "verbose_name_plural": "Domicilios de alumnos",
            },
        ),
    ]
