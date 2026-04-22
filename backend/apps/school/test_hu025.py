from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.school.models import ActaCierre, Alumno, Calificacion, Grupo, Inscripcion


class CalificacionesGestionFlowTests(TestCase):
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

    def _director_user(self, username="director_hu025"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_director)
        return user

    def _inscripcion(self, matricula="MAT-HU025-001", correo="hu025_1@test.local", periodo="2026-09"):
        alumno = Alumno.objects.create(
            matricula=matricula,
            nombres="Ana",
            apellido_paterno="Diaz",
            apellido_materno="Lopez",
            correo=correo,
            telefono="5553001",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu025",
            periodo=periodo,
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=30,
            estado=Grupo.ESTADO_ACTIVO,
        )
        return Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )

    def test_director_can_capture_calificacion_and_consult(self):
        director = self._director_user()
        inscripcion = self._inscripcion()
        self.client.force_login(director)

        post_response = self.client.post(
            "/panel/escolar/calificaciones/",
            {
                "inscripcion": str(inscripcion.pk),
                "valor": "9.50",
            },
        )

        self.assertEqual(post_response.status_code, 302)
        cal = Calificacion.objects.get(inscripcion=inscripcion)
        self.assertEqual(cal.valor, Decimal("9.50"))

        get_response = self.client.get("/panel/escolar/calificaciones/")
        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, str(inscripcion.pk))

    def test_no_permite_calificacion_duplicada_por_inscripcion(self):
        director = self._director_user("director_hu025_dup")
        inscripcion = self._inscripcion("MAT-HU025-002", "hu025_2@test.local")
        Calificacion.objects.create(
            inscripcion=inscripcion, valor=Decimal("8.00"))
        self.client.force_login(director)

        response = self.client.post(
            "/panel/escolar/calificaciones/",
            {
                "inscripcion": str(inscripcion.pk),
                "valor": "9.00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ya tiene calificación registrada")
        self.assertEqual(Calificacion.objects.filter(
            inscripcion=inscripcion).count(), 1)

    def test_no_permite_captura_si_acta_esta_cerrada_para_director(self):
        director = self._director_user("director_hu025_cierre")
        inscripcion = self._inscripcion(
            "MAT-HU025-003", "hu025_3@test.local", "2026-10")
        ActaCierre.objects.create(
            grupo=inscripcion.grupo,
            periodo=inscripcion.grupo.periodo,
            cerrada_por=director,
            motivo="Cierre de periodo",
        )
        self.client.force_login(director)

        response = self.client.post(
            "/panel/escolar/calificaciones/",
            {
                "inscripcion": str(inscripcion.pk),
                "valor": "9.00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "acta de ese grupo ya está cerrada")
        self.assertFalse(Calificacion.objects.filter(
            inscripcion=inscripcion).exists())

    def test_usuario_sin_rol_director_superusuario_recibe_403(self):
        student_user = self.user_model.objects.create_user(
            username="alumno_hu025",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=student_user, rol=self.rol_alumno)
        self.client.force_login(student_user)

        response = self.client.get("/panel/escolar/calificaciones/")

        self.assertEqual(response.status_code, 403)


# PCB-014 / MOD-04 / HU-025 – Gestión de calificaciones con captura y consulta
class PCB014CalificacionCapturaConsultaTests(TestCase):
    """PCB-014 / MOD-04 / HU-025 – Gestión de calificaciones con captura y consulta.

    Verifica que un Director Escolar puede capturar una calificación válida
    para una inscripción y consultarla después mediante GET. Comprueba la
    persistencia correcta del valor numérico en base de datos.
    """

    def setUp(self):
        User = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.director = User.objects.create_user(
            username="pcb014_director",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=self.director, rol=self.rol_director)

        alumno = Alumno.objects.create(
            matricula="MAT-PCB014-001",
            nombres="Carlos",
            apellido_paterno="Ruiz",
            apellido_materno="Mora",
            correo="pcb014_alumno@test.local",
            telefono="5550001",
        )
        grupo = Grupo.objects.create(
            curso_slug="pcb014-curso",
            periodo="2026-04",
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=20,
            estado=Grupo.ESTADO_ACTIVO,
        )
        self.inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )

    def test_captura_y_consulta_calificacion_valida(self):
        from decimal import Decimal

        self.client.force_login(self.director)

        # Captura: POST con valor válido
        post_response = self.client.post(
            "/panel/escolar/calificaciones/",
            {
                "inscripcion": str(self.inscripcion.pk),
                "valor": "8.75",
            },
        )

        # Vista redirige al guardar correctamente
        self.assertEqual(post_response.status_code, 302)

        # Persistencia: calificación guardada en BD con valor correcto
        cal = Calificacion.objects.get(inscripcion=self.inscripcion)
        self.assertEqual(cal.valor, Decimal("8.75"))

        # Consulta: GET posterior muestra la calificación registrada
        get_response = self.client.get("/panel/escolar/calificaciones/")
        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, str(self.inscripcion.pk))


# ---------------------------------------------------------------------------
# HU-025 — Edición de calificación ya capturada antes del cierre de acta
# ---------------------------------------------------------------------------

class CalificacionEdicionAntesDelCierreTests(TestCase):
    """HU-025 — Verifica que un Director Escolar puede editar (corregir) una
    calificación ya capturada siempre que el acta del grupo NO esté cerrada.

    El formulario CalificacionForm excluye el propio instance del check de
    duplicado, por lo que la edición debe persistir el nuevo valor.
    """

    def setUp(self):
        User = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.director = User.objects.create_user(
            username="director_edit_cal",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=self.director, rol=self.rol_director)

        alumno = Alumno.objects.create(
            matricula="MAT-EDICAL-001",
            nombres="Marcos",
            apellido_paterno="Vega",
            apellido_materno="Rivas",
            correo="marcos.vega.edical@test.local",
            telefono="5556001",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-edical",
            periodo="2026-12",
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=20,
            estado=Grupo.ESTADO_ACTIVO,
        )
        self.inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        # Calificación inicial ya capturada
        self.calificacion = Calificacion.objects.create(
            inscripcion=self.inscripcion,
            valor=Decimal("7.00"),
        )

    def test_editar_calificacion_antes_de_cierre_actualiza_valor(self):
        """POST ?edit=<pk> con nuevo valor actualiza la calificación en BD."""
        self.client.force_login(self.director)

        response = self.client.post(
            f"/panel/escolar/calificaciones/?edit={self.calificacion.pk}",
            {
                "inscripcion": str(self.inscripcion.pk),
                "valor": "9.50",
            },
        )

        # La vista redirige tras guardar correctamente
        self.assertEqual(response.status_code, 302)

        # El valor en BD debe haber cambiado
        self.calificacion.refresh_from_db()
        self.assertEqual(self.calificacion.valor, Decimal("9.50"))

    def test_editar_calificacion_no_crea_registro_duplicado(self):
        """Editar no genera una segunda Calificacion para la misma inscripcion."""
        self.client.force_login(self.director)

        self.client.post(
            f"/panel/escolar/calificaciones/?edit={self.calificacion.pk}",
            {
                "inscripcion": str(self.inscripcion.pk),
                "valor": "8.00",
            },
        )

        # Debe existir exactamente una calificación para esta inscripción
        self.assertEqual(
            Calificacion.objects.filter(
                inscripcion=self.inscripcion).count(), 1
        )
        self.calificacion.refresh_from_db()
        self.assertEqual(self.calificacion.valor, Decimal("8.00"))
