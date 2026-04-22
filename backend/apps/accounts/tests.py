from unittest.mock import Mock

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.models import Session
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from apps.accounts.admin import RolAdmin, RolPermisosForm, UsuarioAdmin
from apps.accounts.models import Rol, UsuarioRol
from apps.accounts.forms import UsuarioChangeForm, UsuarioCreateForm
from apps.governance.models import EventoAuditoria, Permiso, RolPermiso


class UsuarioFormsTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user_model.objects.create_user(
            username="existing_user",
            email="existing_user@test.local",
            password="Pass12345!",
        )

    def test_usuario_create_form_rejects_duplicate_username_and_email(self):
        form = UsuarioCreateForm(
            data={
                "username": "existing_user",
                "email": "existing_user@test.local",
                "first_name": "Test",
                "last_name": "User",
                "password1": "Pass12345!",
                "password2": "Pass12345!",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
        self.assertIn("email", form.errors)

    def test_usuario_change_form_preserves_username_and_email(self):
        user = self.user_model.objects.create_user(
            username="stable_user",
            email="stable_user@test.local",
            password="Pass12345!",
            first_name="Before",
        )

        form = UsuarioChangeForm(
            data={
                "username": "hacked_username",
                "email": "hacked_email@test.local",
                "first_name": "After",
                "last_name": "User",
                "is_active": True,
                "is_staff": False,
                "password": user.password,
            },
            instance=user,
        )

        self.assertTrue(form.is_valid(), form.errors)
        updated = form.save()
        self.assertEqual(updated.username, "stable_user")
        self.assertEqual(updated.email, "stable_user@test.local")
        self.assertEqual(updated.first_name, "After")

    def test_create_user_stores_password_hashed(self):
        raw_password = "Pass12345!"
        user = self.user_model.objects.create_user(
            username="hash_check_user",
            email="hash_check_user@test.local",
            password=raw_password,
        )

        self.assertNotEqual(user.password, raw_password)
        self.assertTrue(user.password.startswith("pbkdf2_")
                        or user.password.startswith("scrypt$"))
        self.assertTrue(user.check_password(raw_password))


class UsuarioAdminLifecycleTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.factory = RequestFactory()
        self.superuser = self.user_model.objects.create_superuser(
            username="admin_root",
            email="admin_root@test.local",
            password="Pass12345!",
        )
        self.admin_obj = UsuarioAdmin(self.user_model, admin.site)

    def _request(self, method="post", path="/admin/", data=None):
        req_factory = self.factory.post if method == "post" else self.factory.get
        request = req_factory(path, data or {})
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        request.user = self.superuser
        return request

    def test_save_model_create_generates_audit_event(self):
        request = self._request(data={"motivo": "alta inicial"})
        new_user = self.user_model(
            username="created_by_admin",
            email="created_by_admin@test.local",
        )
        new_user.set_password("Pass12345!")

        self.admin_obj.save_model(
            request,
            new_user,
            form=Mock(changed_data=[], cleaned_data={}),
            change=False,
        )

        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="USER_CREATE",
                entidad="User",
                entidad_id=str(new_user.pk),
                resultado="OK",
            ).exists()
        )

    def test_save_model_update_generates_audit_event(self):
        user = self.user_model.objects.create_user(
            username="editable_user",
            email="editable_user@test.local",
            password="Pass12345!",
            first_name="Before",
        )
        request = self._request(data={"motivo": "edicion"})

        user.first_name = "After"
        form = Mock(
            changed_data=["first_name"],
            cleaned_data={"first_name": "After"},
        )

        self.admin_obj.save_model(request, user, form=form, change=True)
        user.refresh_from_db()

        audit_event = EventoAuditoria.objects.filter(
            accion="USER_UPDATE",
            entidad="User",
            entidad_id=str(user.pk),
            resultado="OK",
        ).first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(user.first_name, "After")
        self.assertEqual(
            audit_event.detalle.get("cambios", {}).get(
                "first_name", {}).get("despues"),
            "After",
        )

    def test_get_readonly_fields_for_existing_user_includes_username_and_email(self):
        request = self._request(method="get")
        user = self.user_model.objects.create_user(
            username="readonly_target",
            email="readonly_target@test.local",
            password="Pass12345!",
        )

        readonly_fields = self.admin_obj.get_readonly_fields(request, obj=user)

        self.assertIn("username", readonly_fields)
        self.assertIn("email", readonly_fields)

    def test_desactivar_disables_user_revokes_sessions_and_audits(self):
        user = self.user_model.objects.create_user(
            username="to_disable",
            email="to_disable@test.local",
            password="Pass12345!",
        )
        self.client.force_login(user)
        self.assertTrue(Session.objects.exists())

        request = self._request(data={"motivo": "baja operativa"})
        self.admin_obj.desactivar(
            request, self.user_model.objects.filter(pk=user.pk))

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        active_session_user_ids = [
            s.get_decoded().get("_auth_user_id")
            for s in Session.objects.filter(expire_date__isnull=False)
        ]
        self.assertNotIn(str(user.pk), active_session_user_ids)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="USER_DEACTIVATE",
                entidad="User",
                entidad_id=str(user.pk),
                detalle__motivo="baja operativa",
                resultado="OK",
            ).exists()
        )

    def test_activar_reenables_user_and_audits(self):
        user = self.user_model.objects.create_user(
            username="to_enable",
            email="to_enable@test.local",
            password="Pass12345!",
            is_active=False,
        )
        request = self._request(data={"motivo": "reactivacion"})

        self.admin_obj.activar(
            request, self.user_model.objects.filter(pk=user.pk))

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="USER_ACTIVATE",
                entidad="User",
                entidad_id=str(user.pk),
                detalle__motivo="reactivacion",
                resultado="OK",
            ).exists()
        )


class RolPermisosAdminTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.factory = RequestFactory()
        self.superuser = self.user_model.objects.create_superuser(
            username="roles_admin",
            email="roles_admin@test.local",
            password="Pass12345!",
        )
        self.rol_admin = RolAdmin(Rol, admin.site)
        self.perm_1 = Permiso.objects.create(
            codigo="PERM_VIEW_USERS",
            nombre="Ver usuarios",
            modulo="MOD-03",
        )
        self.perm_2 = Permiso.objects.create(
            codigo="PERM_EDIT_USERS",
            nombre="Editar usuarios",
            modulo="MOD-03",
        )

    def _request(self):
        request = self.factory.post("/admin/accounts/rol/")
        request.user = self.superuser
        return request

    def test_rol_permisos_form_updates_assignments_and_diff(self):
        rol = Rol.objects.create(
            nombre="Control Escolar", codigo="CTRL_ESC", activo=True)
        RolPermiso.objects.create(rol=rol, permiso=self.perm_1)

        form = RolPermisosForm(
            data={
                "nombre": rol.nombre,
                "codigo": rol.codigo,
                "activo": True,
                "permisos": [str(self.perm_2.pk)],
            },
            instance=rol,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.assertFalse(RolPermiso.objects.filter(
            rol=rol, permiso=self.perm_1).exists())
        self.assertTrue(RolPermiso.objects.filter(
            rol=rol, permiso=self.perm_2).exists())
        self.assertEqual(form._perm_diff["antes"], [self.perm_1.codigo])
        self.assertEqual(form._perm_diff["despues"], [self.perm_2.codigo])

    def test_rol_admin_save_model_logs_permission_audit_when_diff_present(self):
        rol = Rol.objects.create(
            nombre="Operacion", codigo="OPER", activo=True)
        request = self._request()
        mock_form = Mock(
            _perm_diff={"antes": ["PERM_VIEW_USERS"], "despues": ["PERM_EDIT_USERS"]})

        self.rol_admin.save_model(request, rol, mock_form, change=True)

        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ROL_PERMISOS_UPDATE",
                entidad="Rol",
                entidad_id=str(rol.pk),
                resultado="OK",
                detalle__antes=["PERM_VIEW_USERS"],
                detalle__despues=["PERM_EDIT_USERS"],
            ).exists()
        )


# ---------------------------------------------------------------------------
# HU-018 / HU-019 — Flujos de usuario vía panel de gobierno
# ---------------------------------------------------------------------------

class GobiernoUsuariosVistaTests(TestCase):
    """HU-018/019 — Verifica los flujos de alta, edición y cambio de estado
    de usuarios a través de las vistas del panel de gobierno."""

    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(
            username="superadmin_gov_hu018",
            email="superadmin_gov_hu018@test.local",
            password="Pass12345!",
        )
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )

    def test_panel_crea_usuario_director_audita_y_asigna_rol(self):
        """POST /panel/gobierno/usuarios/nuevo/ crea usuario con rol y genera auditoría."""
        self.client.force_login(self.superuser)

        response = self.client.post(
            "/panel/gobierno/usuarios/nuevo/",
            {
                "email": "nuevo.director.gov@test.local",
                "first_name": "Nuevo",
                "last_name": "Director",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
                "rol_inicial": str(self.rol_director.pk),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        User = get_user_model()
        usuario = User.objects.filter(
            email="nuevo.director.gov@test.local").first()
        self.assertIsNotNone(usuario)
        self.assertTrue(
            UsuarioRol.objects.filter(
                usuario=usuario, rol=self.rol_director).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::USUARIO_ALTA",
                entidad="User",
                resultado="ok",
                detalle__rol="DIRECTOR_ESCOLAR",
            ).exists()
        )

    def test_panel_edita_usuario_actualiza_nombre_y_audita(self):
        """POST /panel/gobierno/usuarios/<pk>/editar/ actualiza nombre y audita."""
        User = get_user_model()
        target = User.objects.create_user(
            username="target_edit_gov",
            email="target_edit_gov@test.local",
            password="Pass12345!",
            first_name="Original",
        )
        self.client.force_login(self.superuser)

        response = self.client.post(
            f"/panel/gobierno/usuarios/{target.pk}/editar/",
            {"first_name": "Editado", "last_name": "Apellido"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        self.assertEqual(target.first_name, "Editado")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::USUARIO_EDITAR",
                entidad="User",
                entidad_id=str(target.pk),
                resultado="ok",
            ).exists()
        )

    def test_panel_estado_toggle_desactiva_usuario_activo(self):
        """POST /panel/gobierno/usuarios/<pk>/estado/ invierte is_active y audita."""
        User = get_user_model()
        target = User.objects.create_user(
            username="target_estado_gov",
            email="target_estado_gov@test.local",
            password="Pass12345!",
            is_active=True,
        )
        self.client.force_login(self.superuser)

        response = self.client.post(
            f"/panel/gobierno/usuarios/{target.pk}/estado/",
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::USUARIO_ESTADO",
                entidad="User",
                entidad_id=str(target.pk),
                resultado="ok",
                detalle__is_active=False,
            ).exists()
        )
