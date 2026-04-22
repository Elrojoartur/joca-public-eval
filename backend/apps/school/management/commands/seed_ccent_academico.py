from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.fields import NOT_PROVIDED
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
    help = "Seed académico CCENT (idempotente): cursos, periodo, aulas, docentes, horarios y asignaciones."

    @transaction.atomic
    def handle(self, *args, **options):
        # --- 1) Crear/obtener catálogo base ---
        cursos = self._seed_cursos()
        periodo = self._seed_periodo()
        aulas = self._seed_aulas()
        docentes = self._seed_docentes()

        # --- 2) Asociar catálogo a Grupos existentes ---
        grupos = list(Grupo.objects.all().order_by("id"))
        if not grupos:
            self.stdout.write(self.style.WARNING("No hay Grupos; solo se creó catálogo (Curso/Periodo/Aula/Docente)."))
            return

        for idx, g in enumerate(grupos):
            curso_ref = cursos[idx % len(cursos)]
            aula_ref = aulas[idx % len(aulas)]
            docente_ref = docentes[idx % len(docentes)]

            # Set FKs opcionales (solo si existen en el modelo actual y están vacías)
            update_fields = []
            if hasattr(g, "curso_ref_id") and not g.curso_ref_id:
                g.curso_ref = curso_ref
                update_fields.append("curso_ref")
            if hasattr(g, "periodo_ref_id") and not g.periodo_ref_id:
                g.periodo_ref = periodo
                update_fields.append("periodo_ref")

            if update_fields:
                g.save(update_fields=update_fields)

            # --- 3) Horarios normalizados ---
            # Regla simple e idempotente:
            # SAB -> Sábado 09:00-14:00
            # SEM -> Lunes y Miércoles 18:00-20:00
            if getattr(g, "tipo_horario", None) == "SAB":
                self._get_or_create_horario(g, "SAB", "09:00", "14:00", aula_ref)
            else:
                self._get_or_create_horario(g, "LUN", "18:00", "20:00", aula_ref)
                self._get_or_create_horario(g, "MIE", "18:00", "20:00", aula_ref)

            # --- 4) Asignación de docente ---
            DocenteGrupo.objects.get_or_create(
                docente=docente_ref,
                grupo=g,
                defaults={"rol": "TIT", "activo": True},
            )

        # --- 5) Resumen ---
        self.stdout.write(self.style.SUCCESS("Seed académico aplicado (idempotente)."))
        self.stdout.write(
            f"Totales -> Curso:{Curso.objects.count()}  Periodo:{Periodo.objects.count()}  "
            f"Aula:{Aula.objects.count()}  Docente:{Docente.objects.count()}  "
            f"GrupoHorario:{GrupoHorario.objects.count()}  DocenteGrupo:{DocenteGrupo.objects.count()}"
        )

    # =========================
    # Seeds por entidad
    # =========================

    def _seed_cursos(self):
        # 2 cursos
        specs = [
            {
                "slug": "electronica-basica",
                "clave": "ELEC-BAS",
                "codigo": "ELEC-BAS",
                "nombre": "Electrónica básica",
                "titulo": "Electrónica básica",
                "descripcion": "Curso base de electrónica.",
            },
            {
                "slug": "electronica-automotriz",
                "clave": "ELEC-AUTO",
                "codigo": "ELEC-AUTO",
                "nombre": "Electrónica automotriz",
                "titulo": "Electrónica automotriz",
                "descripcion": "Curso de electrónica aplicada a automoción.",
            },
        ]
        cursos = []
        for spec in specs:
            obj = self._upsert_by_best_key(Curso, spec)
            cursos.append(obj)
        return cursos

    def _seed_periodo(self):
        # 1 periodo
        spec = {
            "slug": "2026-01",
            "clave": "2026-01",
            "codigo": "2026-01",
            "nombre": "Enero 2026",
            "periodo": "2026-01",
            "fecha_inicio": date(2026, 1, 1),
            "fecha_fin": date(2026, 1, 31),
            "activo": True,
        }
        return self._upsert_by_best_key(Periodo, spec)

    def _seed_aulas(self):
        specs = [
            {"nombre": "Aula 1", "clave": "A1", "codigo": "A1", "capacidad": 25},
            {"nombre": "Aula 2", "clave": "A2", "codigo": "A2", "capacidad": 25},
            {"nombre": "Laboratorio", "clave": "LAB", "codigo": "LAB", "capacidad": 15},
        ]
        aulas = []
        for spec in specs:
            aulas.append(self._upsert_by_best_key(Aula, spec))
        return aulas

    def _seed_docentes(self):
        specs = [
            {"correo": "docente1@ccent.mx", "nombres": "Docente", "apellidos": "Uno"},
            {"correo": "docente2@ccent.mx", "nombres": "Docente", "apellidos": "Dos"},
        ]
        docentes = []
        for spec in specs:
            docentes.append(self._upsert_by_best_key(Docente, spec))
        return docentes

    # =========================
    # Helpers robustos (sin “inventar” campos)
    # =========================

    def _field_names(self, model):
        return {f.name for f in model._meta.fields}

    def _pick_key_field(self, model, candidates):
        fields = self._field_names(model)

        # 1) Prioriza un campo unique si está en candidatos
        for f in model._meta.fields:
            if f.name in fields and getattr(f, "unique", False) and f.name in candidates:
                return f.name

        # 2) Si existe algún candidato, usa el primero que exista
        for c in candidates:
            if c in fields:
                return c

        # 3) Fallback: primer CharField/SlugField no-id
        for f in model._meta.fields:
            if f.name != "id" and f.get_internal_type() in ("CharField", "SlugField", "EmailField"):
                return f.name

        # 4) Último recurso: id (pero no sirve para upsert real)
        return "id"

    def _upsert_by_best_key(self, model, spec: dict):
        """
        Idempotente sin asumir nombres: elige el mejor 'key field' disponible y:
        - busca con filter().first() para evitar MultipleObjectsReturned
        - si no existe, crea rellenando campos requeridos con defaults razonables
        """
        fields = self._field_names(model)

        # Candidatos por entidad (en orden de preferencia)
        if model is Docente:
            key = self._pick_key_field(model, ["correo", "email", "username", "matricula", "clave", "codigo", "nombre"])
        elif model is Aula:
            key = self._pick_key_field(model, ["clave", "codigo", "nombre", "aula"])
        elif model is Curso:
            key = self._pick_key_field(model, ["slug", "clave", "codigo", "nombre", "titulo"])
        elif model is Periodo:
            key = self._pick_key_field(model, ["slug", "clave", "codigo", "periodo", "nombre"])
        else:
            key = self._pick_key_field(model, ["slug", "clave", "codigo", "nombre"])

        if key != "id" and key in fields and key in spec:
            lookup = {key: spec[key]}
        else:
            # Si no hay key usable, intenta por el primer campo común disponible en spec
            lookup = {}
            for k, v in spec.items():
                if k in fields:
                    lookup = {k: v}
                    break

        obj = model.objects.filter(**lookup).first() if lookup else None
        if obj:
            # opcional: actualizar campos “de relleno” si existen y están vacíos
            self._safe_update(obj, spec)
            return obj

        create_kwargs = {k: v for k, v in spec.items() if k in fields}
        if lookup:
            create_kwargs.update(lookup)

        self._fill_required_fields(model, create_kwargs, spec)
        return model.objects.create(**create_kwargs)

    def _safe_update(self, obj, spec: dict):
        """Actualiza solo campos existentes y vacíos, sin pisar datos reales."""
        fields = {f.name: f for f in obj._meta.fields}
        changed = []
        for k, v in spec.items():
            if k in fields and k not in ("id",):
                current = getattr(obj, k, None)
                if current in (None, "", 0) and v not in (None, ""):
                    setattr(obj, k, v)
                    changed.append(k)
        if changed:
            obj.save(update_fields=changed)

    def _fill_required_fields(self, model, create_kwargs: dict, spec: dict):
        """
        Rellena campos requeridos sin default y sin null, con valores seguros por tipo.
        """
        for f in model._meta.fields:
            if f.name in create_kwargs:
                continue
            if f.primary_key or f.auto_created:
                continue

            # Si es nullable o tiene default, no es obligatorio rellenarlo
            has_default = f.default is not NOT_PROVIDED
            if getattr(f, "null", False) or has_default:
                continue

            # Campos automáticos
            if getattr(f, "auto_now", False) or getattr(f, "auto_now_add", False):
                continue

            itype = f.get_internal_type()

            if itype in ("CharField", "SlugField", "TextField"):
                # usa algo del spec si existe, si no un placeholder estable
                create_kwargs[f.name] = spec.get("nombre") or spec.get("titulo") or f"{model.__name__}_{f.name}"
            elif itype in ("EmailField",):
                create_kwargs[f.name] = spec.get("correo") or f"{model.__name__.lower()}@example.com"
            elif itype in ("IntegerField", "PositiveIntegerField", "SmallIntegerField", "BigIntegerField"):
                # capacidad preferida
                if f.name == "capacidad":
                    create_kwargs[f.name] = spec.get("capacidad", 25)
                else:
                    create_kwargs[f.name] = 0
            elif itype in ("BooleanField",):
                create_kwargs[f.name] = True
            elif itype in ("DateField",):
                create_kwargs[f.name] = spec.get(f.name, date.today())
            elif itype in ("DateTimeField",):
                create_kwargs[f.name] = timezone.now()
            elif itype in ("DecimalField", "FloatField"):
                create_kwargs[f.name] = Decimal("0.00") if itype == "DecimalField" else 0.0
            elif itype == "ForeignKey":
                # Si existe FK requerida, intenta usar un registro existente del modelo relacionado
                rel_model = f.remote_field.model
                rel_obj = rel_model.objects.first()
                if rel_obj is None:
                    raise RuntimeError(
                        f"No se puede crear {model.__name__}: FK requerida '{f.name}' no tiene registros en {rel_model.__name__}."
                    )
                create_kwargs[f.name] = rel_obj
            else:
                # Último recurso: intenta string vacío (mejor fallar explícito si es inválido)
                create_kwargs[f.name] = None

    def _get_or_create_horario(self, grupo, dia, hi, hf, aula):
        h_i = time.fromisoformat(hi)
        h_f = time.fromisoformat(hf)
        GrupoHorario.objects.get_or_create(
            grupo=grupo,
            dia=dia,
            hora_inicio=h_i,
            hora_fin=h_f,
            defaults={"aula_ref": aula, "activo": True},
        )