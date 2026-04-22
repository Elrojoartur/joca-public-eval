from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import Permiso, RolPermiso
from apps.school.models import Alumno, Curso, Grupo, GrupoHorario, Inscripcion, Periodo


@dataclass(frozen=True)
class RolSpec:
    codigo: str
    nombre: str


class Command(BaseCommand):
    help = (
        "Prepara ambiente base para 20 pruebas de caja negra: "
        "roles/permisos, cuentas, cursos, grupos, alumnos e inscripciones."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--periodo",
            default="2026-01",
            help="Periodo académico en formato YYYY-MM.",
        )
        parser.add_argument(
            "--alumnos-por-grupo",
            type=int,
            default=10,
            help="Cantidad de alumnos por grupo (recomendado 10-15).",
        )
        parser.add_argument(
            "--password-base",
            default="PruebasHU2026!",
            help="Contraseña base para usuarios creados.",
        )
        parser.add_argument(
            "--correo-oficial",
            default="CCENTjoca@gmail.com",
            help="Correo oficial para generar alias únicos de alumnos.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        periodo_codigo = (opts["periodo"] or "").strip()
        alumnos_por_grupo = int(opts["alumnos_por_grupo"])
        password_base = opts["password_base"]
        correo_oficial = (opts["correo_oficial"] or "").strip().lower()

        if alumnos_por_grupo < 10 or alumnos_por_grupo > 15:
            raise ValueError(
                "--alumnos-por-grupo debe estar en el rango 10-15.")
        if "@" not in correo_oficial:
            raise ValueError("--correo-oficial no es un correo válido.")

        roles = self._upsert_roles()
        self._upsert_nav_permissions(roles)
        self._upsert_base_users(roles, password_base, correo_oficial)

        periodo, _ = Periodo.objects.get_or_create(
            codigo=periodo_codigo,
            defaults=Periodo.defaults_for(periodo_codigo),
        )

        cursos = self._upsert_courses_from_catalog()
        grupos = self._upsert_groups_for_courses(cursos, periodo)
        counts = self._seed_students_and_enrollments(
            grupos=grupos,
            alumnos_por_grupo=alumnos_por_grupo,
            correo_oficial=correo_oficial,
            password_base=password_base,
        )

        self._seed_adeudos_hu012(grupos)
        self.stdout.write(self.style.SUCCESS(
            "Preparación de pruebas completada."))
        self.stdout.write(
            f"Resumen: cursos={len(cursos)} grupos={len(grupos)} "
            f"alumnos_creados={counts['alumnos_creados']} "
            f"inscripciones_creadas={counts['inscripciones_creadas']}"
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Modelo actualizado: ahora se permiten 3 grupos por curso/periodo "
                "(SEM-AM, SEM-PM, SAB-SAB)."
            )
        )

    def _upsert_roles(self) -> dict[str, Rol]:
        specs = [
            RolSpec(codigo="SUPERUSUARIO", nombre="Superusuario"),
            RolSpec(codigo="DIRECTOR_ESCOLAR", nombre="Director escolar"),
            RolSpec(codigo="ADMINISTRATIVO_COMERCIAL",
                    nombre="Administrativo comercial"),
            RolSpec(codigo="ALUMNO", nombre="Usuario alumno"),
            RolSpec(codigo="CLIENTE", nombre="Cliente"),
        ]
        out: dict[str, Rol] = {}
        for spec in specs:
            rol, _ = Rol.objects.update_or_create(
                codigo=spec.codigo,
                defaults={"nombre": spec.nombre, "activo": True},
            )
            out[spec.codigo] = rol
        return out

    def _upsert_nav_permissions(self, roles: dict[str, Rol]) -> None:
        perms = {
            "NAV_ESCOLAR": "Acceso menú Escolar",
            "NAV_VENTAS": "Acceso menú Ventas",
            "NAV_REPORTES": "Acceso menú Reportes",
            "NAV_GOBIERNO": "Acceso menú Gobierno",
            "NAV_ALUMNO": "Acceso menú Alumno",
        }

        permisos: dict[str, Permiso] = {}
        for code, name in perms.items():
            permiso, _ = Permiso.objects.update_or_create(
                codigo=code,
                defaults={
                    "nombre": name,
                    "modulo": "PANEL",
                    "activo": True,
                },
            )
            permisos[code] = permiso

        by_role = {
            "SUPERUSUARIO": [
                "NAV_ESCOLAR",
                "NAV_VENTAS",
                "NAV_REPORTES",
                "NAV_GOBIERNO",
                "NAV_ALUMNO",
            ],
            "DIRECTOR_ESCOLAR": ["NAV_ESCOLAR", "NAV_REPORTES", "NAV_GOBIERNO"],
            "ADMINISTRATIVO_COMERCIAL": ["NAV_VENTAS", "NAV_REPORTES", "NAV_GOBIERNO"],
            "ALUMNO": ["NAV_ALUMNO"],
        }

        for role_code, codes in by_role.items():
            rol = roles[role_code]
            keep_ids = [permisos[c].id for c in codes]
            RolPermiso.objects.filter(rol=rol).exclude(
                permiso_id__in=keep_ids).delete()
            for code in codes:
                RolPermiso.objects.get_or_create(
                    rol=rol, permiso=permisos[code])

    def _upsert_base_users(
        self,
        roles: dict[str, Rol],
        password_base: str,
        correo_oficial: str,
    ) -> None:
        User = get_user_model()

        group_director, _ = Group.objects.get_or_create(
            name="director_escolar")
        group_comercial, _ = Group.objects.get_or_create(
            name="administrativo_comercial")
        group_alumno, _ = Group.objects.get_or_create(name="alumno")

        def upsert_user(
            username: str,
            email: str,
            role_code: str,
            is_staff: bool,
            is_superuser: bool,
            group: Group | None,
        ):
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    "email": email,
                    "is_active": True,
                    "is_staff": is_staff,
                    "is_superuser": is_superuser,
                },
            )
            user.set_password(password_base)
            user.save(update_fields=["password"])

            if group:
                user.groups.add(group)

            UsuarioRol.objects.update_or_create(
                usuario=user,
                defaults={"rol": roles[role_code]},
            )

        local, domain = correo_oficial.split("@", 1)

        upsert_user(
            username="superusuario",
            email=f"{local}+superusuario@{domain}",
            role_code="SUPERUSUARIO",
            is_staff=True,
            is_superuser=True,
            group=None,
        )
        upsert_user(
            username="director_escolar",
            email=f"{local}+director@{domain}",
            role_code="DIRECTOR_ESCOLAR",
            is_staff=True,
            is_superuser=False,
            group=group_director,
        )
        upsert_user(
            username="administrativo_comercial",
            email=f"{local}+comercial@{domain}",
            role_code="ADMINISTRATIVO_COMERCIAL",
            is_staff=True,
            is_superuser=False,
            group=group_comercial,
        )
        upsert_user(
            username="cuenta_bloqueable_hu012",
            email=f"{local}+hu012@{domain}",
            role_code="ALUMNO",
            is_staff=False,
            is_superuser=False,
            group=group_alumno,
        )

    def _upsert_courses_from_catalog(self) -> list[Curso]:
        catalog_path = (
            Path(__file__).resolve().parents[4]
            / "apps"
            / "ui"
            / "catalogs"
            / "cursos.json"
        )
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))

        cursos: list[Curso] = []
        for item in raw:
            codigo = (item.get("id") or "").strip()[:40]
            nombre = (item.get("nombre") or codigo).strip()[:120]
            descripcion = (item.get("descripcion") or "").strip()
            if not codigo:
                continue

            curso, _ = Curso.objects.update_or_create(
                codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "descripcion": descripcion,
                    "activo": True,
                },
            )
            cursos.append(curso)
        return cursos

    def _upsert_groups_for_courses(self, cursos: list[Curso], periodo: Periodo) -> list[Grupo]:
        all_groups: list[Grupo] = []
        for curso in cursos:
            sem_am_group, _ = Grupo.objects.update_or_create(
                curso_ref=curso,
                periodo_ref=periodo,
                tipo_horario=Grupo.HORARIO_SEM,
                turno=Grupo.TURNO_AM,
                defaults={
                    "cupo": 15,
                    "estado": Grupo.ESTADO_ACTIVO,
                },
            )
            sem_pm_group, _ = Grupo.objects.update_or_create(
                curso_ref=curso,
                periodo_ref=periodo,
                tipo_horario=Grupo.HORARIO_SEM,
                turno=Grupo.TURNO_PM,
                defaults={
                    "cupo": 15,
                    "estado": Grupo.ESTADO_ACTIVO,
                },
            )
            sab_group, _ = Grupo.objects.update_or_create(
                curso_ref=curso,
                periodo_ref=periodo,
                tipo_horario=Grupo.HORARIO_SAB,
                turno=Grupo.TURNO_SAB,
                defaults={
                    "cupo": 15,
                    "estado": Grupo.ESTADO_ACTIVO,
                },
            )

            # Turnos solicitados: 09-11 y 19-21 en entre semana + sabatino 09-14.
            self._replace_group_schedule(
                sem_am_group,
                [
                    ("LUN", "09:00", "11:00"),
                    ("MIE", "09:00", "11:00"),
                    ("VIE", "09:00", "11:00"),
                ],
            )
            self._replace_group_schedule(
                sem_pm_group,
                [
                    ("MAR", "19:00", "21:00"),
                    ("JUE", "19:00", "21:00"),
                    ("VIE", "19:00", "21:00"),
                ],
            )
            self._replace_group_schedule(
                sab_group,
                [("SAB", "09:00", "14:00")],
            )

            all_groups.extend([sem_am_group, sem_pm_group, sab_group])

        return all_groups

    def _replace_group_schedule(self, group: Grupo, slots: list[tuple[str, str, str]]) -> None:
        from datetime import time

        GrupoHorario.objects.filter(grupo=group).delete()
        for day, hh_ini, hh_fin in slots:
            GrupoHorario.objects.create(
                grupo=group,
                dia=day,
                hora_inicio=time.fromisoformat(hh_ini),
                hora_fin=time.fromisoformat(hh_fin),
                activo=True,
            )

    def _seed_students_and_enrollments(
        self,
        grupos: list[Grupo],
        alumnos_por_grupo: int,
        correo_oficial: str,
        password_base: str,
    ) -> dict[str, int]:
        User = get_user_model()
        rol_alumno = Rol.objects.get(codigo="ALUMNO")
        group_alumno, _ = Group.objects.get_or_create(name="alumno")

        local, domain = correo_oficial.split("@", 1)

        nombres = [
            "Ana", "Luis", "María", "José", "Elena", "Carlos", "Sofía", "Miguel", "Paula", "Jorge",
            "Lucía", "Fernando", "Diana", "Raúl", "Andrea", "Héctor", "Camila", "Rubén", "Valeria", "Sergio",
        ]
        apellidos = [
            "García", "López", "Hernández", "Martínez", "González", "Pérez", "Rodríguez", "Sánchez", "Ramírez", "Torres",
            "Flores", "Rivera", "Gómez", "Díaz", "Cruz", "Morales", "Ortiz", "Reyes", "Vargas", "Castillo",
        ]

        alumnos_creados = 0
        inscripciones_creadas = 0

        for group in grupos:
            course_code = (group.curso_ref.codigo or "CURSO").upper()
            iniciales = self._initials_from_code(course_code)
            turno = "S" if group.tipo_horario == Grupo.HORARIO_SAB else "E"

            for seq in range(1, alumnos_por_grupo + 1):
                matricula = f"CCENT{iniciales}{turno}{seq:03d}"
                first_name = nombres[(group.pk + seq) % len(nombres)]
                last_name = apellidos[(group.pk + seq * 3) % len(apellidos)]
                second_last = apellidos[(group.pk + seq * 5) % len(apellidos)]

                email = f"{local}+{matricula.lower()}@{domain}"

                alumno, was_created = Alumno.objects.update_or_create(
                    matricula=matricula,
                    defaults={
                        "nombres": first_name,
                        "apellido_paterno": last_name,
                        "apellido_materno": second_last,
                        "correo": email,
                        "telefono": "5512345678",
                    },
                )
                if was_created:
                    alumnos_creados += 1

                user, _ = User.objects.update_or_create(
                    username=matricula,
                    defaults={
                        "email": email,
                        "is_active": True,
                        "is_staff": False,
                        "is_superuser": False,
                    },
                )
                user.set_password(password_base)
                user.save(update_fields=["password"])
                user.groups.add(group_alumno)

                UsuarioRol.objects.update_or_create(
                    usuario=user,
                    defaults={"rol": rol_alumno},
                )

                _, created = Inscripcion.objects.get_or_create(
                    alumno=alumno,
                    grupo=group,
                    defaults={"estado": Inscripcion.ESTADO_ACTIVA},
                )
                if created:
                    inscripciones_creadas += 1

        return {
            "alumnos_creados": alumnos_creados,
            "inscripciones_creadas": inscripciones_creadas,
        }

    def _initials_from_code(self, course_code: str) -> str:
        cleaned = "".join(ch if ch.isalnum() else " " for ch in course_code)
        parts = [p for p in cleaned.split() if p]
        if not parts:
            return "CUR"
        if len(parts) == 1:
            token = parts[0]
            return (token[:3] if len(token) >= 3 else token.ljust(3, "X")).upper()
        return ("".join(p[0] for p in parts)[:3]).upper().ljust(3, "X")

    def _seed_adeudos_hu012(self, grupos: list[Grupo]) -> None:
        """Crea un adeudo (OrdenPOS pendiente) para cuenta_bloqueable_hu012.

        Permite que las pruebas de caja negra de HU012 (bloqueo de cuenta por
        intentos fallidos) también muestren una orden con saldo pendiente.
        """
        from django.apps import apps as _apps
        try:
            Concepto = _apps.get_model("sales", "Concepto")
            OrdenPOS = _apps.get_model("sales", "OrdenPOS")
            OrdenItem = _apps.get_model("sales", "OrdenItem")
        except LookupError:
            self.stdout.write(self.style.WARNING(
                "sales app no disponible — adeudos HU012 omitidos."))
            return

        if not grupos:
            return

        User = get_user_model()
        user = User.objects.filter(username="cuenta_bloqueable_hu012").first()
        if not user:
            return

        alumno, _ = Alumno.objects.update_or_create(
            matricula="HU012BLAB",
            defaults={
                "nombres": "Cuenta",
                "apellido_paterno": "Bloqueable",
                "apellido_materno": "HU012",
                "correo": user.email or "hu012@ccent.local",
                "telefono": "5500000012",
            },
        )

        grupo = grupos[0]

        insc, _ = Inscripcion.objects.get_or_create(
            alumno=alumno,
            grupo=grupo,
            defaults={"estado": Inscripcion.ESTADO_ACTIVA},
        )

        concepto_mens, _ = Concepto.objects.update_or_create(
            nombre="Mensualidad",
            defaults={"precio": Decimal("1200.00"), "activo": True},
        )
        concepto_mat, _ = Concepto.objects.update_or_create(
            nombre="Material",
            defaults={"precio": Decimal("350.00"), "activo": True},
        )

        orden, _ = OrdenPOS.objects.get_or_create(
            inscripcion=insc,
            defaults={"estado": OrdenPOS.ESTADO_PENDIENTE},
        )

        OrdenItem.objects.update_or_create(
            orden=orden,
            concepto=concepto_mens,
            defaults={"cantidad": 1, "precio_unit": Decimal("1200.00")},
        )
        OrdenItem.objects.update_or_create(
            orden=orden,
            concepto=concepto_mat,
            defaults={"cantidad": 1, "precio_unit": Decimal("350.00")},
        )

        self.stdout.write(self.style.SUCCESS(
            f"Adeudo HU012 OK: orden #{orden.pk} pendiente $1,550.00 "
            f"para alumno '{alumno.matricula}' (sin pago registrado)."))
