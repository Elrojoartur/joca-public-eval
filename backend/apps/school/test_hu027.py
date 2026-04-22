from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.school.models import Alumno, Calificacion, Grupo, Inscripcion


class BoletaPdfPorPeriodoFlowTests(TestCase):
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

    def _director_user(self, username="director_hu027"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_director)
        return user

    def _alumno_user(self, username, email):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
            email=email,
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_alumno)
        return user

    def _inscripcion_con_calificacion(
        self,
        matricula="MAT-HU027-001",
        correo="hu027_1@test.local",
        periodo="2026-11",
        valor="9.20",
    ):
        alumno = Alumno.objects.create(
            matricula=matricula,
            nombres="Nora",
            apellido_paterno="Luna",
            apellido_materno="Vera",
            correo=correo,
            telefono="5552701",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu027",
            periodo=periodo,
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=30,
            estado=Grupo.ESTADO_ACTIVO,
        )
        inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        Calificacion.objects.create(
            inscripcion=inscripcion,
            valor=Decimal(valor),
        )
        return alumno, inscripcion

    def test_director_can_emit_boleta_pdf_por_periodo(self):
        director = self._director_user()
        alumno, inscripcion = self._inscripcion_con_calificacion()
        self.client.force_login(director)

        response = self.client.get(
            f"/panel/escolar/boleta/?alumno={alumno.pk}&periodo={inscripcion.grupo.periodo}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("boleta_", response["Content-Disposition"])
        self.assertIn(inscripcion.grupo.periodo,
                      response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_alumno_can_emit_own_boleta_pdf_por_periodo(self):
        alumno, inscripcion = self._inscripcion_con_calificacion(
            matricula="MAT-HU027-002",
            correo="alumno.hu027@test.local",
            periodo="2026-12",
        )
        alumno_user = self._alumno_user(
            "alumno_hu027", "alumno.hu027@test.local")
        self.client.force_login(alumno_user)

        response = self.client.get(
            f"/panel/alumno/boleta/pdf/?periodo={inscripcion.grupo.periodo}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("boleta_", response["Content-Disposition"])
        self.assertIn(alumno.matricula, response["Content-Disposition"])

    def test_alumno_cannot_emit_boleta_of_other_student_from_escolar_route(self):
        target_alumno, inscripcion = self._inscripcion_con_calificacion(
            matricula="MAT-HU027-003",
            correo="target.hu027@test.local",
            periodo="2027-01",
        )
        other_user = self._alumno_user(
            "otro_alumno_hu027", "other.hu027@test.local")
        self.client.force_login(other_user)

        response = self.client.get(
            f"/panel/escolar/boleta/?alumno={target_alumno.pk}&periodo={inscripcion.grupo.periodo}"
        )

        self.assertEqual(response.status_code, 403)

    def test_alumno_boleta_pdf_rejects_invalid_period_format(self):
        self._inscripcion_con_calificacion(
            matricula="MAT-HU027-004",
            correo="periodo.hu027@test.local",
        )
        alumno_user = self._alumno_user(
            "alumno_hu027_periodo", "periodo.hu027@test.local")
        self.client.force_login(alumno_user)

        response = self.client.get("/panel/alumno/boleta/pdf/?periodo=2026-13")

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Periodo inválido", status_code=400)
