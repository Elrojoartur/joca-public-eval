from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.sales.models import Concepto, CorteCaja, OrdenPOS, Pago
from apps.school.models import Alumno, Grupo, Inscripcion


class CorteCajaTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )

    def _comercial_user(self, username="comercial_hu035"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_comercial)
        return user

    def _inscripcion(self, matricula="MAT-HU035-001", correo="hu035_1@test.local", periodo="2028-02"):
        alumno = Alumno.objects.create(
            matricula=matricula,
            nombres="Erika",
            apellido_paterno="Nava",
            apellido_materno="Silva",
            correo=correo,
            telefono="5553501",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu035",
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

    def test_realiza_corte_con_confirmacion_y_audita(self):
        comercial = self._comercial_user()
        inscripcion = self._inscripcion()
        concepto = Concepto.objects.create(
            nombre="Concepto HU035 cierre",
            precio=Decimal("900.00"),
            activo=True,
        )
        orden = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=OrdenPOS.ESTADO_PAGADA,
        )
        orden.items.create(concepto=concepto, cantidad=1,
                           precio_unit=Decimal("900.00"))
        Pago.objects.create(
            orden=orden,
            monto=Decimal("900.00"),
            metodo="EFECTIVO",
        )
        self.client.force_login(comercial)

        response = self.client.post(
            "/panel/ventas/corte-caja/",
            {
                "confirmar": "SI",
                "notas": "Cierre diario turno matutino",
            },
        )

        self.assertEqual(response.status_code, 302)
        corte = CorteCaja.objects.get(fecha_operacion=timezone.localdate())
        self.assertEqual(corte.total_ordenes, 1)
        self.assertEqual(corte.total_pagos, 1)
        resumen = CorteCaja.resumen_calculado(timezone.localdate())
        self.assertEqual(resumen["monto_ordenes"], Decimal("900.00"))
        self.assertEqual(resumen["monto_pagos"], Decimal("900.00"))
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="VENTAS::CORTE_CAJA",
                entidad="CorteCaja",
                entidad_id=str(corte.pk),
                detalle__fecha_operacion=str(timezone.localdate()),
            ).exists()
        )

    def test_no_permite_corte_duplicado_mismo_dia(self):
        comercial = self._comercial_user("comercial_hu035_dup")
        CorteCaja.objects.create(
            fecha_operacion=timezone.localdate(),
            total_ordenes=0,
            total_pagos=0,
            realizado_por=comercial,
        )
        self.client.force_login(comercial)

        response = self.client.post(
            "/panel/ventas/corte-caja/",
            {
                "confirmar": "SI",
                "notas": "Intento duplicado",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(CorteCaja.objects.filter(
            fecha_operacion=timezone.localdate()).count(), 1)

    def test_bloquea_venta_post_corte_para_comercial(self):
        comercial = self._comercial_user("comercial_hu035_block_pos")
        inscripcion = self._inscripcion("MAT-HU035-002", "hu035_2@test.local")
        concepto = Concepto.objects.create(
            nombre="Concepto HU035",
            precio=Decimal("450.00"),
            activo=True,
        )
        CorteCaja.objects.create(
            fecha_operacion=timezone.localdate(),
            total_ordenes=0,
            total_pagos=0,
            realizado_por=comercial,
        )
        self.client.force_login(comercial)

        response = self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(inscripcion.pk),
                "concepto_id": str(concepto.pk),
                "cantidad": "1",
                "metodo": "EFECTIVO",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            OrdenPOS.objects.filter(
                inscripcion=inscripcion,
            ).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="VENTAS::MOVIMIENTO_DENEGADO_POST_CORTE",
                detalle__modulo="pos",
            ).exists()
        )

    def test_bloquea_pago_post_corte_para_comercial(self):
        comercial = self._comercial_user("comercial_hu035_block_pay")
        inscripcion = self._inscripcion("MAT-HU035-003", "hu035_3@test.local")
        concepto = Concepto.objects.create(
            nombre="Concepto HU035 pago",
            precio=Decimal("1000.00"),
            activo=True,
        )
        orden = OrdenPOS.objects.create(
            inscripcion=inscripcion,
            estado=OrdenPOS.ESTADO_PENDIENTE,
        )
        orden.items.create(concepto=concepto, cantidad=1,
                           precio_unit=Decimal("1000.00"))
        CorteCaja.objects.create(
            fecha_operacion=timezone.localdate(),
            total_ordenes=0,
            total_pagos=0,
            realizado_por=comercial,
        )
        self.client.force_login(comercial)

        response = self.client.post(
            "/panel/ventas/estado-cuenta/",
            {
                "orden_id": str(orden.pk),
                "monto": "100.00",
                "metodo": "EFECTIVO",
                "auth_code": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Pago.objects.filter(orden=orden).count(), 0)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="VENTAS::MOVIMIENTO_DENEGADO_POST_CORTE",
                detalle__modulo="estado_cuenta",
            ).exists()
        )
