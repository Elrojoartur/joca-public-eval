# Comparativo de avance: Mapa de navegabilidad vs 49 HU

Fecha: 2026-03-17

## 1) Alcance comparado

### A. Mapa de navegabilidad (imagen compartida)
Se identifican 7 modulos con 26 funcionalidades hoja:

1. Portal publico (3)
- Informacion institucional
- Accesos a secciones publicas
- Contacto

2. Inicio de sesion (3)
- Inicio de sesion
- Cerrar sesion y revocar tokens
- Gestion de sesion/tokens

3. Usuarios (4)
- Usuarios
- Roles y permisos
- Bitacora de cambios
- Accesos rapidos por rol

4. Escolar (4)
- Alumnos
- Grupos
- Inscripciones
- Calificacion

5. Ventas (4)
- Catalogo de servicios
- Ventas a alumnos
- Estado de cuenta
- Indicadores de venta

6. Configuracion y gobierno (4)
- Parametros e integraciones
- Seguridad
- Respaldos y auditoria
- Catalogo de maestros

7. Tableros y reportes (4)
- Tablero ejecutivo
- Reportes academicos
- Reportes comerciales
- Exportacion de documentos

### B. Historias de usuario oficiales
- Total oficial: 49 HU (HU-001 a HU-049)
- Fuente: docs/plan_cierre_49_hu.md

---

## 2) Resultado de comparacion

## Avance sobre mapa de navegabilidad
- Cobertura funcional observada: 26/26
- Porcentaje: 100%

## Avance sobre 49 HU
- Cobertura declarada en trazabilidad oficial: 49/49
- Porcentaje declarado: 100%
- Referencia: docs/trazabilidad_hu_iteracion_01.md

---

## 3) Que falta por hacer (pendiente real)

No se detecta pendiente funcional critica en los modulos del mapa base.

Los pendientes son de alineacion y gobernanza documental:

1. Actualizar el mapa de navegabilidad a version 49 HU
- El mapa actual representa el nucleo (26 funcionalidades), pero no todas las capacidades agregadas del alcance oficial 49 HU.
- Ejemplos no visibles en el mapa actual:
  - Recuperacion de contrasena
  - Bloqueo por intentos fallidos
  - Cierre por inactividad
  - Descuentos autorizados
  - Inventario y alertas de stock
  - Corte de caja
  - Programacion de envios de reportes
  - Favoritos de tablero

2. Alinear texto de HU-026 en plan maestro
- En docs/plan_cierre_49_hu.md aparece "RFC (sin homoclave)".
- El sistema ya se ajusto a RFC vigente de Mexico (12/13 caracteres con homoclave).
- Se recomienda actualizar la redaccion de HU-026 para evitar inconsistencia de auditoria.

3. Consolidar evidencia de cierre por HU en una sola matriz ejecutiva
- Mantener una tabla unica con: HU, modulo, estado, test automatico, evidencia manual y fecha de verificacion.

---

## 4) Recomendacion de cierre

Semaforo de proyecto:
- Funcionalidad: VERDE
- Pruebas base por modulo: VERDE
- Documentacion de alcance y navegabilidad: AMARILLO (por actualizar mapa y redaccion puntual HU-026)

Conclusion:
- El sistema esta en estado de cierre funcional para alcance 49 HU.
- Lo pendiente para "cierre total" es principalmente documental y de evidencia de presentacion.
