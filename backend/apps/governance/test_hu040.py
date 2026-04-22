from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria, ParametroSistema


class IntegracionesPreviasHabilitacionTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )

    def _director(self, username):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_director)
        return user

    def test_no_habilita_smtp_sin_prueba_exitosa(self):
        director = self._director("director_hu040_smtp_denied")
        self.client.force_login(director)

        response = self.client.post(
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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ParametroSistema.objects.get(
            clave="smtp_enabled").valor, "0")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::PARAMETROS_SMTP_ENABLE_DENIED",
                entidad="ParametroSistema",
                entidad_id="smtp",
            ).exists()
        )

    def test_habilita_smtp_tras_prueba_exitosa(self):
        director = self._director("director_hu040_smtp_ok")
        self.client.force_login(director)

        smtp_mock = MagicMock()
        smtp_mock.__enter__ = MagicMock(return_value=smtp_mock)
        smtp_mock.__exit__ = MagicMock(return_value=False)
        smtp_mock.noop.return_value = (250, b"OK")

        with patch("apps.ui.views_gobierno.smtplib.SMTP", return_value=smtp_mock):
            test_response = self.client.post(
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

        save_response = self.client.post(
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

        self.assertEqual(test_response.status_code, 200)
        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(ParametroSistema.objects.get(
            clave="smtp_enabled").valor, "1")
        self.assertEqual(ParametroSistema.objects.get(
            clave="smtp_test_status").valor, "ok")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::PARAMETROS_SMTP_TEST",
                entidad="ParametroSistema",
                entidad_id="smtp",
                resultado="ok",
            ).exists()
        )

    def test_no_habilita_pasarela_sin_prueba_exitosa(self):
        director = self._director("director_hu040_pasarela_denied")
        self.client.force_login(director)

        response = self.client.post(
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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ParametroSistema.objects.get(
            clave="pasarela_enabled").valor, "0")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::PARAMETROS_PASARELA_ENABLE_DENIED",
                entidad="ParametroSistema",
                entidad_id="pasarela",
            ).exists()
        )

    def test_habilita_pasarela_tras_prueba_exitosa(self):
        director = self._director("director_hu040_pasarela_ok")
        self.client.force_login(director)

        test_response = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "pasarela",
                "operation": "test",
                "pasarela_proveedor": "Stripe",
                "pasarela_public_key": "pk_test_demo",
            },
            follow=True,
        )
        save_response = self.client.post(
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

        self.assertEqual(test_response.status_code, 200)
        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(ParametroSistema.objects.get(
            clave="pasarela_enabled").valor, "1")
        self.assertEqual(ParametroSistema.objects.get(
            clave="pasarela_test_status").valor, "ok")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::PARAMETROS_PASARELA_TEST",
                entidad="ParametroSistema",
                entidad_id="pasarela",
                resultado="ok",
            ).exists()
        )

    def test_smtp_prueba_intenta_conexion_smtplib(self):
        """_validate_smtp_config llama a smtplib.SMTP con host:port cuando operation=test."""
        director = self._director("director_hu040_smtp_conn")
        self.client.force_login(director)

        smtp_mock = MagicMock()
        smtp_mock.__enter__ = MagicMock(return_value=smtp_mock)
        smtp_mock.__exit__ = MagicMock(return_value=False)
        smtp_mock.noop.return_value = (250, b"OK")

        with patch("apps.ui.views_gobierno.smtplib.SMTP", return_value=smtp_mock) as patched_smtp:
            self.client.post(
                "/panel/gobierno/parametros/",
                {
                    "section": "smtp",
                    "operation": "test",
                    "smtp_host": "smtp.verifica.local",
                    "smtp_port": "465",
                    "smtp_user": "sender",
                    "smtp_from": "noreply@verifica.local",
                },
                follow=True,
            )

        patched_smtp.assert_called_once_with(
            "smtp.verifica.local", 465, timeout=5)
        smtp_mock.noop.assert_called_once()
        self.assertEqual(
            ParametroSistema.objects.get(clave="smtp_test_status").valor, "ok"
        )

    def test_smtp_prueba_registra_error_si_falla_conexion(self):
        """Si smtplib lanza excepción, smtp_test_status queda en 'error' y no se puede habilitar."""
        director = self._director("director_hu040_smtp_fail")
        self.client.force_login(director)

        with patch(
            "apps.ui.views_gobierno.smtplib.SMTP",
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            self.client.post(
                "/panel/gobierno/parametros/",
                {
                    "section": "smtp",
                    "operation": "test",
                    "smtp_host": "smtp.falla.local",
                    "smtp_port": "25",
                    "smtp_user": "",
                    "smtp_from": "noreply@falla.local",
                },
                follow=True,
            )

        self.assertEqual(
            ParametroSistema.objects.get(
                clave="smtp_test_status").valor, "error"
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::PARAMETROS_SMTP_TEST",
                resultado="error",
            ).exists()
        )
