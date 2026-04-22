from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria, ParametroSistema


class RotacionCredencialesIntegracionesTests(TestCase):
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

    def test_director_rota_credenciales_smtp_y_audita(self):
        director = self._user_with_role(
            "director_hu041_smtp", self.rol_director)
        ParametroSistema.objects.create(
            categoria=ParametroSistema.CATEGORIA_SMTP,
            clave="smtp_host",
            valor="smtp.test.local",
            activo=True,
        )
        ParametroSistema.objects.create(
            categoria=ParametroSistema.CATEGORIA_SMTP,
            clave="smtp_port",
            valor="587",
            activo=True,
        )
        ParametroSistema.objects.create(
            categoria=ParametroSistema.CATEGORIA_SMTP,
            clave="smtp_password",
            valor="old_secret",
            activo=True,
        )
        self.client.force_login(director)

        response = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "smtp",
                "operation": "rotate",
                "smtp_host": "smtp.test.local",
                "smtp_port": "587",
                "smtp_user": "mailer",
                "smtp_from": "noreply@test.local",
                "smtp_password": "old_secret",
                "smtp_enabled": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        new_secret = ParametroSistema.objects.get(clave="smtp_password").valor
        self.assertNotEqual(new_secret, "old_secret")
        self.assertEqual(ParametroSistema.objects.get(
            clave="smtp_rotation_version").valor, "1")
        self.assertEqual(ParametroSistema.objects.get(
            clave="smtp_enabled").valor, "0")
        self.assertEqual(ParametroSistema.objects.get(
            clave="smtp_test_status").valor, "pendiente")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::PARAMETROS_SMTP_ROTATE",
                entidad="ParametroSistema",
                entidad_id="smtp",
                resultado="ok",
            ).exists()
        )

    def test_director_rota_credenciales_pasarela_y_audita(self):
        director = self._user_with_role(
            "director_hu041_pasarela", self.rol_director)
        ParametroSistema.objects.create(
            categoria=ParametroSistema.CATEGORIA_PASARELA,
            clave="pasarela_proveedor",
            valor="Stripe",
            activo=True,
        )
        ParametroSistema.objects.create(
            categoria=ParametroSistema.CATEGORIA_PASARELA,
            clave="pasarela_public_key",
            valor="pk_test_demo",
            activo=True,
        )
        ParametroSistema.objects.create(
            categoria=ParametroSistema.CATEGORIA_PASARELA,
            clave="pasarela_secret_key",
            valor="sk_old_secret",
            activo=True,
        )
        self.client.force_login(director)

        response = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "pasarela",
                "operation": "rotate",
                "pasarela_proveedor": "Stripe",
                "pasarela_public_key": "pk_test_demo",
                "pasarela_secret_key": "sk_old_secret",
                "pasarela_enabled": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        new_secret = ParametroSistema.objects.get(
            clave="pasarela_secret_key").valor
        self.assertNotEqual(new_secret, "sk_old_secret")
        self.assertEqual(ParametroSistema.objects.get(
            clave="pasarela_rotation_version").valor, "1")
        self.assertEqual(ParametroSistema.objects.get(
            clave="pasarela_enabled").valor, "0")
        self.assertEqual(ParametroSistema.objects.get(
            clave="pasarela_test_status").valor, "pendiente")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::PARAMETROS_PASARELA_ROTATE",
                entidad="ParametroSistema",
                entidad_id="pasarela",
                resultado="ok",
            ).exists()
        )

    def test_alumno_no_puede_rotar_credenciales(self):
        alumno = self._user_with_role("alumno_hu041", self.rol_alumno)
        self.client.force_login(alumno)

        response = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "smtp",
                "operation": "rotate",
            },
        )

        self.assertEqual(response.status_code, 403)
