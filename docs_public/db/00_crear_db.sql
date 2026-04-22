-- Crea base de datos y usuario para PostgreSQL
-- Ajusta las contraseñas antes de ejecutar en producción

BEGIN;
  DO $$
  BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'CCENT_user') THEN
      CREATE ROLE CCENT_user LOGIN PASSWORD 'cambia_esta_contrasena';
    END IF;
  END
  $$;

  DO $$
  BEGIN
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'CCENT_db') THEN
      CREATE DATABASE CCENT_db OWNER CCENT_user;
    END IF;
  END
  $$;

  GRANT ALL PRIVILEGES ON DATABASE CCENT_db TO CCENT_user;
END;

-- Ejecuta en el servidor con una cuenta con permisos (por ejemplo, el superusuario de Postgres).
-- Cambia la contraseña por la definitiva antes de aplicar en prod.
