# Trazabilidad HU - Corte oficial 49 HU

## Aclaracion de alcance
- Esta trazabilidad sustituye la iteracion previa de 28 HU.
- El archivo de historias de 28 ya no aplica al alcance vigente.
- El alcance oficial del sistema es de 49 historias de usuario (HU-001 a HU-049).

## Fuente oficial
- Base funcional: `docs/reglas_negocio.md`
- Plan maestro: `docs/plan_cierre_49_hu.md`

## Estado global
- Total HU: 49
- Cobertura declarada: 49/49
- Semaforo: OK

## Evidencia transversal por modulo
1. Portal publico
- Vistas y plantillas en `backend/apps/public_portal/` y `backend/apps/ui/templates/ui/portal*.html`.
- Pruebas: `backend/apps/public_portal/tests.py`.

2. Acceso y sesion
- Flujo de login, lockout, captcha y recuperacion en `backend/apps/ui/views_auth.py` y `backend/apps/authn/views.py`.
- Pruebas: `backend/apps/authn/tests.py`.

3. Usuarios y roles
- Control de cuentas y roles en `backend/apps/accounts/` y `backend/apps/sales/views.py`.
- Pruebas: `backend/apps/accounts/test_hu021.py`, `backend/apps/sales/tests.py`.

4. Escolar
- Alumnos, grupos, inscripciones, calificaciones y actas en `backend/apps/ui/views_school.py`.
- Pruebas: `backend/apps/school/test_hu022.py` a `backend/apps/school/test_hu028.py`.

5. Ventas POS
- Catalogo, POS, pagos, indicadores, descuentos, inventario y corte en `backend/apps/sales/views.py`.
- Pruebas: `backend/apps/sales/test_hu029.py` a `backend/apps/sales/test_hu035.py`.

6. Configuracion y gobierno
- Parametros, politicas, respaldos, auditoria, integraciones y catalogos en `backend/apps/ui/views_gobierno.py`.
- Pruebas: `backend/apps/governance/test_hu036.py` a `backend/apps/governance/test_hu042.py`.

7. Reportes y tablero
- Ejecutivo, academico, comercial, exportaciones, filtros, programacion y favoritos en `backend/apps/ui/views_reportes.py`.
- Pruebas: `backend/apps/ui/test_hu043.py` a `backend/apps/ui/test_hu049.py`.

## Matriz consolidada 49 HU
| Rango HU | Modulo | Estado | Evidencia principal |
|---|---|---|---|
| HU-001 a HU-007 | Portal publico | OK | `docs/plan_cierre_49_hu.md` + `backend/apps/public_portal/tests.py` |
| HU-008 a HU-014 | Acceso y sesion | OK | `docs/plan_cierre_49_hu.md` + `backend/apps/authn/tests.py` |
| HU-015 a HU-021 | Usuarios y roles | OK | `docs/plan_cierre_49_hu.md` + `backend/apps/accounts/test_hu021.py` |
| HU-022 a HU-028 | Escolar | OK | `docs/plan_cierre_49_hu.md` + `backend/apps/school/test_hu022.py` ... `test_hu028.py` |
| HU-029 a HU-035 | Ventas POS | OK | `docs/plan_cierre_49_hu.md` + `backend/apps/sales/test_hu029.py` ... `test_hu035.py` |
| HU-036 a HU-042 | Configuracion y gobierno | OK | `docs/plan_cierre_49_hu.md` + `backend/apps/governance/test_hu036.py` ... `test_hu042.py` |
| HU-043 a HU-049 | Reportes y tablero | OK | `docs/plan_cierre_49_hu.md` + `backend/apps/ui/test_hu043.py` ... `test_hu049.py` |

## Nota de validaciones
- Se mantiene validacion homogenea en frontend y backend para captura de datos.
- Referencia de reglas: `docs/validaciones_entradas_por_modulo.md`.
