from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria


class GovernanceAuditViewTests(TestCase):
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

    def test_gobierno_auditoria_requires_allowed_role(self):
        user = self._user_with_role("alumno_auditoria", self.rol_alumno)
        self.client.force_login(user)

        response = self.client.get("/panel/gobierno/auditoria/")

        self.assertEqual(response.status_code, 403)

    def test_gobierno_auditoria_lists_latest_200_events(self):
        for idx in range(205):
            EventoAuditoria.objects.create(
                accion=f"TEST::{idx:03}",
                entidad="Sesion",
                entidad_id=str(idx),
                resultado="ok",
                detalle={"idx": idx},
            )

        user = self._user_with_role("director_auditoria", self.rol_director)
        self.client.force_login(user)

        response = self.client.get("/panel/gobierno/auditoria/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bitácora de cambios")
        self.assertContains(response, "TEST::204")
        self.assertNotContains(response, "TEST::000")


# ---------------------------------------------------------------------------
# HU-017 — Filtros de la bitácora de auditoría
# ---------------------------------------------------------------------------

class BitacoraFiltrosTests(TestCase):
    """HU-017 — Verifica que los filtros de la vista de bitácora funcionan
    correctamente (por acción y por resultado)."""

    def setUp(self):
        User = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.director = User.objects.create_user(
            username="director_filtros_hu017",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=self.director, rol=self.rol_director)

    def test_bitacora_filtra_por_accion(self):
        """GET ?accion=EVENTO_A devuelve solo eventos que contengan ese texto."""
        EventoAuditoria.objects.create(
            accion="MODULO::EVENTO_A",
            entidad="User",
            resultado="ok",
            detalle={},
        )
        EventoAuditoria.objects.create(
            accion="MODULO::EVENTO_B",
            entidad="User",
            resultado="ok",
            detalle={},
        )
        self.client.force_login(self.director)

        response = self.client.get(
            "/panel/gobierno/auditoria/?accion=EVENTO_A")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MODULO::EVENTO_A")
        self.assertNotContains(response, "MODULO::EVENTO_B")

    def test_bitacora_filtra_por_resultado(self):
        """GET ?resultado=error devuelve solo eventos con resultado=error."""
        EventoAuditoria.objects.create(
            accion="ACCION::RESULTADO_OK",
            entidad="Sesion",
            resultado="ok",
            detalle={},
        )
        EventoAuditoria.objects.create(
            accion="ACCION::RESULTADO_ERR",
            entidad="Sesion",
            resultado="error",
            detalle={},
        )
        self.client.force_login(self.director)

        response = self.client.get(
            "/panel/gobierno/auditoria/?resultado=error")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ACCION::RESULTADO_ERR")
        self.assertNotContains(response, "ACCION::RESULTADO_OK")
