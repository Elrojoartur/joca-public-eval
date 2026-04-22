"""
Pruebas automatizadas para GuestOnlyRedirectMiddleware y SecurityNoCacheMiddleware.

Casos cubiertos:
  1. Usuario autenticado GET /acceso/             → 302 /panel/
  2. Usuario autenticado GET /acceso/recuperar/   → 302 /panel/
  3. Usuario autenticado GET /acceso/recuperar/enviado/  → 302 /panel/
  4. Usuario autenticado GET /acceso/recuperar/listo/    → 302 /panel/
  5. Usuario NO autenticado GET /acceso/          → 200 (formulario de login)
  6. Usuario autenticado GET /panel/              → 200 con cabeceras no-cache
  7. Usuario NO autenticado GET /panel/           → 302 /acceso/?next=/panel/
  8. POST /salir/ (logout)                        → sesión cerrada, redirect /acceso/
  9. Respuesta HTML autenticada lleva no-cache headers
 10. Content-Type no-HTML (JSON) NO lleva no-cache headers
 11. /acceso/admin/ con usuario autenticado NO redirige a /panel/ (excepción)
"""

import time

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse

from apps.authn.middleware import GuestOnlyRedirectMiddleware, SecurityNoCacheMiddleware
from apps.governance.models import EventoAuditoria

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(username="testuser", password="Pass1234!"):
    return User.objects.create_user(username=username, password=password)


# ---------------------------------------------------------------------------
# GuestOnlyRedirectMiddleware — pruebas de integración con TestClient
# ---------------------------------------------------------------------------

class GuestOnlyRedirectIntegrationTests(TestCase):
    """Usa TestClient para ejercer el middleware a través de la pila Django real."""

    def setUp(self):
        self.user = _make_user("guest_redirect_user")

    # ── Caso 1 ────────────────────────────────────────────────────────────────
    def test_authenticated_user_redirected_from_acceso(self):
        self.client.force_login(self.user)
        response = self.client.get("/acceso/")
        self.assertRedirects(response, "/panel/",
                             fetch_redirect_response=False)

    # ── Caso 2 ────────────────────────────────────────────────────────────────
    def test_authenticated_user_redirected_from_password_reset(self):
        self.client.force_login(self.user)
        response = self.client.get("/acceso/recuperar/")
        self.assertRedirects(response, "/panel/",
                             fetch_redirect_response=False)

    # ── Caso 3 ────────────────────────────────────────────────────────────────
    def test_authenticated_user_redirected_from_password_reset_done(self):
        self.client.force_login(self.user)
        response = self.client.get("/acceso/recuperar/enviado/")
        self.assertRedirects(response, "/panel/",
                             fetch_redirect_response=False)

    # ── Caso 4 ────────────────────────────────────────────────────────────────
    def test_authenticated_user_redirected_from_password_reset_complete(self):
        self.client.force_login(self.user)
        response = self.client.get("/acceso/recuperar/listo/")
        self.assertRedirects(response, "/panel/",
                             fetch_redirect_response=False)

    # ── Caso 5 ────────────────────────────────────────────────────────────────
    def test_anonymous_user_can_access_acceso(self):
        response = self.client.get("/acceso/")
        # Debe mostrar el formulario de login, no redirigir a /panel/
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Location", ""), "/panel/")

    # ── Caso 7 ────────────────────────────────────────────────────────────────
    def test_anonymous_user_redirected_from_panel(self):
        response = self.client.get("/panel/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/acceso/", response["Location"])

    # ── Caso 8 ────────────────────────────────────────────────────────────────
    def test_logout_works_and_clears_session(self):
        self.client.force_login(self.user)
        response = self.client.get("/salir/")
        # El view salir() redirige a /acceso/
        self.assertRedirects(response, "/acceso/",
                             fetch_redirect_response=False)
        # Después del logout el usuario ya no está autenticado
        follow_response = self.client.get("/panel/")
        self.assertEqual(follow_response.status_code, 302)
        self.assertIn("/acceso/", follow_response["Location"])

    # ── Caso 11 ───────────────────────────────────────────────────────────────
    def test_authenticated_user_on_acceso_admin_not_redirected_to_panel(self):
        """
        /acceso/admin/ es una excepción configurada en GUEST_EXCEPTIONS.
        Debe redirigir a /admin/ (comportamiento del RedirectView), no a /panel/.
        """
        self.client.force_login(self.user)
        response = self.client.get("/acceso/admin/")
        # RedirectView permanente hacia /admin/, no hacia /panel/
        self.assertNotEqual(response.get("Location", ""), "/panel/")
        self.assertIn("/admin/", response.get("Location", ""))


# ---------------------------------------------------------------------------
# SecurityNoCacheMiddleware — pruebas unitarias con RequestFactory
# ---------------------------------------------------------------------------

class SecurityNoCacheMiddlewareUnitTests(TestCase):
    """Prueba el middleware directamente sin pasar por la pila URL completa."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = _make_user("nocache_user")

    def _get_middleware(self, final_response: HttpResponse):
        """Crea una instancia del middleware con una respuesta fija."""
        return SecurityNoCacheMiddleware(get_response=lambda r: final_response)

    # ── Caso 6 / Caso 9: HTML autenticada lleva no-cache ─────────────────────
    def test_html_response_authenticated_has_no_cache_headers(self):
        request = self.factory.get("/panel/")
        request.user = self.user  # autenticado

        html_response = HttpResponse(
            "<html></html>", content_type="text/html; charset=utf-8")
        middleware = self._get_middleware(html_response)
        response = middleware(request)

        self.assertIn("no-store", response.get("Cache-Control", ""))
        self.assertEqual(response.get("Pragma"), "no-cache")
        self.assertEqual(response.get("Expires"), "0")

    # ── Caso 10: JSON no lleva no-cache ───────────────────────────────────────
    def test_json_response_authenticated_no_cache_headers_not_set(self):
        """Las respuestas no-HTML (API/JSON) no deben llevar no-cache forzado."""
        from django.http import JsonResponse
        request = self.factory.get("/api/health/")
        request.user = self.user  # autenticado

        json_resp = JsonResponse({"status": "ok"})
        middleware = self._get_middleware(json_resp)
        response = middleware(request)

        # Cache-Control no debe haber sido inyectado por nosotros
        cache_control = response.get("Cache-Control", "")
        self.assertNotIn("no-store", cache_control)

    def test_pdf_response_has_no_cache_headers_not_set(self):
        """Las respuestas PDF no deben verse afectadas."""
        request = self.factory.get("/panel/escolar/boleta/")
        request.user = self.user

        pdf_response = HttpResponse(
            b"%PDF-1.4 ...", content_type="application/pdf")
        middleware = self._get_middleware(pdf_response)
        response = middleware(request)

        cache_control = response.get("Cache-Control", "")
        self.assertNotIn("no-store", cache_control)

    def test_csv_response_has_no_cache_headers_not_set(self):
        """Las respuestas CSV (exportaciones) no deben verse afectadas."""
        request = self.factory.get("/panel/gobierno/auditoria/?export=csv")
        request.user = self.user

        csv_response = HttpResponse(
            "a,b,c", content_type="text/csv; charset=utf-8")
        middleware = self._get_middleware(csv_response)
        response = middleware(request)

        cache_control = response.get("Cache-Control", "")
        self.assertNotIn("no-store", cache_control)

    def test_static_path_skipped_even_if_html(self):
        """Rutas /static/ siempre se omiten, sin importar el Content-Type."""
        request = self.factory.get("/static/ui/style.css")
        request.user = self.user

        # En la práctica sería CSS, pero incluso con text/html debe omitirse
        static_response = HttpResponse("body{}", content_type="text/html")
        middleware = self._get_middleware(static_response)
        response = middleware(request)

        cache_control = response.get("Cache-Control", "")
        self.assertNotIn("no-store", cache_control)

    def test_sensitive_path_anonymous_user_gets_no_cache(self):
        """Una ruta sensible como /acceso/ SÍ lleva no-cache incluso sin autenticar."""
        from django.contrib.auth.models import AnonymousUser
        request = self.factory.get("/acceso/")
        request.user = AnonymousUser()

        html_response = HttpResponse(
            "<html></html>", content_type="text/html; charset=utf-8")
        middleware = self._get_middleware(html_response)
        response = middleware(request)

        self.assertIn("no-store", response.get("Cache-Control", ""))


# ---------------------------------------------------------------------------
# GuestOnlyRedirectMiddleware — pruebas unitarias con RequestFactory
# ---------------------------------------------------------------------------

class GuestOnlyRedirectMiddlewareUnitTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.user = _make_user("unit_guest_user")

    def _get_middleware(self):
        ok_response = HttpResponse("OK")
        return GuestOnlyRedirectMiddleware(get_response=lambda r: ok_response)

    def test_authenticated_on_acceso_returns_redirect(self):
        request = self.factory.get("/acceso/")
        request.user = self.user
        middleware = self._get_middleware()
        response = middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/panel/")

    def test_authenticated_on_acceso_recuperar_returns_redirect(self):
        request = self.factory.get("/acceso/recuperar/")
        request.user = self.user
        middleware = self._get_middleware()
        response = middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/panel/")

    def test_anonymous_on_acceso_passes_through(self):
        from django.contrib.auth.models import AnonymousUser
        request = self.factory.get("/acceso/")
        request.user = AnonymousUser()
        middleware = self._get_middleware()
        response = middleware(request)
        # No redirige → pasa al siguiente (OK)
        self.assertEqual(response.status_code, 200)

    def test_authenticated_on_panel_passes_through(self):
        """El panel no es una ruta de invitados; el middleware no interfiere."""
        request = self.factory.get("/panel/")
        request.user = self.user
        middleware = self._get_middleware()
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_acceso_admin_exception_passes_through(self):
        """/acceso/admin/ está en GUEST_EXCEPTIONS y no debe redirigir a /panel/."""
        request = self.factory.get("/acceso/admin/")
        request.user = self.user
        middleware = self._get_middleware()
        response = middleware(request)
        # Pasa al siguiente handler (no es redirigido a /panel/)
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# HU-013 — Flujo de inactividad de extremo a extremo
# ---------------------------------------------------------------------------

@override_settings(RECAPTCHA_ENABLED=False, ACCESS_IDLE_TIMEOUT_SECONDS=1)
class IdleSessionFullFlowTests(TestCase):
    """HU-013 — Cierre de sesión por inactividad: flujo completo e2e.

    Cubre el ciclo que no estaba cubierto por los tests unitarios existentes:
      1. Login real mediante POST /acceso/ con verificación matemática.
      2. Acceso exitoso a /panel/ (last_activity se actualiza en sesión).
      3. Simulación de tiempo vencido (last_activity retrasado más allá del timeout).
      4. Siguiente petición a /panel/ → IdleTimeoutMiddleware detecta idle
         → logout → 302 /acceso/.
      5. Evento de auditoría AUTH::LOGOUT_IDLE registrado con username correcto.
      6. Usuario ya no está autenticado tras el idle logout.
      7. Re-login exitoso después del logout por inactividad.
    """

    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="idle_e2e_user",
            email="idle_e2e@test.local",
            password="IdlePass456!",
        )

    def _login_via_form(self):
        """Realiza el login completo: GET /acceso/ + POST con verificación matemática."""
        self.client.get("/acceso/")
        answer = self.client.session.get("login_verif_answer")
        return self.client.post(
            "/acceso/",
            {
                "username": self.user.username,
                "password": "IdlePass456!",
                "verificacion": answer,
            },
        )

    def test_idle_full_flow_login_expire_relogin(self):
        """Ciclo completo: login → actividad → idle vencido → logout automático → re-login."""
        # Paso 1: Login real mediante el formulario
        login_resp = self._login_via_form()
        self.assertEqual(login_resp.status_code, 302)
        self.assertEqual(login_resp.url, "/panel/")

        # Paso 2: Primera petición al panel → sesión activa, last_activity actualizado
        panel_resp = self.client.get("/panel/")
        self.assertEqual(panel_resp.status_code, 200)
        self.assertIn("last_activity", self.client.session)

        # Paso 3: Simular tiempo vencido (60 s > timeout de 1 s)
        session = self.client.session
        session["last_activity"] = int(time.time()) - 60
        session.save()

        # Paso 4: La siguiente petición dispara IdleTimeoutMiddleware
        expired_resp = self.client.get("/panel/")
        self.assertEqual(expired_resp.status_code, 302)
        self.assertEqual(expired_resp.url, "/acceso/")

        # Paso 5: Usuario ya no está autenticado
        self.assertNotIn("_auth_user_id", self.client.session)

        # Paso 6: Evento AUTH::LOGOUT_IDLE registrado con el username correcto
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="AUTH::LOGOUT_IDLE",
                detalle__username=self.user.username,
            ).exists()
        )

        # Paso 7: Re-login exitoso tras el idle logout
        relogin_resp = self._login_via_form()
        self.assertEqual(relogin_resp.status_code, 302)
        self.assertEqual(relogin_resp.url, "/panel/")
        self.assertEqual(
            int(self.client.session.get("_auth_user_id")), self.user.pk
        )
