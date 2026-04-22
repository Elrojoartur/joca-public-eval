import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria


class PanelAccessSecurityTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.director_role = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )

    def test_panel_escolar_user_without_role_returns_403(self):
        user = self.user_model.objects.create_user(
            username="sin_rol",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.get("/panel/escolar/")

        self.assertEqual(response.status_code, 403)

    def test_panel_escolar_user_with_director_role_returns_200(self):
        user = self.user_model.objects.create_user(
            username="con_rol",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.director_role)
        self.client.force_login(user)

        response = self.client.get("/panel/escolar/")

        self.assertEqual(response.status_code, 200)


class PanelAccessMatrixTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
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
            username=username, password="testpass123")
        UsuarioRol.objects.create(usuario=user, rol=role)
        return user

    def test_panel_redirects_to_login_when_unauthenticated(self):
        response = self.client.get("/panel/escolar/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/acceso/?next=/panel/escolar/", response.url)

    def test_comercial_can_access_ventas_catalogo(self):
        user = self._user_with_role("comercial", self.rol_comercial)
        self.client.force_login(user)

        response = self.client.get("/panel/ventas/catalogo/")

        self.assertEqual(response.status_code, 200)

    def test_comercial_cannot_access_escolar(self):
        user = self._user_with_role("comercial_2", self.rol_comercial)
        self.client.force_login(user)

        response = self.client.get("/panel/escolar/")

        self.assertEqual(response.status_code, 403)

    def test_alumno_can_access_alumno_home(self):
        user = self._user_with_role("alumno", self.rol_alumno)
        self.client.force_login(user)

        response = self.client.get("/panel/alumno/")

        self.assertEqual(response.status_code, 200)

    def test_alumno_cannot_access_sensitive_ventas_subroute(self):
        user = self._user_with_role("alumno_2", self.rol_alumno)
        self.client.force_login(user)

        response = self.client.get("/panel/ventas/cuentas/")

        self.assertEqual(response.status_code, 403)

    def test_director_can_access_reportes_academico(self):
        user = self._user_with_role("director", self.rol_director)
        self.client.force_login(user)

        response = self.client.get("/panel/reportes/academico/")

        self.assertEqual(response.status_code, 200)

    def test_director_cannot_access_reportes_comercial(self):
        user = self._user_with_role("director_2", self.rol_director)
        self.client.force_login(user)

        response = self.client.get("/panel/reportes/comercial/")

        self.assertEqual(response.status_code, 403)

    def test_denied_panel_access_generates_audit_event(self):
        user = self._user_with_role("alumno_3", self.rol_alumno)
        self.client.force_login(user)

        response = self.client.get("/panel/ventas/catalogo/")

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="PANEL::ACCESO_DENEGADO",
                entidad_id="/panel/ventas/catalogo/",
            ).exists()
        )

    def test_superuser_can_access_sensitive_routes(self):
        user = self.user_model.objects.create_superuser(
            username="root_test",
            email="root_test@example.com",
            password="testpass123",
        )
        self.client.force_login(user)

        response_cuentas = self.client.get("/panel/ventas/cuentas/")
        response_gobierno = self.client.get("/panel/gobierno/")
        response_excepciones = self.client.get("/panel/gobierno/excepciones/")

        self.assertEqual(response_cuentas.status_code, 200)
        self.assertEqual(response_gobierno.status_code, 200)
        self.assertEqual(response_excepciones.status_code, 200)

    def test_alumno_cannot_access_gobierno_excepciones(self):
        user = self._user_with_role(
            "alumno_bloqueado_excepciones", self.rol_alumno)
        self.client.force_login(user)

        response = self.client.get("/panel/gobierno/excepciones/")

        self.assertEqual(response.status_code, 403)


class IdleTimeoutMiddlewareTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_superuser(
            username="idle_user",
            email="idle_user@test.local",
            password="testpass123",
        )

    @override_settings(ACCESS_IDLE_TIMEOUT_SECONDS=1)
    def test_inactive_session_logs_out_user_and_audits(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["last_activity"] = int(time.time()) - 10
        session.save()

        response = self.client.get("/panel/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/acceso/")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="AUTH::LOGOUT_IDLE",
                detalle__username=self.user.username,
            ).exists()
        )

    @override_settings(ACCESS_IDLE_TIMEOUT_SECONDS=900)
    def test_active_session_updates_last_activity_and_keeps_user_logged_in(self):
        self.client.force_login(self.user)
        session = self.client.session
        previous = int(time.time()) - 10
        session["last_activity"] = previous
        session.save()

        response = self.client.get("/panel/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            int(self.client.session.get("_auth_user_id")), self.user.pk)
        self.assertGreater(self.client.session.get(
            "last_activity", 0), previous)
