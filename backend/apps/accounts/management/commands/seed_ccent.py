from __future__ import annotations

from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


def _get_model(app_label: str, model_names: list[str]):
    """Devuelve el primer modelo existente en el app (por nombre)."""
    try:
        app = apps.get_app_config(app_label)
    except LookupError:
        return None

    registry = {m.__name__.lower(): m for m in app.get_models()}
    for name in model_names:
        m = registry.get(name.lower())
        if m:
            return m
    return None


def _field_names(model):
    return {f.name for f in model._meta.get_fields() if hasattr(f, "name")}


def _safe_defaults(model, data: dict):
    """Filtra defaults para no pasar campos que no existan en el modelo."""
    fields = _field_names(model)
    return {k: v for k, v in data.items() if k in fields}


class Command(BaseCommand):
    help = "Carga datos semilla idempotentes para CCENT/JOCA (DEV o VPS)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="ChangeMe123!@#",
            help="Password para usuarios semilla (cambiar después).",
        )
        parser.add_argument(
            "--only",
            choices=["all", "users", "school", "sales"],
            default="all",
            help="Sembrar solo un módulo.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        only = opts["only"]
        pwd = opts["password"]

        if only in ("all", "users"):
            self._seed_users(pwd)

        if only in ("all", "school"):
            # 1) Seed escolar base: grupos/alumnos/inscripciones/etc.
            self._seed_school()
            # 2) Seed académico (normalizado): Curso/Periodo/Aula/Docente + Horarios + Asignaciones
            #    Se ejecuta aquí (no al importar el módulo).
            call_command("seed_ccent_academico")

        if only in ("all", "sales"):
            self._seed_sales()

        self.stdout.write(self.style.SUCCESS("Seed CCENT completado."))

    def _seed_users(self, password: str):
        User = get_user_model()
        user_fields = _field_names(User)

        roles = ["director_escolar", "administrativo_comercial", "alumno"]
        groups = {}
        for r in roles:
            g, _ = Group.objects.get_or_create(name=r)
            groups[r] = g

        def upsert_user(
            username: str,
            email: str,
            is_staff: bool,
            is_superuser: bool,
            group_name: str | None,
        ):
            data = {}
            if "email" in user_fields:
                data["email"] = email
            if "is_staff" in user_fields:
                data["is_staff"] = is_staff
            if "is_superuser" in user_fields:
                data["is_superuser"] = is_superuser
            if "is_active" in user_fields:
                data["is_active"] = True

            lookup_field = getattr(User, "USERNAME_FIELD", "username")
            lookup_value = email if lookup_field == "email" else username
            lookup = {lookup_field: lookup_value}

            u, _ = User.objects.update_or_create(**lookup, defaults=data)

            # En DEV conviene que sea determinista: siempre deja el password como el del parámetro
            u.set_password(password)
            u.save(update_fields=["password"])

            if group_name:
                u.groups.add(groups[group_name])

            return u

        upsert_user("Arturo", "arturo@ccent.local", True, True, None)
        upsert_user("director_escolar", "director@ccent.local",
                    True, False, "director_escolar")
        upsert_user("administrativo_comercial", "comercial@ccent.local",
                    True, False, "administrativo_comercial")
        upsert_user("alumno", "alumno@ccent.local", False, False, "alumno")

        self.stdout.write(self.style.SUCCESS("Usuarios/roles semilla OK."))

    # Alias por si en algún momento vuelves a llamar "escolar"
    def _seed_escolar(self):
        return self._seed_school()

    def _seed_school(self):
        Alumno = apps.get_model("school", "Alumno")
        Grupo = apps.get_model("school", "Grupo")
        Inscripcion = apps.get_model("school", "Inscripcion")
        Curso = apps.get_model("school", "Curso")
        Periodo = apps.get_model("school", "Periodo")

        # Opcionales (si existen en tu app)
        Calificacion = None
        ActaCierre = None
        try:
            Calificacion = apps.get_model("school", "Calificacion")
        except Exception:
            pass
        try:
            ActaCierre = apps.get_model("school", "ActaCierre")
        except Exception:
            pass

        # Grupos normalizados por FK + tipo de horario.
        curso_1, _ = Curso.objects.get_or_create(
            codigo="electronica-basica",
            defaults=_safe_defaults(Curso, dict(
                nombre="Electronica basica", activo=True)),
        )
        curso_2, _ = Curso.objects.get_or_create(
            codigo="electronica-automotriz",
            defaults=_safe_defaults(Curso, dict(
                nombre="Electronica automotriz", activo=True)),
        )
        periodo_2026_01, _ = Periodo.objects.get_or_create(
            codigo="2026-01",
            defaults=_safe_defaults(Periodo, Periodo.defaults_for("2026-01")),
        )

        g1, _ = Grupo.objects.update_or_create(
            curso_ref=curso_1,
            periodo_ref=periodo_2026_01,
            tipo_horario=Grupo.HORARIO_SAB,
            turno=Grupo.TURNO_SAB,
            defaults=_safe_defaults(
                Grupo,
                dict(
                    cupo=20,
                    estado=Grupo.ESTADO_ACTIVO,
                ),
            ),
        )
        g2, _ = Grupo.objects.update_or_create(
            curso_ref=curso_2,
            periodo_ref=periodo_2026_01,
            tipo_horario=Grupo.HORARIO_SEM,
            turno=Grupo.TURNO_PM,
            defaults=_safe_defaults(
                Grupo,
                dict(
                    cupo=25,
                    estado=Grupo.ESTADO_ACTIVO,
                ),
            ),
        )

        # Alumnos (matricula unique)
        a1, _ = Alumno.objects.update_or_create(
            matricula="A0001",
            defaults=_safe_defaults(
                Alumno,
                dict(
                    nombre="Juan Carlos",
                    nombres="Juan Carlos",
                    apellido_paterno="Pérez",
                    apellido_materno="López",
                    correo="juan@ccent.local",
                    telefono="5512345678",
                ),
            ),
        )
        a2, _ = Alumno.objects.update_or_create(
            matricula="A0002",
            defaults=_safe_defaults(
                Alumno,
                dict(
                    nombre="María",
                    nombres="María",
                    apellido_paterno="González",
                    apellido_materno="Rodríguez",
                    correo="maria@ccent.local",
                    telefono="5587654321",
                ),
            ),
        )

        # Inscripciones (UniqueConstraint alumno+grupo)
        i1, _ = Inscripcion.objects.update_or_create(
            alumno=a1,
            grupo=g1,
            defaults=_safe_defaults(
                Inscripcion,
                dict(
                    fecha_inscripcion=timezone.now().date(),
                    estado=getattr(Inscripcion, "ESTADO_ACTIVA", "activa"),
                ),
            ),
        )
        i2, _ = Inscripcion.objects.update_or_create(
            alumno=a2,
            grupo=g2,
            defaults=_safe_defaults(
                Inscripcion,
                dict(
                    fecha_inscripcion=timezone.now().date(),
                    estado=getattr(Inscripcion, "ESTADO_ACTIVA", "activa"),
                ),
            ),
        )

        # Calificaciones (si existe el modelo)
        if Calificacion:
            for insc in (i1, i2):
                Calificacion.objects.update_or_create(
                    inscripcion=insc,
                    defaults=_safe_defaults(
                        Calificacion,
                        dict(
                            valor=9,
                            capturado_en=timezone.now(),
                        ),
                    ),
                )

        # Acta de cierre (si existe el modelo)
        if ActaCierre:
            User = get_user_model()
            cerrador = User.objects.filter(username="director_escolar").first(
            ) or User.objects.order_by("id").first()
            if cerrador:
                ActaCierre.objects.update_or_create(
                    grupo=g1,
                    defaults=_safe_defaults(
                        ActaCierre,
                        dict(
                            cerrada_en=timezone.now(),
                            cerrada_por=cerrador,
                            motivo="Cierre de acta semilla para evidencias de pruebas.",
                        ),
                    ),
                )

        self.stdout.write(self.style.SUCCESS("Escolar semilla OK."))

    def _seed_sales(self):
        # Se intenta localizar modelos por nombres probables para no romper si difieren.
        Concepto = _get_model("sales", ["Concepto"])
        Orden = _get_model("sales", ["OrdenPOS", "OrdenPos", "Orden"])
        OrdenItem = _get_model(
            "sales", ["OrdenItem", "OrdenItemPos", "OrdenItemPOS", "Item"])
        Pago = _get_model("sales", ["Pago"])
        Ticket = _get_model("sales", ["Ticket"])

        if not all([Concepto, Orden, OrdenItem, Pago, Ticket]):
            self.stdout.write(
                self.style.WARNING(
                    "Ventas: no se sembró porque faltan modelos o sus nombres difieren. "
                    "Se ajusta seed_ccent.py cuando se confirme el modelo real."
                )
            )
            return

        Inscripcion = apps.get_model("school", "Inscripcion")
        insc = Inscripcion.objects.order_by("id").first()
        if not insc:
            self.stdout.write(self.style.WARNING(
                "Ventas: no hay Inscripcion para asociar Orden."))
            return

        c1, _ = Concepto.objects.update_or_create(
            nombre="Mensualidad",
            defaults=_safe_defaults(Concepto, dict(
                precio=Decimal("1200.00"), activo=1)),
        )
        c2, _ = Concepto.objects.update_or_create(
            nombre="Material",
            defaults=_safe_defaults(Concepto, dict(
                precio=Decimal("350.00"), activo=1)),
        )

        # Productos de electrónica / herramientas (10 items, precio <= $1000 MXN)
        Existencia = _get_model("sales", ["Existencia"])
        _productos_electronica = [
            ("Multímetro digital",                  Decimal(
                "289.00"),  True,  Decimal("15"), Decimal("3")),
            ("Soldador de estaño 40W",               Decimal(
                "199.00"),  True,  Decimal("20"), Decimal("5")),
            ("Osciloscopio portátil básico",          Decimal(
                "999.00"),  True,  Decimal("5"),  Decimal("1")),
            ("Kit resistencias surtidas 100 pcs",    Decimal(
                "85.00"),   True,  Decimal("30"), Decimal("5")),
            ("Kit capacitores surtidos 100 pcs",     Decimal(
                "95.00"),   True,  Decimal("30"), Decimal("5")),
            ("Fuente de poder regulable 30V/5A",
             Decimal("950.00"),  False, Decimal("0"),  Decimal("0")),
            ("Cautín de punta fina",                 Decimal(
                "149.00"),  False, Decimal("0"),  Decimal("0")),
            ("Pinzas de punta para electrónica",     Decimal(
                "75.00"),   False, Decimal("0"),  Decimal("0")),
            ("Protoboard 830 puntos",                Decimal(
                "120.00"),  False, Decimal("0"),  Decimal("0")),
            ("Kit LED surtido 100 pcs",              Decimal(
                "65.00"),   False, Decimal("0"),  Decimal("0")),
        ]
        for _nom, _precio, _inv_habilitado, _stock, _min in _productos_electronica:
            _prod, _ = Concepto.objects.update_or_create(
                nombre=_nom,
                defaults=_safe_defaults(
                    Concepto, dict(precio=_precio, activo=True)),
            )
            if Existencia:
                Existencia.objects.update_or_create(
                    concepto=_prod,
                    defaults=_safe_defaults(
                        Existencia,
                        dict(
                            inventario_habilitado=_inv_habilitado,
                            stock_actual=_stock,
                            stock_minimo=_min,
                        ),
                    ),
                )
        self.stdout.write(self.style.SUCCESS(
            "Productos de electrónica OK (10 items: con stock y sin stock)."))

        orden_lookup = _safe_defaults(Orden, dict(inscripcion=insc))
        if not orden_lookup:
            self.stdout.write(self.style.WARNING(
                "Ventas: el modelo Orden no tiene campos esperados (inscripcion)."))
            return

        orden_defaults = _safe_defaults(
            Orden,
            dict(
                estado="pendiente",
                fecha_emision=timezone.now(),
            ),
        )
        orden, _ = Orden.objects.update_or_create(
            **orden_lookup, defaults=orden_defaults)

        OrdenItem.objects.update_or_create(
            orden=orden,
            concepto=c1,
            defaults=_safe_defaults(
                OrdenItem, dict(cantidad=1, precio_unit=Decimal("1200.00"))
            ),
        )
        OrdenItem.objects.update_or_create(
            orden=orden,
            concepto=c2,
            defaults=_safe_defaults(
                OrdenItem, dict(cantidad=1, precio_unit=Decimal("350.00"))
            ),
        )

        pago = Pago.objects.create(
            **_safe_defaults(
                Pago,
                dict(
                    orden=orden,
                    fecha_pago=timezone.now(),
                    monto=Decimal("1550.00"),
                    metodo="efectivo",
                    auth_code="DEV-OK",
                ),
            )
        )

        Ticket.objects.update_or_create(
            pago=pago,
            defaults=_safe_defaults(Ticket, dict(
                ruta_pdf="tickets/DEV-ticket.pdf", generado_en=timezone.now())),
        )

        self._seed_security_params()
        self.stdout.write(self.style.SUCCESS("Ventas semilla OK."))

    def _seed_security_params(self):
        """Siembra parámetros de seguridad: timeout de sesión 15 min y 3 intentos de login."""
        try:
            ParametroSistema = apps.get_model("governance", "ParametroSistema")
        except LookupError:
            self.stdout.write(self.style.WARNING(
                "governance app no disponible — parámetros de seguridad omitidos."))
            return

        _params = [
            # (clave, valor, categoria)
            ("security_idle_timeout_seconds",  "900", "SEGURIDAD"),   # 15 min
            ("security_max_attempts",           "3",   "SEGURIDAD"),   # 3 intentos
            ("security_lockout_seconds",        "900",
             "SEGURIDAD"),   # bloqueo 15 min
            ("security_attempt_window_seconds",
             "900", "SEGURIDAD"),   # ventana 15 min
        ]
        for clave, valor, categoria in _params:
            ParametroSistema.objects.update_or_create(
                clave=clave,
                defaults={"categoria": categoria,
                          "valor": valor, "activo": True},
            )
        self.stdout.write(self.style.SUCCESS(
            "Parámetros de seguridad OK (timeout=15 min, max_intentos=3)."))
