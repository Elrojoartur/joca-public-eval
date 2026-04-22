/* =======================================================================
   JOCA - MODELO RELACIONAL EN 3FN
   Versión final de cierre técnico para repo, diagramas y VPS.
   Criterio aplicado: eliminación de atributos derivables en órdenes y corte.
   ======================================================================= */

BEGIN;

CREATE SCHEMA IF NOT EXISTS seguridad;
CREATE SCHEMA IF NOT EXISTS gobierno;
CREATE SCHEMA IF NOT EXISTS escolar;
CREATE SCHEMA IF NOT EXISTS ventas;
CREATE SCHEMA IF NOT EXISTS inventario;

-- =========================================================
-- SEGURIDAD
-- =========================================================
CREATE TABLE IF NOT EXISTS seguridad.auth_user (
  id BIGSERIAL PRIMARY KEY,
  username VARCHAR(150) NOT NULL,
  email VARCHAR(254),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_auth_user_username UNIQUE (username),
  CONSTRAINT uq_auth_user_email UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS seguridad.rol (
  id BIGSERIAL PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  codigo VARCHAR(80) NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_rol_nombre UNIQUE (nombre),
  CONSTRAINT uq_rol_codigo UNIQUE (codigo)
);

CREATE TABLE IF NOT EXISTS seguridad.permiso (
  id BIGSERIAL PRIMARY KEY,
  nombre VARCHAR(150) NOT NULL,
  codigo VARCHAR(120) NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_permiso_nombre UNIQUE (nombre),
  CONSTRAINT uq_permiso_codigo UNIQUE (codigo)
);

CREATE TABLE IF NOT EXISTS seguridad.usuario_rol (
  id BIGSERIAL PRIMARY KEY,
  usuario_id BIGINT NOT NULL,
  rol_id BIGINT NOT NULL,
  asignado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_usuario_rol_usuario_id_rol_id UNIQUE (usuario_id, rol_id),
  CONSTRAINT fk_usuario_rol_usuario_id FOREIGN KEY (usuario_id) REFERENCES seguridad.auth_user(id) ON DELETE RESTRICT,
  CONSTRAINT fk_usuario_rol_rol_id FOREIGN KEY (rol_id) REFERENCES seguridad.rol(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS seguridad.rol_permiso (
  id BIGSERIAL PRIMARY KEY,
  rol_id BIGINT NOT NULL,
  permiso_id BIGINT NOT NULL,
  asignado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_rol_permiso_rol_id_permiso_id UNIQUE (rol_id, permiso_id),
  CONSTRAINT fk_rol_permiso_rol_id FOREIGN KEY (rol_id) REFERENCES seguridad.rol(id) ON DELETE RESTRICT,
  CONSTRAINT fk_rol_permiso_permiso_id FOREIGN KEY (permiso_id) REFERENCES seguridad.permiso(id) ON DELETE RESTRICT
);

-- =========================================================
-- GOBIERNO
-- =========================================================
CREATE TABLE IF NOT EXISTS gobierno.evento_auditoria (
  id BIGSERIAL PRIMARY KEY,
  actor_id BIGINT,
  accion VARCHAR(80) NOT NULL,
  resultado VARCHAR(80) NOT NULL,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_evento_auditoria_actor_id FOREIGN KEY (actor_id) REFERENCES seguridad.auth_user(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS gobierno.respaldo_sistema (
  id BIGSERIAL PRIMARY KEY,
  generado_por_id BIGINT,
  ruta_archivo VARCHAR(500) NOT NULL,
  generado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_respaldo_sistema_generado_por_id FOREIGN KEY (generado_por_id) REFERENCES seguridad.auth_user(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS gobierno.parametro_sistema (
  id BIGSERIAL PRIMARY KEY,
  clave VARCHAR(120) NOT NULL,
  valor TEXT NOT NULL,
  actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_parametro_sistema_clave UNIQUE (clave)
);

-- =========================================================
-- ESCOLAR
-- =========================================================
CREATE TABLE IF NOT EXISTS escolar.alumno (
  id_alumno BIGSERIAL PRIMARY KEY,
  matricula VARCHAR(30) NOT NULL,
  nombres VARCHAR(120) NOT NULL,
  apellido_paterno VARCHAR(120) NOT NULL,
  apellido_materno VARCHAR(120),
  correo VARCHAR(254),
  curp VARCHAR(18),
  rfc VARCHAR(13),
  CONSTRAINT uq_alumno_matricula UNIQUE (matricula),
  CONSTRAINT uq_alumno_correo UNIQUE (correo),
  CONSTRAINT uq_alumno_curp UNIQUE (curp)
);

CREATE TABLE escolar.alumno_domicilio (
  id BIGSERIAL PRIMARY KEY,
  alumno_id BIGINT NOT NULL UNIQUE,
  calle VARCHAR(150),
  numero VARCHAR(20),
  colonia VARCHAR(120),
  codigo_postal CHAR(5),
  estado VARCHAR(120),
  pais VARCHAR(120) NOT NULL DEFAULT 'México',
  actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_alumno_domicilio_alumno_id
    FOREIGN KEY (alumno_id)
    REFERENCES escolar.alumno(id_alumno)
    ON DELETE RESTRICT,
  CONSTRAINT ck_alumno_domicilio_codigo_postal
    CHECK (codigo_postal IS NULL OR codigo_postal ~ '^[0-9]{5}$')
);



CREATE TABLE IF NOT EXISTS escolar.curso (
  id BIGSERIAL PRIMARY KEY,
  codigo VARCHAR(50) NOT NULL,
  nombre VARCHAR(180) NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_curso_codigo UNIQUE (codigo)
);

CREATE TABLE IF NOT EXISTS escolar.periodo (
  id BIGSERIAL PRIMARY KEY,
  codigo VARCHAR(40) NOT NULL,
  fecha_inicio DATE NOT NULL,
  fecha_fin DATE NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_periodo_codigo UNIQUE (codigo),
  CONSTRAINT ck_periodo_fechas CHECK (fecha_fin >= fecha_inicio)
);

CREATE TABLE IF NOT EXISTS escolar.grupo (
  id BIGSERIAL PRIMARY KEY,
  curso_ref_id BIGINT NOT NULL,
  periodo_ref_id BIGINT NOT NULL,
  tipo_horario VARCHAR(40) NOT NULL,
  cupo INTEGER NOT NULL DEFAULT 0,
  estado SMALLINT NOT NULL DEFAULT 1,
  CONSTRAINT uq_grupo_curso_ref_id_periodo_ref_id_tipo_horario UNIQUE (curso_ref_id, periodo_ref_id, tipo_horario),
  CONSTRAINT ck_grupo_cupo CHECK (cupo >= 0),
  CONSTRAINT ck_grupo_estado CHECK (estado IN (0,1,2)),
  CONSTRAINT fk_grupo_curso_ref_id FOREIGN KEY (curso_ref_id) REFERENCES escolar.curso(id) ON DELETE RESTRICT,
  CONSTRAINT fk_grupo_periodo_ref_id FOREIGN KEY (periodo_ref_id) REFERENCES escolar.periodo(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS escolar.docente (
  id BIGSERIAL PRIMARY KEY,
  nombres VARCHAR(120) NOT NULL,
  apellido_paterno VARCHAR(120) NOT NULL,
  apellido_materno VARCHAR(120),
  correo VARCHAR(254),
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_docente_correo UNIQUE (correo)
);

CREATE TABLE IF NOT EXISTS escolar.docente_grupo (
  id BIGSERIAL PRIMARY KEY,
  docente_id BIGINT NOT NULL,
  grupo_id BIGINT NOT NULL,
  rol VARCHAR(60) NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_docente_grupo_docente_id_grupo_id_rol UNIQUE (docente_id, grupo_id, rol),
  CONSTRAINT fk_docente_grupo_docente_id FOREIGN KEY (docente_id) REFERENCES escolar.docente(id) ON DELETE RESTRICT,
  CONSTRAINT fk_docente_grupo_grupo_id FOREIGN KEY (grupo_id) REFERENCES escolar.grupo(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS escolar.aula (
  id BIGSERIAL PRIMARY KEY,
  clave VARCHAR(40) NOT NULL,
  nombre VARCHAR(120) NOT NULL,
  capacidad INTEGER NOT NULL DEFAULT 0,
  activa BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_aula_clave UNIQUE (clave),
  CONSTRAINT ck_aula_capacidad CHECK (capacidad >= 0)
);

CREATE TABLE IF NOT EXISTS escolar.grupo_horario (
  id BIGSERIAL PRIMARY KEY,
  grupo_id BIGINT NOT NULL,
  aula_ref_id BIGINT NOT NULL,
  dia VARCHAR(15) NOT NULL,
  hora_inicio TIME NOT NULL,
  hora_fin TIME NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_grupo_horario_grupo_id_dia_hora_inicio_hora_fin UNIQUE (grupo_id, dia, hora_inicio, hora_fin),
  CONSTRAINT ck_grupo_horario_horas CHECK (hora_fin > hora_inicio),
  CONSTRAINT fk_grupo_horario_grupo_id FOREIGN KEY (grupo_id) REFERENCES escolar.grupo(id) ON DELETE RESTRICT,
  CONSTRAINT fk_grupo_horario_aula_ref_id FOREIGN KEY (aula_ref_id) REFERENCES escolar.aula(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS escolar.inscripcion (
  id BIGSERIAL PRIMARY KEY,
  alumno_id BIGINT NOT NULL,
  grupo_id BIGINT NOT NULL,
  fecha_inscripcion DATE NOT NULL DEFAULT CURRENT_DATE,
  estado VARCHAR(20) NOT NULL,
  CONSTRAINT uq_inscripcion_alumno_id_grupo_id UNIQUE (alumno_id, grupo_id),
  CONSTRAINT ck_inscripcion_estado CHECK (estado IN ('activa','baja','concluida')),
  CONSTRAINT fk_inscripcion_alumno_id FOREIGN KEY (alumno_id) REFERENCES escolar.alumno(id_alumno) ON DELETE RESTRICT,
  CONSTRAINT fk_inscripcion_grupo_id FOREIGN KEY (grupo_id) REFERENCES escolar.grupo(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS escolar.calificacion (
  id BIGSERIAL PRIMARY KEY,
  inscripcion_id BIGINT NOT NULL,
  valor NUMERIC(5,2) NOT NULL,
  capturado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_calificacion_inscripcion_id UNIQUE (inscripcion_id),
  CONSTRAINT ck_calificacion_rango CHECK (valor BETWEEN 0 AND 10),
  CONSTRAINT fk_calificacion_inscripcion_id FOREIGN KEY (inscripcion_id) REFERENCES escolar.inscripcion(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS escolar.acta_cierre (
  id BIGSERIAL PRIMARY KEY,
  grupo_id BIGINT NOT NULL,
  cerrada_por_id BIGINT NOT NULL,
  cerrada_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_acta_cierre_grupo_id UNIQUE (grupo_id),
  CONSTRAINT fk_acta_cierre_grupo_id FOREIGN KEY (grupo_id) REFERENCES escolar.grupo(id) ON DELETE RESTRICT,
  CONSTRAINT fk_acta_cierre_cerrada_por_id FOREIGN KEY (cerrada_por_id) REFERENCES seguridad.auth_user(id) ON DELETE RESTRICT
);

-- =========================================================
-- VENTAS
-- =========================================================
CREATE TABLE IF NOT EXISTS ventas.concepto (
  id BIGSERIAL PRIMARY KEY,
  nombre VARCHAR(180) NOT NULL,
  precio NUMERIC(12,2) NOT NULL DEFAULT 0,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_concepto_nombre UNIQUE (nombre),
  CONSTRAINT ck_concepto_precio CHECK (precio >= 0)
);

CREATE TABLE IF NOT EXISTS ventas.orden_pos (
  id BIGSERIAL PRIMARY KEY,
  inscripcion_id BIGINT NOT NULL,
  fecha_emision TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  estado VARCHAR(20) NOT NULL,
  CONSTRAINT uq_orden_pos_inscripcion_id UNIQUE (inscripcion_id),
  CONSTRAINT ck_orden_pos_estado CHECK (estado IN ('abierta','pagada','cancelada')),
  CONSTRAINT fk_orden_pos_inscripcion_id FOREIGN KEY (inscripcion_id) REFERENCES escolar.inscripcion(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS ventas.orden_item (
  id BIGSERIAL PRIMARY KEY,
  orden_id BIGINT NOT NULL,
  concepto_id BIGINT NOT NULL,
  cantidad INTEGER NOT NULL,
  precio_unit NUMERIC(12,2) NOT NULL,
  CONSTRAINT uq_orden_item_orden_id_concepto_id UNIQUE (orden_id, concepto_id),
  CONSTRAINT ck_orden_item_cantidad CHECK (cantidad > 0),
  CONSTRAINT ck_orden_item_precio CHECK (precio_unit >= 0),
  CONSTRAINT fk_orden_item_orden_id FOREIGN KEY (orden_id) REFERENCES ventas.orden_pos(id) ON DELETE RESTRICT,
  CONSTRAINT fk_orden_item_concepto_id FOREIGN KEY (concepto_id) REFERENCES ventas.concepto(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS ventas.pago (
  id BIGSERIAL PRIMARY KEY,
  orden_id BIGINT NOT NULL,
  fecha_pago TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  monto NUMERIC(12,2) NOT NULL,
  metodo VARCHAR(20) NOT NULL,
  CONSTRAINT ck_pago_monto CHECK (monto > 0),
  CONSTRAINT ck_pago_metodo CHECK (metodo IN ('efectivo','transferencia','tarjeta','otro')),
  CONSTRAINT fk_pago_orden_id FOREIGN KEY (orden_id) REFERENCES ventas.orden_pos(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS ventas.ticket (
  id BIGSERIAL PRIMARY KEY,
  pago_id BIGINT NOT NULL,
  generado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ruta_pdf VARCHAR(500),
  CONSTRAINT uq_ticket_pago_id UNIQUE (pago_id),
  CONSTRAINT fk_ticket_pago_id FOREIGN KEY (pago_id) REFERENCES ventas.pago(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS ventas.corte_caja (
  id BIGSERIAL PRIMARY KEY,
  fecha_operacion DATE NOT NULL,
  realizado_por_id BIGINT NOT NULL,
  CONSTRAINT uq_corte_caja_fecha_operacion UNIQUE (fecha_operacion),
  CONSTRAINT fk_corte_caja_realizado_por_id FOREIGN KEY (realizado_por_id) REFERENCES seguridad.auth_user(id) ON DELETE RESTRICT
);

-- =========================================================
-- INVENTARIO
-- =========================================================
CREATE TABLE IF NOT EXISTS inventario.existencia (
  id BIGSERIAL PRIMARY KEY,
  concepto_id BIGINT NOT NULL,
  inventario_habilitado BOOLEAN NOT NULL DEFAULT TRUE,
  stock_actual NUMERIC(12,2) NOT NULL,
  stock_minimo NUMERIC(12,2) NOT NULL,
  CONSTRAINT uq_existencia_concepto_id UNIQUE (concepto_id),
  CONSTRAINT ck_existencia_stock CHECK (stock_actual >= 0 AND stock_minimo >= 0),
  CONSTRAINT fk_existencia_concepto_id FOREIGN KEY (concepto_id) REFERENCES ventas.concepto(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS inventario.alerta_stock (
  id BIGSERIAL PRIMARY KEY,
  existencia_id BIGINT NOT NULL,
  stock_actual NUMERIC(12,2) NOT NULL,
  stock_minimo NUMERIC(12,2) NOT NULL,
  activa BOOLEAN NOT NULL DEFAULT TRUE,
  generado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ck_alerta_stock_valores CHECK (stock_actual >= 0 AND stock_minimo >= 0),
  CONSTRAINT fk_alerta_stock_existencia_id FOREIGN KEY (existencia_id) REFERENCES inventario.existencia(id) ON DELETE RESTRICT
);

-- =========================================================
-- ÍNDICES DE APOYO
-- =========================================================
CREATE INDEX IF NOT EXISTS ix_usuario_rol_usuario_id ON seguridad.usuario_rol(usuario_id);
CREATE INDEX IF NOT EXISTS ix_usuario_rol_rol_id ON seguridad.usuario_rol(rol_id);
CREATE INDEX IF NOT EXISTS ix_rol_permiso_rol_id ON seguridad.rol_permiso(rol_id);
CREATE INDEX IF NOT EXISTS ix_rol_permiso_permiso_id ON seguridad.rol_permiso(permiso_id);
CREATE INDEX IF NOT EXISTS ix_evento_auditoria_actor_id ON gobierno.evento_auditoria(actor_id);
CREATE INDEX IF NOT EXISTS ix_respaldo_sistema_generado_por_id ON gobierno.respaldo_sistema(generado_por_id);
CREATE INDEX IF NOT EXISTS ix_grupo_curso_ref_id ON escolar.grupo(curso_ref_id);
CREATE INDEX IF NOT EXISTS ix_grupo_periodo_ref_id ON escolar.grupo(periodo_ref_id);
CREATE INDEX IF NOT EXISTS ix_docente_grupo_docente_id ON escolar.docente_grupo(docente_id);
CREATE INDEX IF NOT EXISTS ix_docente_grupo_grupo_id ON escolar.docente_grupo(grupo_id);
CREATE INDEX IF NOT EXISTS ix_grupo_horario_grupo_id ON escolar.grupo_horario(grupo_id);
CREATE INDEX IF NOT EXISTS ix_grupo_horario_aula_ref_id ON escolar.grupo_horario(aula_ref_id);
CREATE INDEX IF NOT EXISTS ix_inscripcion_alumno_id ON escolar.inscripcion(alumno_id);
CREATE INDEX ix_alumno_domicilio_alumno_id ON escolar.alumno_domicilio(alumno_id);
CREATE INDEX IF NOT EXISTS ix_inscripcion_grupo_id ON escolar.inscripcion(grupo_id);
CREATE INDEX IF NOT EXISTS ix_calificacion_inscripcion_id ON escolar.calificacion(inscripcion_id);
CREATE INDEX IF NOT EXISTS ix_acta_cierre_grupo_id ON escolar.acta_cierre(grupo_id);
CREATE INDEX IF NOT EXISTS ix_acta_cierre_cerrada_por_id ON escolar.acta_cierre(cerrada_por_id);
CREATE INDEX IF NOT EXISTS ix_existencia_concepto_id ON inventario.existencia(concepto_id);
CREATE INDEX IF NOT EXISTS ix_alerta_stock_existencia_id ON inventario.alerta_stock(existencia_id);
CREATE INDEX IF NOT EXISTS ix_orden_pos_inscripcion_id ON ventas.orden_pos(inscripcion_id);
CREATE INDEX IF NOT EXISTS ix_orden_item_orden_id ON ventas.orden_item(orden_id);
CREATE INDEX IF NOT EXISTS ix_orden_item_concepto_id ON ventas.orden_item(concepto_id);
CREATE INDEX IF NOT EXISTS ix_pago_orden_id ON ventas.pago(orden_id);
CREATE INDEX IF NOT EXISTS ix_ticket_pago_id ON ventas.ticket(pago_id);
CREATE INDEX IF NOT EXISTS ix_corte_caja_realizado_por_id ON ventas.corte_caja(realizado_por_id);

-- =========================================================
-- COMENTARIOS DOCUMENTALES
-- =========================================================
COMMENT ON TABLE escolar.alumno_domicilio IS 'Domicilio complementario del alumno; conserva una relación 1:1 con escolar.alumno.';
COMMENT ON TABLE inventario.alerta_stock IS 'Snapshot de alerta de inventario; conserva el estado observado al momento de generarse.';
COMMENT ON TABLE ventas.orden_pos IS 'Orden principal; el monto total se deriva del detalle en ventas.orden_item.';
COMMENT ON TABLE ventas.corte_caja IS 'Registro del corte; los montos se obtienen por consulta y no se almacenan en esta versión estricta.';

-- =========================================================
-- VISTAS DE APOYO (VALORES DERIVADOS)
-- =========================================================
CREATE OR REPLACE VIEW ventas.v_orden_total_calculado AS
SELECT
  oi.orden_id,
  SUM(oi.cantidad * oi.precio_unit) AS total_orden
FROM ventas.orden_item oi
GROUP BY oi.orden_id;

CREATE OR REPLACE VIEW ventas.v_corte_caja_resumen AS
SELECT
  o.fecha_emision::date AS fecha_operacion,
  COALESCE(SUM(oi.cantidad * oi.precio_unit), 0) AS total_ordenes,
  COALESCE(SUM(p.monto), 0) AS total_pagos
FROM ventas.orden_pos o
LEFT JOIN ventas.orden_item oi ON oi.orden_id = o.id
LEFT JOIN ventas.pago p ON p.orden_id = o.id
GROUP BY o.fecha_emision::date;

COMMIT;

/* =======================================================================
   CONSULTA DE DICCIONARIO / TRAZABILIDAD DEL MODELO
   ======================================================================= */
WITH cols AS (
  SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attnum AS ordinal_position,
    a.attname AS column_name,
    format_type(a.atttypid, a.atttypmod) AS data_type,
    CASE WHEN a.attnotnull THEN 'NO' ELSE 'YES' END AS is_nullable,
    pg_get_expr(ad.adbin, ad.adrelid) AS column_default,
    col_description(a.attrelid, a.attnum) AS comment
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_attribute a ON a.attrelid = c.oid
  LEFT JOIN pg_attrdef ad ON ad.adrelid = c.oid AND ad.adnum = a.attnum
  WHERE c.relkind = 'r'
    AND n.nspname IN ('escolar','ventas','inventario','seguridad','gobierno')
    AND a.attnum > 0
    AND NOT a.attisdropped
),
pk_cols AS (
  SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    con.conname AS pk_name
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN unnest(con.conkey) AS k(attnum) ON true
  JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
  WHERE con.contype = 'p'
    AND n.nspname IN ('escolar','ventas','inventario','seguridad','gobierno')
),
uq_cols AS (
  SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    string_agg(DISTINCT con.conname, ', ' ORDER BY con.conname) AS unique_names
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN unnest(con.conkey) AS k(attnum) ON true
  JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
  WHERE con.contype = 'u'
    AND n.nspname IN ('escolar','ventas','inventario','seguridad','gobierno')
  GROUP BY n.nspname, c.relname, a.attname
),
fk_map AS (
  SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    con.conname AS fk_name,
    rn.nspname AS ref_schema,
    rc.relname AS ref_table,
    ra.attname AS ref_column
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_class rc ON rc.oid = con.confrelid
  JOIN pg_namespace rn ON rn.oid = rc.relnamespace
  JOIN unnest(con.conkey) WITH ORDINALITY AS ck(attnum, ord) ON true
  JOIN unnest(con.confkey) WITH ORDINALITY AS fk(attnum, ord) ON fk.ord = ck.ord
  JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ck.attnum
  JOIN pg_attribute ra ON ra.attrelid = rc.oid AND ra.attnum = fk.attnum
  WHERE con.contype = 'f'
    AND n.nspname IN ('escolar','ventas','inventario','seguridad','gobierno')
),
fk_cols AS (
  SELECT
    schema_name,
    table_name,
    column_name,
    string_agg(fk_ref, '; ' ORDER BY fk_ref) AS fk_refs
  FROM (
    SELECT DISTINCT
      schema_name,
      table_name,
      column_name,
      fk_name || ' -> ' || ref_schema || '.' || ref_table || '(' || ref_column || ')' AS fk_ref
    FROM fk_map
  ) s
  GROUP BY schema_name, table_name, column_name
),
checks AS (
  SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    string_agg(con.conname || ': ' || pg_get_constraintdef(con.oid), ' | ' ORDER BY con.conname) AS check_defs
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE con.contype = 'c'
    AND n.nspname IN ('escolar','ventas','inventario','seguridad','gobierno')
  GROUP BY n.nspname, c.relname
)
SELECT
  cols.schema_name AS esquema,
  cols.table_name AS tabla,
  cols.ordinal_position AS orden,
  cols.column_name AS campo,
  cols.data_type AS tipo,
  cols.is_nullable AS nulo,
  COALESCE(cols.column_default, '') AS default_val,
  COALESCE(pk_cols.pk_name, '') AS pk,
  COALESCE(uq_cols.unique_names, '') AS unique_val,
  COALESCE(fk_cols.fk_refs, '') AS foreign_keys,
  COALESCE(checks.check_defs, '') AS checks_tabla,
  COALESCE(cols.comment, '') AS comentario
FROM cols
LEFT JOIN pk_cols
  ON pk_cols.schema_name = cols.schema_name
 AND pk_cols.table_name = cols.table_name
 AND pk_cols.column_name = cols.column_name
LEFT JOIN uq_cols
  ON uq_cols.schema_name = cols.schema_name
 AND uq_cols.table_name = cols.table_name
 AND uq_cols.column_name = cols.column_name
LEFT JOIN fk_cols
  ON fk_cols.schema_name = cols.schema_name
 AND fk_cols.table_name = cols.table_name
 AND fk_cols.column_name = cols.column_name
LEFT JOIN checks
  ON checks.schema_name = cols.schema_name
 AND checks.table_name = cols.table_name
ORDER BY esquema, tabla, orden;