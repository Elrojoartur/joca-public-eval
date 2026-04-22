# Reglas de negocio — JOCA/CCENT

**Propósito:** Este documento consolida y normaliza las reglas de negocio del sistema JOCA/CCENT en formato verificable para implementación y pruebas. Se utiliza como fuente de verdad para evitar ambigüedad durante la codificación, particularmente al operar con agentes (Codex/Copilot) y al preparar evidencias para revisión académica.

**Fuente operativa de trazabilidad:** matriz de historias de usuario (49 HU) ubicada en el repositorio como `Historias de usuario Copia.xlsx`.

**Convención:**
- `BR-###` identifica la regla de negocio normalizada.
- `RN-...` conserva el identificador original de la regla (equivalente/alias).
- La sección “Trazabilidad” enlaza cada BR con las HU relevantes (módulo, rol y evidencia esperada).
- Cuando una regla no tiene HU asociada en el MVP, se marca como **Backlog** y se propone una `HU-FUT-###`.

**Fecha de actualización:** 2026-03-03 (America/Mexico_City)

---

## Roles operativos (resumen)

- **Visitante:** consulta información pública y realiza contacto.
- **Alumno:** consulta información académica y realiza acciones permitidas por su rol (p. ej., pagos/estado de cuenta).
- **Administrativo Comercial:** opera POS, registra pagos, gestiona cortes y catálogo comercial.
- **Director Escolar:** administra grupos, inscripciones, calificaciones, boletas y cierres académicos.
- **Superusuario:** administra usuarios/roles, parámetros de gobierno, bitácoras y configuraciones.

---

## Matriz de trazabilidad BR ↔ HU (resumen)

| BR | RN | HU relacionadas | Módulos |
|---|---|---|---|
| BR-001 | RN-A01 | HU 004, HU 039 | MOD-01, MOD-06 |
| BR-002 | RN-A02 | HU 023, HU 044 | MOD-04, MOD-07 |
| BR-003 | RN-A03 | HU 023, HU 039 | MOD-04, MOD-06 |
| BR-004 | RN-A04 | HU 023, HU 024 | MOD-04 |
| BR-005 | RN-A05 | HU 023, HU 028, HU 044, HU 047 | MOD-04, MOD-07 |
| BR-006 | RN-P01 | HU 022, HU 024 | MOD-04 |
| BR-007 | RN-P02 | HU 022 | MOD-04 |
| BR-008 | RN-P03 | HU 022 | MOD-04 |
| BR-009 | RN-P04 | HU 022 | MOD-04 |
| BR-010 | RN-P05 | HU 022 | MOD-04 |
| BR-011 | RN-I01 | HU 024 | MOD-04 |
| BR-012 | RN-I02 | HU 024 | MOD-04 |
| BR-013 | RN-I03 | HU 024 | MOD-04 |
| BR-014 | RN-I04 | HU 024 | MOD-04 |
| BR-015 | RN-C01 | HU-FUT-001 | — |
| BR-016 | RN-C02 | HU 025 | MOD-04 |
| BR-017 | RN-C03 | HU 025, HU 043, HU 044 | MOD-04, MOD-07 |
| BR-018 | RN-C04 | HU 027, HU 046 | MOD-04, MOD-07 |
| BR-019 | RN-C05 | HU 028, HU 025 | MOD-04 |
| BR-020 | RN-V01 | HU 029, HU 039 | MOD-05, MOD-06 |
| BR-021 | RN-V02 | HU 030 | MOD-05 |
| BR-022 | RN-V03 | HU 030, HU 029 | MOD-05 |
| BR-023 | RN-V04 | HU 030, HU 029, HU 034 | MOD-05 |
| BR-024 | RN-V05 | HU 031 | MOD-05 |
| BR-025 | RN-V06 | HU 030, HU 031 | MOD-05 |
| BR-026 | RN-V07 | HU 033 | MOD-05 |
| BR-027 | RN-V08 | HU 035, HU 045 | MOD-05, MOD-07 |
| BR-028 | RN-INV01 | HU 030, HU 034, HU 029 | MOD-05 |
| BR-029 | RN-INV02 | HU 034 | MOD-05 |
| BR-030 | RN-INV03 | HU-FUT-002 | — |
| BR-031 | RN-INV04 | HU-FUT-003 | — |
| BR-032 | RN-INV05 | HU-FUT-004 | — |
| BR-033 | RN-F01 | HU-FUT-005 | — |
| BR-034 | RN-F02 | HU-FUT-006 | — |
| BR-035 | RN-F03 | HU 026 | MOD-04 |
| BR-036 | RN-S01 | HU 016, HU 021, HU 015 | MOD-03 |
| BR-037 | RN-S02 | HU 017, HU 042, HU 038 | MOD-03, MOD-06 |
| BR-038 | RN-S03 | HU 039, HU 020, HU 029 | MOD-03, MOD-05, MOD-06 |
| BR-039 | RN-S04 | HU 008, HU 012, HU 013, HU 010, HU 037, HU 005 | MOD-01, MOD-02, MOD-06 |

---

## Oferta académica y operación escolar

### BR-001 — cursos por categoría/área con estatus activo/inactivo (RN-A01)
**Estado:** Implementada/MVP

**Descripción:** Oferta académica: cursos por categoría/área con estatus activo/inactivo

**Alcance (módulos):** `MOD-01 Portal Publico`, `MOD-06 Configuración y Gobierno`
**Roles típicos:** `Administrativo Comercial`, `Alumno`, `Director Escolar`, `Superusuario`
**Entidades/Tablas relevantes:** `FormaPago`, `Horario`, `Plan`, `Producto`, `Servicio`, `categoria`, `duración`, `fecha_inicio`, `modalidad`
**Endpoints explícitos en HU:** `GET /cursos`

**Validación UI:** El portal y los formularios de administración presentan únicamente registros con estado permitido y aplican filtros por categoría/periodo cuando corresponda.

**Validación API/Backend:** El servicio aplica filtros server-side, respeta estatus activo/inactivo y valida integridad referencial (Curso↔Grupo↔Periodo).

**Restricción/Constraint BD:** Se aplican llaves foráneas y restricciones de dominio (estatus enumerado), con índices por campos de búsqueda (categoría, periodo, estado).

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 004** — Visualizar oferta de cursos (MOD-01 Portal Publico)
- **HU 039** — Administrar catálogos maestros (académicos y comerciales) (MOD-06 Configuración y Gobierno)

### BR-002 — Cursos se imparten mediante grupos; grupo pertenece a curso y periodo; nombre… (RN-A02)
**Estado:** Implementada/MVP

**Descripción:** Cursos se imparten mediante grupos; grupo pertenece a curso y periodo; nombre/código

**Alcance (módulos):** `MOD-04 Escolar`, `MOD-07 Reportes y Tablero`
**Roles típicos:** `Director Escolar`
**Entidades/Tablas relevantes:** `Grupo`, `Periodo`, `ReporteCalificaciones`, `ReporteInscripciones`
**Endpoints explícitos en HU:** —

**Validación UI:** El portal y los formularios de administración presentan únicamente registros con estado permitido y aplican filtros por categoría/periodo cuando corresponda.

**Validación API/Backend:** El servicio aplica filtros server-side, respeta estatus activo/inactivo y valida integridad referencial (Curso↔Grupo↔Periodo).

**Restricción/Constraint BD:** Se aplican llaves foráneas y restricciones de dominio (estatus enumerado), con índices por campos de búsqueda (categoría, periodo, estado).

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 023** — Administrar grupos (periodo, cupo, estado) (MOD-04 Escolar)
- **HU 044** — Generar reportes académicos (inscripciones por periodo, calificaciones) (MOD-07 Reportes y Tablero)

### BR-003 — Grupo con uno o varios horarios (días y rangos de hora) (RN-A03)
**Estado:** Implementada/MVP

**Descripción:** Grupo con uno o varios horarios (días y rangos de hora)

**Alcance (módulos):** `MOD-04 Escolar`, `MOD-06 Configuración y Gobierno`
**Roles típicos:** `Director Escolar`, `Superusuario`
**Entidades/Tablas relevantes:** `FormaPago`, `Grupo`, `Horario`, `Periodo`, `Plan`, `Producto`, `Servicio`
**Endpoints explícitos en HU:** —

**Validación UI:** El portal y los formularios de administración presentan únicamente registros con estado permitido y aplican filtros por categoría/periodo cuando corresponda.

**Validación API/Backend:** El servicio aplica filtros server-side, respeta estatus activo/inactivo y valida integridad referencial (Curso↔Grupo↔Periodo).

**Restricción/Constraint BD:** Se aplican llaves foráneas y restricciones de dominio (estatus enumerado), con índices por campos de búsqueda (categoría, periodo, estado).

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 023** — Administrar grupos (periodo, cupo, estado) (MOD-04 Escolar)
- **HU 039** — Administrar catálogos maestros (académicos y comerciales) (MOD-06 Configuración y Gobierno)

### BR-004 — Grupo con cupo; impedir inscripción cuando cupo completo (RN-A04)
**Estado:** Implementada/MVP

**Descripción:** Grupo con cupo; impedir inscripción cuando cupo completo

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** `Director Escolar`
**Entidades/Tablas relevantes:** `Alumno`, `Grupo`, `Inscripción`, `Periodo`
**Endpoints explícitos en HU:** —

**Validación UI:** El portal y los formularios de administración presentan únicamente registros con estado permitido y aplican filtros por categoría/periodo cuando corresponda.

**Validación API/Backend:** El servicio aplica filtros server-side, respeta estatus activo/inactivo y valida integridad referencial (Curso↔Grupo↔Periodo).

**Restricción/Constraint BD:** Se aplican llaves foráneas y restricciones de dominio (estatus enumerado), con índices por campos de búsqueda (categoría, periodo, estado).

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 023** — Administrar grupos (periodo, cupo, estado) (MOD-04 Escolar)
- **HU 024** — Administrar inscripciones (alta, baja, consulta) (MOD-04 Escolar)

### BR-005 — Periodo define ventana (inicio/fin) y estado (abierto/cerrado); operaciones r… (RN-A05)
**Estado:** Implementada/MVP

**Descripción:** Periodo define ventana (inicio/fin) y estado (abierto/cerrado); operaciones restringidas

**Alcance (módulos):** `MOD-04 Escolar`, `MOD-07 Reportes y Tablero`
**Roles típicos:** `Director Escolar`
**Entidades/Tablas relevantes:** `Acta`, `EventoAuditoria`, `FiltroReporte`, `Grupo`, `Periodo`, `PresetFiltro`, `ReporteCalificaciones`, `ReporteInscripciones`
**Endpoints explícitos en HU:** —

**Validación UI:** El portal y los formularios de administración presentan únicamente registros con estado permitido y aplican filtros por categoría/periodo cuando corresponda.

**Validación API/Backend:** El servicio aplica filtros server-side, respeta estatus activo/inactivo y valida integridad referencial (Curso↔Grupo↔Periodo).

**Restricción/Constraint BD:** Se aplican llaves foráneas y restricciones de dominio (estatus enumerado), con índices por campos de búsqueda (categoría, periodo, estado).

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 023** — Administrar grupos (periodo, cupo, estado) (MOD-04 Escolar)
- **HU 028** — Cerrar acta de calificaciones por grupo (MOD-04 Escolar)
- **HU 044** — Generar reportes académicos (inscripciones por periodo, calificaciones) (MOD-07 Reportes y Tablero)
- **HU 047** — Filtrar y segmentar reportes (MOD-07 Reportes y Tablero)


## Personas (alumnos, tutores y contactos)

### BR-006 — Alumno con matrícula, identidad y estatus (RN-P01)
**Estado:** Implementada/MVP

**Descripción:** Alumno con matrícula, identidad y estatus

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** `Director Escolar`
**Entidades/Tablas relevantes:** `Alumno`, `DocumentoAlumno`, `EventoAuditoria`, `Grupo`, `Inscripción`
**Endpoints explícitos en HU:** —

**Validación UI:** El formulario de alumno valida obligatoriedad, formatos y selección de contacto principal; cuando aplica menor de edad, exige tutor y contacto.

**Validación API/Backend:** Los endpoints de alumno normalizan datos, validan unicidad de matrícula y aplican reglas condicionales (menor→tutor).

**Restricción/Constraint BD:** Se modelan entidades dependientes (contactos, domicilios, tutor, emergencia) en tablas separadas con FK y restricciones (único principal por alumno).

**Errores esperados:** `400 BAD REQUEST` por datos inválidos., `401 UNAUTHORIZED`/`403 FORBIDDEN` por autenticación/autorización.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 022** — Administrar expediente de alumno (MOD-04 Escolar)
- **HU 024** — Administrar inscripciones (alta, baja, consulta) (MOD-04 Escolar)

### BR-007 — Alumno con múltiples contactos (teléfonos/correos) y uno principal (RN-P02)
**Estado:** Implementada/MVP

**Descripción:** Alumno con múltiples contactos (teléfonos/correos) y uno principal

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** `Director Escolar`
**Entidades/Tablas relevantes:** `Alumno`, `DocumentoAlumno`, `EventoAuditoria`
**Endpoints explícitos en HU:** —

**Validación UI:** El formulario de alumno valida obligatoriedad, formatos y selección de contacto principal; cuando aplica menor de edad, exige tutor y contacto.

**Validación API/Backend:** Los endpoints de alumno normalizan datos, validan unicidad de matrícula y aplican reglas condicionales (menor→tutor).

**Restricción/Constraint BD:** Se modelan entidades dependientes (contactos, domicilios, tutor, emergencia) en tablas separadas con FK y restricciones (único principal por alumno).

**Errores esperados:** `400 BAD REQUEST` por datos inválidos., `401 UNAUTHORIZED`/`403 FORBIDDEN` por autenticación/autorización.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 022** — Administrar expediente de alumno (MOD-04 Escolar)

### BR-008 — Domicilio del alumno con vigencia (actual/histórico) (RN-P03)
**Estado:** Implementada/MVP

**Descripción:** Domicilio del alumno con vigencia (actual/histórico)

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** `Director Escolar`
**Entidades/Tablas relevantes:** `Alumno`, `DocumentoAlumno`, `EventoAuditoria`
**Endpoints explícitos en HU:** —

**Validación UI:** El formulario de alumno valida obligatoriedad, formatos y selección de contacto principal; cuando aplica menor de edad, exige tutor y contacto.

**Validación API/Backend:** Los endpoints de alumno normalizan datos, validan unicidad de matrícula y aplican reglas condicionales (menor→tutor).

**Restricción/Constraint BD:** Se modelan entidades dependientes (contactos, domicilios, tutor, emergencia) en tablas separadas con FK y restricciones (único principal por alumno).

**Errores esperados:** `400 BAD REQUEST` por datos inválidos., `401 UNAUTHORIZED`/`403 FORBIDDEN` por autenticación/autorización.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 022** — Administrar expediente de alumno (MOD-04 Escolar)

### BR-009 — registrar tutor/responsable y contacto (RN-P04)
**Estado:** Implementada/MVP

**Descripción:** Alumno menor: registrar tutor/responsable y contacto

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** `Director Escolar`
**Entidades/Tablas relevantes:** `Alumno`, `DocumentoAlumno`, `EventoAuditoria`
**Endpoints explícitos en HU:** —

**Validación UI:** El formulario de alumno valida obligatoriedad, formatos y selección de contacto principal; cuando aplica menor de edad, exige tutor y contacto.

**Validación API/Backend:** Los endpoints de alumno normalizan datos, validan unicidad de matrícula y aplican reglas condicionales (menor→tutor).

**Restricción/Constraint BD:** Se modelan entidades dependientes (contactos, domicilios, tutor, emergencia) en tablas separadas con FK y restricciones (único principal por alumno).

**Errores esperados:** `400 BAD REQUEST` por datos inválidos., `401 UNAUTHORIZED`/`403 FORBIDDEN` por autenticación/autorización.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 022** — Administrar expediente de alumno (MOD-04 Escolar)

### BR-010 — Contacto de emergencia por alumno (RN-P05)
**Estado:** Implementada/MVP

**Descripción:** Contacto de emergencia por alumno

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** `Director Escolar`
**Entidades/Tablas relevantes:** `Alumno`, `DocumentoAlumno`, `EventoAuditoria`
**Endpoints explícitos en HU:** —

**Validación UI:** El formulario de alumno valida obligatoriedad, formatos y selección de contacto principal; cuando aplica menor de edad, exige tutor y contacto.

**Validación API/Backend:** Los endpoints de alumno normalizan datos, validan unicidad de matrícula y aplican reglas condicionales (menor→tutor).

**Restricción/Constraint BD:** Se modelan entidades dependientes (contactos, domicilios, tutor, emergencia) en tablas separadas con FK y restricciones (único principal por alumno).

**Errores esperados:** `400 BAD REQUEST` por datos inválidos., `401 UNAUTHORIZED`/`403 FORBIDDEN` por autenticación/autorización.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 022** — Administrar expediente de alumno (MOD-04 Escolar)


## Inscripciones y elegibilidad

### BR-011 — Alumno puede inscribirse a varios grupos en distintos periodos, sujeto a reglas (RN-I01)
**Estado:** Implementada/MVP

**Descripción:** Alumno puede inscribirse a varios grupos en distintos periodos, sujeto a reglas

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** `Director Escolar`
**Entidades/Tablas relevantes:** `Alumno`, `Grupo`, `Inscripción`
**Endpoints explícitos en HU:** —

**Validación UI:** La UI evita doble inscripción al mismo grupo y muestra claramente cupo/saldo/estado de inscripción; las bajas requieren motivo.

**Validación API/Backend:** El backend verifica cupo, unicidad alumno-grupo, transiciones válidas de estado y auditoría de baja (actor, timestamp, motivo).

**Restricción/Constraint BD:** Se define constraint UNIQUE(alumno_id, grupo_id) y se preserva histórico mediante soft-delete/estado en vez de DELETE físico.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 024** — Administrar inscripciones (alta, baja, consulta) (MOD-04 Escolar)

### BR-012 — Impedir inscripción duplicada al mismo grupo (unicidad alumno-grupo) (RN-I02)
**Estado:** Implementada/MVP

**Descripción:** Impedir inscripción duplicada al mismo grupo (unicidad alumno-grupo)

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** `Director Escolar`
**Entidades/Tablas relevantes:** `Alumno`, `Grupo`, `Inscripción`
**Endpoints explícitos en HU:** —

**Validación UI:** La UI evita doble inscripción al mismo grupo y muestra claramente cupo/saldo/estado de inscripción; las bajas requieren motivo.

**Validación API/Backend:** El backend verifica cupo, unicidad alumno-grupo, transiciones válidas de estado y auditoría de baja (actor, timestamp, motivo).

**Restricción/Constraint BD:** Se define constraint UNIQUE(alumno_id, grupo_id) y se preserva histórico mediante soft-delete/estado en vez de DELETE físico.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 024** — Administrar inscripciones (alta, baja, consulta) (MOD-04 Escolar)

### BR-013 — Inscripción con ciclo de vida (activa, baja, concluida), motivo y timestamps (RN-I03)
**Estado:** Implementada/MVP

**Descripción:** Inscripción con ciclo de vida (activa, baja, concluida), motivo y timestamps

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** `Director Escolar`
**Entidades/Tablas relevantes:** `Alumno`, `Grupo`, `Inscripción`
**Endpoints explícitos en HU:** —

**Validación UI:** La UI evita doble inscripción al mismo grupo y muestra claramente cupo/saldo/estado de inscripción; las bajas requieren motivo.

**Validación API/Backend:** El backend verifica cupo, unicidad alumno-grupo, transiciones válidas de estado y auditoría de baja (actor, timestamp, motivo).

**Restricción/Constraint BD:** Se define constraint UNIQUE(alumno_id, grupo_id) y se preserva histórico mediante soft-delete/estado en vez de DELETE físico.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 024** — Administrar inscripciones (alta, baja, consulta) (MOD-04 Escolar)

### BR-014 — Baja conserva trazabilidad (quién, cuándo, por qué); no elimina evidencia (RN-I04)
**Estado:** Implementada/MVP

**Descripción:** Baja conserva trazabilidad (quién, cuándo, por qué); no elimina evidencia

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** `Director Escolar`
**Entidades/Tablas relevantes:** `Alumno`, `Grupo`, `Inscripción`
**Endpoints explícitos en HU:** —

**Validación UI:** La UI evita doble inscripción al mismo grupo y muestra claramente cupo/saldo/estado de inscripción; las bajas requieren motivo.

**Validación API/Backend:** El backend verifica cupo, unicidad alumno-grupo, transiciones válidas de estado y auditoría de baja (actor, timestamp, motivo).

**Restricción/Constraint BD:** Se define constraint UNIQUE(alumno_id, grupo_id) y se preserva histórico mediante soft-delete/estado en vez de DELETE físico.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 024** — Administrar inscripciones (alta, baja, consulta) (MOD-04 Escolar)


## Calificaciones, boletas y actas

### BR-015 — Asistencia por sesión/fecha asociada a inscripción (RN-C01)
**Estado:** Backlog (no existe HU asociada en la matriz actual)

**Descripción:** Asistencia por sesión/fecha asociada a inscripción

**Alcance (módulos):** —
**Roles típicos:** —
**Entidades/Tablas relevantes:** —
**Endpoints explícitos en HU:** —

**Validación UI:** La captura de calificaciones valida rangos y completitud por rubro; boleta/acta se habilita solo cuando procede.

**Validación API/Backend:** El backend valida rangos, calcula promedios determinísticamente y bloquea edición al cerrar acta, salvo flujo autorizado.

**Restricción/Constraint BD:** Se aplican CHECKs de rango, constraints de integridad y marca de cierre (lock) para impedir escrituras no autorizadas.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Documentación y creación de HU futura con criterios de aceptación y pruebas previstas.

**Trazabilidad (HU relacionadas):**
—
**HU sugerida (backlog):** HU-FUT-001

### BR-016 — Calificaciones por rubro/unidad/parcial, asociadas a inscripción; validar rangos (RN-C02)
**Estado:** Implementada/MVP

**Descripción:** Calificaciones por rubro/unidad/parcial, asociadas a inscripción; validar rangos

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** `Alumno`, `Director Escolar`
**Entidades/Tablas relevantes:** `Acta`, `Calificacion`, `Evaluación`
**Endpoints explícitos en HU:** —

**Validación UI:** La captura de calificaciones valida rangos y completitud por rubro; boleta/acta se habilita solo cuando procede.

**Validación API/Backend:** El backend valida rangos, calcula promedios determinísticamente y bloquea edición al cerrar acta, salvo flujo autorizado.

**Restricción/Constraint BD:** Se aplican CHECKs de rango, constraints de integridad y marca de cierre (lock) para impedir escrituras no autorizadas.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 025** — Gestionar calificaciones (captura, consulta) (MOD-04 Escolar)

### BR-017 — Calcular promedios y estatus académico a partir de calificaciones (RN-C03)
**Estado:** Implementada/MVP

**Descripción:** Calcular promedios y estatus académico a partir de calificaciones

**Alcance (módulos):** `MOD-04 Escolar`, `MOD-07 Reportes y Tablero`
**Roles típicos:** `Administrativo Comercial`, `Alumno`, `Director Escolar`
**Entidades/Tablas relevantes:** `Acta`, `AlertaStock`, `Calificacion`, `Evaluación`, `Indicador`, `KPI`, `ReporteCalificaciones`, `ReporteInscripciones`
**Endpoints explícitos en HU:** —

**Validación UI:** La captura de calificaciones valida rangos y completitud por rubro; boleta/acta se habilita solo cuando procede.

**Validación API/Backend:** El backend valida rangos, calcula promedios determinísticamente y bloquea edición al cerrar acta, salvo flujo autorizado.

**Restricción/Constraint BD:** Se aplican CHECKs de rango, constraints de integridad y marca de cierre (lock) para impedir escrituras no autorizadas.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 025** — Gestionar calificaciones (captura, consulta) (MOD-04 Escolar)
- **HU 043** — Visualizar tablero ejecutivo (matrícula, ventas del día, morosidad, alertas de inventario) (MOD-07 Reportes y Tablero)
- **HU 044** — Generar reportes académicos (inscripciones por periodo, calificaciones) (MOD-07 Reportes y Tablero)

### BR-018 — Emisión de boleta por periodo cuando calificaciones requeridas completas (RN-C04)
**Estado:** Implementada/MVP

**Descripción:** Emisión de boleta por periodo cuando calificaciones requeridas completas

**Alcance (módulos):** `MOD-04 Escolar`, `MOD-07 Reportes y Tablero`
**Roles típicos:** `Alumno`, `Director Escolar`
**Entidades/Tablas relevantes:** `Boleta`, `Calificacion`, `ExportacionReporte`, `Periodo`
**Endpoints explícitos en HU:** —

**Validación UI:** La captura de calificaciones valida rangos y completitud por rubro; boleta/acta se habilita solo cuando procede.

**Validación API/Backend:** El backend valida rangos, calcula promedios determinísticamente y bloquea edición al cerrar acta, salvo flujo autorizado.

**Restricción/Constraint BD:** Se aplican CHECKs de rango, constraints de integridad y marca de cierre (lock) para impedir escrituras no autorizadas.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 027** — Emitir boleta por periodo (PDF) (MOD-04 Escolar)
- **HU 046** — Exportar reportes (PDF/CSV) (MOD-07 Reportes y Tablero)

### BR-019 — Cierre de acta por grupo/periodo; bloquea edición; flujo controlado corrección (RN-C05)
**Estado:** Implementada/MVP

**Descripción:** Cierre de acta por grupo/periodo; bloquea edición; flujo controlado corrección

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** `Alumno`, `Director Escolar`
**Entidades/Tablas relevantes:** `Acta`, `Calificacion`, `Evaluación`, `EventoAuditoria`
**Endpoints explícitos en HU:** —

**Validación UI:** La captura de calificaciones valida rangos y completitud por rubro; boleta/acta se habilita solo cuando procede.

**Validación API/Backend:** El backend valida rangos, calcula promedios determinísticamente y bloquea edición al cerrar acta, salvo flujo autorizado.

**Restricción/Constraint BD:** Se aplican CHECKs de rango, constraints de integridad y marca de cierre (lock) para impedir escrituras no autorizadas.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 028** — Cerrar acta de calificaciones por grupo (MOD-04 Escolar)
- **HU 025** — Gestionar calificaciones (captura, consulta) (MOD-04 Escolar)


## Ventas POS (órdenes, pagos, descuentos y corte)

### BR-020 — Catálogo de productos/conceptos de cobro con precio y estado (RN-V01)
**Estado:** Implementada/MVP

**Descripción:** Catálogo de productos/conceptos de cobro con precio y estado

**Alcance (módulos):** `MOD-05 Ventas POS`, `MOD-06 Configuración y Gobierno`
**Roles típicos:** `Administrativo Comercial`, `Superusuario`
**Entidades/Tablas relevantes:** `Categoria`, `Existencia`, `FormaPago`, `Horario`, `Impuesto`, `Plan`, `Producto`, `Servicio`
**Endpoints explícitos en HU:** —

**Validación UI:** El POS valida cantidades, stock y autorización de descuentos; el corte de caja requiere confirmación y muestra resumen.

**Validación API/Backend:** El backend persiste cabecera/detalle, fija precio aplicado por renglón, permite pagos múltiples y aplica bloqueo post-corte.

**Restricción/Constraint BD:** Se modelan Venta/Detalle/Pago/Ticket/Corte con FK; se preserva histórico de precios y se evita edición retroactiva tras cierre.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 029** — Administrar catálogo (servicios, colegiaturas, materiales) (MOD-05 Ventas POS)
- **HU 039** — Administrar catálogos maestros (académicos y comerciales) (MOD-06 Configuración y Gobierno)

### BR-021 — Venta (orden POS) cabecera+detalle items (producto,cantidad,precio) (RN-V02)
**Estado:** Implementada/MVP

**Descripción:** Venta (orden POS) cabecera+detalle items (producto,cantidad,precio)

**Alcance (módulos):** `MOD-05 Ventas POS`
**Roles típicos:** `Administrativo Comercial`, `Alumno`
**Entidades/Tablas relevantes:** `Cliente`, `DetalleVenta`, `Ticket`, `Venta`
**Endpoints explícitos en HU:** —

**Validación UI:** El POS valida cantidades, stock y autorización de descuentos; el corte de caja requiere confirmación y muestra resumen.

**Validación API/Backend:** El backend persiste cabecera/detalle, fija precio aplicado por renglón, permite pagos múltiples y aplica bloqueo post-corte.

**Restricción/Constraint BD:** Se modelan Venta/Detalle/Pago/Ticket/Corte con FK; se preserva histórico de precios y se evita edición retroactiva tras cierre.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 030** — Registrar venta en punto de venta (POS) a alumno y emitir ticket (MOD-05 Ventas POS)

### BR-022 — Registrar precio aplicado por renglón (histórico) (RN-V03)
**Estado:** Implementada/MVP

**Descripción:** Registrar precio aplicado por renglón (histórico)

**Alcance (módulos):** `MOD-05 Ventas POS`
**Roles típicos:** `Administrativo Comercial`, `Alumno`
**Entidades/Tablas relevantes:** `Categoria`, `Cliente`, `DetalleVenta`, `Existencia`, `Impuesto`, `Producto`, `Ticket`, `Venta`
**Endpoints explícitos en HU:** —

**Validación UI:** El POS valida cantidades, stock y autorización de descuentos; el corte de caja requiere confirmación y muestra resumen.

**Validación API/Backend:** El backend persiste cabecera/detalle, fija precio aplicado por renglón, permite pagos múltiples y aplica bloqueo post-corte.

**Restricción/Constraint BD:** Se modelan Venta/Detalle/Pago/Ticket/Corte con FK; se preserva histórico de precios y se evita edición retroactiva tras cierre.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 030** — Registrar venta en punto de venta (POS) a alumno y emitir ticket (MOD-05 Ventas POS)
- **HU 029** — Administrar catálogo (servicios, colegiaturas, materiales) (MOD-05 Ventas POS)

### BR-023 — No vender con stock insuficiente si inventario habilitado (RN-V04)
**Estado:** Implementada/MVP

**Descripción:** No vender con stock insuficiente si inventario habilitado

**Alcance (módulos):** `MOD-05 Ventas POS`
**Roles típicos:** `Administrativo Comercial`, `Alumno`
**Entidades/Tablas relevantes:** `AlertaStock`, `Categoria`, `Cliente`, `DetalleVenta`, `Existencia`, `Impuesto`, `Producto`, `Ticket`, `Venta`
**Endpoints explícitos en HU:** —

**Validación UI:** El POS valida cantidades, stock y autorización de descuentos; el corte de caja requiere confirmación y muestra resumen.

**Validación API/Backend:** El backend persiste cabecera/detalle, fija precio aplicado por renglón, permite pagos múltiples y aplica bloqueo post-corte.

**Restricción/Constraint BD:** Se modelan Venta/Detalle/Pago/Ticket/Corte con FK; se preserva histórico de precios y se evita edición retroactiva tras cierre.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 030** — Registrar venta en punto de venta (POS) a alumno y emitir ticket (MOD-05 Ventas POS)
- **HU 029** — Administrar catálogo (servicios, colegiaturas, materiales) (MOD-05 Ventas POS)
- **HU 034** — Notificar existencias mínimas (MOD-05 Ventas POS)

### BR-024 — Múltiples pagos por orden; saldo (RN-V05)
**Estado:** Implementada/MVP

**Descripción:** Múltiples pagos por orden; saldo

**Alcance (módulos):** `MOD-05 Ventas POS`
**Roles típicos:** `Administrativo Comercial`, `Alumno`
**Entidades/Tablas relevantes:** `Alumno`, `EstadoCuenta`, `Pago`
**Endpoints explícitos en HU:** —

**Validación UI:** El POS valida cantidades, stock y autorización de descuentos; el corte de caja requiere confirmación y muestra resumen.

**Validación API/Backend:** El backend persiste cabecera/detalle, fija precio aplicado por renglón, permite pagos múltiples y aplica bloqueo post-corte.

**Restricción/Constraint BD:** Se modelan Venta/Detalle/Pago/Ticket/Corte con FK; se preserva histórico de precios y se evita edición retroactiva tras cierre.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 031** — Registrar pagos y consultar estado de cuenta (MOD-05 Ventas POS)

### BR-025 — Emitir ticket por pago/orden; folio; PDF opcional (RN-V06)
**Estado:** Implementada/MVP

**Descripción:** Emitir ticket por pago/orden; folio; PDF opcional

**Alcance (módulos):** `MOD-05 Ventas POS`
**Roles típicos:** `Administrativo Comercial`, `Alumno`
**Entidades/Tablas relevantes:** `Alumno`, `Cliente`, `DetalleVenta`, `EstadoCuenta`, `Pago`, `Ticket`, `Venta`
**Endpoints explícitos en HU:** —

**Validación UI:** El POS valida cantidades, stock y autorización de descuentos; el corte de caja requiere confirmación y muestra resumen.

**Validación API/Backend:** El backend persiste cabecera/detalle, fija precio aplicado por renglón, permite pagos múltiples y aplica bloqueo post-corte.

**Restricción/Constraint BD:** Se modelan Venta/Detalle/Pago/Ticket/Corte con FK; se preserva histórico de precios y se evita edición retroactiva tras cierre.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 030** — Registrar venta en punto de venta (POS) a alumno y emitir ticket (MOD-05 Ventas POS)
- **HU 031** — Registrar pagos y consultar estado de cuenta (MOD-05 Ventas POS)

### BR-026 — Descuentos solo con autorización; evidencia; topes (RN-V07)
**Estado:** Implementada/MVP

**Descripción:** Descuentos solo con autorización; evidencia; topes

**Alcance (módulos):** `MOD-05 Ventas POS`
**Roles típicos:** `Administrativo Comercial`
**Entidades/Tablas relevantes:** `Autorización`, `Permiso`, `ReglaDescuento`
**Endpoints explícitos en HU:** —

**Validación UI:** El POS valida cantidades, stock y autorización de descuentos; el corte de caja requiere confirmación y muestra resumen.

**Validación API/Backend:** El backend persiste cabecera/detalle, fija precio aplicado por renglón, permite pagos múltiples y aplica bloqueo post-corte.

**Restricción/Constraint BD:** Se modelan Venta/Detalle/Pago/Ticket/Corte con FK; se preserva histórico de precios y se evita edición retroactiva tras cierre.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 033** — Aplicar descuento autorizado (MOD-05 Ventas POS)

### BR-027 — Corte de caja; bloqueo cambios retroactivos salvo auditoría (RN-V08)
**Estado:** Implementada/MVP

**Descripción:** Corte de caja; bloqueo cambios retroactivos salvo auditoría

**Alcance (módulos):** `MOD-05 Ventas POS`, `MOD-07 Reportes y Tablero`
**Roles típicos:** `Administrativo Comercial`
**Entidades/Tablas relevantes:** `CorteCaja`, `MovimientoCaja`, `ReporteVentas`
**Endpoints explícitos en HU:** —

**Validación UI:** El POS valida cantidades, stock y autorización de descuentos; el corte de caja requiere confirmación y muestra resumen.

**Validación API/Backend:** El backend persiste cabecera/detalle, fija precio aplicado por renglón, permite pagos múltiples y aplica bloqueo post-corte.

**Restricción/Constraint BD:** Se modelan Venta/Detalle/Pago/Ticket/Corte con FK; se preserva histórico de precios y se evita edición retroactiva tras cierre.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 035** — Realizar corte de caja (MOD-05 Ventas POS)
- **HU 045** — Generar reportes comerciales (ventas por periodo, cortes de caja) (MOD-07 Reportes y Tablero)


## Inventario, compras y proveedores

### BR-028 — Inventario por movimientos derivados de ventas/compras/ajustes (RN-INV01)
**Estado:** Implementada/MVP

**Descripción:** Inventario por movimientos derivados de ventas/compras/ajustes

**Alcance (módulos):** `MOD-05 Ventas POS`
**Roles típicos:** `Administrativo Comercial`, `Alumno`
**Entidades/Tablas relevantes:** `AlertaStock`, `Categoria`, `Cliente`, `DetalleVenta`, `Existencia`, `Impuesto`, `Producto`, `Ticket`, `Venta`
**Endpoints explícitos en HU:** —

**Validación UI:** El sistema muestra alertas de stock mínimo y evita flujos que provoquen stock negativo cuando inventario está activo.

**Validación API/Backend:** El backend registra movimientos (entrada/salida/ajuste) derivados de ventas y alertas por umbral.

**Restricción/Constraint BD:** Se registra kardex por movimientos; se prohíben saldos negativos con constraints/validación transaccional.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 030** — Registrar venta en punto de venta (POS) a alumno y emitir ticket (MOD-05 Ventas POS)
- **HU 034** — Notificar existencias mínimas (MOD-05 Ventas POS)
- **HU 029** — Administrar catálogo (servicios, colegiaturas, materiales) (MOD-05 Ventas POS)

### BR-029 — Stock mínimo y alertas (RN-INV02)
**Estado:** Implementada/MVP

**Descripción:** Stock mínimo y alertas

**Alcance (módulos):** `MOD-05 Ventas POS`
**Roles típicos:** `Administrativo Comercial`
**Entidades/Tablas relevantes:** `AlertaStock`, `Existencia`
**Endpoints explícitos en HU:** —

**Validación UI:** El sistema muestra alertas de stock mínimo y evita flujos que provoquen stock negativo cuando inventario está activo.

**Validación API/Backend:** El backend registra movimientos (entrada/salida/ajuste) derivados de ventas y alertas por umbral.

**Restricción/Constraint BD:** Se registra kardex por movimientos; se prohíben saldos negativos con constraints/validación transaccional.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 034** — Notificar existencias mínimas (MOD-05 Ventas POS)

### BR-030 — Compras cabecera+detalle; entradas a inventario (RN-INV03)
**Estado:** Backlog (no existe HU asociada en la matriz actual)

**Descripción:** Compras cabecera+detalle; entradas a inventario

**Alcance (módulos):** —
**Roles típicos:** —
**Entidades/Tablas relevantes:** —
**Endpoints explícitos en HU:** —

**Validación UI:** El sistema muestra alertas de stock mínimo y evita flujos que provoquen stock negativo cuando inventario está activo.

**Validación API/Backend:** El backend registra movimientos (entrada/salida/ajuste) derivados de ventas y alertas por umbral.

**Restricción/Constraint BD:** Se registra kardex por movimientos; se prohíben saldos negativos con constraints/validación transaccional.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Documentación y creación de HU futura con criterios de aceptación y pruebas previstas.

**Trazabilidad (HU relacionadas):**
—
**HU sugerida (backlog):** HU-FUT-002

### BR-031 — Proveedores variables; compra registra proveedor utilizado (RN-INV04)
**Estado:** Backlog (no existe HU asociada en la matriz actual)

**Descripción:** Proveedores variables; compra registra proveedor utilizado

**Alcance (módulos):** —
**Roles típicos:** —
**Entidades/Tablas relevantes:** —
**Endpoints explícitos en HU:** —

**Validación UI:** El sistema muestra alertas de stock mínimo y evita flujos que provoquen stock negativo cuando inventario está activo.

**Validación API/Backend:** El backend registra movimientos (entrada/salida/ajuste) derivados de ventas y alertas por umbral.

**Restricción/Constraint BD:** Se registra kardex por movimientos; se prohíben saldos negativos con constraints/validación transaccional.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Documentación y creación de HU futura con criterios de aceptación y pruebas previstas.

**Trazabilidad (HU relacionadas):**
—
**HU sugerida (backlog):** HU-FUT-003

### BR-032 — Historial de costos por compra; no sobrescribir costo histórico (RN-INV05)
**Estado:** Backlog (no existe HU asociada en la matriz actual)

**Descripción:** Historial de costos por compra; no sobrescribir costo histórico

**Alcance (módulos):** —
**Roles típicos:** —
**Entidades/Tablas relevantes:** —
**Endpoints explícitos en HU:** —

**Validación UI:** El sistema muestra alertas de stock mínimo y evita flujos que provoquen stock negativo cuando inventario está activo.

**Validación API/Backend:** El backend registra movimientos (entrada/salida/ajuste) derivados de ventas y alertas por umbral.

**Restricción/Constraint BD:** Se registra kardex por movimientos; se prohíben saldos negativos con constraints/validación transaccional.

**Errores esperados:** `409 CONFLICT` cuando la operación viola unicidad/estado/cupo/cierre., `400 BAD REQUEST` cuando falla validación de formato o rango., `403 FORBIDDEN` cuando el rol carece de permiso.

**Evidencia mínima:**
- Documentación y creación de HU futura con criterios de aceptación y pruebas previstas.

**Trazabilidad (HU relacionadas):**
—
**HU sugerida (backlog):** HU-FUT-004


## Facturación y datos fiscales (México)

### BR-033 — Cliente puede requerir factura; registrar datos fiscales (RN-F01)
**Estado:** Backlog (no existe HU asociada en la matriz actual)

**Descripción:** Cliente puede requerir factura; registrar datos fiscales

**Alcance (módulos):** —
**Roles típicos:** —
**Entidades/Tablas relevantes:** —
**Endpoints explícitos en HU:** —

**Validación UI:** Cuando el cliente solicita factura, la UI solicita únicamente los datos fiscales requeridos y valida formato básico.

**Validación API/Backend:** El backend trata datos fiscales como entidad opcional, valida RFC/CP y asocia la referencia fiscal a la venta cuando aplica.

**Restricción/Constraint BD:** Se separan datos fiscales en entidad independiente con integridad referencial hacia cliente/venta.

**Errores esperados:** `400 BAD REQUEST` por datos inválidos., `401 UNAUTHORIZED`/`403 FORBIDDEN` por autenticación/autorización.

**Evidencia mínima:**
- Documentación y creación de HU futura con criterios de aceptación y pruebas previstas.

**Trazabilidad (HU relacionadas):**
—
**HU sugerida (backlog):** HU-FUT-005

### BR-034 — Datos fiscales entidad separada opcional (RN-F02)
**Estado:** Backlog (no existe HU asociada en la matriz actual)

**Descripción:** Datos fiscales entidad separada opcional

**Alcance (módulos):** —
**Roles típicos:** —
**Entidades/Tablas relevantes:** —
**Endpoints explícitos en HU:** —

**Validación UI:** Cuando el cliente solicita factura, la UI solicita únicamente los datos fiscales requeridos y valida formato básico.

**Validación API/Backend:** El backend trata datos fiscales como entidad opcional, valida RFC/CP y asocia la referencia fiscal a la venta cuando aplica.

**Restricción/Constraint BD:** Se separan datos fiscales en entidad independiente con integridad referencial hacia cliente/venta.

**Errores esperados:** `400 BAD REQUEST` por datos inválidos., `401 UNAUTHORIZED`/`403 FORBIDDEN` por autenticación/autorización.

**Evidencia mínima:**
- Documentación y creación de HU futura con criterios de aceptación y pruebas previstas.

**Trazabilidad (HU relacionadas):**
—
**HU sugerida (backlog):** HU-FUT-006

### BR-035 — Validar consistencia mínima RFC y CP fiscal conforme práctica vigente (RN-F03)
**Estado:** Implementada/MVP

**Descripción:** Validar consistencia mínima RFC y CP fiscal conforme práctica vigente

**Alcance (módulos):** `MOD-04 Escolar`
**Roles típicos:** —
**Entidades/Tablas relevantes:** `Alumno`
**Endpoints explícitos en HU:** —

**Validación UI:** Cuando el cliente solicita factura, la UI solicita únicamente los datos fiscales requeridos y valida formato básico.

**Validación API/Backend:** El backend trata datos fiscales como entidad opcional, valida RFC/CP y asocia la referencia fiscal a la venta cuando aplica.

**Restricción/Constraint BD:** Se separan datos fiscales en entidad independiente con integridad referencial hacia cliente/venta.

**Errores esperados:** `400 BAD REQUEST` por datos inválidos., `401 UNAUTHORIZED`/`403 FORBIDDEN` por autenticación/autorización.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 026** — Validar CURP y RFC (sin homoclave) (MOD-04 Escolar)


## Seguridad, roles, gobierno y auditoría

### BR-036 — Control de acceso basado en roles; usuario con uno o varios roles; permisos (RN-S01)
**Estado:** Implementada/MVP

**Descripción:** Control de acceso basado en roles; usuario con uno o varios roles; permisos

**Alcance (módulos):** `MOD-03 Usuarios y Roles`
**Roles típicos:** `Superusuario`
**Entidades/Tablas relevantes:** `EventoAuditoria`, `Permiso`, `Rol`, `RolPermiso`, `Usuario`, `UsuarioRol`
**Endpoints explícitos en HU:** —

**Validación UI:** Las pantallas sensibles se ocultan/deniegan por rol; login aplica CAPTCHA y políticas de bloqueo/inactividad.

**Validación API/Backend:** El backend aplica RBAC, registra auditoría de eventos críticos y aplica políticas de sesión/tokens/intententos.

**Restricción/Constraint BD:** Se preservan bitácoras inmutables y se privilegia desactivación (soft delete) sobre eliminación física en entidades referenciadas.

**Errores esperados:** `400 BAD REQUEST` por datos inválidos., `401 UNAUTHORIZED`/`403 FORBIDDEN` por autenticación/autorización.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 016** — Administrar roles y permisos (MOD-03 Usuarios y Roles)
- **HU 021** — Asignar roles a usuario (MOD-03 Usuarios y Roles)
- **HU 015** — Administrar usuarios (alta, edición, baja, activación) (MOD-03 Usuarios y Roles)

### BR-037 — Auditoría/bitácora de acciones relevantes (RN-S02)
**Estado:** Implementada/MVP

**Descripción:** Auditoría/bitácora de acciones relevantes

**Alcance (módulos):** `MOD-03 Usuarios y Roles`, `MOD-06 Configuración y Gobierno`
**Roles típicos:** `Superusuario`
**Entidades/Tablas relevantes:** `EventoAuditoria`, `EvidenciaConfig`, `Respaldo`
**Endpoints explícitos en HU:** —

**Validación UI:** Las pantallas sensibles se ocultan/deniegan por rol; login aplica CAPTCHA y políticas de bloqueo/inactividad.

**Validación API/Backend:** El backend aplica RBAC, registra auditoría de eventos críticos y aplica políticas de sesión/tokens/intententos.

**Restricción/Constraint BD:** Se preservan bitácoras inmutables y se privilegia desactivación (soft delete) sobre eliminación física en entidades referenciadas.

**Errores esperados:** `400 BAD REQUEST` por datos inválidos., `401 UNAUTHORIZED`/`403 FORBIDDEN` por autenticación/autorización.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 017** — Consultar bitácora de cambios (MOD-03 Usuarios y Roles)
- **HU 042** — Exportar bitácora y evidencias de configuración (CSV/PDF, hash) (MOD-06 Configuración y Gobierno)
- **HU 038** — Gestionar respaldos y auditoría (generar, restaurar, bitácora) (MOD-06 Configuración y Gobierno)

### BR-038 — Parámetros de gobierno; catálogos; impedir eliminar referenciados; solo desac… (RN-S03)
**Estado:** Implementada/MVP

**Descripción:** Parámetros de gobierno; catálogos; impedir eliminar referenciados; solo desactivar

**Alcance (módulos):** `MOD-03 Usuarios y Roles`, `MOD-05 Ventas POS`, `MOD-06 Configuración y Gobierno`
**Roles típicos:** `Administrativo Comercial`, `Superusuario`
**Entidades/Tablas relevantes:** `Categoria`, `EventoAuditoria`, `Existencia`, `FormaPago`, `Horario`, `Impuesto`, `Plan`, `Producto`, `Servicio`, `Sesión`, `Token`, `Usuario`
**Endpoints explícitos en HU:** —

**Validación UI:** Las pantallas sensibles se ocultan/deniegan por rol; login aplica CAPTCHA y políticas de bloqueo/inactividad.

**Validación API/Backend:** El backend aplica RBAC, registra auditoría de eventos críticos y aplica políticas de sesión/tokens/intententos.

**Restricción/Constraint BD:** Se preservan bitácoras inmutables y se privilegia desactivación (soft delete) sobre eliminación física en entidades referenciadas.

**Errores esperados:** `400 BAD REQUEST` por datos inválidos., `401 UNAUTHORIZED`/`403 FORBIDDEN` por autenticación/autorización.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 039** — Administrar catálogos maestros (académicos y comerciales) (MOD-06 Configuración y Gobierno)
- **HU 020** — Cambiar estado de usuario (desactivar/reactivar) (MOD-03 Usuarios y Roles)
- **HU 029** — Administrar catálogo (servicios, colegiaturas, materiales) (MOD-05 Ventas POS)

### BR-039 — intentos, expiración sesión/tokens, CAPTCHA; evidencia (RN-S04)
**Estado:** Implementada/MVP

**Descripción:** Políticas de seguridad: intentos, expiración sesión/tokens, CAPTCHA; evidencia

**Alcance (módulos):** `MOD-01 Portal Publico`, `MOD-02 Portal Publico`, `MOD-06 Configuración y Gobierno`
**Roles típicos:** `Administrativo Comercial`, `Alumno`, `Director Escolar`, `Superusuario`
**Entidades/Tablas relevantes:** `BitacoraAcceso`, `Captcha`, `PoliticaSeguridad`, `Sesión`, `Token`, `Usuario`, `asunto`, `captcha_token`, `mensaje`
**Endpoints explícitos en HU:** `POST /auth/login`, `POST /contacto`

**Validación UI:** Las pantallas sensibles se ocultan/deniegan por rol; login aplica CAPTCHA y políticas de bloqueo/inactividad.

**Validación API/Backend:** El backend aplica RBAC, registra auditoría de eventos críticos y aplica políticas de sesión/tokens/intententos.

**Restricción/Constraint BD:** Se preservan bitácoras inmutables y se privilegia desactivación (soft delete) sobre eliminación física en entidades referenciadas.

**Errores esperados:** `400 BAD REQUEST` por datos inválidos., `401 UNAUTHORIZED`/`403 FORBIDDEN` por autenticación/autorización.

**Evidencia mínima:**
- Ejecución de pruebas del repositorio (`pytest` o `python manage.py test`) y validación manual de la pantalla correspondiente.
- Registro de auditoría/bitácora cuando la regla implique operación sensible (cierres, bajas, descuentos, cambios de seguridad).

**Trazabilidad (HU relacionadas):**
- **HU 008** — Iniciar sesión con CAPTCHA (MOD-02 Portal Publico)
- **HU 012** — Bloquear por intentos fallidos (MOD-02 Portal Publico)
- **HU 013** — Cerrar sesión por inactividad (MOD-02 Portal Publico)
- **HU 010** — Gestionar sesión y tokens (MOD-02 Portal Publico)
- **HU 037** — Configurar políticas de seguridad (contraseña, intentos, caducidad de sesión) (MOD-06 Configuración y Gobierno)
- **HU 005** — Enviar mensaje de contacto con CAPTCHA (MOD-01 Portal Publico)

