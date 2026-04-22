from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.sales.models import Concepto, CorteCaja, OrdenPOS, Pago
from apps.school.models import Alumno, Grupo, Inscripcion


class ReporteComercialHU045Tests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
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

    def _crear_orden_con_pago(self, sufijo, periodo, estado, monto, fecha_corte):
        alumno = Alumno.objects.create(
            matricula=f"M-HU045-{sufijo}",
            nombres=f"Alumno {sufijo}",
            apellido_paterno="Demo",
            correo=f"hu045_{sufijo}@test.local",
        )
        grupo = Grupo.objects.create(
            curso_slug=f"curso-hu045-{sufijo}",
            periodo=periodo,
            tipo_horario=Grupo.HORARIO_SEM,
            cupo=30,
            estado=Grupo.ESTADO_ACTIVO,
        )
        inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        concepto = Concepto.objects.create(
            nombre=f"Concepto HU045 {sufijo}",
            precio=Decimal(monto),
            activo=True,
        )
        orden = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=estado,
        )
        orden.items.create(concepto=concepto, cantidad=1,
                           precio_unit=Decimal(monto))
        Pago.objects.create(
            orden=orden,
            monto=Decimal(monto),
            metodo="EFECTIVO",
        )
        CorteCaja.objects.create(
            fecha_operacion=fecha_corte,
            total_ordenes=1,
            total_pagos=1,
            notas=f"Corte {periodo}",
        )
        return orden

    def test_comercial_filtra_reporte_por_periodo_y_muestra_cortes(self):
        comercial = self._user_with_role("comercial_hu045", self.rol_comercial)
        self._crear_orden_con_pago(
            "001", "2026-01", OrdenPOS.ESTADO_PAGADA, "1200.00", "2026-01-30"
        )
        self._crear_orden_con_pago(
            "002", "2026-02", OrdenPOS.ESTADO_PENDIENTE, "700.00", "2026-02-28"
        )

        self.client.force_login(comercial)
        response = self.client.get(
            "/panel/reportes/comercial/?periodo=2026-01")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ventas por per")
        self.assertContains(response, "Cortes de caja")

        self.assertEqual(response.context["periodo_activo"], "2026-01")
        self.assertEqual(response.context["kpi"]["ordenes_pos"], 1)
        self.assertEqual(response.context["kpi"]["pagos"], 1)
        self.assertEqual(response.context["kpi"]
                         ["ventas_periodo_total"], "1200.00")
        self.assertEqual(response.context["kpi"]
                         ["pagos_periodo_total"], "1200.00")
        self.assertEqual(response.context["kpi"]["cortes_periodo"], 1)

        ordenes = list(response.context["ordenes"])
        self.assertEqual(len(ordenes), 1)
        self.assertEqual(ordenes[0].periodo, "2026-01")

        pagos = list(response.context["pagos"])
        self.assertEqual(len(pagos), 1)
        self.assertEqual(pagos[0].orden.periodo, "2026-01")

        ventas_por_periodo = list(response.context["ventas_por_periodo"])
        self.assertEqual(len(ventas_por_periodo), 1)
        self.assertEqual(ventas_por_periodo[0]["periodo"], "2026-01")

        cortes = list(response.context["cortes_caja"])
        self.assertEqual(len(cortes), 1)
        self.assertEqual(str(cortes[0].fecha_operacion), "2026-01-30")

    def test_alumno_no_puede_acceder_reporte_comercial(self):
        alumno = self._user_with_role("alumno_hu045", self.rol_alumno)
        self.client.force_login(alumno)

        response = self.client.get("/panel/reportes/comercial/")

        self.assertEqual(response.status_code, 403)
