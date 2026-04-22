from django.db import migrations


FORWARD_SQL = """
DO $$
BEGIN
    -- 1) Normaliza el tipo de alumno_id para que coincida con school_alumno.id_alumno (integer)
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'school_inscripcion'
          AND column_name = 'alumno_id'
          AND data_type <> 'integer'
    ) THEN
        ALTER TABLE public.school_inscripcion
            ALTER COLUMN alumno_id TYPE integer USING alumno_id::integer;
    END IF;

    -- 2) Crea FK fisica si no existe
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'school_inscripcion_alumno_id_fk_school_alumno_id_alumno'
    ) THEN
        ALTER TABLE ONLY public.school_inscripcion
            ADD CONSTRAINT school_inscripcion_alumno_id_fk_school_alumno_id_alumno
            FOREIGN KEY (alumno_id)
            REFERENCES public.school_alumno(id_alumno)
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;
"""


REVERSE_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'school_inscripcion_alumno_id_fk_school_alumno_id_alumno'
    ) THEN
        ALTER TABLE ONLY public.school_inscripcion
            DROP CONSTRAINT school_inscripcion_alumno_id_fk_school_alumno_id_alumno;
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0015_normalize_grupo_acta_3fn"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
