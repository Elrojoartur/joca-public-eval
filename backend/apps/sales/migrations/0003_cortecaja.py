from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sales", "0002_existencia_alertastock"),
    ]

    operations = [
        migrations.CreateModel(
            name="CorteCaja",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_operacion", models.DateField(db_index=True, unique=True)),
                ("cerrado_en", models.DateTimeField(default=django.utils.timezone.now)),
                ("total_ordenes", models.PositiveIntegerField(default=0)),
                ("monto_ordenes", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total_pagos", models.PositiveIntegerField(default=0)),
                ("monto_pagos", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("notas", models.CharField(blank=True, max_length=255)),
                (
                    "realizado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cortes_caja",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Corte de caja",
                "verbose_name_plural": "Cortes de caja",
                "ordering": ["-fecha_operacion", "-cerrado_en"],
            },
        ),
    ]
