from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.sales.models import Concepto, CorteCaja, OrdenPOS, Pago
from apps.school.models import Alumno, Calificacion, Grupo, Inscripcion


class FiltrarSegmentarReportesHU047Tests(TestCase):
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

    def _user_with_role(self, username, role):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=role)
        return user

    def _crear_base_academica(self):
        alumno_a = Alumno.objects.create(
            matricula="A-HU047-001",
            nombres="Ana",
            apellido_paterno="Activa",
            correo="hu047_a@test.local",
        )
        alumno_b = Alumno.objects.create(
            matricula="A-HU047-002",
            nombres="Beto",
            apellido_paterno="Baja",
            correo="hu047_b@test.local",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu047-acad",
            periodo="2026-05",
            tipo_horario=Grupo.HORARIO_SEM,
            cupo=30,
            estado=Grupo.ESTADO_ACTIVO,
        )
        insc_a = Inscripcion.objects.create(
            alumno=alumno_a,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        insc_b = Inscripcion.objects.create(
            alumno=alumno_b,
            grupo=grupo,
            estado=Inscripcion.ESTADO_BAJA,
        )
        Calificacion.objects.create(inscripcion=insc_a, valor=Decimal("9.40"))
        Calificacion.objects.create(inscripcion=insc_b, valor=Decimal("7.10"))

    def _crear_base_comercial(self):
        alumno = Alumno.objects.create(
            matricula="A-HU047-003",
            nombres="Carla",
            apellido_paterno="Comercial",
            correo="hu047_c@test.local",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu047-com",
            periodo="2026-06",
            tipo_horario=Grupo.HORARIO_SEM,
            cupo=30,
            estado=Grupo.ESTADO_ACTIVO,
        )
        inscripcion = Inscripcion.objects.create(
            alumno=alumno,
            grupo=grupo,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        concepto_pagada = Concepto.objects.create(
            nombre="Concepto HU047 pagada",
            precio=Decimal("1000.00"),
            activo=True,
        )
        orden_pagada = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=OrdenPOS.ESTADO_PAGADA,
        )
        orden_pagada.items.create(
            concepto=concepto_pagada,
            cantidad=1,
            precio_unit=Decimal("1000.00"),
        )
        alumno_pendiente = Alumno.objects.create(
            matricula="A-HU047-004",
            nombres="Dario",
            apellido_paterno="Pendiente",
            correo="hu047_d@test.local",
        )
        grupo_pendiente = Grupo.objects.create(
            curso_slug="curso-hu047-com-pend",
            periodo="2026-07",
            tipo_horario=Grupo.HORARIO_SEM,
            cupo=30,
            estado=Grupo.ESTADO_ACTIVO,
        )
        inscripcion_pendiente = Inscripcion.objects.create(
            alumno=alumno_pendiente,
            grupo=grupo_pendiente,
            estado=Inscripcion.ESTADO_ACTIVA,
        )
        concepto_pendiente = Concepto.objects.create(
            nombre="Concepto HU047 pendiente",
            precio=Decimal("800.00"),
            activo=True,
        )
        orden_pendiente = OrdenPOS.objects.create(
            inscripcion=inscripcion_pendiente,
            estado=OrdenPOS.ESTADO_PENDIENTE,
        )
        orden_pendiente.items.create(
            concepto=concepto_pendiente,
            cantidad=1,
            precio_unit=Decimal("800.00"),
        )
        Pago.objects.create(
            orden=orden_pagada,
            monto=Decimal("1000.00"),
            metodo="EFECTIVO",
        )
        Pago.objects.create(
            orden=orden_pendiente,
            monto=Decimal("300.00"),
            metodo="TRANSFERENCIA",
        )
        CorteCaja.objects.create(
            fecha_operacion="2026-06-30",
            total_ordenes=1,
            total_pagos=1,
            notas="Corte junio",
        )

    def test_director_filtra_y_segmenta_reporte_academico(self):
        director = self._user_with_role("director_hu047", self.rol_director)
        self._crear_base_academica()

        self.client.force_login(director)
        response = self.client.get(
            "/panel/reportes/academico/?periodo=2026-05&estado=activa&calif_desde=9.00"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Segmentación por estado")
        self.assertContains(response, "Segmentación de calificaciones")

        self.assertEqual(response.context["estado_activo"], "activa")
        self.assertEqual(response.context["kpi"]["inscripciones"], 1)
        self.assertEqual(response.context["kpi"]["calificaciones"], 1)

        segmentos = response.context["segmentos_calificacion"]
        self.assertEqual(segmentos["alto_9_10"], 1)
        self.assertEqual(segmentos["medio_8_89"], 0)
        self.assertEqual(segmentos["bajo_menor_8"], 0)

        por_estado = list(response.context["inscripciones_por_estado"])
        self.assertEqual(len(por_estado), 1)
        self.assertEqual(por_estado[0]["estado"], "activa")

    def test_comercial_filtra_y_segmenta_reporte_comercial(self):
        comercial = self._user_with_role("comercial_hu047", self.rol_comercial)
        self._crear_base_comercial()

        self.client.force_login(comercial)
        response = self.client.get(
            "/panel/reportes/comercial/?estado=pagada&metodo=EFECTIVO"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Segmentación por estado de orden")
        self.assertContains(response, "Segmentación por método de pago")

        self.assertEqual(response.context["estado_activo"], "pagada")
        self.assertEqual(response.context["metodo_activo"], "EFECTIVO")
        self.assertEqual(response.context["kpi"]["ordenes_pos"], 1)
        self.assertEqual(response.context["kpi"]["pagos"], 1)

        por_estado = list(response.context["ordenes_por_estado"])
        self.assertEqual(len(por_estado), 1)
        self.assertEqual(por_estado[0]["estado"], "pagada")

        por_metodo = list(response.context["pagos_por_metodo"])
        self.assertEqual(len(por_metodo), 1)
        self.assertEqual(por_metodo[0]["metodo"], "EFECTIVO")
