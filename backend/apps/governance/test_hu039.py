from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.sales.models import Concepto
from apps.school.models import Curso


class CatalogosMaestrosHU039Tests(TestCase):
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

    def test_director_administra_catalogos_academico_y_comercial(self):
        director = self._user_with_role("director_hu039", self.rol_director)
        self.client.force_login(director)

        resp_curso = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "catalogos",
                "operation": "create_curso",
                "curso_codigo": "ELEC-BAS",
                "curso_nombre": "Electronica Basica",
                "curso_descripcion": "Modulo inicial",
                "curso_activo": "on",
            },
            follow=True,
        )
        resp_concepto = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "catalogos",
                "operation": "create_concepto",
                "concepto_nombre": "Colegiatura HU039",
                "concepto_precio": "1250.00",
                "concepto_activo": "on",
            },
            follow=True,
        )

        self.assertEqual(resp_curso.status_code, 200)
        self.assertEqual(resp_concepto.status_code, 200)

        curso = Curso.objects.get(codigo="ELEC-BAS")
        concepto = Concepto.objects.get(nombre="Colegiatura HU039")

        self.assertEqual(curso.nombre, "Electronica Basica")
        self.assertTrue(curso.activo)
        self.assertEqual(concepto.precio, Decimal("1250.00"))
        self.assertTrue(concepto.activo)

        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::CATALOGOS_MAESTROS_CURSO_UPSERT",
                entidad="Curso",
                entidad_id=str(curso.id),
                resultado="ok",
            ).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::CATALOGOS_MAESTROS_CONCEPTO_UPSERT",
                entidad="Concepto",
                entidad_id=str(concepto.id),
                resultado="ok",
            ).exists()
        )

    def test_solo_desactivar_en_catalogo_comercial(self):
        director = self._user_with_role(
            "director_hu039_toggle", self.rol_director)
        concepto = Concepto.objects.create(
            nombre="Material HU039",
            precio=Decimal("50.00"),
            activo=True,
        )
        self.client.force_login(director)

        response = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "catalogos",
                "operation": "toggle_concepto",
                "concepto_id": str(concepto.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        concepto.refresh_from_db()
        self.assertFalse(concepto.activo)
        self.assertEqual(Concepto.objects.filter(
            nombre="Material HU039").count(), 1)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::CATALOGOS_MAESTROS_CONCEPTO_TOGGLE",
                entidad="Concepto",
                entidad_id=str(concepto.id),
                resultado="ok",
            ).exists()
        )

    def test_alumno_no_puede_administrar_catalogos_maestros(self):
        alumno = self._user_with_role("alumno_hu039", self.rol_alumno)
        self.client.force_login(alumno)

        response = self.client.post(
            "/panel/gobierno/parametros/",
            {
                "section": "catalogos",
                "operation": "create_curso",
                "curso_codigo": "FORB-001",
                "curso_nombre": "No permitido",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Curso.objects.filter(codigo="FORB-001").exists())
