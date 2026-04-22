from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Existencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name="ID")),
                ("inventario_habilitado", models.BooleanField(default=False)),
                ("stock_actual", models.DecimalField(
                    decimal_places=2, default=0, max_digits=12)),
                ("stock_minimo", models.DecimalField(
                    decimal_places=2, default=0, max_digits=12)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "concepto",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="existencia",
                        to="sales.concepto",
                    ),
                ),
            ],
            options={
                "verbose_name": "Existencia",
                "verbose_name_plural": "Existencias",
            },
        ),
        migrations.CreateModel(
            name="AlertaStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name="ID")),
                ("stock_actual", models.DecimalField(
                    decimal_places=2, max_digits=12)),
                ("stock_minimo", models.DecimalField(
                    decimal_places=2, max_digits=12)),
                ("activa", models.BooleanField(default=True)),
                ("creada_en", models.DateTimeField(
                    default=django.utils.timezone.now)),
                (
                    "concepto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="alertas_stock",
                        to="sales.concepto",
                    ),
                ),
                (
                    "existencia",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alertas",
                        to="sales.existencia",
                    ),
                ),
            ],
            options={
                "verbose_name": "Alerta de stock",
                "verbose_name_plural": "Alertas de stock",
                "ordering": ["-creada_en"],
            },
        ),
    ]
