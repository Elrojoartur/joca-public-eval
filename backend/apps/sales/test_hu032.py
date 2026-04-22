from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Rol, UsuarioRol
from apps.sales.models import Concepto, OrdenPOS, Pago
from apps.school.models import Alumno, Grupo, Inscripcion


class IndicadoresVentasDelDiaTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )

    def _comercial_user(self, username="comercial_hu032"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_comercial)
        return user

    def _inscripcion(self, matricula="MAT-HU032-001", correo="hu032_1@test.local", periodo="2027-10"):
        alumno = Alumno.objects.create(
            matricula=matricula,
            nombres="Leo",
            apellido_paterno="Mora",
            apellido_materno="Diaz",
            correo=correo,
            telefono="5553201",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu032",
            periodo=periodo,
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=30,
            estado=Grupo.ESTADO_ACTIVO,
        )
        return Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )

    def test_home_muestra_indicadores_de_ventas_del_dia(self):
        user = self._comercial_user()
        inscripcion = self._inscripcion()
        self.client.force_login(user)

        now = timezone.now()
        orden = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=OrdenPOS.ESTADO_PAGADA,
            fecha_emision=now,
        )
        concepto = Concepto.objects.create(
            nombre="Concepto HU032 hoy",
            precio=Decimal("1500.00"),
            activo=True,
        )
        orden.items.create(concepto=concepto, cantidad=1,
                           precio_unit=Decimal("1500.00"))
        Pago.objects.create(
            orden=orden,
            monto=Decimal("1200.00"),
            metodo="EFECTIVO",
            fecha_pago=now,
        )

        response = self.client.get("/panel/ventas/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Órdenes del día")
        self.assertContains(response, "Venta del día")
        self.assertContains(response, "Cobranza del día")
        self.assertContains(response, "1500.00")
        self.assertContains(response, "1200.00")

    def test_indicadores_excluyen_ventas_de_otros_dias(self):
        user = self._comercial_user("comercial_hu032_old")
        inscripcion = self._inscripcion(
            "MAT-HU032-002", "hu032_2@test.local", "2027-11")
        self.client.force_login(user)

        old_date = timezone.now() - timedelta(days=1)
        orden = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=OrdenPOS.ESTADO_PAGADA,
            fecha_emision=old_date,
        )
        concepto = Concepto.objects.create(
            nombre="Concepto HU032 old",
            precio=Decimal("999.00"),
            activo=True,
        )
        orden.items.create(concepto=concepto, cantidad=1,
                           precio_unit=Decimal("999.00"))
        Pago.objects.create(
            orden=orden,
            monto=Decimal("999.00"),
            metodo="EFECTIVO",
            fecha_pago=old_date,
        )

        response = self.client.get("/panel/ventas/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0.00")

    def test_usuario_sin_rol_ventas_no_accede_a_home_ventas(self):
        user = self.user_model.objects.create_user(
            username="sin_rol_hu032",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.get("/panel/ventas/")

        self.assertEqual(response.status_code, 403)


# PCB-018 / MOD-05 / HU-032 – Visualización de indicadores de ventas del día
class PCB018IndicadoresVentasTests(TestCase):
    """PCB-018 / MOD-05 / HU-032 – Visualización de indicadores de ventas del día.

    Verifica que la vista principal de ventas calcula y muestra correctamente
    los indicadores del día: total de ventas y cobranza, tomando solo las
    operaciones registradas en la fecha actual.
    """

    def setUp(self):
        User = get_user_model()
        self.rol_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )
        self.comercial = User.objects.create_user(
            username="pcb018_comercial",
            password="testpass123",
        )
        UsuarioRol.objects.create(
            usuario=self.comercial, rol=self.rol_comercial)

        alumno = Alumno.objects.create(
            matricula="MAT-PCB018-001",
            nombres="Elena",
            apellido_paterno="Torres",
            apellido_materno="Gil",
            correo="pcb018_alumno@test.local",
            telefono="5550018",
        )
        grupo = Grupo.objects.create(
            curso_slug="pcb018-curso",
            periodo="2026-08",
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=20,
            estado=Grupo.ESTADO_ACTIVO,
        )
        inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )

        now = timezone.now()
        self.orden = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=OrdenPOS.ESTADO_PAGADA,
            fecha_emision=now,
        )
        concepto = Concepto.objects.create(
            nombre="PCB018 Inscripcion Agosto",
            precio=Decimal("2000.00"),
            activo=True,
        )
        self.orden.items.create(
            concepto=concepto,
            cantidad=1,
            precio_unit=Decimal("2000.00"),
        )
        Pago.objects.create(
            orden=self.orden,
            monto=Decimal("2000.00"),
            metodo="EFECTIVO",
            fecha_pago=now,
        )

    def test_home_ventas_muestra_indicadores_del_dia_correctos(self):
        self.client.force_login(self.comercial)

        response = self.client.get("/panel/ventas/")

        self.assertEqual(response.status_code, 200)

        # Indicadores de venta del día presentes en el HTML
        self.assertContains(response, "2000.00")   # total_ventas_hoy
        self.assertContains(response, "Órdenes del día")
        self.assertContains(response, "Venta del día")


# ---------------------------------------------------------------------------
# HU-032 — KPIs con datos de diferentes días: solo hoy debe sumar
# ---------------------------------------------------------------------------

class KPIsDiasDistintosTests(TestCase):
    """HU-032 — Crea órdenes/pagos de HOY y de AYER simultáneamente y verifica
    que los indicadores del home de ventas solo suman los de la fecha actual."""

    def setUp(self):
        User = get_user_model()
        self.rol_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )
        self.comercial = User.objects.create_user(
            username="hu032_multidiia",
            password="testpass123",
        )
        UsuarioRol.objects.create(
            usuario=self.comercial, rol=self.rol_comercial)

    def _crear_inscripcion(self, matricula, correo, periodo):
        alumno = Alumno.objects.create(
            matricula=matricula,
            nombres="Test",
            apellido_paterno="KPI",
            apellido_materno="Dias",
            correo=correo,
            telefono="5550032",
        )
        grupo = Grupo.objects.create(
            curso_slug=f"curso-kpi-{matricula[-3:]}",
            periodo=periodo,
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=20,
            estado=Grupo.ESTADO_ACTIVO,
        )
        return Inscripcion.objects.create(
            alumno=alumno, grupo=grupo, estado=Inscripcion.ESTADO_ACTIVA)

    def test_kpis_solo_suman_ventas_y_pagos_de_hoy(self):
        """Con una orden de hoy (1500) y una de ayer (999), el KPI muestra 1500 solo."""
        now = timezone.now()
        yesterday = now - timedelta(days=1)

        # Orden de HOY
        insc_hoy = self._crear_inscripcion(
            "MAT-KPIMD-HOY", "kpi.hoy@test.local", "2028-04")
        orden_hoy = OrdenPOS.objects.create(
            inscripcion=insc_hoy,
            estado=OrdenPOS.ESTADO_PAGADA,
            fecha_emision=now,
        )
        concepto_hoy = Concepto.objects.create(
            nombre="KPI Hoy", precio=Decimal("1500.00"), activo=True)
        orden_hoy.items.create(
            concepto=concepto_hoy, cantidad=1, precio_unit=Decimal("1500.00"))
        Pago.objects.create(
            orden=orden_hoy, monto=Decimal("1500.00"),
            metodo="EFECTIVO", fecha_pago=now)

        # Orden de AYER (no debe contar en KPIs de hoy)
        insc_ayer = self._crear_inscripcion(
            "MAT-KPIMD-AYR", "kpi.ayer@test.local", "2028-05")
        orden_ayer = OrdenPOS.objects.create(
            inscripcion=insc_ayer,
            estado=OrdenPOS.ESTADO_PAGADA,
            fecha_emision=yesterday,
        )
        concepto_ayer = Concepto.objects.create(
            nombre="KPI Ayer", precio=Decimal("999.00"), activo=True)
        orden_ayer.items.create(
            concepto=concepto_ayer, cantidad=1, precio_unit=Decimal("999.00"))
        Pago.objects.create(
            orden=orden_ayer, monto=Decimal("999.00"),
            metodo="EFECTIVO", fecha_pago=yesterday)

        self.client.force_login(self.comercial)
        response = self.client.get("/panel/ventas/")

        self.assertEqual(response.status_code, 200)
        # La venta de hoy aparece
        self.assertContains(response, "1500.00")
        # La venta de ayer NO aparece en los indicadores del día
        self.assertNotContains(response, "999.00")
