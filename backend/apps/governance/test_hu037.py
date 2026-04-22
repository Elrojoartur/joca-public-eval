from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria, ParametroSistema


class PoliticasSeguridadTests(TestCase):
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

    def test_director_actualiza_politicas_de_seguridad_y_audita(self):
        director = self._user_with_role("director_hu037", self.rol_director)
        self.client.force_login(director)

        response = self.client.post(
            "/panel/gobierno/seguridad/",
            {
                "section": "policy",
                "security_password_min_length": "10",
                "security_max_attempts": "3",
                "security_attempt_window_seconds": "1200",
                "security_lockout_seconds": "1800",
                "security_idle_timeout_seconds": "600",
                "security_captcha_enabled": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ParametroSistema.objects.get(
            clave="security_password_min_length").valor, "10")
        self.assertEqual(ParametroSistema.objects.get(
            clave="security_max_attempts").valor, "3")
        self.assertEqual(ParametroSistema.objects.get(
            clave="security_captcha_enabled").valor, "1")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::POLITICAS_SEGURIDAD_UPDATE",
                detalle__security_max_attempts="3",
                detalle__security_idle_timeout_seconds="600",
            ).exists()
        )

    @override_settings(RECAPTCHA_ENABLED=False)
    @patch("apps.ui.views_auth._verify_recaptcha", return_value=True)
    def test_login_aplica_max_intentos_configurado(self, _mock_verify):
        user = self.user_model.objects.create_user(
            username="alumno_hu037",
            email="alumno_hu037@test.local",
            password="SecurePass123!",
        )
        ParametroSistema.objects.update_or_create(
            clave="security_max_attempts",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_SEGURIDAD,
                "valor": "2",
                "activo": True,
            },
        )

        for _ in range(2):
            self.client.get("/acceso/")
            answer = self.client.session.get("login_verif_answer")
            self.client.post(
                "/acceso/",
                {
                    "username": user.username,
                    "password": "BadPass999!",
                    "verificacion": answer,
                },
            )

        self.client.get("/acceso/")
        answer = self.client.session.get("login_verif_answer")
        blocked = self.client.post(
            "/acceso/",
            {
                "username": user.username,
                "password": "SecurePass123!",
                "verificacion": answer,
            },
        )

        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "Por seguridad")

    @override_settings(RECAPTCHA_ENABLED=False)
    def test_captcha_deshabilitado_por_politica(self):
        ParametroSistema.objects.update_or_create(
            clave="security_captcha_enabled",
            defaults={
                "categoria": ParametroSistema.CATEGORIA_SEGURIDAD,
                "valor": "0",
                "activo": True,
            },
        )

        response = self.client.get("/acceso/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "class=\"g-recaptcha\"")
        self.assertNotContains(response, "recaptcha/api.js")


# ---------------------------------------------------------------------------
# HU-037 — Efecto inmediato del cambio de política vía panel (e2e)
# ---------------------------------------------------------------------------

class PoliticaEfectoInmediatoTests(TestCase):
    """HU-037 — Valida que cambiar max_attempts vía el panel de seguridad
    bloquea inmediatamente el login tras agotar los nuevos intentos."""

    def setUp(self):
        self.user_model = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )

    def _user_with_role(self, username, rol):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=rol)
        return user

    @override_settings(RECAPTCHA_ENABLED=False)
    @patch("apps.ui.views_auth._verify_recaptcha", return_value=True)
    def test_cambio_politica_via_panel_afecta_lockout_inmediatamente(self, _mock_verify):
        """Panel POST seguridad (max_attempts=2) bloquea el login tras 2 intentos fallidos."""
        # 1. Director actualiza max_attempts a 2 vía panel
        director = self._user_with_role(
            "director_lockout_e2e", self.rol_director)
        self.client.force_login(director)
        self.client.post(
            "/panel/gobierno/seguridad/",
            {
                "section": "policy",
                "security_password_min_length": "8",
                "security_max_attempts": "2",
                "security_attempt_window_seconds": "3600",
                "security_lockout_seconds": "3600",
                "security_idle_timeout_seconds": "900",
                "security_captcha_enabled": "0",
            },
        )
        self.client.logout()

        # 2. Usuario víctima del lockout
        victim = self.user_model.objects.create_user(
            username="victima_lockout_e2e",
            email="victima_lockout_e2e@test.local",
            password="SecurePass123!",
        )

        # 3. Dos intentos fallidos agotan el límite de 2
        for _ in range(2):
            self.client.get("/acceso/")
            answer = self.client.session.get("login_verif_answer")
            self.client.post(
                "/acceso/",
                {
                    "username": victim.username,
                    "password": "BadPass999!",
                    "verificacion": answer,
                },
            )

        # 4. El siguiente intento (con clave correcta) queda bloqueado
        self.client.get("/acceso/")
        answer = self.client.session.get("login_verif_answer")
        blocked = self.client.post(
            "/acceso/",
            {
                "username": victim.username,
                "password": "SecurePass123!",
                "verificacion": answer,
            },
        )

        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "Por seguridad")
