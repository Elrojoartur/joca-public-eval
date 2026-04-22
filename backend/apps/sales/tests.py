from django.contrib.auth import get_user_model
from django.test import TestCase
from decimal import Decimal

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria
from apps.school.models import Alumno, Curso, Grupo, Inscripcion, Periodo
from apps.sales.models import Concepto, OrdenItem, OrdenPOS


class VentasBacklogHuTests(TestCase):
    def setUp(self):
        role = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )
        self.user = get_user_model().objects.create_user(
            username="comercial_hu",
            password="testpass123",
        )
        UsuarioRol.objects.create(usuario=self.user, rol=role)
        self.client.force_login(self.user)

    def test_hu_fut_002_compras_get_200(self):
        response = self.client.get("/panel/ventas/inventario/compras/")
        self.assertEqual(response.status_code, 200)

    def test_hu_fut_003_proveedores_post_redirect(self):
        response = self.client.post(
            "/panel/ventas/inventario/proveedores/",
            {"nombre": "Proveedor Demo",
             "rfc": "XAXX010101000", "contacto": "demo"},
        )
        self.assertEqual(response.status_code, 302)

    def test_hu_fut_005_datos_fiscales_post_redirect(self):
        response = self.client.post(
            "/panel/ventas/facturacion/datos-fiscales/",
            {
                "requiere_factura": "on",
                "razon_social": "Cliente Demo SA de CV",
                "rfc": "XAXX010101000",
                "cp_fiscal": "01010",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_hu_fut_002_compras_permite_editar_y_eliminar_en_sesion(self):
        create_response = self.client.post(
            "/panel/ventas/inventario/compras/",
            {
                "action": "save",
                "proveedor": "Proveedor Base",
                "referencia": "FAC-1001",
                "total": "1200.50",
            },
        )
        self.assertEqual(create_response.status_code, 302)

        compras = self.client.session.get("inv_compras_demo", [])
        self.assertEqual(len(compras), 1)
        item_id = compras[0]["id"]

        update_response = self.client.post(
            "/panel/ventas/inventario/compras/",
            {
                "action": "save",
                "item_id": item_id,
                "proveedor": "Proveedor Editado",
                "referencia": "FAC-2002",
                "total": "1500.00",
            },
        )
        self.assertEqual(update_response.status_code, 302)

        compras = self.client.session.get("inv_compras_demo", [])
        self.assertEqual(compras[0]["proveedor"], "Proveedor Editado")
        self.assertEqual(compras[0]["referencia"], "FAC-2002")

        delete_response = self.client.post(
            "/panel/ventas/inventario/compras/",
            {
                "action": "delete",
                "item_id": item_id,
            },
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertEqual(self.client.session.get("inv_compras_demo", []), [])

    def test_hu_fut_003_proveedores_permite_editar_y_eliminar_en_sesion(self):
        create_response = self.client.post(
            "/panel/ventas/inventario/proveedores/",
            {
                "action": "save",
                "nombre": "Proveedor Demo",
                "rfc": "XAXX010101000",
                "contacto": "demo",
            },
        )
        self.assertEqual(create_response.status_code, 302)

        proveedores = self.client.session.get("inv_proveedores_demo", [])
        self.assertEqual(len(proveedores), 1)
        item_id = proveedores[0]["id"]

        update_response = self.client.post(
            "/panel/ventas/inventario/proveedores/",
            {
                "action": "save",
                "item_id": item_id,
                "nombre": "Proveedor Editado",
                "rfc": "XAXX010101000",
                "contacto": "contacto nuevo",
            },
        )
        self.assertEqual(update_response.status_code, 302)

        proveedores = self.client.session.get("inv_proveedores_demo", [])
        self.assertEqual(proveedores[0]["nombre"], "Proveedor Editado")

        delete_response = self.client.post(
            "/panel/ventas/inventario/proveedores/",
            {
                "action": "delete",
                "item_id": item_id,
            },
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertEqual(self.client.session.get(
            "inv_proveedores_demo", []), [])


class VentasControlCuentasTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.rol_admin_comercial = Rol.objects.create(
            nombre="Administrativo Comercial",
            codigo="ADMINISTRATIVO_COMERCIAL",
            activo=True,
        )
        self.rol_alumno = Rol.objects.create(
            nombre="Alumno",
            codigo="ALUMNO",
            activo=True,
        )
        self.rol_cliente = Rol.objects.create(
            nombre="Cliente",
            codigo="CLIENTE",
            activo=True,
        )
        self.rol_director = Rol.objects.create(
            nombre="Director Escolar",
            codigo="DIRECTOR_ESCOLAR",
            activo=True,
        )
        self.curso = Curso.objects.create(
            codigo="CURSO-TEST", nombre="Curso Test")
        self.periodo = Periodo.objects.create(
            codigo="2026-09",
            **Periodo.defaults_for("2026-09"),
        )
        self.grupo = Grupo.objects.create(
            curso_ref=self.curso,
            periodo_ref=self.periodo,
            tipo_horario=Grupo.HORARIO_SEM,
            turno=Grupo.TURNO_PM,
            cupo=30,
            estado=Grupo.ESTADO_ACTIVO,
        )

    def test_usuario_sin_rol_recibe_403_en_control_cuentas(self):
        user = self.user_model.objects.create_user(
            username="sinrol", password="testpass123")
        self.client.force_login(user)

        response = self.client.get("/panel/ventas/cuentas/")

        self.assertEqual(response.status_code, 403)

    def test_admin_comercial_puede_crear_alumno_y_cliente(self):
        user = self.user_model.objects.create_user(
            username="admincom", password="testpass123")
        UsuarioRol.objects.create(usuario=user, rol=self.rol_admin_comercial)
        self.client.force_login(user)

        alumno_resp = self.client.post(
            "/panel/ventas/cuentas/",
            {
                "tipo": "alumno",
                "username": "alumno_nuevo",
                "correo": "alumno_nuevo@test.local",
                "password": "testpass123",
                "nombres": "Alumno",
                "apellido_paterno": "Demo",
                "matricula": "MAT-9001",
                "grupo_id": str(self.grupo.pk),
            },
        )
        cliente_resp = self.client.post(
            "/panel/ventas/cuentas/",
            {
                "tipo": "cliente",
                "username": "cliente_nuevo",
                "correo": "cliente_nuevo@test.local",
                "password": "testpass123",
            },
        )

        self.assertEqual(alumno_resp.status_code, 302)
        self.assertEqual(cliente_resp.status_code, 302)
        self.assertTrue(Alumno.objects.filter(matricula="MAT-9001").exists())
        alumno = Alumno.objects.get(matricula="MAT-9001")
        self.assertTrue(
            Inscripcion.objects.filter(
                alumno=alumno,
                grupo=self.grupo,
                estado=Inscripcion.ESTADO_ACTIVA,
            ).exists()
        )
        insc = Inscripcion.objects.get(alumno=alumno, grupo=self.grupo)
        orden = OrdenPOS.objects.get(inscripcion=insc)
        self.assertEqual(orden.total_calculado, 1000)
        self.assertTrue(
            OrdenItem.objects.filter(
                orden=orden,
                concepto__nombre="Inscripcion escolar",
                precio_unit=1000,
            ).exists()
        )
        self.assertTrue(self.user_model.objects.filter(
            username="cliente_nuevo").exists())
        alumno_user = self.user_model.objects.get(username="alumno_nuevo")
        self.assertTrue(
            UsuarioRol.objects.filter(
                usuario=alumno_user,
                rol=self.rol_alumno,
            ).exists()
        )

    def test_alta_alumno_con_factura_aplica_iva_en_venta_inscripcion(self):
        user = self.user_model.objects.create_user(
            username="admincom_factura", password="testpass123")
        UsuarioRol.objects.create(usuario=user, rol=self.rol_admin_comercial)
        self.client.force_login(user)

        response = self.client.post(
            "/panel/ventas/cuentas/",
            {
                "tipo": "alumno",
                "username": "alumno_factura",
                "correo": "alumno_factura@test.local",
                "password": "testpass123",
                "nombres": "Alumno",
                "apellido_paterno": "Factura",
                "matricula": "MAT-9002",
                "grupo_id": str(self.grupo.pk),
                "requiere_factura_alumno": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        alumno = Alumno.objects.get(matricula="MAT-9002")
        insc = Inscripcion.objects.get(alumno=alumno, grupo=self.grupo)
        orden = OrdenPOS.objects.get(inscripcion=insc)
        self.assertEqual(orden.total_calculado, 1160)
        self.assertEqual(orden.items.count(), 2)
        self.assertTrue(
            OrdenItem.objects.filter(
                orden=orden,
                concepto__nombre="IVA inscripcion 16%",
                precio_unit=Decimal("160.00"),
            ).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="CUENTAS::CREAR",
                detalle__tipo="alumno",
                detalle__username="alumno_factura",
                detalle__rol="ALUMNO",
            ).exists()
        )

    def test_superuser_puede_crear_cuenta_con_privilegios(self):
        superuser = self.user_model.objects.create_superuser(
            username="root",
            email="root@test.local",
            password="testpass123",
        )
        self.client.force_login(superuser)

        response = self.client.post(
            "/panel/ventas/cuentas/",
            {
                "tipo": "usuario",
                "username": "director_staff",
                "correo": "director_staff@test.local",
                "password": "testpass123",
                "role_code": "DIRECTOR_ESCOLAR",
                "is_staff": "on",
            },
        )

        created = self.user_model.objects.get(username="director_staff")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertTrue(
            UsuarioRol.objects.filter(
                usuario=created,
                rol=self.rol_director,
            ).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="CUENTAS::CREAR",
                detalle__tipo="usuario",
                detalle__username="director_staff",
                detalle__rol="DIRECTOR_ESCOLAR",
                detalle__is_staff=True,
            ).exists()
        )

    def test_admin_comercial_no_puede_crear_usuario_general_y_audita_denegado(self):
        user = self.user_model.objects.create_user(
            username="admincom_denegado", password="testpass123")
        UsuarioRol.objects.create(usuario=user, rol=self.rol_admin_comercial)
        self.client.force_login(user)

        response = self.client.post(
            "/panel/ventas/cuentas/",
            {
                "tipo": "usuario",
                "username": "no_permitido",
                "correo": "no_permitido@test.local",
                "password": "testpass123",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.user_model.objects.filter(
            username="no_permitido").exists())
        self.assertTrue(
            EventoAuditoria.objects.filter(
                accion="CUENTAS::CREAR_DENEGADO",
                detalle__reason="non_superuser_tipo_no_permitido",
            ).exists()
        )
