from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.school.models import Curso, Docente, DocenteGrupo, Grupo, Periodo


class GruposAdministracionFlowTests(TestCase):
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
        self.curso = Curso.objects.create(
            codigo="curso-prueba",
            nombre="Curso Prueba",
            activo=True,
        )
        self.periodo = Periodo.objects.create(
            codigo="2026-01",
            **Periodo.defaults_for("2026-01"),
        )

    def _director_user(self, username="director_hu023"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_director)
        return user

    def test_director_can_create_update_delete_grupo(self):
        director = self._director_user()
        self.client.force_login(director)

        create_response = self.client.post(
            "/panel/escolar/grupos/",
            {
                "curso_ref": self.curso.pk,
                "periodo_ref": self.periodo.pk,
                "tipo_horario": Grupo.HORARIO_SAB,
                "cupo": 25,
                "estado": Grupo.ESTADO_ACTIVO,
            },
        )

        self.assertEqual(create_response.status_code, 302)
        grupo = Grupo.objects.get(
            curso_ref__codigo="curso-prueba", periodo_ref__codigo="2026-01")
        self.assertEqual(grupo.cupo, 25)
        self.assertTrue(grupo.horarios.exists())
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::GRUPO_CREATE",
                entidad="Grupo",
                entidad_id=str(grupo.pk),
                detalle__periodo="2026-01",
            ).exists()
        )

        update_response = self.client.post(
            f"/panel/escolar/grupos/?edit={grupo.pk}",
            {
                "curso_ref": self.curso.pk,
                "periodo_ref": self.periodo.pk,
                "tipo_horario": Grupo.HORARIO_SEM,
                "cupo": 18,
                "estado": Grupo.ESTADO_INACTIVO,
            },
        )

        self.assertEqual(update_response.status_code, 302)
        grupo.refresh_from_db()
        self.assertEqual(grupo.cupo, 18)
        self.assertEqual(grupo.estado, Grupo.ESTADO_INACTIVO)
        self.assertEqual(grupo.tipo_horario, Grupo.HORARIO_SEM)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::GRUPO_UPDATE",
                entidad="Grupo",
                entidad_id=str(grupo.pk),
                detalle__cupo=18,
                detalle__estado=Grupo.ESTADO_INACTIVO,
            ).exists()
        )

        delete_response = self.client.post(
            "/panel/escolar/grupos/",
            {"delete_id": str(grupo.pk)},
        )

        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(Grupo.objects.filter(pk=grupo.pk).exists())
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::GRUPO_DELETE",
                entidad="Grupo",
                entidad_id=str(grupo.pk),
            ).exists()
        )

    def test_grupos_filter_by_period_and_state(self):
        director = self._director_user("director_hu023_filter")
        self.client.force_login(director)

        Grupo.objects.create(
            curso_slug="curso-a",
            periodo="2026-01",
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=20,
            estado=Grupo.ESTADO_ACTIVO,
        )
        Grupo.objects.create(
            curso_slug="curso-b",
            periodo="2026-02",
            tipo_horario=Grupo.HORARIO_SEM,
            cupo=30,
            estado=Grupo.ESTADO_INACTIVO,
        )

        response = self.client.get(
            "/panel/escolar/grupos/?periodo=2026-01&estado=1")

        self.assertEqual(response.status_code, 200)
        grupos = list(response.context["grupos"])
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0].periodo, "2026-01")
        self.assertEqual(grupos[0].estado, Grupo.ESTADO_ACTIVO)

    @patch("apps.ui.views_school.load_cursos")
    def test_generar_grupos_por_periodo_crea_sabatino_y_semana_con_auditoria(self, mock_load_cursos):
        mock_load_cursos.return_value = [
            {"slug": "curso-gen-a"},
            {"slug": "curso-gen-b"},
        ]
        director = self._director_user("director_hu023_gen")
        self.client.force_login(director)

        response = self.client.post(
            "/panel/escolar/grupos/generar/",
            {"periodo": "2026-03"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Grupo.objects.filter(
                periodo_ref__codigo="2026-03", curso_ref__codigo="curso-gen-a").count(),
            3,
        )
        self.assertEqual(
            Grupo.objects.filter(
                periodo_ref__codigo="2026-03", curso_ref__codigo="curso-gen-b").count(),
            3,
        )
        for grupo in Grupo.objects.filter(periodo_ref__codigo="2026-03"):
            self.assertTrue(grupo.horarios.exists())
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::GRUPO_GENERAR",
                detalle__periodo="2026-03",
                detalle__grupos_creados=6,
            ).exists()
        )

    def test_user_without_director_or_superuser_role_gets_403(self):
        user = self.user_model.objects.create_user(
            username="alumno_hu023",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_alumno)
        self.client.force_login(user)

        response = self.client.get("/panel/escolar/grupos/")

        self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# HU-023 — Grupos con docentes asignados
# ---------------------------------------------------------------------------

class GrupoDocenteAsignacionTests(TestCase):
    """HU-023 — Verifica que DocenteGrupo asocia correctamente Docente y Grupo,
    aplica la restricción de unicidad docente+grupo y soporta múltiples roles.

    La asignación de docentes a grupos se gestiona a nivel de modelo
    (no hay vista de panel para ello); este test documenta y protege
    ese comportamiento para la entrega académica.
    """

    def setUp(self):
        self.curso = Curso.objects.create(
            codigo="curso-docente-test",
            nombre="Curso Docente Test",
            activo=True,
        )
        self.periodo = Periodo.objects.create(
            codigo="2026-05",
            **Periodo.defaults_for("2026-05"),
        )
        self.grupo = Grupo.objects.create(
            curso_ref=self.curso,
            periodo_ref=self.periodo,
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=20,
            estado=Grupo.ESTADO_ACTIVO,
        )
        self.docente = Docente.objects.create(
            nombres="Laura",
            apellido_paterno="Méndez",
            apellido_materno="Torres",
            correo="laura.mendez@test.local",
        )

    def test_asignar_docente_titular_a_grupo(self):
        """Un docente puede ser asignado como titular a un grupo."""
        asignacion = DocenteGrupo.objects.create(
            docente=self.docente,
            grupo=self.grupo,
            rol="TIT",
        )
        self.assertEqual(asignacion.rol, "TIT")
        self.assertTrue(asignacion.activo)
        self.assertEqual(self.grupo.asignaciones_docentes.count(), 1)

    def test_no_permite_asignacion_duplicada_mismo_docente_grupo(self):
        """La restricción uq_docente_grupo impide duplicar la asignación."""
        DocenteGrupo.objects.create(
            docente=self.docente,
            grupo=self.grupo,
            rol="TIT",
        )
        with self.assertRaises(IntegrityError):
            DocenteGrupo.objects.create(
                docente=self.docente,
                grupo=self.grupo,
                rol="AUX",
            )

    def test_dos_docentes_distintos_pueden_estar_en_el_mismo_grupo(self):
        """Varios docentes con roles diferentes pueden compartir un grupo."""
        docente_aux = Docente.objects.create(
            nombres="Pedro",
            apellido_paterno="García",
            apellido_materno="López",
            correo="pedro.garcia@test.local",
        )
        DocenteGrupo.objects.create(
            docente=self.docente, grupo=self.grupo, rol="TIT")
        DocenteGrupo.objects.create(
            docente=docente_aux, grupo=self.grupo, rol="AUX")

        asignaciones = DocenteGrupo.objects.filter(grupo=self.grupo)
        self.assertEqual(asignaciones.count(), 2)
        roles = set(asignaciones.values_list("rol", flat=True))
        self.assertEqual(roles, {"TIT", "AUX"})

    def test_desactivar_asignacion_no_borra_el_registro(self):
        """Marcar activo=False conserva el historial sin eliminar la fila."""
        asignacion = DocenteGrupo.objects.create(
            docente=self.docente,
            grupo=self.grupo,
            rol="TIT",
            activo=True,
        )
        asignacion.activo = False
        asignacion.save(update_fields=["activo"])

        asignacion.refresh_from_db()
        self.assertFalse(asignacion.activo)
        self.assertEqual(DocenteGrupo.objects.filter(
            grupo=self.grupo).count(), 1)
