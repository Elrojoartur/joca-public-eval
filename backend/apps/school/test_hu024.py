from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.sales.models import OrdenPOS
from apps.school.models import Alumno, Grupo, Inscripcion


class InscripcionesAdministracionFlowTests(TestCase):
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

    def _director_user(self, username="director_hu024"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_director)
        return user

    def _alumno(self, matricula="MAT-HU024-001", email="hu024_1@test.local"):
        return Alumno.objects.create(
            matricula=matricula,
            nombres="Ana",
            apellido_paterno="Perez",
            apellido_materno="Lopez",
            correo=email,
            telefono="5550001",
        )

    def _grupo(self, periodo="2026-04", cupo=2, estado=Grupo.ESTADO_ACTIVO):
        return Grupo.objects.create(
            curso_slug="curso-hu024",
            periodo=periodo,
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=cupo,
            estado=estado,
        )

    def test_director_can_create_inscripcion_and_logs_audit(self):
        director = self._director_user()
        alumno = self._alumno()
        grupo = self._grupo()
        self.client.force_login(director)

        response = self.client.post(
            "/panel/escolar/inscripciones/",
            {
                "action": "crear",
                "alumno_id": str(alumno.pk),
                "grupo_id": str(grupo.pk),
            },
        )

        self.assertEqual(response.status_code, 302)
        insc = Inscripcion.objects.get(alumno=alumno, grupo=grupo)
        self.assertEqual(insc.estado, Inscripcion.ESTADO_ACTIVA)
        self.assertTrue(OrdenPOS.objects.filter(inscripcion=insc).exists())
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::INSCRIPCION_CREAR",
                entidad="Inscripcion",
                entidad_id=str(insc.pk),
                detalle__alumno=alumno.pk,
                detalle__grupo=grupo.pk,
            ).exists()
        )

    def test_baja_y_reactivar_inscripcion_con_auditoria(self):
        director = self._director_user("director_hu024_baja")
        alumno = self._alumno("MAT-HU024-002", "hu024_2@test.local")
        grupo = self._grupo("2026-05", cupo=2)
        insc = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        self.client.force_login(director)

        baja = self.client.post(
            "/panel/escolar/inscripciones/",
            {
                "action": "baja",
                "id_inscripcion": str(insc.pk),
            },
        )
        self.assertEqual(baja.status_code, 302)
        insc.refresh_from_db()
        self.assertEqual(insc.estado, Inscripcion.ESTADO_BAJA)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::INSCRIPCION_BAJA",
                entidad_id=str(insc.pk),
            ).exists()
        )

        reactivar = self.client.post(
            "/panel/escolar/inscripciones/",
            {
                "action": "reactivar",
                "id_inscripcion": str(insc.pk),
            },
        )
        self.assertEqual(reactivar.status_code, 302)
        insc.refresh_from_db()
        self.assertEqual(insc.estado, Inscripcion.ESTADO_ACTIVA)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::INSCRIPCION_REACTIVAR",
                entidad_id=str(insc.pk),
            ).exists()
        )

    def test_no_permite_crear_inscripcion_si_grupo_esta_lleno(self):
        director = self._director_user("director_hu024_cupo")
        grupo = self._grupo("2026-06", cupo=1)
        alumno_1 = self._alumno("MAT-HU024-003", "hu024_3@test.local")
        alumno_2 = self._alumno("MAT-HU024-004", "hu024_4@test.local")
        Inscripcion.objects.create(
            alumno=alumno_1,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        self.client.force_login(director)

        response = self.client.post(
            "/panel/escolar/inscripciones/",
            {
                "action": "crear",
                "alumno_id": str(alumno_2.pk),
                "grupo_id": str(grupo.pk),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Inscripcion.objects.filter(alumno=alumno_2, grupo=grupo).exists()
        )

    def test_consulta_inscripciones_aplica_filtros(self):
        director = self._director_user("director_hu024_filter")
        self.client.force_login(director)
        alumno_1 = self._alumno("MAT-HU024-005", "hu024_5@test.local")
        alumno_2 = self._alumno("MAT-HU024-006", "hu024_6@test.local")
        grupo_1 = self._grupo("2026-07", cupo=3, estado=Grupo.ESTADO_ACTIVO)
        grupo_2 = self._grupo("2026-08", cupo=3, estado=Grupo.ESTADO_ACTIVO)

        insc_1 = Inscripcion.objects.create(
            alumno=alumno_1,
            grupo=grupo_1,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        Inscripcion.objects.create(
            alumno=alumno_2,
            grupo=grupo_2,
            estado=Inscripcion.ESTADO_BAJA,
        )

        response = self.client.get(
            "/panel/escolar/inscripciones/?periodo=2026-07&estado=activa"
        )

        self.assertEqual(response.status_code, 200)
        inscripciones = list(response.context["inscripciones"])
        self.assertEqual(len(inscripciones), 1)
        self.assertEqual(inscripciones[0].pk, insc_1.pk)

    def test_director_puede_editar_inscripcion_y_mover_a_otro_grupo(self):
        director = self._director_user("director_hu024_edit")
        self.client.force_login(director)

        alumno = self._alumno("MAT-HU024-007", "hu024_7@test.local")
        grupo_origen = self._grupo(
            "2026-09", cupo=2, estado=Grupo.ESTADO_ACTIVO)
        grupo_destino = self._grupo(
            "2026-10", cupo=2, estado=Grupo.ESTADO_ACTIVO)

        insc = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo_origen,
            estado=Inscripcion.ESTADO_ACTIVA,
        )

        response = self.client.post(
            "/panel/escolar/inscripciones/",
            {
                "action": "editar",
                "id_inscripcion": str(insc.pk),
                "grupo_id_editar": str(grupo_destino.pk),
            },
        )

        self.assertEqual(response.status_code, 302)
        insc.refresh_from_db()
        self.assertEqual(insc.grupo_id, grupo_destino.pk)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::INSCRIPCION_EDITAR",
                entidad_id=str(insc.pk),
                detalle__grupo_nuevo=grupo_destino.pk,
            ).exists()
        )

    def test_usuario_sin_rol_director_superusuario_recibe_403(self):
        user = self.user_model.objects.create_user(
            username="alumno_hu024",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_alumno)
        self.client.force_login(user)

        response = self.client.get("/panel/escolar/inscripciones/")

        self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# HU-024 — Baja de inscripción con reversión de OrdenPOS
# ---------------------------------------------------------------------------

class InscripcionBajaReversionOrdenTests(TestCase):
    """HU-024 — Verifica que al dar de baja una inscripción la OrdenPOS
    asociada queda en estado 'cancelada', cerrando el flujo de facturación.
    """

    def setUp(self):
        User = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.director = User.objects.create_user(
            username="director_baja_orden",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=self.director, rol=self.rol_director)

        self.alumno = Alumno.objects.create(
            matricula="MAT-BAJA-ORD-001",
            nombres="Sofía",
            apellido_paterno="Reyes",
            apellido_materno="Mora",
            correo="sofia.reyes.baja@test.local",
            telefono="5559001",
        )
        self.grupo = Grupo.objects.create(
            curso_slug="curso-baja-orden",
            periodo="2026-11",
            tipo_horario=Grupo.HORARIO_SAB,
            cupo=10,
            estado=Grupo.ESTADO_ACTIVO,
        )
        self.insc = Inscripcion.objects.create(
            alumno=self.alumno,
            grupo=self.grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        # Crear OrdenPOS pendiente asociada a la inscripción
        self.orden = OrdenPOS.objects.create(
            inscripcion=self.insc,
            estado=OrdenPOS.ESTADO_PENDIENTE,
        )

    def test_baja_inscripcion_cancela_orden_pos_asociada(self):
        """Al dar de baja una inscripción, la OrdenPOS debe quedar en 'cancelada'."""
        self.client.force_login(self.director)

        response = self.client.post(
            "/panel/escolar/inscripciones/",
            {
                "action": "baja",
                "id_inscripcion": str(self.insc.pk),
            },
        )

        self.assertEqual(response.status_code, 302)

        # La inscripción queda en baja
        self.insc.refresh_from_db()
        self.assertEqual(self.insc.estado, Inscripcion.ESTADO_BAJA)

        # La OrdenPOS queda cancelada
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, OrdenPOS.ESTADO_CANCELADA)

        # Auditoría registrada
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="ESCOLAR::INSCRIPCION_BAJA",
                entidad_id=str(self.insc.pk),
            ).exists()
        )

    def test_baja_sobre_orden_ya_cancelada_no_falla(self):
        """Si la OrdenPOS ya estaba cancelada, la baja no lanza error."""
        self.orden.estado = OrdenPOS.ESTADO_CANCELADA
        self.orden.save(update_fields=["estado"])

        self.client.force_login(self.director)

        response = self.client.post(
            "/panel/escolar/inscripciones/",
            {
                "action": "baja",
                "id_inscripcion": str(self.insc.pk),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.insc.refresh_from_db()
        self.assertEqual(self.insc.estado, Inscripcion.ESTADO_BAJA)
        # La orden permanece cancelada sin error
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, OrdenPOS.ESTADO_CANCELADA)
