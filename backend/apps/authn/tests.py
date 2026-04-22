from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.governance.models import EventoAuditoria


class PasswordResetAuditTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()

    def test_password_reset_request_generates_audit_event(self):
        self.user_model.objects.create_user(
            username="reset_user",
            email="reset_user@test.local",
            password="OldPass123!",
        )

        response = self.client.post(
            reverse("password_reset"),
            {"email": "reset_user@test.local"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reset_user@test.local", mail.outbox[0].to)
        self.assertIn("/acceso/recuperar/", mail.outbox[0].body)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="AUTH::PASSWORD_RESET_REQUEST",
                detalle__email="reset_user@test.local",
            ).exists()
        )

    def test_password_reset_request_with_unknown_email_does_not_send_email(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "unknown_user@test.local"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="AUTH::PASSWORD_RESET_REQUEST",
                detalle__email="unknown_user@test.local",
            ).exists()
        )

    def test_password_reset_confirm_updates_password_and_audits(self):
        user = self.user_model.objects.create_user(
            username="reset_confirm_user",
            email="reset_confirm_user@test.local",
            password="OldPass123!",
        )
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        confirm_url = reverse(
            "password_reset_confirm",
            kwargs={"uidb64": uidb64, "token": token},
        )

        get_response = self.client.get(confirm_url)
        self.assertEqual(get_response.status_code, 302)
        self.assertIn("set-password", get_response.url)

        response = self.client.post(
            get_response.url,
            {
                "new_password1": "NewPass456!",
                "new_password2": "NewPass456!",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("password_reset_complete"))

        user.refresh_from_db()
        self.assertTrue(user.check_password("NewPass456!"))
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="AUTH::PASSWORD_RESET_CONFIRM",
                detalle__user_id=user.pk,
            ).exists()
        )

    def test_password_reset_confirm_invalid_link_audits_denied(self):
        response = self.client.get(
            reverse(
                "password_reset_confirm",
                kwargs={"uidb64": "invalid", "token": "invalid-token"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Solicitar otro enlace")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="AUTH::PASSWORD_RESET_CONFIRM_DENIED",
                detalle__reason="invalid_or_expired_token",
            ).exists()
        )


class LoginCaptchaFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username="alumno001",
            email="alumno001@test.local",
            password="SecurePass123!",
        )

    def test_login_get_generates_security_question(self):
        response = self.client.get("/acceso/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verificaci\u00f3n de seguridad")
        self.assertIn("login_verif_question", self.client.session)
        self.assertIn("login_verif_answer", self.client.session)

    @override_settings(RECAPTCHA_ENABLED=False)
    def test_login_rejects_incorrect_security_verification(self):
        self.client.get("/acceso/")

        response = self.client.post(
            "/acceso/",
            {
                "username": self.user.username,
                "password": "SecurePass123!",
                "verificacion": "0000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verificaci")
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(RECAPTCHA_ENABLED=False)
    def test_login_accepts_correct_security_verification_and_audits(self):
        self.client.get("/acceso/")
        answer = self.client.session.get("login_verif_answer")

        response = self.client.post(
            "/acceso/",
            {
                "username": self.user.username,
                "password": "SecurePass123!",
                "verificacion": answer,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/panel/")
        self.assertEqual(
            int(self.client.session.get("_auth_user_id")), self.user.pk)
        self.assertNotIn("login_verif_question", self.client.session)
        self.assertNotIn("login_verif_answer", self.client.session)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="AUTH::LOGIN",
                detalle__username=self.user.username,
                resultado="ok",
            ).exists()
        )

    @override_settings(
        RECAPTCHA_ENABLED=True,
        RECAPTCHA_SITE_KEY="site-key-test",
        RECAPTCHA_SECRET_KEY="secret-key-test",
    )
    @patch("apps.ui.views_auth._verify_recaptcha", return_value=False)
    def test_login_requires_captcha_when_enabled(self, _mock_verify):
        self.client.get("/acceso/")
        answer = self.client.session.get("login_verif_answer")

        response = self.client.post(
            "/acceso/",
            {
                "username": self.user.username,
                "password": "SecurePass123!",
                "verificacion": answer,
                "g-recaptcha-response": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CAPTCHA")
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(RECAPTCHA_ENABLED=False)
    def test_login_rejects_invalid_credentials_and_audits(self):
        self.client.get("/acceso/")
        answer = self.client.session.get("login_verif_answer")

        response = self.client.post(
            "/acceso/",
            {
                "username": self.user.username,
                "password": "BadPass999!",
                "verificacion": answer,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Usuario o contrase")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="AUTH::LOGIN_FAIL",
                detalle__username=self.user.username,
                detalle__reason="invalid_credentials",
            ).exists()
        )

    @override_settings(RECAPTCHA_ENABLED=False, ACCESS_MAX_ATTEMPTS=3)
    def test_login_blocks_after_repeated_failed_attempts(self):
        for _ in range(3):
            self.client.get("/acceso/")
            answer = self.client.session.get("login_verif_answer")
            self.client.post(
                "/acceso/",
                {
                    "username": self.user.username,
                    "password": "BadPass999!",
                    "verificacion": answer,
                },
            )

        self.client.get("/acceso/")
        answer = self.client.session.get("login_verif_answer")
        blocked = self.client.post(
            "/acceso/",
            {
                "username": self.user.username,
                "password": "SecurePass123!",
                "verificacion": answer,
            },
        )

        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "Por seguridad")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="AUTH::LOGIN_BLOCKED",
                detalle__username=self.user.username,
                detalle__reason="lockout",
            ).exists()
        )

    @override_settings(RECAPTCHA_ENABLED=False, ACCESS_MAX_ATTEMPTS=3)
    def test_successful_login_resets_failed_attempt_counter(self):
        for _ in range(2):
            self.client.get("/acceso/")
            answer = self.client.session.get("login_verif_answer")
            self.client.post(
                "/acceso/",
                {
                    "username": self.user.username,
                    "password": "BadPass999!",
                    "verificacion": answer,
                },
            )

        self.client.get("/acceso/")
        answer = self.client.session.get("login_verif_answer")
        ok = self.client.post(
            "/acceso/",
            {
                "username": self.user.username,
                "password": "SecurePass123!",
                "verificacion": answer,
            },
        )

        self.assertEqual(ok.status_code, 302)
        self.assertEqual(ok.url, "/panel/")

        # El usuario está autenticado; hay que cerrar sesión antes de volver
        # a /acceso/ o GuestOnlyRedirectMiddleware lo envía a /panel/ y
        # login_verif_answer nunca se setea en la sesión.
        self.client.logout()
        self.client.get("/acceso/")
        answer = self.client.session.get("login_verif_answer")
        invalid_once = self.client.post(
            "/acceso/",
            {
                "username": self.user.username,
                "password": "BadPass999!",
                "verificacion": answer,
            },
        )

        self.assertEqual(invalid_once.status_code, 200)
        self.assertContains(invalid_once, "Usuario o contrase")
        self.assertNotContains(invalid_once, "Por seguridad")

    @override_settings(RECAPTCHA_ENABLED=False, ACCESS_MAX_ATTEMPTS=3)
    def test_login_lockout_is_per_user_even_if_ip_changes(self):
        for i in range(3):
            self.client.get("/acceso/", HTTP_X_FORWARDED_FOR=f"10.0.0.{i + 1}")
            answer = self.client.session.get("login_verif_answer")
            self.client.post(
                "/acceso/",
                {
                    "username": self.user.username,
                    "password": "BadPass999!",
                    "verificacion": answer,
                },
                HTTP_X_FORWARDED_FOR=f"10.0.0.{i + 1}",
            )

        self.client.get("/acceso/", HTTP_X_FORWARDED_FOR="10.0.1.1")
        answer = self.client.session.get("login_verif_answer")
        blocked = self.client.post(
            "/acceso/",
            {
                "username": self.user.username,
                "password": "SecurePass123!",
                "verificacion": answer,
            },
            HTTP_X_FORWARDED_FOR="10.0.1.1",
        )

        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "Por seguridad")
        self.assertNotIn("_auth_user_id", self.client.session)


class LogoutRevokeTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username="logout_user",
            email="logout_user@test.local",
            password="SecurePass123!",
        )

    def test_logout_closes_session_revokes_tokens_and_audits(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["access_token"] = "access-token-value"
        session["refresh_token"] = "refresh-token-value"
        session.save()

        response = self.client.get("/salir/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/acceso/")

        session_after = self.client.session
        self.assertNotIn("_auth_user_id", session_after)
        self.assertNotIn("access_token", session_after)
        self.assertNotIn("refresh_token", session_after)

        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="AUTH::LOGOUT",
                detalle__username=self.user.username,
                resultado="ok",
            ).exists()
        )


# PCB-013 / MOD-02 / HU-011 – Rechazo de credenciales inválidas
@override_settings(RECAPTCHA_ENABLED=False)
class PCB013InvalidCredentialsTests(TestCase):
    """PCB-013 / MOD-02 / HU-011 – Rechazo de credenciales inválidas.

    Verifica que el sistema rechaza el acceso cuando las credenciales son
    inválidas: la vista devuelve 200, muestra mensaje de error, no crea
    sesión autenticada y registra el evento de auditoría de fallo.
    """

    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="pcb013user",
            email="pcb013@test.local",
            password="CorrectPass123!",
        )

    def test_rechazo_credenciales_invalidas(self):
        # GET inicializa el reto de verificación matemática en sesión
        self.client.get("/acceso/")
        answer = self.client.session.get("login_verif_answer")

        # POST con usuario real pero contraseña incorrecta
        response = self.client.post(
            "/acceso/",
            {
                "username": self.user.username,
                "password": "ContraseniaWrong999!",
                "verificacion": answer,
            },
        )

        # Ruta permanece en el formulario de login (no redirige)
        self.assertEqual(response.status_code, 200)

        # Mensaje de rechazo visible
        self.assertContains(response, "Usuario o contrase")

        # Sesión no contiene usuario autenticado
        self.assertNotIn("_auth_user_id", self.client.session)

        # Auditoría de intento fallido registrada
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="AUTH::LOGIN_FAIL",
                detalle__username=self.user.username,
                detalle__reason="invalid_credentials",
            ).exists()
        )
