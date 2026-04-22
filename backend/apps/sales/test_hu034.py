from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.sales.models import AlertaStock, Concepto, Existencia, OrdenPOS
from apps.school.models import Alumno, Grupo, Inscripcion


class ExistenciasMinimasTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )

    def _comercial_user(self, username="comercial_hu034"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_comercial)
        return user

    def _inscripcion(self, matricula="MAT-HU034-001", correo="hu034_1@test.local", periodo="2028-01"):
        alumno = Alumno.objects.create(
            matricula=matricula,
            nombres="Ariadna",
            apellido_paterno="Luna",
            apellido_materno="Vera",
            correo=correo,
            telefono="5553401",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu034",
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

    def test_genera_alerta_cuando_stock_llega_a_minimo(self):
        comercial = self._comercial_user()
        inscripcion = self._inscripcion()
        concepto = Concepto.objects.create(
            nombre="Material HU034",
            precio=Decimal("120.00"),
            activo=True,
        )
        existencia = Existencia.objects.create(
            concepto=concepto,
            inventario_habilitado=True,
            stock_actual=Decimal("2.00"),
            stock_minimo=Decimal("1.00"),
        )
        self.client.force_login(comercial)

        response = self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(inscripcion.pk),
                "concepto_id": str(concepto.pk),
                "cantidad": "1",
                "metodo": "EFECTIVO",
            },
        )

        self.assertEqual(response.status_code, 302)
        existencia.refresh_from_db()
        self.assertEqual(existencia.stock_actual, Decimal("1.00"))
        self.assertTrue(
            AlertaStock.objects.filter(
                existencia__concepto=concepto,
                activa=True,
                stock_actual=Decimal("1.00"),
                stock_minimo=Decimal("1.00"),
            ).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="INVENTARIO::STOCK_MINIMO_ALERTA",
                detalle__concepto=concepto.nombre,
                detalle__stock_actual="1.00",
                detalle__stock_minimo="1.00",
            ).exists()
        )

    def test_rechaza_venta_si_stock_insuficiente(self):
        comercial = self._comercial_user("comercial_hu034_short")
        inscripcion = self._inscripcion("MAT-HU034-002", "hu034_2@test.local")
        concepto = Concepto.objects.create(
            nombre="Servicio HU034",
            precio=Decimal("250.00"),
            activo=True,
        )
        existencia = Existencia.objects.create(
            concepto=concepto,
            inventario_habilitado=True,
            stock_actual=Decimal("1.00"),
            stock_minimo=Decimal("1.00"),
        )
        self.client.force_login(comercial)

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
        self.assertFalse(
            OrdenPOS.objects.filter(
                inscripcion=inscripcion,
            ).exists()
        )
        existencia.refresh_from_db()
        self.assertEqual(existencia.stock_actual, Decimal("1.00"))
        self.assertFalse(AlertaStock.objects.filter(
            existencia__concepto=concepto).exists())

    def test_home_muestra_tabla_de_alertas_stock(self):
        comercial = self._comercial_user("comercial_hu034_home")
        concepto = Concepto.objects.create(
            nombre="Papeleria HU034",
            precio=Decimal("90.00"),
            activo=True,
        )
        existencia = Existencia.objects.create(
            concepto=concepto,
            inventario_habilitado=True,
            stock_actual=Decimal("0.50"),
            stock_minimo=Decimal("1.00"),
        )
        AlertaStock.objects.create(
            existencia=existencia,
            stock_actual=Decimal("0.50"),
            stock_minimo=Decimal("1.00"),
            activa=True,
        )
        self.client.force_login(comercial)

        response = self.client.get("/panel/ventas/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alertas de stock mínimo")
        self.assertContains(response, "Papeleria HU034")

    @override_settings(
        CONTACT_EMAIL="responsable@joca.local",
        DEFAULT_FROM_EMAIL="noreply@joca.local",
        SITE_NAME="CCENT",
    )
    def test_envia_correo_al_responsable_cuando_stock_alcanza_minimo(self):
        """Al generar una AlertaStock se dispara send_mail al CONTACT_EMAIL."""
        comercial = self._comercial_user("comercial_hu034_mail")
        inscripcion = self._inscripcion(
            "MAT-HU034-010", "hu034_mail@test.local", "2028-02"
        )
        concepto = Concepto.objects.create(
            nombre="Marcador HU034",
            precio=Decimal("30.00"),
            activo=True,
        )
        Existencia.objects.create(
            concepto=concepto,
            inventario_habilitado=True,
            stock_actual=Decimal("2.00"),
            stock_minimo=Decimal("1.00"),
        )
        self.client.force_login(comercial)

        with patch("apps.sales.views.send_mail") as mock_send:
            response = self.client.post(
                "/panel/ventas/pos/",
                {
                    "inscripcion_id": str(inscripcion.pk),
                    "concepto_id": str(concepto.pk),
                    "cantidad": "1",
                    "metodo": "EFECTIVO",
                },
            )

        self.assertEqual(response.status_code, 302)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        subject = call_kwargs[1].get("subject") or call_kwargs[0][0]
        recipient_list = call_kwargs[1].get(
            "recipient_list") or call_kwargs[0][3]
        self.assertIn("Marcador HU034", subject)
        self.assertIn("responsable@joca.local", recipient_list)
