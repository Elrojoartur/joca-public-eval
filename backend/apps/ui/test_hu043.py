from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Rol, UsuarioRol
from apps.school.models import Alumno, Grupo, Inscripcion
from apps.sales.models import AlertaStock, Concepto, Existencia, OrdenPOS, Pago


class TableroEjecutivoHU043Tests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.rol_alumno = Rol.objects.create(
            nombre="Alumno",
            codigo="ALUMNO",
            activo=True,
        )

    def _user_with_role(self, username, role):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=role)
        return user

    def _crear_inscripcion(self):
        alumno = Alumno.objects.create(
            matricula="A-043-001",
            nombres="Ada",
            apellido_paterno="Lovelace",
            correo="ada043@test.local",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-demo",
            periodo="2026-03",
            tipo_horario=Grupo.HORARIO_SEM,
            cupo=30,
            estado=Grupo.ESTADO_ACTIVO,
        )
        return Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )

    def test_tablero_ejecutivo_muestra_kpis_hu043(self):
        director = self._user_with_role("director_hu043", self.rol_director)
        inscripcion = self._crear_inscripcion()

        concepto = Concepto.objects.create(
            nombre="Colegiatura", precio=Decimal("1000.00"), activo=True)
        existencia = Existencia.objects.create(
            concepto=concepto,
            inventario_habilitado=True,
            stock_actual=Decimal("2.00"),
            stock_minimo=Decimal("5.00"),
        )
        AlertaStock.objects.create(
            existencia=existencia,
            stock_actual=Decimal("2.00"),
            stock_minimo=Decimal("5.00"),
            activa=True,
        )

        orden = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=OrdenPOS.ESTADO_PENDIENTE,
        )
        orden.items.create(
            concepto=concepto,
            cantidad=1,
            precio_unit=Decimal("1000.00"),
        )
        Pago.objects.create(
            orden=orden,
            monto=Decimal("150.00"),
            metodo="efectivo",
            fecha_pago=timezone.now(),
        )

        self.client.force_login(director)
        response = self.client.get("/panel/reportes/ejecutivo/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matricula activa")
        self.assertContains(response, "Ventas del dia")
        self.assertContains(response, "Morosidad")
        self.assertContains(response, "Alertas de inventario")

        kpi = response.context["kpi"]
        self.assertEqual(kpi["matricula_activa"], 1)
        self.assertEqual(kpi["ventas_dia"], "150.00")
        self.assertEqual(kpi["morosidad"], "850.00")
        self.assertEqual(kpi["alertas_inventario"], 2)

    def test_alumno_no_puede_acceder_tablero_ejecutivo(self):
        alumno = self._user_with_role("alumno_hu043", self.rol_alumno)
        self.client.force_login(alumno)

        response = self.client.get("/panel/reportes/ejecutivo/")

        self.assertEqual(response.status_code, 403)


# PCB-019 / MOD-07 / HU-043 – Visualización de tablero ejecutivo
class PCB019TableroEjecutivoTests(TestCase):
    """PCB-019 / MOD-07 / HU-043 – Visualización de tablero ejecutivo.

    Verifica que la vista del tablero ejecutivo responde HTTP 200 para un
    Director Escolar y que los KPIs principales (matrícula activa, ventas
    del día, morosidad y alertas de inventario) se calculan correctamente
    a partir de los datos preparados en el test.
    """

    def setUp(self):
        User = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.director = User.objects.create_user(
            username="pcb019_director",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=self.director, rol=self.rol_director)

        # Inscripcion activa → contribuye a matricula_activa
        alumno = Alumno.objects.create(
            matricula="MAT-PCB019-001",
            nombres="Raul",
            apellido_paterno="Soto",
            correo="pcb019_alumno@test.local",
        )
        grupo = Grupo.objects.create(
            curso_slug="pcb019-curso",
            periodo="2026-09",
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=20,
            estado=Grupo.ESTADO_ACTIVO,
        )
        inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )

        # Concepto + OrdenPOS pendiente → contribuye a morosidad
        concepto = Concepto.objects.create(
            nombre="PCB019 Colegiatura",
            precio=Decimal("1200.00"),
            activo=True,
        )
        orden = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=OrdenPOS.ESTADO_PENDIENTE,
        )
        orden.items.create(
            concepto=concepto,
            cantidad=1,
            precio_unit=Decimal("1200.00"),
        )

        # Pago del día → contribuye a ventas del día
        Pago.objects.create(
            orden=orden,
            monto=Decimal("400.00"),
            metodo="EFECTIVO",
            fecha_pago=timezone.now(),
        )

        # Alerta de stock activa → contribuye a alertas_inventario
        existencia = Existencia.objects.create(
            concepto=concepto,
            inventario_habilitado=True,
            stock_actual=Decimal("1.00"),
            stock_minimo=Decimal("10.00"),
        )
        AlertaStock.objects.create(
            existencia=existencia,
            stock_actual=Decimal("1.00"),
            stock_minimo=Decimal("10.00"),
            activa=True,
        )

    def test_tablero_ejecutivo_accesible_y_kpis_correctos(self):
        self.client.force_login(self.director)

        response = self.client.get("/panel/reportes/ejecutivo/")

        # Vista accesible
        self.assertEqual(response.status_code, 200)

        # Etiquetas de KPIs reales presentes en el HTML
        self.assertContains(response, "Matricula activa")
        self.assertContains(response, "Ventas del dia")
        self.assertContains(response, "Morosidad")
        self.assertContains(response, "Alertas de inventario")

        # Valores del contexto calculados correctamente
        kpi = response.context["kpi"]
        # 1 inscripción activa
        self.assertEqual(kpi["matricula_activa"], 1)
        self.assertEqual(kpi["ventas_dia"], "400.00")      # pago de $400 hoy
        # $1200 - $400 pagado
        self.assertEqual(kpi["morosidad"], "800.00")
        self.assertGreaterEqual(
            kpi["alertas_inventario"], 1)  # ≥1 alerta activa
