from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.school.models import ActaCierre, Alumno, Calificacion, Grupo, Inscripcion


class CierreActaPorGrupoFlowTests(TestCase):
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

    def _director_user(self, username="director_hu028"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_director)
        return user

    def _inscripcion(self, matricula="MAT-HU028-001", correo="hu028_1@test.local", periodo="2027-02"):
        alumno = Alumno.objects.create(
            matricula=matricula,
            nombres="Eva",
            apellido_paterno="Nava",
            apellido_materno="Soto",
            correo=correo,
            telefono="5552801",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu028",
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

    def test_director_can_close_acta_and_generates_audit_event(self):
        director = self._director_user()
        inscripcion = self._inscripcion()
        self.client.force_login(director)

        response = self.client.post(
            "/panel/escolar/acta/cerrar/",
            {
                "grupo": str(inscripcion.grupo.pk),
                "periodo": inscripcion.grupo.periodo,
                "motivo": "Cierre final de grupo",
            },
        )

        self.assertEqual(response.status_code, 302)
        acta = ActaCierre.objects.get(
            grupo=inscripcion.grupo,
        )
        self.assertEqual(acta.cerrada_por, director)
        self.assertEqual(acta.motivo, "Cierre final de grupo")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::CIERRE_ACTA",
                entidad="ActaCierre",
                entidad_id=str(acta.pk),
                detalle__grupo=inscripcion.grupo.pk,
                detalle__periodo=inscripcion.grupo.periodo,
            ).exists()
        )

    def test_no_duplicate_close_for_same_grupo_periodo(self):
        director = self._director_user("director_hu028_dup")
        inscripcion = self._inscripcion(
            "MAT-HU028-002", "hu028_2@test.local", "2027-03")
        self.client.force_login(director)

        first = self.client.post(
            "/panel/escolar/acta/cerrar/",
            {
                "grupo": str(inscripcion.grupo.pk),
                "periodo": inscripcion.grupo.periodo,
                "motivo": "Primer cierre",
            },
        )
        self.assertEqual(first.status_code, 302)

        second = self.client.post(
            "/panel/escolar/acta/cerrar/",
            {
                "grupo": str(inscripcion.grupo.pk),
                "periodo": inscripcion.grupo.periodo,
                "motivo": "Intento duplicado",
            },
        )

        self.assertEqual(second.status_code, 302)
        self.assertEqual(
            ActaCierre.objects.filter(
                grupo=inscripcion.grupo,
            ).count(),
            1,
        )

    def test_director_cannot_capture_calificacion_after_acta_close(self):
        director = self._director_user("director_hu028_lock")
        inscripcion = self._inscripcion(
            "MAT-HU028-003", "hu028_3@test.local", "2027-04")
        ActaCierre.objects.create(
            grupo=inscripcion.grupo,
            cerrada_por=director,
            motivo="Acta cerrada",
        )
        self.client.force_login(director)

        response = self.client.post(
            "/panel/escolar/calificaciones/",
            {
                "inscripcion": str(inscripcion.pk),
                "valor": "8.50",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "acta de ese grupo ya está cerrada")
        self.assertFalse(Calificacion.objects.filter(
            inscripcion=inscripcion).exists())

    def test_usuario_sin_rol_director_superusuario_recibe_403_en_cierre_acta(self):
        student_user = self.user_model.objects.create_user(
            username="alumno_hu028",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=student_user, rol=self.rol_alumno)
        inscripcion = self._inscripcion(
            "MAT-HU028-004", "hu028_4@test.local", "2027-05")
        self.client.force_login(student_user)

        response = self.client.post(
            "/panel/escolar/acta/cerrar/",
            {
                "grupo": str(inscripcion.grupo.pk),
                "periodo": inscripcion.grupo.periodo,
                "motivo": "No autorizado",
            },
        )

        self.assertEqual(response.status_code, 403)


# PCB-015 / MOD-04 / HU-028 – Cierre de acta de calificaciones por grupo
class PCB015CierreActaTests(TestCase):
    """PCB-015 / MOD-04 / HU-028 – Cierre de acta de calificaciones por grupo.

    Verifica que un Director Escolar puede cerrar el acta de un grupo,
    que el registro de ActaCierre queda persistido con los datos correctos,
    que el acta bloquea la captura posterior de calificaciones y que el
    evento de auditoría correspondiente queda registrado.
    """

    def setUp(self):
        User = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.director = User.objects.create_user(
            username="pcb015_director",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=self.director, rol=self.rol_director)

        alumno = Alumno.objects.create(
            matricula="MAT-PCB015-001",
            nombres="Marco",
            apellido_paterno="Luna",
            apellido_materno="Rios",
            correo="pcb015_alumno@test.local",
            telefono="5550015",
        )
        self.grupo = Grupo.objects.create(
            curso_slug="pcb015-curso",
            periodo="2026-06",
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=20,
            estado=Grupo.ESTADO_ACTIVO,
        )
        self.inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=self.grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )

    def test_cierre_acta_persiste_bloquea_y_audita(self):
        self.client.force_login(self.director)

        # Cierre del acta: POST con grupo, periodo y motivo
        post_response = self.client.post(
            "/panel/escolar/acta/cerrar/",
            {
                "grupo": str(self.grupo.pk),
                "periodo": self.grupo.periodo,
                "motivo": "PCB-015 cierre final",
            },
        )

        # Vista redirige tras cerrar correctamente
        self.assertEqual(post_response.status_code, 302)

        # ActaCierre persistida con datos correctos
        acta = ActaCierre.objects.get(grupo=self.grupo)
        self.assertEqual(acta.cerrada_por, self.director)
        self.assertEqual(acta.motivo, "PCB-015 cierre final")

        # Bloqueo: intento de captura de calificación rechazado
        bloqueo = self.client.post(
            "/panel/escolar/calificaciones/",
            {
                "inscripcion": str(self.inscripcion.pk),
                "valor": "9.00",
            },
        )
        self.assertEqual(bloqueo.status_code, 200)
        self.assertContains(bloqueo, "acta de ese grupo ya está cerrada")
        self.assertFalse(Calificacion.objects.filter(
            inscripcion=self.inscripcion).exists())

        # Auditoría de cierre registrada
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::CIERRE_ACTA",
                entidad="ActaCierre",
                entidad_id=str(acta.pk),
                detalle__grupo=self.grupo.pk,
            ).exists()
        )
