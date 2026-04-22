# Matriz de auditoría técnica conservadora — 49 HU
## Proyecto JOCA / CCENT · Corte: 14 de abril de 2026

### Criterio de evaluación
Escala por columna: **100** = completo y verificable · **75** = mayormente completo ·
**50** = parcial o pendiente de validación real · **25** = muy incompleto · **0** = sin evidencia

| Columna | Qué evalúa |
|---|---|
| **Impl** | URL + vista/controlador + template/API + modelo/servicio + validaciones |
| **Oper** | Funcionamiento extremo a extremo en sistema real. Si no hay evidencia de VPS ≤ 75. |
| **Prueba** | Tests automatizados, PCB, assertions, evidencia documental |
| **Cierre** | Lista para entrega sin bloqueantes ni integración crítica faltante |

**Fórmula:** `Total = (Impl + Oper + Prueba + Cierre) / 4`

---

## Tabla completa — 49 HU

| HU | Nombre | Impl | Oper | Prueba | Cierre | **Total** | Observación |
|---|---|:---:|:---:|:---:|:---:|:---:|---|
| HU-001 | Consultar información institucional | 100 | 75 | 100 | 100 | **94** | Ruta + vista + template + tests PCB. Operación en VPS no confirmada directamente, pero sin dependencias externas. |
| HU-002 | Accesos rápidos a secciones públicas | 100 | 75 | 100 | 100 | **94** | Links verificados en tests. Sin bloqueantes. |
| HU-003 | Consultar datos de contacto | 100 | 75 | 100 | 100 | **94** | PCB-011 verifica datos institucionales con `override_settings`. |
| HU-004 | Visualizar oferta de cursos | 100 | 75 | 75 | 100 | **88** | Catálogo JSON funcional, carrusel renderizado. Test de paginación pre-existente en FAIL (`"Paginacion de cursos"` no encontrado en template actual). Flujo principal correcto. |
| HU-005 | Enviar mensaje de contacto con CAPTCHA | 100 | 75 | 100 | 100 | **94** | Corregido en esta sesión: doble envío (institucional + acuse), fail_silently=False. PCB-013 con 5 casos en verde. |
| HU-006 | Visualizar avisos vigentes | 100 | 75 | 100 | 100 | **94** | Vista + catálogo JSON + filtro por fecha_fin. Tests cubren vigentes/expirados. |
| HU-007 | Consultar preguntas frecuentes | 100 | 75 | 100 | 100 | **94** | Vista + catálogo JSON + filtro `activa`. Tests en verde. |
| HU-008 | Iniciar sesión con CAPTCHA | 100 | 75 | 100 | 100 | **94** | `views_auth.acceso` con reCAPTCHA v2/v3, pregunta matemática, auditoría. `LoginCaptchaFlowTests` con 6 casos. |
| HU-009 | Cerrar sesión y revocar tokens | 100 | 75 | 100 | 100 | **94** | `salir()` + `LogoutRevokeTests.test_logout_closes_session_revokes_tokens_and_audits`. |
| HU-010 | Gestionar sesión y tokens | 100 | 75 | 100 | 100 | **94** | `GuestOnlyRedirectMiddleware` + headers no-cache + `IdleTimeoutMiddleware`. 19 tests en verde. |
| HU-011 | Rechazar credenciales inválidas | 100 | 75 | 100 | 100 | **94** | `test_login_rejects_invalid_credentials_and_audits` + PCB-013. Auditoría registra `AUTH::LOGIN_FAIL`. |
| HU-012 | Bloquear por intentos fallidos | 100 | 75 | 100 | 100 | **94** | Tests: bloqueo per-user, reset de contador, cambio de IP. Política configurable vía ParametroSistema. |
| HU-013 | Cerrar sesión por inactividad | 100 | 75 | 75 | 100 | **88** | `IdleTimeoutMiddleware` con timeout configurable. Tests de integración en verde. No existe test específico que simule flujo de idle completo de extremo a extremo. |
| HU-014 | Recuperar contraseña por correo | 100 | 75 | 100 | 100 | **94** | `AuditPasswordResetView` / `AuditPasswordResetConfirmView`. 4 tests en `PasswordResetAuditTests`. Flujo interno completo; depende de SMTP del VPS para entrega real. |
| HU-015 | Administrar usuarios (ABAC) | 100 | 75 | 100 | 100 | **94** | `gobierno_usuarios_lista/nuevo/editar/estado`. `accounts/tests.py` cubre 8 casos de ciclo de vida completo. |
| HU-016 | Administrar roles y permisos | 100 | 75 | 100 | 100 | **94** | `gobierno_roles_lista/asignar/retirar`. `RolPermisosAdminTests` con diff y auditoría. |
| HU-017 | Consultar bitácora de cambios | 100 | 75 | 75 | 100 | **88** | `gobierno_auditoria()` con paginación, filtros y exportación CSV+SHA256. Test de exportación en HU-042. No existe test dedicado exclusivamente a la vista del visor de bitácora. |
| HU-018 | Registrar usuario | 100 | 75 | 75 | 100 | **88** | `gobierno_usuarios_nuevo()` completo. Tests de `accounts/tests.py` cubren duplicados y hash. Sin test e2e del flujo de registro desde el panel de gobierno. |
| HU-019 | Editar usuario | 100 | 75 | 75 | 100 | **88** | `gobierno_usuarios_editar()` implementado. `test_save_model_update_generates_audit_event` cubre lógica de admin. Sin test Django que valide el POST via vista del panel directamente. |
| HU-020 | Cambiar estado de usuario | 100 | 75 | 100 | 100 | **94** | `gobierno_usuarios_estado()` + `test_desactivar_disables_user_revokes_sessions_and_audits` + `test_activar_reenables_user_and_audits`. |
| HU-021 | Asignar roles a usuario | 100 | 75 | 75 | 100 | **88** | `gobierno_roles_asignar/retirar`. `UserRoleAssignmentAuditTests` cubre asignación con auditoría. Solo 2 tests; no cubre retiro de rol ni rol no encontrado. |
| HU-022 | Administrar expediente de alumno | 100 | 75 | 75 | 75 | **81** | `escolar_alumnos()` + `escolar_expediente()` con CURP/RFC + domicilio. Tests HU-022 en verde. Integración con `escolar_generar_acceso` pendiente de validación real en VPS. |
| HU-023 | Administrar grupos | 100 | 75 | 75 | 75 | **81** | `escolar_grupos()` + `escolar_grupos_generar()` + sync de horarios. Tests HU-023 en verde. Sin test que cubra grupos con docentes asignados. |
| HU-024 | Administrar inscripciones | 100 | 75 | 75 | 75 | **81** | `escolar_inscripciones()` con `ensure_inscripcion_sale()`. Tests HU-024. Sin test que valide baja de inscripción + reversión de orden POS asociada. |
| HU-025 | Gestionar calificaciones | 100 | 75 | 75 | 75 | **81** | `escolar_calificaciones()` captura + bloqueo por ActaCierre. Tests HU-025. Sin test de edición de calificación ya capturada antes del cierre. |
| HU-026 | Validar CURP y RFC vigente | 100 | 75 | 100 | 100 | **94** | `validators.py` con regex CURP 18 chars + RFC 12/13 chars. 4 tests: válido, CURP inválido, RFC inválido, RFC vacío. |
| HU-027 | Emitir boleta PDF | 100 | 75 | 100 | 100 | **94** | `_render_boleta_pdf()` con ReportLab. 4 tests: director, alumno propio, alumno ajeno (403), período inválido. |
| HU-028 | Cerrar acta de calificaciones | 100 | 75 | 100 | 100 | **94** | `cerrar_acta()` + bloqueo de calificaciones posteriores. 5 tests incluyendo PCB-015. Auditoría registrada. |
| HU-029 | Administrar catálogo de servicios | 100 | 75 | 100 | 100 | **94** | `ventas_catalogo()` CRUD + ProtectedError + IntegrityError + auditoría. Tests HU-029 en verde. |
| HU-030 | Registrar venta POS y emitir ticket | 100 | 75 | 75 | 75 | **81** | `ventas_pos()` + OrdenPOS + ticket. Tests HU-030. Sin test que valide content-type PDF del ticket ni flujo con alumno sin orden previa. |
| HU-031 | Registrar pagos y estado de cuenta | 100 | 75 | 75 | 75 | **81** | `ventas_estado_cuenta()` + Pago. Tests HU-031. Sin test de estado de cuenta con múltiples pagos parciales. |
| HU-032 | Visualizar indicadores de ventas del día | 100 | 75 | 75 | 75 | **81** | `ventas_home()` calcula KPIs en tiempo real. `IndicadoresVentasDelDiaTests` + `PCB018IndicadoresVentasTests` en `test_hu032.py`. Sin test de KPIs con datos de diferentes días. |
| HU-033 | Aplicar descuento autorizado | 100 | 75 | 75 | 75 | **81** | `DescuentoAutorizadoPosTests`. Descuento validado por rol DIRECTOR_ESCOLAR. Sin test que valide descuento > 100% rechazado ni nota de justificación obligatoria. |
| HU-034 | Notificar existencias mínimas | 75 | 50 | 75 | 50 | **63** | AlertaStock se persiste en BD y se muestra en `ventas_home()`. **No hay envío de correo ni notificación activa** al usuario cuando se genera la alerta. "Notificar" implica aviso activo, no solo tabla pasiva. Tests cubren creación de alerta y rechazo de venta, pero no notificación externa. |
| HU-035 | Realizar corte de caja | 100 | 75 | 100 | 100 | **94** | `ventas_corte_caja()` con bloqueo y auditoría. Tests HU-035 en verde. UNIQUE en CorteCaja.fecha_operacion previene duplicados. |
| HU-036 | Configurar parámetros e integraciones | 100 | 75 | 75 | 75 | **81** | `gobierno_parametros()` con 6 secciones. Tests HU-036 cubren INSTITUCION + PERIODO. Secciones SMTP y PASARELA sin test de escenario exitoso completo con `@override_settings EMAIL_BACKEND`. |
| HU-037 | Configurar políticas de seguridad | 100 | 75 | 75 | 100 | **88** | `gobierno_seguridad()` + `security_policy.py` con getters y rangos validados. Tests HU-037. Sin test que valide que el cambio de política afecta inmediatamente al lockout del login en la misma sesión. |
| HU-038 | Gestionar respaldos y auditoría | 100 | 75 | 100 | 100 | **94** | `gobierno_respaldos()` genera/restaura con SHA256 + payload JSON. Tests HU-038 en verde. |
| HU-039 | Administrar catálogos maestros | 100 | 75 | 100 | 100 | **94** | `_handle_catalogos_maestros()` para Curso/Aula/Docente/Concepto con UPSERT + TOGGLE. Tests HU-039: 3 casos incluyendo control de rol. |
| HU-040 | Probar integraciones SMTP/pasarela | 100 | 50 | 75 | 75 | **75** | `_handle_smtp_parametros()` con `smtp_test_status`. Tests HU-040: 4 métodos incluyendo caso positivo con mock. Prueba real SMTP depende de backend del VPS; operación real no confirmable desde código. Implementada en código pero pendiente de validación real en VPS. |
| HU-041 | Rotar secretos y credenciales | 100 | 75 | 100 | 100 | **94** | Rotación SMTP + pasarela en `_handle_smtp_parametros`. 3 tests incluyendo control de rol Alumno (403). |
| HU-042 | Exportar bitácora y evidencias | 100 | 75 | 100 | 100 | **94** | `gobierno_auditoria()` exporta CSV con hash SHA256. Tests HU-042: 3 casos export CSV + verificación de hash. |
| HU-043 | Visualizar tablero ejecutivo | 100 | 75 | 75 | 75 | **81** | `reporte_ejecutivo()` con Count/Sum/Avg, KPIs reales. Tests HU-043. Sin test que valide todos los KPIs individualmente (alertas, ventas del día, morosidad). |
| HU-044 | Generar reportes académicos | 100 | 75 | 75 | 75 | **81** | `reporte_academico()` con filtro por período, CSV/PDF con ReportLab. Tests HU-044: filtro por periodo + control de rol. Sin test que valide contenido real del CSV/PDF generado. |
| HU-045 | Generar reportes comerciales | 100 | 75 | 75 | 75 | **81** | `reporte_comercial()` con ventas, cortes de caja, inscripciones. Tests HU-045 en verde. Sin test de contenido CSV/PDF. |
| HU-046 | Exportar reportes PDF/CSV | 100 | 75 | 75 | 100 | **88** | `_build_*_pdf_bytes()` / `_build_*_csv_bytes()` con ReportLab + hash SHA256. Tests HU-046 cubren Content-Type correcto. Sin validación de contenido interno del CSV/PDF. |
| HU-047 | Filtrar y segmentar reportes | 100 | 75 | 75 | 75 | **81** | `reporte_academico()` + `reporte_comercial()` con parámetros GET. `FiltrarSegmentarReportesHU047Tests` existe. Sin test de combinación de filtros múltiples simultáneos. |
| HU-048 | Programar envío periódico de reportes | 100 | 50 | 75 | 75 | **75** | `reporte_programacion()` + `ejecutar_envio_periodico_reportes()` + `_schedule_is_due()`. Tests HU-048 con `locmem`. Envío periódico automático requiere cron/job externo en VPS; ejecución autónoma real no confirmada desde código. |
| HU-049 | Guardar vistas favoritas del tablero | 100 | 75 | 75 | 100 | **88** | `reportes_home()` guarda favoritos en `ParametroSistema` por usuario con auditoría. Tests HU-049 cubren guardado. Sin test que valide recuperación de favoritos en GET posterior. |

---

## Resumen consolidado

### HUs con total ≥ 94% — Prácticamente cerradas (24 HUs)

HU-001, HU-002, HU-003, HU-005, HU-006, HU-007, HU-008, HU-009, HU-010, HU-011,
HU-012, HU-014, HU-015, HU-016, HU-020, HU-026, HU-027, HU-028, HU-029, HU-035,
HU-038, HU-039, HU-041, HU-042

### HUs entre 81% y 93% — Mayormente cerradas, detalle menor pendiente (22 HUs)

HU-004, HU-013, HU-017, HU-018, HU-019, HU-021, HU-022, HU-023, HU-024, HU-025,
HU-030, HU-031, HU-032, HU-033, HU-036, HU-037, HU-043, HU-044, HU-045, HU-046,
HU-047, HU-049

### HUs entre 75% y 80% — Funcionales pero con gaps relevantes (2 HUs)

HU-040 (75%), HU-048 (75%)

### HUs por debajo de 75% — Bloqueante para entrega (1 HU)

HU-034 (63%)

---

## Porcentaje global del sistema

| Métrica | Valor |
|---|---|
| HUs evaluadas | 49 |
| Suma de totales | 4 320 puntos |
| **Promedio global** | **88.2 %** |
| HUs en 100% de cierre complето | 0 (ninguna llega a 100 por operación VPS no confirmada) |
| HU con bloqueante real | 1 (HU-034) |

---

## Lista priorizada para entrega

### Pendientes críticos — esta semana

| Prioridad | HU | Problema concreto | Acción mínima verificable |
|:---:|---|---|---|
| 1 | **HU-034** | `AlertaStock` se persiste pero no hay notificación activa al usuario. "Notificar" implica aviso visible/push/correo en el momento, no solo una tabla pasiva. | Agregar banner/toast en `ventas_home()` al generarse la alerta, o enviar correo inmediato al CONTACT_EMAIL. Sin esto la HU no cumple el enunciado funcional. |
| 2 | **HU-004** | Test `test_portal_courses_pagination_is_available` en FAIL desde antes de esta sesión (assertion busca texto que ya no existe en el template). | Actualizar el assertion para buscar el selector real de paginación en el template actual (ej. `aria-label="Paginacion"` o el id/clase real). |
| 3 | **HU-040** | Prueba SMTP tiene test de caso positivo con mock, pero la operación real nunca fue confirmada en VPS. | Ejecutar el flujo de prueba en VPS con credenciales reales y registrar captura/log como evidencia de entrega. |
| 4 | **HU-048** | El envío periódico automático requiere cron o comando externo activo. Sin job configurado en VPS el flujo no se ejecuta. | Verificar que el management command `enviar_reportes_periodicos` (o equivalente) está en crontab del VPS y documentarlo. |

### Pendientes que pueden pasar a fase posterior

| HU | Motivo de postergación segura |
|---|---|
| HU-013 | Falta test específico de idle completo; `IdleTimeoutMiddleware` funciona y tiene test de integración. |
| HU-017 | Falta test dedicado al visor; exportación ya cubierta en HU-042. |
| HU-018/019 | Sin test e2e de vista de panel; lógica correcta y probada a nivel unit/admin. |
| HU-021 | Solo 2 tests; retiro de rol no cubierto. Bajo riesgo de regresión. |
| HU-022/023 | Integración `escolar_generar_acceso` y grupos con docentes no probados. Flujo principal verde. |
| HU-024/025 | Baja de inscripción con reversión POS y edición de calificación no cubiertas. Riesgo medio. |
| HU-030/031 | Falta test de PDF de ticket y multipago parcial. Flujo principal en verde. |
| HU-033 | Sin test de descuento > 100% o justificación obligatoria. Bajo riesgo. |
| HU-036 | Test de SMTP/PASARELA escenario exitoso faltante. Funcionalidad existe. |
| HU-043/044/045 | Falta aserción de contenido CSV/PDF; Content-Type y hash cubiertos. |
| HU-049 | Falta test de recuperación de favoritos en GET; guardado probado. |

---

*Generado automáticamente por auditoría técnica — 14 abril 2026*
*Evaluación conservadora: operación en VPS no asumida si no hay evidencia directa en código o documentación.*
