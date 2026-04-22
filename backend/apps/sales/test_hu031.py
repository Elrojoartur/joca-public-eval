from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.sales.models import Concepto, OrdenPOS, Pago
from apps.school.models import Alumno, Grupo, Inscripcion


class PagosEstadoCuentaFlowTests(TestCase):
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

    def _comercial_user(self, username="comercial_hu031"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_comercial)
        return user

    def _orden(self, matricula="MAT-HU031-001", correo="hu031_1@test.local", periodo="2027-08", monto="1800.00"):
        alumno = Alumno.objects.create(
            matricula=matricula,
            nombres="Mia",
            apellido_paterno="Nunez",
            apellido_materno="Diaz",
            correo=correo,
            telefono="5553101",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu031",
            periodo=periodo,
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=30,
            estado=Grupo.ESTADO_ACTIVO,
        )
        inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        orden = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=OrdenPOS.ESTADO_PENDIENTE,
        )
        concepto = Concepto.objects.create(
            nombre=f"Concepto {matricula}",
            precio=Decimal(monto),
            activo=True,
        )
        orden.items.create(
            concepto=concepto,
            cantidad=1,
            precio_unit=Decimal(monto),
        )
        return orden

    def test_admin_comercial_can_register_pago_and_update_estado_cuenta(self):
        user = self._comercial_user()
        orden = self._orden()
        self.client.force_login(user)

        first = self.client.post(
            "/panel/ventas/estado-cuenta/",
            {
                "orden_id": str(orden.pk),
                "monto": "800.00",
                "metodo": "EFECTIVO",
            },
        )
        self.assertEqual(first.status_code, 302)

        orden.refresh_from_db()
        self.assertEqual(orden.estado, OrdenPOS.ESTADO_PARCIAL)
        self.assertEqual(Pago.objects.filter(orden=orden).count(), 1)

        second = self.client.post(
            "/panel/ventas/estado-cuenta/",
            {
                "orden_id": str(orden.pk),
                "monto": "1000.00",
                "metodo": "TARJETA",
                "auth_code": "AUTH-123",
            },
        )
        self.assertEqual(second.status_code, 302)

        orden.refresh_from_db()
        self.assertEqual(orden.estado, OrdenPOS.ESTADO_PAGADA)
        total_pagado = sum(p.monto for p in Pago.objects.filter(orden=orden))
        self.assertEqual(total_pagado, Decimal("1800.00"))
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="VENTAS::PAGO_CREATE",
                entidad="Pago",
                detalle__orden=orden.pk,
            ).exists()
        )

    def test_no_permite_pago_mayor_al_saldo(self):
        user = self._comercial_user("comercial_hu031_saldo")
        orden = self._orden(
            "MAT-HU031-002", "hu031_2@test.local", "2027-09", "1000.00")
        self.client.force_login(user)

        response = self.client.post(
            "/panel/ventas/estado-cuenta/",
            {
                "orden_id": str(orden.pk),
                "monto": "1200.00",
                "metodo": "EFECTIVO",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Pago.objects.filter(orden=orden).count(), 0)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, OrdenPOS.ESTADO_PENDIENTE)

    def test_usuario_sin_rol_comercial_recibe_403_en_estado_cuenta(self):
        user = self.user_model.objects.create_user(
            username="alumno_hu031",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_alumno)
        self.client.force_login(user)

        response = self.client.get("/panel/ventas/estado-cuenta/")

        self.assertEqual(response.status_code, 403)


# PCB-017 / MOD-05 / HU-031 – Registro de pagos y consulta de estado de cuenta
class PCB017PagoEstadoCuentaTests(TestCase):
    """PCB-017 / MOD-05 / HU-031 – Registro de pagos y consulta de estado de cuenta.

    Verifica que un Administrativo Comercial registra un pago parcial sobre
    una orden existente, que el estado de la orden se actualiza a PARCIAL,
    el pago queda persistido en BD y la vista de estado de cuenta responde
    HTTP 200 con la información de la orden.
    """

    def setUp(self):
        User = get_user_model()
        self.rol_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )
        self.comercial = User.objects.create_user(
            username="pcb017_comercial",
            password="testpass123",
        )
        UsuarioRol.objects.create(
            usuario=self.comercial, rol=self.rol_comercial)

        alumno = Alumno.objects.create(
            matricula="MAT-PCB017-001",
            nombres="Sofia",
            apellido_paterno="Ibarra",
            apellido_materno="Cruz",
            correo="pcb017_alumno@test.local",
            telefono="5550017",
        )
        grupo = Grupo.objects.create(
            curso_slug="pcb017-curso",
            periodo="2026-07",
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=20,
            estado=Grupo.ESTADO_ACTIVO,
        )
        inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        self.orden = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=OrdenPOS.ESTADO_PENDIENTE,
        )
        concepto = Concepto.objects.create(
            nombre="PCB017 Colegiatura Julio",
            precio=Decimal("1500.00"),
            activo=True,
        )
        self.orden.items.create(
            concepto=concepto,
            cantidad=1,
            precio_unit=Decimal("1500.00"),
        )

    def test_pago_parcial_actualiza_estado_y_queda_en_estado_cuenta(self):
        self.client.force_login(self.comercial)

        # Registro de pago parcial
        post_response = self.client.post(
            "/panel/ventas/estado-cuenta/",
            {
                "orden_id": str(self.orden.pk),
                "monto": "600.00",
                "metodo": "EFECTIVO",
            },
        )

        # Vista redirige tras registrar el pago
        self.assertEqual(post_response.status_code, 302)

        # Estado de la orden actualizado a PARCIAL
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, OrdenPOS.ESTADO_PARCIAL)

        # Pago persistido con monto y método correctos
        pago = Pago.objects.get(orden=self.orden)
        self.assertEqual(pago.monto, Decimal("600.00"))
        self.assertEqual(pago.metodo, "EFECTIVO")

        # Consulta de estado de cuenta: GET responde 200
        get_response = self.client.get("/panel/ventas/estado-cuenta/")
        self.assertEqual(get_response.status_code, 200)


# ---------------------------------------------------------------------------
# HU-031 — Estado de cuenta con múltiples pagos parciales
# ---------------------------------------------------------------------------

class EstadoCuentaMultiplesPagosParcialesTests(TestCase):
    """HU-031 — Verifica que múltiples pagos parciales acumulan correctamente
    hasta liquidad la orden completa, actualizando su estado en cada paso."""

    def setUp(self):
        User = get_user_model()
        self.rol_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )
        self.comercial = User.objects.create_user(
            username="hu031_multipago",
            password="testpass123",
        )
        UsuarioRol.objects.create(
            usuario=self.comercial, rol=self.rol_comercial)

        alumno = Alumno.objects.create(
            matricula="MAT-HU031-MP-001",
            nombres="Carmen",
            apellido_paterno="Delgado",
            apellido_materno="Cruz",
            correo="carmen.delgado.mp@test.local",
            telefono="5550031",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu031-mp",
            periodo="2028-03",
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=20,
            estado=Grupo.ESTADO_ACTIVO,
        )
        inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        self.orden = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=OrdenPOS.ESTADO_PENDIENTE,
        )
        concepto = Concepto.objects.create(
            nombre="HU031-MP Colegiatura",
            precio=Decimal("3000.00"),
            activo=True,
        )
        self.orden.items.create(
            concepto=concepto,
            cantidad=1,
            precio_unit=Decimal("3000.00"),
        )

    def test_tres_pagos_parciales_liquidan_la_orden(self):
        """Tres pagos parciales (1000+1000+1000) deben dejar la orden en PAGADA."""
        self.client.force_login(self.comercial)

        # Primer pago parcial
        r1 = self.client.post(
            "/panel/ventas/estado-cuenta/",
            {"orden_id": str(self.orden.pk), "monto": "1000.00",
             "metodo": "EFECTIVO"},
        )
        self.assertEqual(r1.status_code, 302)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, OrdenPOS.ESTADO_PARCIAL)

        # Segundo pago parcial
        r2 = self.client.post(
            "/panel/ventas/estado-cuenta/",
            {"orden_id": str(self.orden.pk), "monto": "1000.00",
             "metodo": "TARJETA"},
        )
        self.assertEqual(r2.status_code, 302)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, OrdenPOS.ESTADO_PARCIAL)

        # Tercer pago: liquida el saldo restante
        r3 = self.client.post(
            "/panel/ventas/estado-cuenta/",
            {"orden_id": str(self.orden.pk), "monto": "1000.00",
             "metodo": "TRANSFERENCIA"},
        )
        self.assertEqual(r3.status_code, 302)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, OrdenPOS.ESTADO_PAGADA)

        # Total acumulado igual al importe de la orden
        total_pagado = sum(
            p.monto for p in Pago.objects.filter(orden=self.orden))
        self.assertEqual(total_pagado, Decimal("3000.00"))
        self.assertEqual(Pago.objects.filter(orden=self.orden).count(), 3)
