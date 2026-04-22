from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.sales.models import Concepto, CorteCaja, OrdenPOS, Pago
from apps.school.models import Alumno, Calificacion, Grupo, Inscripcion


class ExportarReportesHU046Tests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.rol_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
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

    def _crear_base_academica(self, periodo="2026-01"):
        alumno = Alumno.objects.create(
            matricula="A-HU046-001",
            nombres="Alumno",
            apellido_paterno="Demo",
            correo="hu046_acad@test.local",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu046-acad",
            periodo=periodo,
            tipo_horario=Grupo.HORARIO_SEM,
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
            valor=Decimal("9.10"),
        )

    def _crear_base_comercial(self, periodo="2026-02"):
        alumno = Alumno.objects.create(
            matricula="A-HU046-002",
            nombres="Alumno",
            apellido_paterno="Comercial",
            correo="hu046_com@test.local",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu046-com",
            periodo=periodo,
            tipo_horario=Grupo.HORARIO_SEM,
            cupo=30,
            estado=Grupo.ESTADO_ACTIVO,
        )
        inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        concepto = Concepto.objects.create(
            nombre="Concepto HU046",
            precio=Decimal("1500.00"),
            activo=True,
        )
        orden = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=OrdenPOS.ESTADO_PAGADA,
        )
        orden.items.create(concepto=concepto, cantidad=1,
                           precio_unit=Decimal("1500.00"))
        Pago.objects.create(
            orden=orden,
            monto=Decimal("1500.00"),
            metodo="EFECTIVO",
        )
        CorteCaja.objects.create(
            fecha_operacion="2026-02-27",
            total_ordenes=1,
            total_pagos=1,
            notas="Corte HU046",
        )

    def test_director_exporta_reporte_academico_csv_con_hash(self):
        director = self._user_with_role(
            "director_hu046_csv", self.rol_director)
        self._crear_base_academica(periodo="2026-01")
        self.client.force_login(director)

        response = self.client.get(
            "/panel/reportes/academico/?periodo=2026-01&export=csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("X-Export-SHA256", response)
        payload = response.content.decode("utf-8")
        self.assertIn("inscripciones", payload)
        self.assertIn("calificaciones", payload)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="REPORTES::ACADEMICO_EXPORT",
                entidad="ReporteAcademico",
                resultado="ok",
                detalle__format="csv",
            ).exists()
        )

    def test_director_exporta_reporte_academico_pdf_con_hash(self):
        director = self._user_with_role(
            "director_hu046_pdf", self.rol_director)
        self._crear_base_academica(periodo="2026-03")
        self.client.force_login(director)

        response = self.client.get(
            "/panel/reportes/academico/?periodo=2026-03&export=pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("X-Export-SHA256", response)
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="REPORTES::ACADEMICO_EXPORT",
                entidad="ReporteAcademico",
                resultado="ok",
                detalle__format="pdf",
            ).exists()
        )

    def test_comercial_exporta_reporte_comercial_csv_con_hash(self):
        comercial = self._user_with_role(
            "comercial_hu046_csv", self.rol_comercial)
        self._crear_base_comercial(periodo="2026-02")
        self.client.force_login(comercial)

        response = self.client.get(
            "/panel/reportes/comercial/?periodo=2026-02&export=csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("X-Export-SHA256", response)
        payload = response.content.decode("utf-8")
        self.assertIn("ventas", payload)
        self.assertIn("cortes", payload)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="REPORTES::COMERCIAL_EXPORT",
                entidad="ReporteComercial",
                resultado="ok",
                detalle__format="csv",
            ).exists()
        )

    def test_comercial_exporta_reporte_comercial_pdf_con_hash(self):
        comercial = self._user_with_role(
            "comercial_hu046_pdf", self.rol_comercial)
        self._crear_base_comercial(periodo="2026-04")
        self.client.force_login(comercial)

        response = self.client.get(
            "/panel/reportes/comercial/?periodo=2026-04&export=pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("X-Export-SHA256", response)
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="REPORTES::COMERCIAL_EXPORT",
                entidad="ReporteComercial",
                resultado="ok",
                detalle__format="pdf",
            ).exists()
        )

    def test_alumno_no_puede_exportar_reportes(self):
        alumno = self._user_with_role("alumno_hu046", self.rol_alumno)
        self.client.force_login(alumno)

        response_academico = self.client.get(
            "/panel/reportes/academico/?export=csv")
        response_comercial = self.client.get(
            "/panel/reportes/comercial/?export=pdf")

        self.assertEqual(response_academico.status_code, 403)
        self.assertEqual(response_comercial.status_code, 403)


# PCB-020 / MOD-07 / HU-046 – Exportación de reportes en PDF y CSV
class PCB020ExportarReportesTests(TestCase):
    """PCB-020 / MOD-07 / HU-046 – Exportación de reportes en PDF y CSV.

    Verifica que la vista reporte_academico entrega correctamente archivos
    CSV y PDF: status 200, content-type apropiado, cabecera
    Content-Disposition con 'attachment' y contenido no vacío.
    Se usa el reporte académico porque es accesible con DIRECTOR_ESCOLAR
    y acepta ?export=csv / ?export=pdf sin parámetros adicionales.
    """

    def setUp(self):
        User = get_user_model()
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.director = User.objects.create_user(
            username="pcb020_director",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=self.director, rol=self.rol_director)

        # Datos mínimos: 1 inscripción activa con calificación
        alumno = Alumno.objects.create(
            matricula="MAT-PCB020-001",
            nombres="Carlos",
            apellido_paterno="Reyes",
            correo="pcb020_alumno@test.local",
        )
        grupo = Grupo.objects.create(
            curso_slug="pcb020-curso",
            periodo="2026-10",
            tipo_horario=Grupo.HORARIO_SEM,
            cupo=25,
            estado=Grupo.ESTADO_ACTIVO,
        )
        inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        Calificacion.objects.create(
            inscripcion=inscripcion,
            valor=Decimal("8.50"),
        )

    def test_exportacion_csv_reporte_academico(self):
        """GET ?export=csv → text/csv, Content-Disposition attachment, body con cabeceras CSV."""
        self.client.force_login(self.director)

        response = self.client.get("/panel/reportes/academico/?export=csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(len(response.content) > 0)
        payload = response.content.decode("utf-8")
        self.assertIn("seccion", payload)   # cabecera real del CSV académico
        self.assertIn("X-Export-SHA256", response)

    def test_exportacion_pdf_reporte_academico(self):
        """GET ?export=pdf → application/pdf, Content-Disposition attachment, firma %PDF."""
        self.client.force_login(self.director)

        response = self.client.get("/panel/reportes/academico/?export=pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn("X-Export-SHA256", response)
