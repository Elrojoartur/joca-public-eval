from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria, ParametroSistema


class ParametrosIntegracionesTests(TestCase):
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

    def _user_with_role(self, username, rol):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=rol)
        return user

    def test_director_actualiza_parametros_institucion_y_periodo(self):
        director = self._user_with_role("director_hu036_1", self.rol_director)
        self.client.force_login(director)

        resp_inst = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "institucion",
                "institucion_nombre": "Instituto JOCA",
                "institucion_rfc": "XAXX010101000",
                "institucion_direccion": "Av. Demo 123",
            },
            follow=True,
        )
        resp_periodo = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "periodo",
                "periodo_activo": "2026-03",
                "periodo_inicio": "2026-03-01",
                "periodo_fin": "2026-07-31",
            },
            follow=True,
        )

        self.assertEqual(resp_inst.status_code, 200)
        self.assertEqual(resp_periodo.status_code, 200)
        self.assertEqual(
            ParametroSistema.objects.get(clave="institucion_nombre").valor,
            "Instituto JOCA",
        )
        self.assertEqual(
            ParametroSistema.objects.get(clave="periodo_activo").valor,
            "2026-03",
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::PARAMETROS_INSTITUCION_UPDATE",
                detalle__institucion_nombre="Instituto JOCA",
            ).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::PARAMETROS_PERIODO_UPDATE",
                detalle__periodo_activo="2026-03",
            ).exists()
        )

    def test_director_actualiza_integraciones_smtp_y_pasarela(self):
        director = self._user_with_role("director_hu036_2", self.rol_director)
        self.client.force_login(director)

        smtp_mock = MagicMock()
        smtp_mock.__enter__ = MagicMock(return_value=smtp_mock)
        smtp_mock.__exit__ = MagicMock(return_value=False)
        smtp_mock.noop.return_value = (250, b"OK")

        with patch("apps.ui.views_gobierno.smtplib.SMTP", return_value=smtp_mock):
            resp_smtp_test = self.client.post(
                "/panel/gobierno/parametros/",
                {
                    "section": "smtp",
                    "operation": "test",
                    "smtp_host": "smtp.test.local",
                    "smtp_port": "587",
                    "smtp_user": "mailer",
                    "smtp_from": "noreply@test.local",
                },
                follow=True,
            )
        resp_smtp = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "smtp",
                "operation": "save",
                "smtp_host": "smtp.test.local",
                "smtp_port": "587",
                "smtp_user": "mailer",
                "smtp_from": "noreply@test.local",
                "smtp_enabled": "on",
            },
            follow=True,
        )
        resp_pasarela_test = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "pasarela",
                "operation": "test",
                "pasarela_proveedor": "Stripe",
                "pasarela_public_key": "pk_test_demo",
            },
            follow=True,
        )
        resp_pasarela = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "pasarela",
                "operation": "save",
                "pasarela_proveedor": "Stripe",
                "pasarela_public_key": "pk_test_demo",
                "pasarela_enabled": "on",
            },
            follow=True,
        )

        self.assertEqual(resp_smtp_test.status_code, 200)
        self.assertEqual(resp_smtp.status_code, 200)
        self.assertEqual(resp_pasarela_test.status_code, 200)
        self.assertEqual(resp_pasarela.status_code, 200)
        self.assertEqual(ParametroSistema.objects.get(
            clave="smtp_host").valor, "smtp.test.local")
        self.assertEqual(ParametroSistema.objects.get(
            clave="smtp_enabled").valor, "1")
        self.assertEqual(ParametroSistema.objects.get(
            clave="pasarela_proveedor").valor, "Stripe")
        self.assertEqual(ParametroSistema.objects.get(
            clave="pasarela_enabled").valor, "1")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::PARAMETROS_SMTP_UPDATE",
                detalle__smtp_host="smtp.test.local",
            ).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::PARAMETROS_PASARELA_UPDATE",
                detalle__pasarela_proveedor="Stripe",
            ).exists()
        )

    def test_alumno_no_puede_acceder_a_parametros(self):
        alumno = self._user_with_role("alumno_hu036", self.rol_alumno)
        self.client.force_login(alumno)

        response = self.client.get("/panel/gobierno/parametros/")

        self.assertEqual(response.status_code, 403)
