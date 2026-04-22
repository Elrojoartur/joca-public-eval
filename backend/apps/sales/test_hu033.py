from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.sales.models import Concepto, OrdenPOS
from apps.school.models import Alumno, Grupo, Inscripcion


class DescuentoAutorizadoPosTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )
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

    def _comercial_user(self, username="comercial_hu033"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_comercial)
        return user

    def _director_user(self, username="director_hu033"):
        user = self.user_model.objects.create_user(
            username=username,
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=user, rol=self.rol_director)
        return user

    def _inscripcion(self, matricula="MAT-HU033-001", correo="hu033_1@test.local", periodo="2027-12"):
        alumno = Alumno.objects.create(
            matricula=matricula,
            nombres="Nora",
            apellido_paterno="Saenz",
            apellido_materno="Vega",
            correo=correo,
            telefono="5553301",
        )
        grupo = Grupo.objects.create(
            curso_slug="curso-hu033",
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

    def test_aplica_descuento_autorizado_con_director_y_audita(self):
        comercial = self._comercial_user()
        director = self._director_user()
        inscripcion = self._inscripcion()
        concepto = Concepto.objects.create(
            nombre="Colegiatura HU033",
            precio=Decimal("1000.00"),
            activo=True,
        )
        self.client.force_login(comercial)

        response = self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(inscripcion.pk),
                "concepto_id": str(concepto.pk),
                "cantidad": "1",
                "descuento_pct": "20",
                "descuento_motivo": "Beca parcial",
                "autoriza_username": director.username,
                "metodo": "EFECTIVO",
            },
        )

        self.assertEqual(response.status_code, 302)
        orden = OrdenPOS.objects.get(inscripcion=inscripcion)
        self.assertEqual(orden.total_calculado, Decimal("800.00"))
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="VENTAS::DESCUENTO_APLICADO",
                entidad="OrdenPOS",
                entidad_id=str(orden.pk),
                detalle__autoriza=director.username,
                detalle__descuento_pct="20",
            ).exists()
        )

    def test_rechaza_descuento_sin_autorizador(self):
        comercial = self._comercial_user("comercial_hu033_noauth")
        inscripcion = self._inscripcion("MAT-HU033-002", "hu033_2@test.local")
        concepto = Concepto.objects.create(
            nombre="Material HU033",
            precio=Decimal("500.00"),
            activo=True,
        )
        self.client.force_login(comercial)

        response = self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(inscripcion.pk),
                "concepto_id": str(concepto.pk),
                "cantidad": "1",
                "descuento_pct": "10",
                "descuento_motivo": "Promo",
                "metodo": "EFECTIVO",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            OrdenPOS.objects.filter(
                inscripcion=inscripcion,
            ).exists()
        )

    def test_rechaza_descuento_sobre_tope_para_comercial(self):
        comercial = self._comercial_user("comercial_hu033_tope")
        director = self._director_user("director_hu033_tope")
        inscripcion = self._inscripcion("MAT-HU033-003", "hu033_3@test.local")
        concepto = Concepto.objects.create(
            nombre="Servicio HU033",
            precio=Decimal("700.00"),
            activo=True,
        )
        self.client.force_login(comercial)

        response = self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(inscripcion.pk),
                "concepto_id": str(concepto.pk),
                "cantidad": "1",
                "descuento_pct": "40",
                "descuento_motivo": "Beca extendida",
                "autoriza_username": director.username,
                "metodo": "EFECTIVO",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            OrdenPOS.objects.filter(
                inscripcion=inscripcion,
            ).exists()
        )

    def test_descuento_100_es_rechazado_porque_total_queda_cero(self):
        """Un descuento del 100% deja total=0, que la vista rechaza explícitamente."""
        comercial = self._comercial_user("comercial_hu033_100")
        director = self._director_user("director_hu033_100")
        inscripcion = self._inscripcion(
            "MAT-HU033-100", "hu033_100@test.local", "2028-06")
        concepto = Concepto.objects.create(
            nombre="Colegiatura HU033-100",
            precio=Decimal("500.00"),
            activo=True,
        )
        self.client.force_login(comercial)

        response = self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(inscripcion.pk),
                "concepto_id": str(concepto.pk),
                "cantidad": "1",
                "descuento_pct": "100",
                "descuento_motivo": "Beca completa",
                "autoriza_username": director.username,
                "metodo": "EFECTIVO",
            },
        )

        # La vista redirige (no 500)
        self.assertEqual(response.status_code, 302)
        # La orden NO se crea porque total=0 queda rechazado
        self.assertFalse(
            OrdenPOS.objects.filter(inscripcion=inscripcion).exists()
        )

    def test_descuento_requiere_motivo_no_vacio(self):
        """Un descuento > 0 sin motivo debe ser rechazado (motivo obligatorio)."""
        comercial = self._comercial_user("comercial_hu033_nomot")
        director = self._director_user("director_hu033_nomot")
        inscripcion = self._inscripcion(
            "MAT-HU033-NOMOT", "hu033_nomot@test.local", "2028-07")
        concepto = Concepto.objects.create(
            nombre="Servicio HU033-NOMOT",
            precio=Decimal("600.00"),
            activo=True,
        )
        self.client.force_login(comercial)

        response = self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(inscripcion.pk),
                "concepto_id": str(concepto.pk),
                "cantidad": "1",
                "descuento_pct": "10",
                "descuento_motivo": "",   # motivo vacío
                "autoriza_username": director.username,
                "metodo": "EFECTIVO",
            },
        )

        self.assertEqual(response.status_code, 302)
        # Sin motivo no se genera orden
        self.assertFalse(
            OrdenPOS.objects.filter(inscripcion=inscripcion).exists()
        )

    def test_rechaza_autorizador_sin_rol_valido(self):
        comercial = self._comercial_user("comercial_hu033_badrole")
        bad_authorizer = self.user_model.objects.create_user(
            username="alumno_autoriza_no",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=bad_authorizer, rol=self.rol_alumno)
        inscripcion = self._inscripcion("MAT-HU033-004", "hu033_4@test.local")
        concepto = Concepto.objects.create(
            nombre="Colegiatura HU033-B",
            precio=Decimal("900.00"),
            activo=True,
        )
        self.client.force_login(comercial)

        response = self.client.post(
            "/panel/ventas/pos/",
            {
                "inscripcion_id": str(inscripcion.pk),
                "concepto_id": str(concepto.pk),
                "cantidad": "1",
                "descuento_pct": "15",
                "descuento_motivo": "Caso especial",
                "autoriza_username": bad_authorizer.username,
                "metodo": "EFECTIVO",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            OrdenPOS.objects.filter(
                inscripcion=inscripcion,
            ).exists()
        )
