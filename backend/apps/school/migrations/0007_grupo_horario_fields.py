from datetime import time
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0006_update_grupos_horario"),
    ]

    operations = [
        migrations.AddField(
            model_name="grupo",
            name="curso_slug",
            field=models.SlugField(default="curso", max_length=80),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="grupo",
            name="tipo_horario",
            field=models.CharField(
                choices=[("SAB", "Sabatino"), ("SEM", "Entre semana")],
                default="SAB",
                max_length=3,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="grupo",
            name="dias",
            field=models.CharField(default="Sábado", max_length=60),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="grupo",
            name="hora_inicio",
            field=models.TimeField(default=time(9, 0)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="grupo",
            name="hora_fin",
            field=models.TimeField(default=time(14, 0)),
            preserve_default=False,
        ),
    ]
