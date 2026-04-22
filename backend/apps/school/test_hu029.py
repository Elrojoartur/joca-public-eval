"""
HU-029 — Expediente de alumno: domicilio, matrícula automática e información académica.

Casos de prueba:
  1. Crear alumno con domicilio válido en una sola operación.
  2. Editar domicilio existente sin afectar datos del alumno.
  3. Rechazar código postal con formato inválido.
  4. Matrícula autogenerada (CCENT-NNNN) en alta de alumno.
  5. Edición manual de matrícula vía POST es ignorada por backend.
  6. Vista de expediente muestra curso, grupo y horario de inscripción activa.
"""
import re
from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.school.models import (
    Alumno,
    AlumnoDomicilio,
    Grupo,
    GrupoHorario,
    Inscripcion,
)
from apps.school.validators import _curp_check_digit
from apps.ui.forms import AlumnoDomicilioForm, AlumnoForm

_CCENT_RE = re.compile(r"^CCENT-\d{4}$")

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _valid_curp():
    base17 = "LOPA900101HDFRRN0"
    return f"{base17}{_curp_check_digit(base17)}"


def _make_alumno(matricula, correo, nombres="Ana", ap="García", am="López", telefono="5550000"):
    return Alumno.objects.create(
        matricula=matricula,
        nombres=nombres,
        apellido_paterno=ap,
        apellido_materno=am,
        correo=correo,
        telefono=telefono,
    )


def _make_grupo_con_horario(curso_slug="ELEC-BAS", periodo="2026-04",
                            tipo=Grupo.HORARIO_SEM, turno=Grupo.TURNO_PM,
                            cupo=25):
    grupo = Grupo.objects.create(
        curso_slug=curso_slug,
        periodo=periodo,
        tipo_horario=tipo,
        turno=turno,
        cupo=cupo,
    )
    GrupoHorario.objects.create(
        grupo=grupo,
        dia="LUN",
        hora_inicio=time(19, 0),
        hora_fin=time(21, 0),
        activo=True,
    )
    GrupoHorario.objects.create(
        grupo=grupo,
        dia="MIE",
        hora_inicio=time(19, 0),
        hora_fin=time(21, 0),
        activo=True,
    )
    return grupo


# ─── Clase base ───────────────────────────────────────────────────────────────


class _BaseHU029(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )

    def _director(self, username="dir_hu029"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_director)
        return user

    def _post_alumno(self, extra=None, username="dir_hu029_post"):
        """Realiza POST de alta de alumno con datos base válidos."""
        director = self._director(username)
        self.client.force_login(director)
        payload = {
            "nombres": "Rosa",
            "apellido_paterno": "Medina",
            "apellido_materno": "Torres",
            "correo": f"{username}@test.local",
            "telefono": "5551000",
            "curp": "",
            "rfc": "",
            # domicilio vacío — todos opcionales
            "calle": "",
            "numero": "",
            "colonia": "",
            "codigo_postal": "",
            "estado": "",
            "pais": "",
        }
        if extra:
            payload.update(extra)
        return self.client.post("/panel/escolar/alumnos/", payload)


# ─── Caso 1: Crear alumno con domicilio válido ─────────────────────────────────


class CrearAlumnoConDomicilioTests(_BaseHU029):
    def test_alta_con_domicilio_completo_guarda_alumno_y_domicilio(self):
        """POST con domicilio válido crea Alumno + AlumnoDomicilio en BD."""
        resp = self._post_alumno(
            extra={
                "correo": "caso1_hu029@test.local",
                "calle": "Av. Reforma",
                "numero": "101",
                "colonia": "Centro",
                "codigo_postal": "06600",
                "estado": "Ciudad de México",
                "pais": "México",
            },
            username="dir_hu029_caso1",
        )

        self.assertEqual(resp.status_code, 302,
                         "Debería redirigir al listado tras el alta.")
        alumno = Alumno.objects.get(correo="caso1_hu029@test.local")
        self.assertIsNotNone(alumno, "El alumno no fue creado en BD.")

        dom = AlumnoDomicilio.objects.filter(alumno=alumno).first()
        self.assertIsNotNone(dom, "Debe existir AlumnoDomicilio relacionado.")
        self.assertEqual(dom.calle, "Av. Reforma")
        self.assertEqual(dom.numero, "101")
        self.assertEqual(dom.codigo_postal, "06600")
        self.assertEqual(dom.estado, "Ciudad de México")

    def test_alta_sin_domicilio_crea_alumno_sin_error(self):
        """POST sin domicilio (campos vacíos) crea alumno y guarda domicilio en blanco."""
        resp = self._post_alumno(
            extra={"correo": "caso1b_hu029@test.local"},
            username="dir_hu029_caso1b",
        )

        self.assertEqual(resp.status_code, 302)
        alumno = Alumno.objects.get(correo="caso1b_hu029@test.local")
        # AlumnoDomicilio se crea igual (vacío) porque el form siempre es enviado
        dom = AlumnoDomicilio.objects.filter(alumno=alumno).first()
        self.assertIsNotNone(dom)
        self.assertEqual(dom.calle, "")


# ─── Caso 2: Editar domicilio existente ────────────────────────────────────────


class EditarDomicilioTests(_BaseHU029):
    def test_edicion_domicilio_actualiza_campos_sin_cambiar_alumno(self):
        """PUT del domicilio via form modifica sólo los campos de dirección."""
        director = self._director("dir_hu029_ed")
        self.client.force_login(director)

        alumno = _make_alumno("HU029-ED-001", "edicion_hu029@test.local")
        AlumnoDomicilio.objects.create(
            alumno=alumno,
            calle="Calle Vieja",
            numero="5",
            colonia="Barrio Antiguo",
            codigo_postal="11100",
            estado="Jalisco",
            pais="México",
        )

        resp = self.client.post(
            f"/panel/escolar/alumnos/?edit={alumno.pk}",
            {
                "nombres": alumno.nombres,
                "apellido_paterno": alumno.apellido_paterno,
                "apellido_materno": alumno.apellido_materno,
                "correo": alumno.correo,
                "telefono": alumno.telefono,
                "curp": "",
                "rfc": "",
                "calle": "Calle Nueva",
                "numero": "99",
                "colonia": "Colonia Actualizada",
                "codigo_postal": "44100",
                "estado": "Jalisco",
                "pais": "México",
            },
        )

        self.assertEqual(resp.status_code, 302, "Edición debe redirigir.")
        dom = AlumnoDomicilio.objects.get(alumno=alumno)
        self.assertEqual(dom.calle, "Calle Nueva")
        self.assertEqual(dom.numero, "99")
        self.assertEqual(dom.colonia, "Colonia Actualizada")
        self.assertEqual(dom.codigo_postal, "44100")

        # El alumno no cambió de nombre ni correo
        alumno.refresh_from_db()
        self.assertEqual(alumno.correo, "edicion_hu029@test.local")

    def test_edicion_domicilio_via_form_directo(self):
        """AlumnoDomicilioForm actualiza instancia existente correctamente."""
        alumno = _make_alumno("HU029-ED-002", "formdir_hu029@test.local")
        dom = AlumnoDomicilio.objects.create(
            alumno=alumno,
            calle="Original",
            numero="1",
            estado="Sonora",
            pais="México",
        )

        form = AlumnoDomicilioForm(
            data={
                "calle": "Actualizada",
                "numero": "2",
                "colonia": "Nueva Colonia",
                "codigo_postal": "83000",
                "estado": "Sonora",
                "pais": "México",
            },
            instance=dom,
        )

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.calle, "Actualizada")
        self.assertEqual(saved.codigo_postal, "83000")


# ─── Caso 3: Código postal inválido ────────────────────────────────────────────


class CodigoPostalValidacionTests(_BaseHU029):
    def _form_con_cp(self, cp_value):
        return AlumnoDomicilioForm(data={
            "calle": "Calle Test",
            "numero": "1",
            "colonia": "Colonia",
            "codigo_postal": cp_value,
            "estado": "CDMX",
            "pais": "México",
        })

    def test_rechaza_codigo_postal_con_letras(self):
        form = self._form_con_cp("ABCDE")
        self.assertFalse(form.is_valid())
        self.assertIn("codigo_postal", form.errors)

    def test_rechaza_codigo_postal_con_menos_de_cinco_digits(self):
        form = self._form_con_cp("1234")
        self.assertFalse(form.is_valid())
        self.assertIn("codigo_postal", form.errors)

    def test_rechaza_codigo_postal_con_mas_de_cinco_digits(self):
        form = self._form_con_cp("123456")
        self.assertFalse(form.is_valid())
        self.assertIn("codigo_postal", form.errors)

    def test_acepta_codigo_postal_valido_cinco_digitos(self):
        form = self._form_con_cp("06600")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["codigo_postal"], "06600")

    def test_acepta_codigo_postal_vacio(self):
        """CP vacío es permitido — campo opcional."""
        form = self._form_con_cp("")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["codigo_postal"], "")

    def test_post_con_cp_invalido_no_crea_alumno(self):
        """Envío de formulario con CP inválido devuelve 200 sin crear alumno."""
        resp = self._post_alumno(
            extra={
                "correo": "cp_invalido_hu029@test.local",
                "codigo_postal": "XXXXX",
            },
            username="dir_hu029_cp",
        )

        self.assertEqual(resp.status_code, 200,
                         "Debe re-mostrar el form con error.")
        self.assertFalse(
            Alumno.objects.filter(
                correo="cp_invalido_hu029@test.local").exists()
        )


# ─── Caso 4: Matrícula autogenerada ────────────────────────────────────────────


class MatriculaAutogeneradaTests(_BaseHU029):
    def test_matricula_generada_con_formato_ccent_nnnn_en_alta_http(self):
        """POST de alta de alumno asigna matrícula con patrón CCENT-NNNN."""
        resp = self._post_alumno(
            extra={"correo": "mat4_hu029@test.local"},
            username="dir_hu029_mat4",
        )

        self.assertEqual(resp.status_code, 302)
        alumno = Alumno.objects.get(correo="mat4_hu029@test.local")
        self.assertRegex(alumno.matricula, _CCENT_RE,
                         f"Matrícula '{alumno.matricula}' no cumple el patrón CCENT-NNNN.")

    def test_matricula_generada_en_modelo_sin_vista(self):
        """Alumno.save() asigna matrícula si no se proporcionó una."""
        alumno = Alumno(
            nombres="Pedro",
            apellido_paterno="Soto",
            correo="mat4b_hu029@test.local",
            telefono="5551004",
        )
        alumno.save()
        self.assertRegex(alumno.matricula, _CCENT_RE)

    def test_multiples_alumnos_obtienen_matriculas_unicas(self):
        """Dos alumnos creados sin matrícula reciben matrículas distintas."""
        a1 = Alumno.objects.create(
            nombres="Uno",
            apellido_paterno="Test",
            correo="m1_hu029@test.local",
            telefono="5551011",
        )
        a2 = Alumno.objects.create(
            nombres="Dos",
            apellido_paterno="Test",
            correo="m2_hu029@test.local",
            telefono="5551012",
        )
        self.assertNotEqual(a1.matricula, a2.matricula)
        self.assertRegex(a1.matricula, _CCENT_RE)
        self.assertRegex(a2.matricula, _CCENT_RE)


# ─── Caso 5: Edición manual de matrícula ignorada por backend ──────────────────


class MatriculaInmutableTests(_BaseHU029):
    def test_edicion_post_con_matricula_manual_no_sobrescribe(self):
        """Si el POST incluye un campo 'matricula', el backend lo ignora."""
        director = self._director("dir_hu029_imm")
        self.client.force_login(director)

        alumno = _make_alumno("HU029-IMM-001", "inmutable_hu029@test.local",
                              nombres="Lucía", ap="Sanz", am="Gil")

        resp = self.client.post(
            f"/panel/escolar/alumnos/?edit={alumno.pk}",
            {
                "matricula": "TRAMPA-9999",   # intento de inyectar matrícula
                "nombres": alumno.nombres,
                "apellido_paterno": alumno.apellido_paterno,
                "apellido_materno": alumno.apellido_materno,
                "correo": alumno.correo,
                "telefono": alumno.telefono,
                "curp": "",
                "rfc": "",
                "calle": "",
                "numero": "",
                "colonia": "",
                "codigo_postal": "",
                "estado": "",
                "pais": "",
            },
        )

        self.assertEqual(resp.status_code, 302)
        alumno.refresh_from_db()
        self.assertEqual(
            alumno.matricula,
            "HU029-IMM-001",
            "La matrícula no debe ser modificada por el formulario.",
        )

    def test_alumnoform_no_incluye_campo_matricula(self):
        """AlumnoForm.fields no contiene 'matricula' — no está expuesto al usuario."""
        form = AlumnoForm()
        self.assertNotIn(
            "matricula",
            form.fields,
            "El campo 'matricula' no debe estar en AlumnoForm.",
        )


# ─── Caso 6: Vista expediente muestra curso, grupo y horario ───────────────────


class ExpedienteInformacionAcademicaTests(_BaseHU029):
    def _setup_inscripcion_activa(self):
        alumno = _make_alumno("HU029-EXP-001", "exp_hu029@test.local",
                              nombres="Carla", ap="Ruiz", am="Mora")
        grupo = _make_grupo_con_horario(
            curso_slug="ELEC-BAS",
            periodo="2026-04",
            tipo=Grupo.HORARIO_SEM,
            turno=Grupo.TURNO_PM,
        )
        Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        return alumno, grupo

    def test_expediente_muestra_nombre_curso(self):
        alumno, grupo = self._setup_inscripcion_activa()
        director = self._director("dir_hu029_exp1")
        self.client.force_login(director)

        resp = self.client.get(
            f"/panel/escolar/alumnos/{alumno.pk}/expediente/")

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, grupo.curso_ref.codigo,
                            msg_prefix="El código del curso debe aparecer en el expediente.")

    def test_expediente_muestra_nombre_periodo(self):
        alumno, grupo = self._setup_inscripcion_activa()
        director = self._director("dir_hu029_exp2")
        self.client.force_login(director)

        resp = self.client.get(
            f"/panel/escolar/alumnos/{alumno.pk}/expediente/")

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, grupo.periodo_ref.codigo,
                            msg_prefix="El código de periodo debe aparecer en el expediente.")

    def test_expediente_muestra_horario(self):
        alumno, grupo = self._setup_inscripcion_activa()
        director = self._director("dir_hu029_exp3")
        self.client.force_login(director)

        resp = self.client.get(
            f"/panel/escolar/alumnos/{alumno.pk}/expediente/")

        self.assertEqual(resp.status_code, 200)
        # El horario LUN 19:00-21:00 debe estar renderizado
        self.assertContains(resp, "19:00",
                            msg_prefix="La hora de inicio del horario debe aparecer en la página.")

    def test_expediente_sin_inscripciones_muestra_texto_amigable(self):
        alumno = _make_alumno("HU029-EXP-002", "sininsc_hu029@test.local")
        director = self._director("dir_hu029_exp4")
        self.client.force_login(director)

        resp = self.client.get(
            f"/panel/escolar/alumnos/{alumno.pk}/expediente/")

        self.assertEqual(resp.status_code, 200)
        self.assertContains(
            resp,
            "Sin inscripción activa",
            msg_prefix="Debe mostrar texto amigable cuando no hay inscripciones.",
        )

    def test_expediente_sin_domicilio_muestra_texto_amigable(self):
        alumno = _make_alumno("HU029-EXP-003", "sindom_hu029@test.local")
        director = self._director("dir_hu029_exp5")
        self.client.force_login(director)

        resp = self.client.get(
            f"/panel/escolar/alumnos/{alumno.pk}/expediente/")

        self.assertEqual(resp.status_code, 200)
        self.assertContains(
            resp,
            "No registrado",
            msg_prefix="Debe indicar que no hay domicilio registrado.",
        )

    def test_expediente_muestra_matricula_del_alumno(self):
        alumno = _make_alumno("HU029-EXP-004", "matshow_hu029@test.local")
        director = self._director("dir_hu029_exp6")
        self.client.force_login(director)

        resp = self.client.get(
            f"/panel/escolar/alumnos/{alumno.pk}/expediente/")

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "HU029-EXP-004",
                            msg_prefix="La matrícula del alumno debe aparecer en el expediente.")

    def test_expediente_alumno_inexistente_redirige(self):
        director = self._director("dir_hu029_exp7")
        self.client.force_login(director)

        resp = self.client.get("/panel/escolar/alumnos/99999/expediente/")

        self.assertEqual(resp.status_code, 302,
                         "Un alumno inexistente debe redirigir al listado.")
