import re

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.school.models import Alumno
from apps.school.validators import _curp_check_digit

_CCENT_RE = re.compile(r"^CCENT-\d{4}$")


class CurpRfcValidationFlowTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )

    def _director_user(self, username="director_hu026"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_director)
        return user

    def _valid_curp(self):
        base17 = "LOPA900101HDFRRN0"
        return f"{base17}{_curp_check_digit(base17)}"

    def test_director_can_save_alumno_with_valid_curp_and_rfc_vigente(self):
        director = self._director_user()
        self.client.force_login(director)

        response = self.client.post(
            "/panel/escolar/alumnos/",
            {
                "nombres": "Laura",
                "apellido_paterno": "Ortega",
                "apellido_materno": "Paz",
                "correo": "laura.hu026@test.local",
                "telefono": "5552601",
                "curp": self._valid_curp().lower(),
                "rfc": "lopa900101aaa",
            },
        )

        self.assertEqual(response.status_code, 302)
        alumno = Alumno.objects.get(correo="laura.hu026@test.local")
        self.assertRegex(alumno.matricula, _CCENT_RE)
        self.assertEqual(alumno.curp, self._valid_curp())
        self.assertEqual(alumno.rfc, "LOPA900101AAA")

    def test_rejects_invalid_curp(self):
        director = self._director_user("director_hu026_bad_curp")
        self.client.force_login(director)

        response = self.client.post(
            "/panel/escolar/alumnos/",
            {
                "nombres": "Mario",
                "apellido_paterno": "Diaz",
                "apellido_materno": "Rios",
                "correo": "mario.hu026@test.local",
                "telefono": "5552602",
                "curp": "AAAA000000HDFRRR00",
                "rfc": "MADR900101AAA",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CURP inválida")
        self.assertFalse(Alumno.objects.filter(
            correo="mario.hu026@test.local").exists())

    def test_rejects_invalid_rfc_vigente(self):
        director = self._director_user("director_hu026_bad_rfc")
        self.client.force_login(director)

        response = self.client.post(
            "/panel/escolar/alumnos/",
            {
                "nombres": "Sofia",
                "apellido_paterno": "Ramos",
                "apellido_materno": "Neri",
                "correo": "sofia.hu026@test.local",
                "telefono": "5552603",
                "curp": self._valid_curp(),
                "rfc": "SORA900132",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RFC inválido")
        self.assertFalse(Alumno.objects.filter(
            correo="sofia.hu026@test.local").exists())

    def test_rfc_can_be_empty(self):
        director = self._director_user("director_hu026_empty_rfc")
        self.client.force_login(director)

        response = self.client.post(
            "/panel/escolar/alumnos/",
            {
                "nombres": "Paula",
                "apellido_paterno": "Vega",
                "apellido_materno": "Cruz",
                "correo": "paula.hu026@test.local",
                "telefono": "5552604",
                "curp": self._valid_curp(),
                "rfc": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        alumno = Alumno.objects.get(correo="paula.hu026@test.local")
        self.assertRegex(alumno.matricula, _CCENT_RE)
        self.assertIsNone(alumno.rfc)
