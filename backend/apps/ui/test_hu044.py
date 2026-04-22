from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.school.models import Alumno, Calificacion, Grupo, Inscripcion


class ReporteAcademicoHU044Tests(TestCase):
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

    def _crear_inscripcion_con_calificacion(self, sufijo, periodo, estado, valor):
        alumno = Alumno.objects.create(
            matricula=f"A-044-{sufijo}",
            nombres=f"Alumno {sufijo}",
            apellido_paterno="Demo",
            correo=f"a044_{sufijo}@test.local",
        )
        grupo = Grupo.objects.create(
            curso_slug=f"curso-{sufijo}",
            periodo=periodo,
            tipo_horario=Grupo.HORARIO_SEM,
            cupo=30,
            estado=Grupo.ESTADO_ACTIVO,
        )
        inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=estado,
        )
        Calificacion.objects.create(
            inscripcion=inscripcion,
            valor=Decimal(valor),
        )
        return inscripcion

    def test_director_filtra_reporte_academico_por_periodo(self):
        director = self._user_with_role("director_hu044", self.rol_director)
        self._crear_inscripcion_con_calificacion(
            "001", "2026-01", Inscripcion.ESTADO_ACTIVA, "9.00"
        )
        self._crear_inscripcion_con_calificacion(
            "002", "2026-02", Inscripcion.ESTADO_BAJA, "7.00"
        )

        self.client.force_login(director)
        response = self.client.get(
            "/panel/reportes/academico/?periodo=2026-01")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inscripciones por per")
        self.assertContains(response, "Segmentación de calificaciones")

        self.assertEqual(response.context["periodo_activo"], "2026-01")
        self.assertEqual(response.context["kpi"]["inscripciones"], 1)
        self.assertEqual(response.context["kpi"]["calificaciones"], 1)
        self.assertEqual(response.context["kpi"]["calif_promedio"], "9.00")

        calificaciones = list(response.context["calificaciones"])
        self.assertEqual(len(calificaciones), 1)
        self.assertEqual(
            calificaciones[0].inscripcion.grupo.periodo, "2026-01")

        periodos = {row["periodo"]
                    for row in response.context["inscripciones_por_periodo"]}
        self.assertIn("2026-01", periodos)
        self.assertIn("2026-02", periodos)

    def test_alumno_no_puede_acceder_reporte_academico(self):
        alumno = self._user_with_role("alumno_hu044", self.rol_alumno)
        self.client.force_login(alumno)

        response = self.client.get("/panel/reportes/academico/")

        self.assertEqual(response.status_code, 403)
