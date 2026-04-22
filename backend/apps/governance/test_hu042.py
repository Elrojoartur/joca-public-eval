from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria, ParametroSistema


class ExportarBitacoraEvidenciasTests(TestCase):
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

    def test_director_exporta_auditoria_csv_con_hash(self):
        director = self._user_with_role(
            "director_hu042_csv", self.rol_director)
        EventoAuditoria.objects.create(
            accion="GOBIERNO::TEST_EVENT",
            entidad="ParametroSistema",
            entidad_id="smtp",
            resultado="ok",
            detalle={"k": "v"},
        )
        ParametroSistema.objects.create(
            categoria=ParametroSistema.CATEGORIA_SMTP,
            clave="smtp_host",
            valor="smtp.test.local",
            activo=True,
        )
        self.client.force_login(director)

        response = self.client.get("/panel/gobierno/auditoria/?export=csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("X-Export-SHA256", response)
        payload = response.content.decode("utf-8")
        self.assertIn("GOBIERNO::TEST_EVENT", payload)
        self.assertIn("smtp_host", payload)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::AUDITORIA_EXPORT",
                entidad="EventoAuditoria",
                resultado="ok",
                detalle__format="csv",
            ).exists()
        )

    def test_director_exporta_auditoria_pdf_con_hash(self):
        director = self._user_with_role(
            "director_hu042_pdf", self.rol_director)
        EventoAuditoria.objects.create(
            accion="GOBIERNO::TEST_PDF",
            entidad="RespaldoSistema",
            entidad_id="1",
            resultado="ok",
            detalle={"ok": True},
        )
        self.client.force_login(director)

        response = self.client.get("/panel/gobierno/auditoria/?export=pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("X-Export-SHA256", response)
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::AUDITORIA_EXPORT",
                entidad="EventoAuditoria",
                resultado="ok",
                detalle__format="pdf",
            ).exists()
        )

    def test_alumno_no_puede_exportar_auditoria(self):
        alumno = self._user_with_role("alumno_hu042", self.rol_alumno)
        self.client.force_login(alumno)

        response = self.client.get("/panel/gobierno/auditoria/?export=csv")

        self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# HU-042 — Verificación de integridad del hash SHA256 de la exportación
# ---------------------------------------------------------------------------

class BitacoraSHA256IntegridadTests(TestCase):
    """HU-042 — Verifica que el header X-Export-SHA256 coincide exactamente
    con el hash SHA256 calculado sobre el cuerpo de la respuesta."""

    def setUp(self):
        User = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.director = User.objects.create_user(
            username="director_sha256_integridad",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=self.director, rol=self.rol_director)

    def test_sha256_header_csv_coincide_con_hash_del_cuerpo(self):
        """El header X-Export-SHA256 del CSV es el SHA256 real del cuerpo de la respuesta."""
        import hashlib

        EventoAuditoria.objects.create(
            accion="SHA256::INTEGRIDAD_CSV",
            entidad="User",
            resultado="ok",
            detalle={},
        )
        self.client.force_login(self.director)

        response = self.client.get("/panel/gobierno/auditoria/?export=csv")

        self.assertEqual(response.status_code, 200)
        header_hash = response["X-Export-SHA256"]
        computed_hash = hashlib.sha256(response.content).hexdigest()
        self.assertEqual(
            header_hash,
            computed_hash,
            msg="El hash SHA256 del header no coincide con el contenido real del CSV.",
        )

    def test_sha256_header_pdf_coincide_con_hash_del_cuerpo(self):
        """El header X-Export-SHA256 del PDF es el SHA256 real del cuerpo de la respuesta."""
        import hashlib

        self.client.force_login(self.director)

        response = self.client.get("/panel/gobierno/auditoria/?export=pdf")

        self.assertEqual(response.status_code, 200)
        header_hash = response["X-Export-SHA256"]
        computed_hash = hashlib.sha256(response.content).hexdigest()
        self.assertEqual(
            header_hash,
            computed_hash,
            msg="El hash SHA256 del header no coincide con el contenido real del PDF.",
        )
