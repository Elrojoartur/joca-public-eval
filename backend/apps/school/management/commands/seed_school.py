from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.school.models import (
    Grupo,
    Curso,
    Periodo,
    Aula,
    Docente,
    GrupoHorario,
    DocenteGrupo,
)


class Command(BaseCommand):
    help = "Seed CCENT (idempotente): cursos, periodo, aulas, docentes y relaciones."

    @transaction.atomic
    def handle(self, *args, **options):
        # 1) Cursos (2)
        curso1, _ = Curso.objects.get_or_create(
            # Ajusta estos campos cuando confirmemos el modelo real
            defaults={},
            **self._curso_lookup("electronica-basica", "Electrónica básica"),
        )
        curso2, _ = Curso.objects.get_or_create(
            defaults={},
            **self._curso_lookup("electronica-automotriz", "Electrónica automotriz"),
        )

        # 2) Periodo (1)
        periodo, _ = Periodo.objects.get_or_create(
            defaults={},
            **self._periodo_lookup("2026-01", "Enero 2026"),
        )

        # 3) Aulas (3)
        aula1, _ = Aula.objects.get_or_create(defaults={}, **self._aula_lookup("Aula 1"))
        aula2, _ = Aula.objects.get_or_create(defaults={}, **self._aula_lookup("Aula 2"))
        aula3, _ = Aula.objects.get_or_create(defaults={}, **self._aula_lookup("Laboratorio"))

        # 4) Docentes (2)
        doc1, _ = Docente.objects.get_or_create(
            defaults={},
            **self._docente_lookup("docente1@ccent.mx", "Docente", "Uno"),
        )
        doc2, _ = Docente.objects.get_or_create(
            defaults={},
            **self._docente_lookup("docente2@ccent.mx", "Docente", "Dos"),
        )

        # 5) Asociar a grupos existentes (sin romper los actuales)
        grupos = list(Grupo.objects.all().order_by("id"))
        if not grupos:
            self.stdout.write(self.style.WARNING("No hay grupos; no se crean horarios/asignaciones."))
            return

        # Reglas simples: alterna curso_ref, periodo_ref y docente por grupo
        for idx, g in enumerate(grupos):
            curso_ref = curso1 if idx % 2 == 0 else curso2

            # Set FK opcional (solo si el modelo tiene los campos)
            update = {}
            if hasattr(g, "curso_ref_id") and not g.curso_ref_id:
                update["curso_ref"] = curso_ref
            if hasattr(g, "periodo_ref_id") and not g.periodo_ref_id:
                update["periodo_ref"] = periodo

            if update:
                for k, v in update.items():
                    setattr(g, k, v)
                g.save(update_fields=list(update.keys()))

            # Horarios (ejemplo): SAB 09:00-14:00 para sabatino; SEM LUN/MIE 18:00-20:00
            if g.tipo_horario == "SAB":
                self._get_or_create_horario(g, "SAB", "09:00", "14:00", aula1)
            else:
                self._get_or_create_horario(g, "LUN", "18:00", "20:00", aula2)
                self._get_or_create_horario(g, "MIE", "18:00", "20:00", aula2)

            # Asignación docente
            docente = doc1 if idx % 2 == 0 else doc2
            DocenteGrupo.objects.get_or_create(
                docente=docente,
                grupo=g,
                defaults={"rol": "TIT", "activo": True},
            )

        self.stdout.write(self.style.SUCCESS("Seed CCENT aplicado (idempotente)."))

    def _get_or_create_horario(self, grupo, dia, hi, hf, aula):
        from datetime import time

        h_i = time.fromisoformat(hi)
        h_f = time.fromisoformat(hf)
        GrupoHorario.objects.get_or_create(
            grupo=grupo,
            dia=dia,
            hora_inicio=h_i,
            hora_fin=h_f,
            defaults={"aula_ref": aula, "activo": True},
        )

    # Estos helpers evitan “inventar” campos: se ajustan al modelo real cuando lo confirmemos.
    def _curso_lookup(self, slug, nombre):
        # preferente: slug si existe; si no, nombre.
        if "slug" in [f.name for f in Curso._meta.fields]:
            return {"slug": slug, "nombre": nombre} if "nombre" in [f.name for f in Curso._meta.fields] else {"slug": slug}
        if "nombre" in [f.name for f in Curso._meta.fields]:
            return {"nombre": nombre}
        return {}

    def _periodo_lookup(self, slug, nombre):
        fields = [f.name for f in Periodo._meta.fields]
        if "slug" in fields:
            d = {"slug": slug}
            if "nombre" in fields:
                d["nombre"] = nombre
            return d
        if "nombre" in fields:
            return {"nombre": nombre}
        return {}

    def _aula_lookup(self, nombre):
        fields = [f.name for f in Aula._meta.fields]
        if "nombre" in fields:
            return {"nombre": nombre}
        return {}

    def _docente_lookup(self, correo, nombres, apellidos):
        fields = [f.name for f in Docente._meta.fields]
        d = {}
        if "correo" in fields:
            d["correo"] = correo
        if "nombres" in fields:
            d["nombres"] = nombres
        if "apellidos" in fields:
            d["apellidos"] = apellidos
        return d
