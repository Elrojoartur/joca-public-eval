from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria, ParametroSistema, RespaldoSistema


class RespaldosAuditoriaTests(TestCase):
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

    def test_director_puede_generar_respaldo_y_audita(self):
        director = self._user_with_role("director_hu038", self.rol_director)
        ParametroSistema.objects.create(
            categoria=ParametroSistema.CATEGORIA_INSTITUCION,
            clave="institucion_nombre",
            valor="CCENT",
            activo=True,
        )
        self.client.force_login(director)

        response = self.client.post(
            "/panel/gobierno/respaldos/",
            {
                "accion": "generar",
                "notas": "Respaldo previo a cambios",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        respaldo = RespaldoSistema.objects.first()
        self.assertIsNotNone(respaldo)
        self.assertEqual(respaldo.estado, RespaldoSistema.ESTADO_GENERADO)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::RESPALDO_GENERAR",
                entidad="RespaldoSistema",
                entidad_id=str(respaldo.pk),
            ).exists()
        )

    def test_director_puede_restaurar_parametros_desde_respaldo(self):
        director = self._user_with_role(
            "director_hu038_restore", self.rol_director)
        ParametroSistema.objects.create(
            categoria=ParametroSistema.CATEGORIA_INSTITUCION,
            clave="institucion_nombre",
            valor="ANTES",
            activo=True,
        )
        respaldo = RespaldoSistema.objects.create(
            nombre="backup-demo-hu038",
            checksum="a" * 64,
            payload={
                "parametros": [
                    {
                        "categoria": ParametroSistema.CATEGORIA_INSTITUCION,
                        "clave": "institucion_nombre",
                        "valor": "DESPUES",
                        "activo": True,
                    }
                ],
                "auditoria": {"total_eventos": 0},
            },
            generado_por=director,
        )
        self.client.force_login(director)

        response = self.client.post(
            "/panel/gobierno/respaldos/",
            {
                "accion": "restaurar",
                "respaldo_id": str(respaldo.pk),
                "confirmar": "SI",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ParametroSistema.objects.get(clave="institucion_nombre").valor,
            "DESPUES",
        )
        respaldo.refresh_from_db()
        self.assertEqual(respaldo.estado, RespaldoSistema.ESTADO_RESTAURADO)
        self.assertIsNotNone(respaldo.restaurado_en)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="GOBIERNO::RESPALDO_RESTAURAR",
                entidad="RespaldoSistema",
                entidad_id=str(respaldo.pk),
            ).exists()
        )

    def test_alumno_no_puede_acceder_a_respaldos(self):
        alumno = self._user_with_role("alumno_hu038", self.rol_alumno)
        self.client.force_login(alumno)

        response = self.client.get("/panel/gobierno/respaldos/")

        self.assertEqual(response.status_code, 403)
