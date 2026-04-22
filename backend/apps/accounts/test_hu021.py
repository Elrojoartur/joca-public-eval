from unittest.mock import Mock

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.accounts.admin import UsuarioAdmin
from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria


class UserRoleAssignmentAuditTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.factory = RequestFactory()
        self.superuser = self.user_model.objects.create_superuser(
            username="roles_owner",
            email="roles_owner@test.local",
            password="Pass12345!",
        )
        self.admin_obj = UsuarioAdmin(self.user_model, admin.site)

    def _request(self):
        request = self.factory.post("/admin/accounts/user/")
        request.user = self.superuser
        return request

    def test_save_related_logs_assigned_roles(self):
        user = self.user_model.objects.create_user(
            username="target_roles",
            email="target_roles@test.local",
            password="Pass12345!",
        )
        role_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        role_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )
        UsuarioRol.objects.create(usuario=user, rol=role_director)
        UsuarioRol.objects.create(usuario=user, rol=role_comercial)

        form = Mock(instance=user)
        form.save_m2m = Mock()

        self.admin_obj.save_related(self._request(), form, [], change=True)

        event = EventoAuditoria.objects.filter(
            accion="USER_ROLES_UPDATE",
            entidad="User",
            entidad_id=str(user.pk),
            resultado="OK",
        ).first()

        self.assertIsNotNone(event)
        self.assertEqual(
            set(event.detalle.get("roles", [])),
            {"DIRECTOR_ESCOLAR", "ADMINISTRATIVO_COMERCIAL"},
        )

    def test_save_related_logs_empty_roles_when_user_has_none(self):
        user = self.user_model.objects.create_user(
            username="target_without_roles",
            email="target_without_roles@test.local",
            password="Pass12345!",
        )
        form = Mock(instance=user)
        form.save_m2m = Mock()

        self.admin_obj.save_related(self._request(), form, [], change=True)

        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="USER_ROLES_UPDATE",
                entidad="User",
                entidad_id=str(user.pk),
                resultado="OK",
                detalle__roles=[],
            ).exists()
        )


# ---------------------------------------------------------------------------
# HU-021 — Asignación y retiro de roles vía panel de gobierno
# ---------------------------------------------------------------------------

class GobiernoRolesVistaTests(TestCase):
    """HU-021 — Verifica asignación, retiro y deduplicación de roles vía
    las vistas del panel de gobierno (no via admin)."""

    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(
            username="superadmin_roles_hu021",
            email="superadmin_roles_hu021@test.local",
            password="Pass12345!",
        )
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.target_user = User.objects.create_user(
            username="target_rol_panel_hu021",
            email="target_rol_panel_hu021@test.local",
            password="Pass12345!",
        )

    def test_panel_asignar_rol_crea_asignacion_y_audita(self):
        """POST /panel/gobierno/roles/asignar/ crea UsuarioRol y genera auditoría."""
        self.client.force_login(self.superuser)

        response = self.client.post(
            "/panel/gobierno/roles/asignar/",
            {
                "usuario_id": str(self.target_user.pk),
                "rol_id": str(self.rol_director.pk),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            UsuarioRol.objects.filter(
                usuario=self.target_user, rol=self.rol_director
            ).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::ROL_ASIGNAR",
                entidad="UsuarioRol",
                entidad_id=str(self.target_user.pk),
                resultado="ok",
                detalle__rol="Director Escolar",
            ).exists()
        )

    def test_panel_retirar_rol_elimina_asignacion_y_audita(self):
        """POST /panel/gobierno/roles/<pk>/retirar/ elimina UsuarioRol y audita."""
        asignacion = UsuarioRol.objects.create(
            usuario=self.target_user, rol=self.rol_director
        )
        self.client.force_login(self.superuser)

        response = self.client.post(
            f"/panel/gobierno/roles/{asignacion.pk}/retirar/",
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            UsuarioRol.objects.filter(pk=asignacion.pk).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::ROL_RETIRAR",
                entidad="UsuarioRol",
                resultado="ok",
                detalle__rol="Director Escolar",
            ).exists()
        )

    def test_panel_asignar_rol_duplicado_no_genera_segundo_registro(self):
        """Asignar un rol que ya posee el usuario genera warning, no un duplicado."""
        UsuarioRol.objects.create(
            usuario=self.target_user, rol=self.rol_director)
        self.client.force_login(self.superuser)

        self.client.post(
            "/panel/gobierno/roles/asignar/",
            {
                "usuario_id": str(self.target_user.pk),
                "rol_id": str(self.rol_director.pk),
            },
        )

        self.assertEqual(
            UsuarioRol.objects.filter(
                usuario=self.target_user, rol=self.rol_director
            ).count(),
            1,
        )
