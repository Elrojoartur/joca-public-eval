from datetime import date
import calendar
import re

from django.db import migrations, models


def _defaults_periodo(codigo):
    year, month = codigo.split("-", 1)
    year_i = int(year)
    month_i = int(month)
    _, last_day = calendar.monthrange(year_i, month_i)
    return {
        "fecha_inicio": date(year_i, month_i, 1),
        "fecha_fin": date(year_i, month_i, last_day),
        "activo": True,
    }


def _normalize_periodo(codigo):
    raw = (codigo or "").strip()
    if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", raw):
        return raw

    m = re.search(r"(\d{4})[-_/ ]?(0[1-9]|1[0-2])", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    return "2099-12"


def forwards(apps, schema_editor):
    Curso = apps.get_model("school", "Curso")
    Periodo = apps.get_model("school", "Periodo")
    Grupo = apps.get_model("school", "Grupo")
    ActaCierre = apps.get_model("school", "ActaCierre")
    Inscripcion = apps.get_model("school", "Inscripcion")
    GrupoHorario = apps.get_model("school", "GrupoHorario")
    DocenteGrupo = apps.get_model("school", "DocenteGrupo")

    canonical_by_key = {}
    for grupo in Grupo.objects.order_by("id").all().iterator():
        curso_id = grupo.curso_ref_id
        periodo_id = grupo.periodo_ref_id

        if not curso_id:
            curso_codigo = (
                grupo.curso_slug or "").strip() or f"curso-{grupo.pk}"
            curso, _ = Curso.objects.get_or_create(
                codigo=curso_codigo,
                defaults={
                    "nombre": curso_codigo.replace("-", " ")[:120] or curso_codigo,
                    "activo": True,
                },
            )
            curso_id = curso.id

        if not periodo_id:
            periodo_codigo = _normalize_periodo(grupo.periodo)
            periodo, _ = Periodo.objects.get_or_create(
                codigo=periodo_codigo,
                defaults=_defaults_periodo(periodo_codigo),
            )
            periodo_id = periodo.id

        key = (curso_id, periodo_id, grupo.tipo_horario)
        canonical_id = canonical_by_key.get(key)
        if not canonical_id:
            canonical_by_key[key] = grupo.id
            Grupo.objects.filter(pk=grupo.pk).update(
                curso_ref_id=curso_id, periodo_ref_id=periodo_id)
            continue

        # Reasignar inscripciones, evitando duplicados alumno+grupo.
        for insc in Inscripcion.objects.filter(grupo_id=grupo.id).iterator():
            exists = Inscripcion.objects.filter(
                alumno_id=insc.alumno_id, grupo_id=canonical_id).exists()
            if exists:
                insc.delete()
            else:
                insc.grupo_id = canonical_id
                insc.save(update_fields=["grupo"])

        GrupoHorario.objects.filter(
            grupo_id=grupo.id).update(grupo_id=canonical_id)
        DocenteGrupo.objects.filter(
            grupo_id=grupo.id).update(grupo_id=canonical_id)

        for acta in ActaCierre.objects.filter(grupo_id=grupo.id).iterator():
            duplicate = ActaCierre.objects.filter(
                grupo_id=canonical_id,
                periodo_ref_id=acta.periodo_ref_id,
            ).exists()
            if duplicate:
                acta.delete()
            else:
                acta.grupo_id = canonical_id
                acta.save(update_fields=["grupo"])

        grupo.delete()

    for acta in ActaCierre.objects.select_related("grupo", "grupo__periodo_ref").all().iterator():
        if acta.periodo_ref_id:
            continue

        periodo_obj = None
        if acta.grupo_id and getattr(acta.grupo, "periodo_ref_id", None):
            periodo_obj = acta.grupo.periodo_ref
        elif acta.periodo:
            periodo_codigo = _normalize_periodo(acta.periodo)
            periodo_obj, _ = Periodo.objects.get_or_create(
                codigo=periodo_codigo,
                defaults=_defaults_periodo(periodo_codigo),
            )

        if periodo_obj:
            acta.periodo_ref_id = periodo_obj.id
            acta.save(update_fields=["periodo_ref"])


def backwards(apps, schema_editor):
    Grupo = apps.get_model("school", "Grupo")
    ActaCierre = apps.get_model("school", "ActaCierre")

    for grupo in Grupo.objects.select_related("curso_ref", "periodo_ref").all().iterator():
        curso_slug = grupo.curso_ref.codigo if grupo.curso_ref_id else ""
        periodo = grupo.periodo_ref.codigo if grupo.periodo_ref_id else ""
        Grupo.objects.filter(pk=grupo.pk).update(
            curso_slug=curso_slug, periodo=periodo)

    for acta in ActaCierre.objects.select_related("periodo_ref").all().iterator():
        periodo = acta.periodo_ref.codigo if acta.periodo_ref_id else ""
        ActaCierre.objects.filter(pk=acta.pk).update(periodo=periodo)


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("school", "0014_alumno_rfc_vigente"),
    ]

    operations = [
        migrations.AddField(
            model_name="actacierre",
            name="periodo_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="actas_cierre",
                to="school.periodo",
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="grupo",
            name="curso_ref",
            field=models.ForeignKey(
                on_delete=models.PROTECT,
                related_name="grupos",
                to="school.curso",
            ),
        ),
        migrations.AlterField(
            model_name="grupo",
            name="periodo_ref",
            field=models.ForeignKey(
                on_delete=models.PROTECT,
                related_name="grupos",
                to="school.periodo",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="actacierre",
            name="uq_actacierre_grupo_periodo",
        ),
        migrations.AddConstraint(
            model_name="actacierre",
            constraint=models.UniqueConstraint(
                fields=("grupo", "periodo_ref"),
                name="uq_actacierre_grupo_periodoref",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="grupo",
            name="uq_grupo_curso_periodo_tipo",
        ),
        migrations.RemoveField(
            model_name="actacierre",
            name="periodo",
        ),
        migrations.RemoveField(
            model_name="grupo",
            name="curso_slug",
        ),
        migrations.RemoveField(
            model_name="grupo",
            name="periodo",
        ),
        migrations.AlterField(
            model_name="actacierre",
            name="periodo_ref",
            field=models.ForeignKey(
                on_delete=models.PROTECT,
                related_name="actas_cierre",
                to="school.periodo",
            ),
        ),
    ]
