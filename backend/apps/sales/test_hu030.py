from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.sales.models import Concepto, OrdenPOS, Pago, Ticket
from apps.school.models import Alumno, Grupo, Inscripcion


class VentasPosRegistroTicketTests(TestCase):
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

    def _comercial_user(self, username="comercial_hu030"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_comercial)
        return user

    def _inscripcion(self, matricula="MAT-HU030-001", correo="hu030_1@test.local", periodo="2027-06"):
        alumno = Alumno.objects.create(
            matricula=matricula,
            nombres="Lia",
            apellido_paterno="Ortiz",
            apellido_materno="Rios",
            correo=correo,
            telefono="5553001",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu030",
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

    def test_admin_comercial_can_register_pos_sale_and_emit_ticket(self):
        user = self._comercial_user()
        inscripcion = self._inscripcion()
        concepto = Concepto.objects.create(
            nombre="Colegiatura Junio",
            precio=Decimal("1200.00"),
            activo=True,
        )
        self.client.force_login(user)

        response = self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(inscripcion.pk),
                "concepto_id": str(concepto.pk),
                "cantidad": "2",
                "metodo": "EFECTIVO",
            },
        )

        self.assertEqual(response.status_code, 302)
        orden = OrdenPOS.objects.get(inscripcion=inscripcion)
        self.assertEqual(orden.total_calculado, Decimal("2400.00"))
        self.assertEqual(orden.estado, OrdenPOS.ESTADO_PAGADA)

        pago = Pago.objects.get(orden=orden)
        self.assertEqual(pago.monto, Decimal("2400.00"))
        self.assertEqual(pago.metodo, "EFECTIVO")

        ticket = Ticket.objects.get(pago=pago)
        self.assertIn(str(pago.pk), ticket.ruta_pdf)

        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="VENTAS::ORDEN_CREATE",
                entidad="OrdenPOS",
                entidad_id=str(orden.pk),
                detalle__monto="2400.00",
            ).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="VENTAS::TICKET_EMIT",
                entidad="Ticket",
                entidad_id=str(ticket.pk),
                detalle__orden=orden.pk,
            ).exists()
        )

    def test_no_duplicate_order_for_same_inscripcion_periodo(self):
        user = self._comercial_user("comercial_hu030_dup")
        inscripcion = self._inscripcion(
            "MAT-HU030-002", "hu030_2@test.local", "2027-07")
        concepto = Concepto.objects.create(
            nombre="Material Verano",
            precio=Decimal("300.00"),
            activo=True,
        )
        self.client.force_login(user)

        first = self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(inscripcion.pk),
                "concepto_id": str(concepto.pk),
                "cantidad": "1",
            },
        )
        self.assertEqual(first.status_code, 302)

        second = self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(inscripcion.pk),
                "concepto_id": str(concepto.pk),
                "cantidad": "1",
            },
        )

        self.assertEqual(second.status_code, 302)
        self.assertEqual(
            OrdenPOS.objects.filter(
                inscripcion=inscripcion,
            ).count(),
            1,
        )

    def test_usuario_sin_rol_comercial_recibe_403_en_pos(self):
        user = self.user_model.objects.create_user(
            username="alumno_hu030",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_alumno)
        self.client.force_login(user)

        response = self.client.get("/panel/ventas/pos/")

        self.assertEqual(response.status_code, 403)


# PCB-016 / MOD-05 / HU-030 – Registro de venta POS a alumno y emisión de ticket
class PCB016VentaPosTicketTests(TestCase):
    """PCB-016 / MOD-05 / HU-030 – Registro de venta POS a alumno y emisión de ticket.

    Verifica que un Administrativo Comercial registra una venta POS a un alumno,
    el total se calcula correctamente, el ticket queda persistido en BD y la
    página del ticket es accesible con HTTP 200.
    """

    def setUp(self):
        User = get_user_model()
        self.rol_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )
        self.comercial = User.objects.create_user(
            username="pcb016_comercial",
            password="testpass123",
        )
        UsuarioRol.objects.create(
            usuario=self.comercial, rol=self.rol_comercial)

        alumno = Alumno.objects.create(
            matricula="MAT-PCB016-001",
            nombres="Laura",
            apellido_paterno="Vega",
            apellido_materno="Salinas",
            correo="pcb016_alumno@test.local",
            telefono="5550016",
        )
        grupo = Grupo.objects.create(
            curso_slug="pcb016-curso",
            periodo="2026-05",
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=25,
            estado=Grupo.ESTADO_ACTIVO,
        )
        self.inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        self.concepto = Concepto.objects.create(
            nombre="PCB016 Inscripcion Mayo",
            precio=Decimal("800.00"),
            activo=True,
        )

    def test_registro_venta_pos_genera_ticket_accesible(self):
        self.client.force_login(self.comercial)

        # Registro de venta: POST al POS
        post_response = self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(self.inscripcion.pk),
                "concepto_id": str(self.concepto.pk),
                "cantidad": "1",
                "metodo": "EFECTIVO",
            },
        )

        # Vista redirige al ticket tras operación exitosa
        self.assertEqual(post_response.status_code, 302)

        # Orden y total calculado correctamente
        orden = OrdenPOS.objects.get(inscripcion=self.inscripcion)
        self.assertEqual(orden.total_calculado, Decimal("800.00"))

        # Pago persistido con monto y método correctos
        pago = Pago.objects.get(orden=orden)
        self.assertEqual(pago.monto, Decimal("800.00"))
        self.assertEqual(pago.metodo, "EFECTIVO")

        # Ticket registrado en BD con ruta lógica referenciando el pago
        ticket = Ticket.objects.get(pago=pago)
        self.assertIn(str(pago.pk), ticket.ruta_pdf)

        # Página del ticket accesible mediante GET
        ticket_response = self.client.get(f"/panel/ventas/ticket/{ticket.pk}/")
        self.assertEqual(ticket_response.status_code, 200)
        # El ticket se sirve como HTML (vista de comprobante, no PDF binario)
        self.assertIn("text/html", ticket_response.get("Content-Type", ""))


# ---------------------------------------------------------------------------
# HU-030 — Ticket: content-type y acceso cuando alumno no tiene orden previa
# ---------------------------------------------------------------------------

class TicketContentTypeAndNoOrdenTests(TestCase):
    """HU-030 — Verifica el content-type HTML del ticket y el comportamiento
    cuando se intenta acceder a un ticket inexistente."""

    def setUp(self):
        User = get_user_model()
        self.rol_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )
        self.comercial = User.objects.create_user(
            username="hu030_ticket_ct",
            password="testpass123",
        )
        UsuarioRol.objects.create(
            usuario=self.comercial, rol=self.rol_comercial)

        alumno = Alumno.objects.create(
            matricula="MAT-HU030-CT-001",
            nombres="Marco",
            apellido_paterno="Rios",
            apellido_materno="Soto",
            correo="marco.rios.ct@test.local",
            telefono="5550030",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu030-ct",
            periodo="2028-01",
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=20,
            estado=Grupo.ESTADO_ACTIVO,
        )
        self.inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        self.concepto = Concepto.objects.create(
            nombre="PCB030 CT Enero",
            precio=Decimal("500.00"),
            activo=True,
        )

    def test_ticket_view_returns_html_content_type(self):
        """La vista GET /panel/ventas/ticket/<pk>/ retorna text/html (comprobante web, no PDF)."""
        self.client.force_login(self.comercial)

        self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(self.inscripcion.pk),
                "concepto_id": str(self.concepto.pk),
                "cantidad": "1",
                "metodo": "EFECTIVO",
            },
        )
        ticket = Ticket.objects.get(pago__orden__inscripcion=self.inscripcion)
        response = self.client.get(f"/panel/ventas/ticket/{ticket.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.get("Content-Type", ""))

    def test_ticket_inexistente_redirige_sin_error_500(self):
        """Acceder a un ticket_id que no existe devuelve redirect, nunca 500."""
        self.client.force_login(self.comercial)

        response = self.client.get("/panel/ventas/ticket/999999/")

        # La vista redirige al estado de cuenta con mensaje de error controlado
        self.assertEqual(response.status_code, 302)
        self.assertIn("/panel/ventas/", response["Location"])
