from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.sales.models import Concepto


class CatalogoVentasGestionTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
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

    def _comercial_user(self, username="comercial_hu029"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_comercial)
        return user

    def test_admin_comercial_can_create_concepto_con_auditoria(self):
        user = self._comercial_user()
        self.client.force_login(user)

        response = self.client.post(
            "/panel/ventas/catalogo/",
            {
                "nombre": "Colegiatura Mensual",
                "precio": "1500.00",
                "activo": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        concepto = Concepto.objects.get(nombre="Colegiatura Mensual")
        self.assertEqual(concepto.precio, Decimal("1500.00"))
        self.assertTrue(concepto.activo)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="CATALOGO::CONCEPTO_CREATE",
                entidad="Concepto",
                entidad_id=str(concepto.pk),
                detalle__nombre="Colegiatura Mensual",
            ).exists()
        )

    def test_admin_comercial_can_update_concepto_con_auditoria(self):
        user = self._comercial_user("comercial_hu029_upd")
        concepto = Concepto.objects.create(
            nombre="Material Basico",
            precio=Decimal("450.00"),
            activo=True,
        )
        self.client.force_login(user)

        response = self.client.post(
            "/panel/ventas/catalogo/",
            {
                "concepto_id": str(concepto.pk),
                "nombre": "Material Premium",
                "precio": "650.00",
            },
        )

        self.assertEqual(response.status_code, 302)
        concepto.refresh_from_db()
        self.assertEqual(concepto.nombre, "Material Premium")
        self.assertEqual(concepto.precio, Decimal("650.00"))
        self.assertFalse(concepto.activo)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="CATALOGO::CONCEPTO_UPDATE",
                entidad="Concepto",
                entidad_id=str(concepto.pk),
                detalle__nombre="Material Premium",
                detalle__activo=False,
            ).exists()
        )

    def test_admin_comercial_can_toggle_activo(self):
        user = self._comercial_user("comercial_hu029_toggle")
        concepto = Concepto.objects.create(
            nombre="Servicio Extra",
            precio=Decimal("300.00"),
            activo=True,
        )
        self.client.force_login(user)

        response = self.client.post(
            "/panel/ventas/catalogo/",
            {"toggle_id": str(concepto.pk)},
        )

        self.assertEqual(response.status_code, 302)
        concepto.refresh_from_db()
        self.assertFalse(concepto.activo)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="CATALOGO::CONCEPTO_TOGGLE",
                entidad="Concepto",
                entidad_id=str(concepto.pk),
                detalle__activo=False,
            ).exists()
        )

    def test_admin_comercial_can_delete_concepto(self):
        user = self._comercial_user("comercial_hu029_delete")
        concepto = Concepto.objects.create(
            nombre="Concepto Eliminable",
            precio=Decimal("125.00"),
            activo=True,
        )
        self.client.force_login(user)

        response = self.client.post(
            "/panel/ventas/catalogo/",
            {"delete_id": str(concepto.pk)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Concepto.objects.filter(pk=concepto.pk).exists())
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="CATALOGO::CONCEPTO_DELETE",
                entidad="Concepto",
                entidad_id=str(concepto.pk),
                detalle__nombre="Concepto Eliminable",
            ).exists()
        )

    def test_usuario_sin_rol_comercial_recibe_403(self):
        user = self.user_model.objects.create_user(
            username="alumno_hu029",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_alumno)
        self.client.force_login(user)

        response = self.client.get("/panel/ventas/catalogo/")

        self.assertEqual(response.status_code, 403)
