from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.school.models import Alumno


class AlumnoExpedienteFlowTests(TestCase):
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

    def _director_user(self, username="director_hu022"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_director)
        return user

    def test_director_can_create_and_edit_alumno_expediente(self):
        director = self._director_user()
        self.client.force_login(director)

        create_response = self.client.post(
            "/panel/escolar/alumnos/",
            {
                "nombres": "Ana",
                "apellido_paterno": "Diaz",
                "apellido_materno": "Lopez",
                "correo": "ana.hu022@test.local",
                "telefono": "5550101",
            },
        )

        self.assertEqual(create_response.status_code, 302)
        alumno = Alumno.objects.get(correo="ana.hu022@test.local")
        self.assertEqual(alumno.nombres, "Ana")
        # La matrícula se auto-genera con patrón CCENT-NNNN
        self.assertTrue(alumno.matricula.startswith("CCENT-"))
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::ALUMNO_CREATE",
                entidad="Alumno",
                entidad_id=str(alumno.pk),
                detalle__matricula=alumno.matricula,
            ).exists()
        )

        edit_response = self.client.post(
            f"/panel/escolar/alumnos/?edit={alumno.pk}",
            {
                "nombres": "Ana Maria",
                "apellido_paterno": "Diaz",
                "apellido_materno": "Lopez",
                "correo": "ana.hu022@test.local",
                "telefono": "5550101",
            },
        )

        self.assertEqual(edit_response.status_code, 302)
        alumno.refresh_from_db()
        self.assertEqual(alumno.nombres, "Ana Maria")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::ALUMNO_UPDATE",
                entidad="Alumno",
                entidad_id=str(alumno.pk),
                detalle__matricula=alumno.matricula,
            ).exists()
        )

    def test_director_can_delete_alumno_expediente(self):
        director = self._director_user("director_hu022_delete")
        self.client.force_login(director)
        alumno = Alumno.objects.create(
            matricula="MAT-HU022-DEL",
            nombres="Beto",
            apellido_paterno="Perez",
            apellido_materno="Lopez",
            correo="beto.hu022@test.local",
            telefono="5550202",
        )

        response = self.client.post(
            "/panel/escolar/alumnos/",
            {"delete_id": str(alumno.pk)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Alumno.objects.filter(pk=alumno.pk).exists())
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::ALUMNO_DELETE",
                entidad="Alumno",
                entidad_id=str(alumno.pk),
            ).exists()
        )

    def test_user_without_director_or_superuser_role_gets_403(self):
        student_user = self.user_model.objects.create_user(
            username="alumno_hu022",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=student_user, rol=self.rol_alumno)
        self.client.force_login(student_user)

        response = self.client.get("/panel/escolar/alumnos/")

        self.assertEqual(response.status_code, 403)
