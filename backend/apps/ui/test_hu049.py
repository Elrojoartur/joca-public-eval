from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria, ParametroSistema


class GuardarVistasFavoritasTableroHU049Tests(TestCase):
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

    def test_director_guarda_vistas_favoritas_del_tablero(self):
        director = self._user_with_role("director_hu049", self.rol_director)
        self.client.force_login(director)

        response = self.client.post(
            "/panel/reportes/",
            {
                "favorite_views": ["ejecutivo", "comercial", "comercial", "invalida"],
            },
        )

        self.assertEqual(response.status_code, 200)
        key = f"reportes_tablero_favoritos_u{director.id}"
        favorito = ParametroSistema.objects.get(
            categoria=ParametroSistema.CATEGORIA_REPORTES,
            clave=key,
        )
        self.assertEqual(favorito.valor, "ejecutivo,comercial")
        self.assertContains(response, "Accesos favoritos")
        self.assertContains(response, "Tablero ejecutivo")
        self.assertContains(response, "Reporte comercial")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="REPORTES::FAVORITOS_TABLERO_UPDATE",
                entidad="ParametroSistema",
                entidad_id=key,
                resultado="ok",
            ).exists()
        )

    def test_director_ve_favoritas_guardadas_en_get(self):
        director = self._user_with_role(
            "director_hu049_get", self.rol_director)
        ParametroSistema.objects.update_or_create(
            categoria=ParametroSistema.CATEGORIA_REPORTES,
            clave=f"reportes_tablero_favoritos_u{director.id}",
            defaults={
                "valor": "comercial,ejecutivo",
                "activo": True,
            },
        )

        self.client.force_login(director)
        response = self.client.get("/panel/reportes/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accesos favoritos")
        self.assertContains(response, "Reporte comercial")
        self.assertContains(response, "Tablero ejecutivo")

    def test_alumno_no_puede_guardar_favoritas_del_tablero(self):
        alumno = self._user_with_role("alumno_hu049", self.rol_alumno)
        self.client.force_login(alumno)

        response = self.client.post(
            "/panel/reportes/",
            {
                "favorite_views": ["ejecutivo", "comercial"],
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ParametroSistema.objects.filter(
                categoria=ParametroSistema.CATEGORIA_REPORTES,
                clave=f"reportes_tablero_favoritos_u{alumno.id}",
            ).exists()
        )
