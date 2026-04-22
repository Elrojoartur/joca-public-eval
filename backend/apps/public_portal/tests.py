from datetime import date, timedelta
from unittest.mock import patch

from django.utils import timezone
from django.test import TestCase
from django.core import mail
from django.test import override_settings

from apps.public_portal import views as portal_views
from apps.public_portal.views import SECURITY_ANSWER_KEY
from apps.school.models import Curso, Grupo, Periodo


class PortalPublicSectionsTests(TestCase):
    def test_portal_home_is_public_for_visitors(self):
        response = self.client.get("/portal/")

        self.assertEqual(response.status_code, 200)

    def test_portal_has_required_quick_access_links(self):
        response = self.client.get("/portal/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="#cursos"')
        self.assertContains(response, 'href="/portal/avisos/"')
        self.assertContains(response, 'href="/portal/faqs/"')
        self.assertContains(response, 'href="/portal/contacto/"')

    def test_portal_has_mision_vision_link_at_bottom(self):
        response = self.client.get("/portal/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/portal/mision-vision/"')

    @override_settings(
        PORTAL_MISION="Formar tecnicos con enfoque practico.",
        PORTAL_VISION="Ser referente regional en capacitacion tecnologica.",
    )
    def test_mision_vision_page_displays_configured_content(self):
        response = self.client.get("/portal/mision-vision/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Misi\u00f3n")
        self.assertContains(response, "Visi\u00f3n")
        self.assertContains(response, "Formar tecnicos con enfoque practico.")
        self.assertContains(
            response,
            "Ser referente regional en capacitacion tecnologica.",
        )

    def test_portal_shows_contact_fields_for_visitors(self):
        response = self.client.get("/portal/contacto/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tel:")
        self.assertContains(response, "WhatsApp:")
        self.assertContains(response, "Correo:")
        self.assertContains(response, "Horario:")
        self.assertContains(response, "Direcci\u00f3n:")

    def test_portal_courses_include_detail_links(self):
        response = self.client.get("/portal/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/portal/cursos/electronica-basica/')

    def test_portal_filters_courses_server_side(self):
        response = self.client.get(
            "/portal/",
            {
                "categoria": "NoExiste",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No hay cursos para mostrar por ahora.")

    def test_portal_courses_pagination_is_available(self):
        periodo = Periodo.objects.create(
            codigo="2028-01",
            fecha_inicio=date(2028, 1, 1),
            fecha_fin=date(2028, 1, 31),
            activo=True,
        )
        for i in range(1, 10):   # 9 grupos → 2 páginas (threshold = 8)
            curso = Curso.objects.create(
                codigo=f"HU004-PG-{i:02d}",
                nombre=f"Curso paginación {i}",
                activo=True,
            )
            Grupo.objects.create(
                curso_ref=curso,
                periodo_ref=periodo,
                tipo_horario=Grupo.HORARIO_SEM,
                turno=Grupo.TURNO_AM,
                cupo=20,
                estado=Grupo.ESTADO_ACTIVO,
            )

        response = self.client.get("/portal/grupos/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paginación de grupos")
        self.assertContains(response, "Página 1 de 2")

    def test_portal_shows_avisos_section_with_items(self):
        response = self.client.get("/portal/avisos/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Avisos")
        self.assertContains(response, "Inscripciones abiertas")

    def test_portal_shows_faq_section_with_items(self):
        response = self.client.get("/portal/faqs/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Preguntas frecuentes")
        self.assertContains(response, "inscribo a un curso")

    @patch("apps.public_portal.views.load_json_list")
    def test_load_avisos_catalog_returns_only_vigentes(self, mock_load_json_list):
        hoy = timezone.localdate()
        mock_load_json_list.return_value = [
            {
                "id": "old-expired",
                "titulo": "Expirado",
                "fecha_inicio": str(hoy - timedelta(days=10)),
                "fecha_fin": str(hoy - timedelta(days=1)),
            },
            {
                "id": "manual-off",
                "titulo": "Desactivado",
                "fecha": str(hoy),
                "vigente": False,
            },
            {
                "id": "future",
                "titulo": "Futuro",
                "fecha_inicio": str(hoy + timedelta(days=2)),
            },
            {
                "id": "active",
                "titulo": "Vigente",
                "fecha_inicio": str(hoy - timedelta(days=2)),
                "fecha_fin": str(hoy + timedelta(days=5)),
            },
        ]

        avisos = portal_views.load_avisos_catalog()

        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]["id"], "active")

    @patch("apps.public_portal.views.load_json_list")
    def test_load_faqs_catalog_returns_only_active(self, mock_load_json_list):
        mock_load_json_list.return_value = [
            {"id": "faq-1", "pregunta": "Activa", "activa": True},
            {"id": "faq-2", "pregunta": "Inactiva", "activa": False},
            {"id": "faq-3", "pregunta": "Sin bandera"},
        ]

        faqs = portal_views.load_faqs_catalog()

        self.assertEqual(len(faqs), 1)
        self.assertEqual(faqs[0]["id"], "faq-1")

    def test_contact_form_rejects_invalid_security_answer(self):
        self.client.get("/portal/contacto/")

        response = self.client.post(
            "/portal/contacto/",
            {
                "nombre": "Visitante",
                "email": "visitante@test.local",
                "telefono": "4430000000",
                "asunto": "Informacion",
                "mensaje": "Quiero mas informacion",
                "security_answer": "999",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Respuesta incorrecta")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="noreply@test.local")
    def test_contact_form_accepts_valid_submission_and_sends_email(self):
        self.client.get("/portal/contacto/")
        answer = self.client.session.get(SECURITY_ANSWER_KEY)

        response = self.client.post(
            "/portal/contacto/",
            {
                "nombre": "Visitante",
                "email": "visitante@test.local",
                "telefono": "4430000000",
                "asunto": "Informacion",
                "mensaje": "Quiero mas informacion",
                "security_answer": answer,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Listo. Recibimos tu mensaje")
        # Ahora se envían dos correos: notificación institucional + acuse al remitente
        self.assertEqual(len(mail.outbox), 2)
        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(any("Informacion" in s for s in subjects))
        self.assertTrue(any("Recibimos tu mensaje" in s for s in subjects))


# PCB-011 / MOD-01 / HU-003 – Consulta de datos de contacto
@override_settings(
    PORTAL_CONTACT_PHONE="5551234567",
    PORTAL_CONTACT_WHATSAPP="5559876543",
    PORTAL_CONTACT_EMAIL="contacto@test.local",
    PORTAL_CONTACT_ADDRESS="Calle Prueba 99, Col. Test, 58000 Morelia, Michoacan.",
)
class PCB011ContactDataTests(TestCase):
    """PCB-011 / MOD-01 / HU-003 – Consulta de datos de contacto.

    Verifica que la vista pública de contacto responda con HTTP 200 y
    exponga los datos institucionales configurados: teléfono, WhatsApp,
    correo electrónico y dirección física.
    """

    def test_contacto_expone_datos_institucionales(self):
        response = self.client.get("/portal/contacto/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "5551234567")
        self.assertContains(response, "5559876543")
        self.assertContains(response, "contacto@test.local")
        self.assertContains(response, "Calle Prueba 99")


# PCB-012 / MOD-01 / HU-005 – Envío de mensaje de contacto con CAPTCHA
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="noreply@test.local")
class PCB012ContactFormCaptchaTests(TestCase):
    """PCB-012 / MOD-01 / HU-005 – Envío de mensaje de contacto con CAPTCHA.

    Verifica que el formulario de contacto, al recibir una respuesta CAPTCHA
    correcta y datos válidos, muestra confirmación al visitante y persiste
    el mensaje en la base de datos.
    """

    def test_envio_valido_registra_mensaje_y_muestra_confirmacion(self):
        # Paso 1: GET inicializa el reto CAPTCHA en sesión
        self.client.get("/portal/contacto/")
        answer = self.client.session.get(SECURITY_ANSWER_KEY)

        # Paso 2: POST con datos válidos y CAPTCHA correcto
        response = self.client.post(
            "/portal/contacto/",
            {
                "nombre": "Ana Lopez",
                "email": "ana@test.local",
                "telefono": "4431000001",
                "asunto": "PCB-012 solicitud",
                "mensaje": "Mensaje de prueba para PCB-012.",
                "security_answer": answer,
            },
            follow=True,
        )

        # Confirmación visible al visitante
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Listo. Recibimos tu mensaje")

        # Mensaje persistido en base de datos
        from apps.public_portal.models import MensajeContacto
        self.assertTrue(
            MensajeContacto.objects.filter(
                email="ana@test.local",
                asunto="PCB-012 solicitud",
            ).exists()
        )


# ---------------------------------------------------------------------------
# PCB-013 – Doble envío de correo en formulario de contacto
# ---------------------------------------------------------------------------

@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@test.local",
    CONTACT_EMAIL="institucional@test.local",
    SITE_NAME="CCENT Test",
)
class PCB013ContactEmailDualSendTests(TestCase):
    """PCB-013 – Doble envío de correo en formulario de contacto.

    Verifica que, tras un envío válido:
      1. El mensaje queda persistido en MensajeContacto.
      2. Se envía una notificación al correo institucional (CONTACT_EMAIL).
      3. Se envía un acuse de recibo al correo del remitente del formulario.
    """

    def _post_valid_contact(self, email="remitente@test.local"):
        """GET para inicializar CAPTCHA + POST con datos válidos."""
        self.client.get("/portal/contacto/")
        answer = self.client.session.get(SECURITY_ANSWER_KEY)
        return self.client.post(
            "/portal/contacto/",
            {
                "nombre": "Docente Prueba",
                "email": email,
                "telefono": "4431000099",
                "asunto": "Consulta sobre horarios",
                "mensaje": "Necesito información sobre los horarios del siguiente ciclo.",
                "security_answer": answer,
            },
            follow=True,
        )

    def test_mensaje_persistido_en_bd(self):
        """El mensaje queda guardado en MensajeContacto."""
        from apps.public_portal.models import MensajeContacto
        self._post_valid_contact()
        self.assertTrue(
            MensajeContacto.objects.filter(
                email="remitente@test.local").exists()
        )

    def test_se_envian_exactamente_dos_correos(self):
        """Se generan exactamente 2 mensajes en el outbox (institucional + acuse)."""
        from django.core import mail as django_mail
        self._post_valid_contact()
        self.assertEqual(len(django_mail.outbox), 2)

    def test_notificacion_va_al_correo_institucional(self):
        """El primer correo llega a CONTACT_EMAIL con el asunto del formulario."""
        from django.core import mail as django_mail
        self._post_valid_contact()
        institucionales = [
            m for m in django_mail.outbox
            if "institucional@test.local" in m.recipients()
        ]
        self.assertEqual(len(institucionales), 1)
        self.assertIn("Consulta sobre horarios", institucionales[0].subject)
        self.assertIn("Docente Prueba", institucionales[0].body)
        self.assertIn("remitente@test.local", institucionales[0].body)

    def test_acuse_va_al_correo_del_remitente(self):
        """El acuse de recibo llega al correo que el visitante capturó en el formulario."""
        from django.core import mail as django_mail
        self._post_valid_contact()
        acuses = [
            m for m in django_mail.outbox
            if "remitente@test.local" in m.recipients()
        ]
        self.assertEqual(len(acuses), 1)
        self.assertIn("Recibimos tu mensaje", acuses[0].subject)
        self.assertIn("Docente Prueba", acuses[0].body)

    def test_fallo_smtp_institucional_no_bloquea_acuse(self):
        """Si el envío institucional falla, el acuse al remitente se intenta igualmente."""
        from django.core import mail as django_mail
        from unittest.mock import patch

        call_count = {"n": 0}
        original_send = __import__(
            "django.core.mail", fromlist=["send_mail"]
        ).send_mail

        def patched_send_mail(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ConnectionRefusedError("SMTP no disponible")
            return original_send(*args, **kwargs)

        with patch("apps.public_portal.views.send_mail", side_effect=patched_send_mail):
            self.client.get("/portal/contacto/")
            answer = self.client.session.get(SECURITY_ANSWER_KEY)
            self.client.post(
                "/portal/contacto/",
                {
                    "nombre": "Docente B",
                    "email": "docenteb@test.local",
                    "telefono": "",
                    "asunto": "Prueba fallo SMTP",
                    "mensaje": "Test de independencia de envíos.",
                    "security_answer": answer,
                },
                follow=True,
            )

        # Solo el acuse (2ª llamada) llega al outbox real del locmem backend
        self.assertEqual(len(django_mail.outbox), 1)
        self.assertIn("docenteb@test.local",
                      django_mail.outbox[0].recipients())
