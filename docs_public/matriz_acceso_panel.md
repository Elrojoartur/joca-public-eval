# Matriz de acceso /panel

## HU-ID
- HU-020 (Usuarios y Roles)
- HU-021/HU-022 (Seguridad y auditoria)

## Regla central
- Middleware: `backend/apps/authn/middleware.py` (`PanelAccessMiddleware`).
- Todas las rutas bajo `/panel/*` requieren autenticacion.

## Matriz (estado actual)
| Ruta | SUPERUSUARIO | DIRECTOR_ESCOLAR | ADMINISTRATIVO_COMERCIAL | ALUMNO | Resultado esperado sin rol |
|---|---|---|---|---|---|
| `/panel/` | 200 | 200 | 200 | 200 | 403 |
| `/panel/escolar/*` | 200 | 200 | 403 | 403 | 403 |
| `/panel/gobierno/*` | 200 | 200 | 403 | 403 | 403 |
| `/panel/reportes/academico/` | 200 | 200 | 403 | 403 | 403 |
| `/panel/reportes/comercial/` | 200 | 403 | 200 | 403 | 403 |
| `/panel/reportes/*` | 200 | 200 | 200 | 403 | 403 |
| `/panel/ventas/catalogo/` | 200 | 403 | 200 | 403 | 403 |
| `/panel/ventas/pos/` | 200 | 403 | 200 | 403 | 403 |
| `/panel/ventas/estado-cuenta/` | 200 | 403 | 200 | 403 | 403 |
| `/panel/ventas/inventario/*` | 200 | 403 | 200 | 403 | 403 |
| `/panel/ventas/facturacion/*` | 200 | 403 | 200 | 403 | 403 |
| `/panel/ventas/cuentas/` | 200 | 403 | 200 | 403 | 403 |
| `/panel/ventas/` | 200 | 200 | 200 | 200 | 403 |
| `/panel/alumno/*` | 200 | 403 | 403 | 200 | 403 |

## Evidencia tecnica
- Pruebas de matriz: `backend/apps/ui/tests.py` (`PanelAccessMatrixTests`).
- Comandos:
```bash
cd backend
../.venv/bin/python manage.py check
../.venv/bin/python manage.py test apps.ui.tests apps.sales.tests -v 2
```

## Capturas sugeridas para comite
1. `403` en `/panel/ventas/cuentas/` con usuario `ALUMNO`.
2. `200` en `/panel/ventas/catalogo/` con usuario `ADMINISTRATIVO_COMERCIAL`.
3. Redireccion a login para no autenticado en `/panel/escolar/`.
