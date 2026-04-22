from django.urls import path

from . import views
from . import views_reportes
from . import views_gobierno as views_governance
from . import views_alumno

from apps.sales import views as views_sales

app_name = "ui"

urlpatterns = [
    # Panel
    path("", views.panel, name="panel"),

    # Escolar
    path("escolar/", views.escolar, name="panel_escolar"),
    path("escolar/alumnos/", views.escolar_alumnos, name="escolar_alumnos"),
    path("escolar/grupos/", views.escolar_grupos, name="escolar_grupos"),
    path("escolar/grupos/generar/", views.escolar_grupos_generar,
         name="escolar_grupos_generar"),
    path("escolar/inscripciones/", views.escolar_inscripciones,
         name="escolar_inscripciones"),
    path("escolar/calificaciones/", views.escolar_calificaciones,
         name="escolar_calificaciones"),
    path("escolar/acta/cerrar/", views.cerrar_acta, name="escolar_cerrar_acta"),
    path("escolar/boleta/", views.escolar_boleta_pdf, name="escolar_boleta_pdf"),
    path("escolar/alumnos/<int:alumno_id>/expediente/",
         views.escolar_expediente, name="escolar_expediente"),
    path("escolar/alumnos/<int:alumno_id>/generar-acceso/",
         views.escolar_generar_acceso, name="escolar_generar_acceso"),
    path("escolar/alumnos/<int:alumno_id>/boleta/",
         views.escolar_boleta_alumno, name="escolar_boleta_alumno"),

    # Ventas
    path("ventas/", views_sales.ventas_home, name="ventas_home"),
    path("ventas/catalogo/", views_sales.ventas_catalogo, name="ventas_catalogo"),
    path("ventas/pos/", views_sales.ventas_pos, name="ventas_pos"),
    path("ventas/estado-cuenta/", views_sales.ventas_estado_cuenta,
         name="ventas_estado_cuenta"),
    path("ventas/corte-caja/", views_sales.ventas_corte_caja,
         name="ventas_corte_caja"),
    path("ventas/inventario/compras/", views_sales.ventas_inventario_compras,
         name="ventas_inventario_compras"),
    path("ventas/inventario/proveedores/", views_sales.ventas_inventario_proveedores,
         name="ventas_inventario_proveedores"),
    path("ventas/facturacion/datos-fiscales/",
         views_sales.ventas_datos_fiscales, name="ventas_datos_fiscales"),
    path("ventas/cuentas/", views_sales.ventas_cuentas, name="ventas_cuentas"),
    path("ventas/ticket/<int:ticket_id>/",
         views_sales.ventas_ticket, name="ventas_ticket"),

    # Gobierno
    path("gobierno/", views_governance.gobierno_home, name="gobierno_home"),
    path("gobierno/usuarios/", views_governance.gobierno_usuarios_lista,
         name="gobierno_usuarios"),
    path("gobierno/usuarios/nuevo/", views_governance.gobierno_usuarios_nuevo,
         name="gobierno_usuarios_nuevo"),
    path("gobierno/usuarios/<int:pk>/editar/", views_governance.gobierno_usuarios_editar,
         name="gobierno_usuarios_editar"),
    path("gobierno/usuarios/<int:pk>/estado/", views_governance.gobierno_usuarios_estado,
         name="gobierno_usuarios_estado"),
    path("gobierno/roles/", views_governance.gobierno_roles_lista,
         name="gobierno_roles"),
    path("gobierno/roles/asignar/", views_governance.gobierno_roles_asignar,
         name="gobierno_roles_asignar"),
    path("gobierno/roles/<int:pk>/retirar/", views_governance.gobierno_roles_retirar,
         name="gobierno_roles_retirar"),
    path("gobierno/seguridad/", views_governance.gobierno_seguridad,
         name="gobierno_seguridad"),
    path("gobierno/auditoria/", views_governance.gobierno_auditoria,
         name="gobierno_auditoria"),
    path("gobierno/excepciones/", views_governance.gobierno_excepciones,
         name="gobierno_excepciones"),
    path("gobierno/respaldos/", views_governance.gobierno_respaldos,
         name="gobierno_respaldos"),
    path("gobierno/parametros/", views_governance.gobierno_parametros,
         name="gobierno_parametros"),

    # Reportes
    path("reportes/", views_reportes.reportes_home, name="reportes_home"),
    path("reportes/ejecutivo/", views_reportes.reporte_ejecutivo,
         name="reporte_ejecutivo"),
    path("reportes/academico/", views_reportes.reporte_academico,
         name="reporte_academico"),
    path("reportes/comercial/", views_reportes.reporte_comercial,
         name="reporte_comercial"),
    path("reportes/alertas/", views_reportes.reporte_alertas,
         name="reporte_alertas"),
    path("reportes/hu012-adeudos/", views_reportes.reporte_hu012_adeudos,
         name="reporte_hu012_adeudos"),
    path("reportes/programacion/", views_reportes.reporte_programacion,
         name="reporte_programacion"),

    # Alumno
    path("alumno/", views_alumno.alumno_home, name="alumno_home"),
    path("alumno/calificaciones/", views_alumno.alumno_calificaciones,
         name="alumno_calificaciones"),
    path("alumno/boletas/", views_alumno.alumno_boletas, name="alumno_boletas"),
    path("alumno/boleta/pdf/", views_alumno.alumno_boleta_pdf,
         name="alumno_boleta_pdf"),
]
