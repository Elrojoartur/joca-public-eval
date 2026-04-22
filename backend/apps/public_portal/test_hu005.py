"""
Pruebas de caja negra para HU-005: Enviar mensaje de contacto con CAPTCHA.
Valida los escenarios de entrada y salida especificados en el plan de testing.
"""

from django.core import mail
from django.test import TestCase, Client, override_settings
from django.conf import settings
from apps.public_portal.models import MensajeContacto


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class HU005ContactoConCaptchaTests(TestCase):
    """
    Pruebas de caja negra para la funcionalidad de contacto con validación de seguridad.

    Escenarios:
    P1: Datos válidos (nombre, correo, asunto, mensaje) → Envío exitoso
    P2: Correo inválido → Error de formato
    P3: Mensaje vacío → Error de campo obligatorio
    P4: Respuesta de seguridad incorrecta → Rechazo del envío
    """

    def setUp(self):
        self.client = Client()
        self.contact_url = "/portal/contacto/"

    def _get_security_question_and_answer(self):
        """Obtener la pregunta de seguridad y respuesta registrada en sesión."""
        # Hacer GET al formulario para obtener la pregunta
        response = self.client.get(self.contact_url)
        self.assertEqual(response.status_code, 200)

        # La sesión debe tener la respuesta
        session = self.client.session
        security_answer = session.get("portal_contact_security_answer", "")
        return security_answer

    def test_p1_envio_exitoso_con_datos_validos(self):
        """
        P1: nombre válido, correo válido, teléfono opcional, asunto válido, mensaje válido, respuesta de seguridad correcta
        Resultado esperado: Mensaje enviado correctamente y confirmación visible.
        """
        security_answer = self._get_security_question_and_answer()

        response = self.client.post(self.contact_url, {
            "nombre": "Juan Pérez",
            "email": "juan.perez@example.com",
            "telefono": "5551234567",
            "asunto": "Información sobre cursos",
            "mensaje": "Me gustaría conocer más sobre los programas disponibles.",
            "security_answer": security_answer,
        }, follow=True)

        # Verificar que la respuesta es 200 (éxito)
        self.assertEqual(response.status_code, 200)

        # Verificar que hay un mensaje de éxito
        messages = list(response.context["messages"])
        self.assertTrue(any("Listo" in str(m) for m in messages))

        # Verificar que el mensaje se guardó en BD
        self.assertTrue(MensajeContacto.objects.filter(
            nombre="Juan Pérez",
            email="juan.perez@example.com"
        ).exists())

        # Verificar que se enviaron los dos correos: notificación interna + acuse al remitente
        self.assertEqual(len(mail.outbox), 2)
        destinatarios = [msg.to[0] for msg in mail.outbox]
        self.assertIn("juan.perez@example.com", destinatarios)

    def test_p2_error_con_correo_invalido(self):
        """
        P2: correo inválido
        Resultado esperado: Mensaje de error por formato de correo.
        """
        response = self.client.post(self.contact_url, {
            "nombre": "Juan Pérez",
            "email": "correo_invalido",  # Sin @
            "telefono": "5551234567",
            "asunto": "Información",
            "mensaje": "Mensaje de prueba",
            "security_answer": "12345",
        })

        # Verificar que devuelve la forma nuevamente (no redirige)
        self.assertIn("contact_form", response.context)

        # Verificar que hay error en el campo email
        form = response.context["contact_form"]
        self.assertTrue(form.errors.get("email"))

        # NO debe guardarse en BD
        self.assertEqual(MensajeContacto.objects.filter(
            email="correo_invalido"
        ).count(), 0)

    def test_p3_error_con_mensaje_vacio(self):
        """
        P3: mensaje vacío
        Resultado esperado: Mensaje de campo obligatorio.
        """
        security_answer = self._get_security_question_and_answer()

        response = self.client.post(self.contact_url, {
            "nombre": "Juan Pérez",
            "email": "juan.perez@example.com",
            "telefono": "",
            "asunto": "Información",
            "mensaje": "",  # Vacío
            "security_answer": security_answer,
        })

        # Verificar que hay error en el campo mensaje
        form = response.context["contact_form"]
        self.assertTrue(form.errors.get("mensaje"))

        # NO debe guardarse en BD
        self.assertEqual(MensajeContacto.objects.count(), 0)

    def test_p4_rechazo_por_respuesta_seguridad_incorrecta(self):
        """
        P4: Respuesta de seguridad (CAPTCHA) incorrecto
        Resultado esperado: Rechazo del envío por CAPTCHA inválido.
        """
        security_answer = self._get_security_question_and_answer()
        respuesta_incorrecta = "RESPUESTA_INCORRECTA_DELIBERADA"

        response = self.client.post(self.contact_url, {
            "nombre": "Juan Pérez",
            "email": "juan.perez@example.com",
            "telefono": "5551234567",
            "asunto": "Información",
            "mensaje": "Mensaje de prueba",
            "security_answer": respuesta_incorrecta,  # INCORRECTA
        })

        # Verificar que hay error en security_answer
        form = response.context["contact_form"]
        self.assertTrue(form.errors.get("security_answer"))

        # NO debe guardarse en BD
        self.assertEqual(MensajeContacto.objects.count(), 0)

    def test_mensaje_guardado_tiene_datos_correctos(self):
        """
        Validar que el mensaje guardado en BD contiene todos los datos correctamente.
        """
        security_answer = self._get_security_question_and_answer()

        self.client.post(self.contact_url, {
            "nombre": "Arturo López",
            "email": "arturo@test.com",
            "telefono": "5554445555",
            "asunto": "Consulta académica",
            "mensaje": "¿Cuáles son los horarios disponibles?",
            "security_answer": security_answer,
        })

        # Verificar que el mensaje existe con los datos correctos
        msg = MensajeContacto.objects.get(email="arturo@test.com")
        self.assertEqual(msg.nombre, "Arturo López")
        self.assertEqual(msg.telefono, "5554445555")
        self.assertEqual(msg.asunto, "Consulta académica")
        self.assertEqual(msg.mensaje, "¿Cuáles son los horarios disponibles?")
        self.assertFalse(msg.leido)  # No debe estar marcado como leído

        # Verificar que se enviaron los dos correos del flujo de contacto
        self.assertEqual(len(mail.outbox), 2)
        self.assertIsNotNone(msg.enviado_en)  # Debe tener timestamp

    def test_nombre_obligatorio(self):
        """Validar que el nombre es obligatorio."""
        security_answer = self._get_security_question_and_answer()

        response = self.client.post(self.contact_url, {
            "nombre": "",  # Vacío
            "email": "test@test.com",
            "asunto": "Asunto",
            "mensaje": "Mensaje",
            "security_answer": security_answer,
        })

        form = response.context["contact_form"]
        self.assertTrue(form.errors.get("nombre"))

    def test_correo_obligatorio(self):
        """Validar que el correo es obligatorio."""
        security_answer = self._get_security_question_and_answer()

        response = self.client.post(self.contact_url, {
            "nombre": "Nombre",
            "email": "",  # Vacío
            "asunto": "Asunto",
            "mensaje": "Mensaje",
            "security_answer": security_answer,
        })

        form = response.context["contact_form"]
        self.assertTrue(form.errors.get("email"))

    def test_telefono_es_opcional(self):
        """Validar que el teléfono es opcional."""
        security_answer = self._get_security_question_and_answer()

        response = self.client.post(self.contact_url, {
            "nombre": "Nombre",
            "email": "test@test.com",
            "telefono": "",  # Vacío pero debe permitirse
            "asunto": "Asunto",
            "mensaje": "Mensaje",
            "security_answer": security_answer,
        }, follow=True)

        # Debe haber sídio exitoso
        self.assertEqual(response.status_code, 200)
        self.assertTrue(MensajeContacto.objects.filter(
            email="test@test.com"
        ).exists())
