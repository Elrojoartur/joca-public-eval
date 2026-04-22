# Mapa de navegabilidad v2 - Cobertura 49 HU

Fuente de referencia:
- docs/plan_cierre_49_hu.md
- docs/trazabilidad_hu_iteracion_01.md

```mermaid
flowchart TB
  A[Inicio del sistema]\n(Cobertura 49 HU)

  A --> M1[MOD-01 Portal publico]
  A --> M2[MOD-02 Inicio de sesion]
  A --> M3[MOD-03 Usuarios y roles]
  A --> M4[MOD-04 Escolar]
  A --> M5[MOD-05 Ventas POS]
  A --> M6[MOD-06 Configuracion y gobierno]
  A --> M7[MOD-07 Tableros y reportes]

  M1 --> HU001[HU-001 Consultar informacion institucional\nOK]
  M1 --> HU002[HU-002 Accesos rapidos a secciones publicas\nOK]
  M1 --> HU003[HU-003 Consultar datos de contacto\nOK]
  M1 --> HU004[HU-004 Visualizar oferta de cursos\nOK]
  M1 --> HU005[HU-005 Enviar mensaje de contacto con CAPTCHA\nOK]
  M1 --> HU006[HU-006 Visualizar avisos vigentes\nOK]
  M1 --> HU007[HU-007 Consultar preguntas frecuentes\nOK]

  M2 --> HU008[HU-008 Iniciar sesion con CAPTCHA\nOK]
  M2 --> HU009[HU-009 Cerrar sesion y revocar tokens\nOK]
  M2 --> HU010[HU-010 Gestionar sesion y tokens\nOK]
  M2 --> HU011[HU-011 Rechazar credenciales invalidas\nOK]
  M2 --> HU012[HU-012 Bloquear por intentos fallidos\nOK]
  M2 --> HU013[HU-013 Cerrar sesion por inactividad\nOK]
  M2 --> HU014[HU-014 Recuperar contrasena por correo\nOK]

  M3 --> HU015[HU-015 Administrar usuarios\nOK]
  M3 --> HU016[HU-016 Administrar roles y permisos\nOK]
  M3 --> HU017[HU-017 Consultar bitacora de cambios\nOK]
  M3 --> HU018[HU-018 Registrar usuario\nOK]
  M3 --> HU019[HU-019 Editar usuario\nOK]
  M3 --> HU020[HU-020 Cambiar estado de usuario\nOK]
  M3 --> HU021[HU-021 Asignar roles a usuario\nOK]

  M4 --> HU022[HU-022 Administrar expediente de alumno\nOK]
  M4 --> HU023[HU-023 Administrar grupos\nOK]
  M4 --> HU024[HU-024 Administrar inscripciones\nOK]
  M4 --> HU025[HU-025 Gestionar calificaciones\nOK]
  M4 --> HU026[HU-026 Validar CURP y RFC vigente\nOK]
  M4 --> HU027[HU-027 Emitir boleta PDF\nOK]
  M4 --> HU028[HU-028 Cerrar acta por grupo\nOK]

  M5 --> HU029[HU-029 Administrar catalogo\nOK]
  M5 --> HU030[HU-030 Registrar venta POS y ticket\nOK]
  M5 --> HU031[HU-031 Registrar pagos y estado de cuenta\nOK]
  M5 --> HU032[HU-032 Visualizar indicadores de ventas\nOK]
  M5 --> HU033[HU-033 Aplicar descuento autorizado\nOK]
  M5 --> HU034[HU-034 Notificar existencias minimas\nOK]
  M5 --> HU035[HU-035 Realizar corte de caja\nOK]

  M6 --> HU036[HU-036 Parametros e integraciones\nOK]
  M6 --> HU037[HU-037 Politicas de seguridad\nOK]
  M6 --> HU038[HU-038 Respaldos y auditoria\nOK]
  M6 --> HU039[HU-039 Catalogos maestros\nOK]
  M6 --> HU040[HU-040 Probar integraciones SMTP/pasarela\nOK]
  M6 --> HU041[HU-041 Rotar secretos y credenciales\nOK]
  M6 --> HU042[HU-042 Exportar bitacora y evidencias\nOK]

  M7 --> HU043[HU-043 Visualizar tablero ejecutivo\nOK]
  M7 --> HU044[HU-044 Generar reportes academicos\nOK]
  M7 --> HU045[HU-045 Generar reportes comerciales\nOK]
  M7 --> HU046[HU-046 Exportar reportes PDF/CSV\nOK]
  M7 --> HU047[HU-047 Filtrar y segmentar reportes\nOK]
  M7 --> HU048[HU-048 Programar envio periodico\nOK]
  M7 --> HU049[HU-049 Guardar vistas favoritas\nOK]
```
