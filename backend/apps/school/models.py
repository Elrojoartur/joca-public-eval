from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import date
import calendar

from apps.school.validators import validate_curp, validate_rfc_mexico, validate_codigo_postal


class Alumno(models.Model):
    id_alumno = models.AutoField(primary_key=True)
    matricula = models.CharField(max_length=32, unique=True, db_index=True)

    nombres = models.CharField(max_length=120)
    apellido_paterno = models.CharField(max_length=80)
    apellido_materno = models.CharField(max_length=80, blank=True, default="")

    correo = models.EmailField(unique=True, db_index=True)
    telefono = models.CharField(max_length=32, blank=True)
    curp = models.CharField(
        max_length=18,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        validators=[validate_curp],
    )
    rfc = models.CharField(
        max_length=13,
        null=True,
        blank=True,
        validators=[validate_rfc_mexico],
    )

    class Meta:
        verbose_name = "Alumno"
        verbose_name_plural = "Alumnos"
        ordering = ["matricula"]

    @property
    def nombre_completo(self):
        partes = [self.nombres, self.apellido_paterno, self.apellido_materno]
        return " ".join([p for p in partes if p]).strip()

    # Alias temporal para no romper referencias antiguas: alumno.nombres
    @property
    def nombre(self):
        return self.nombre_completo

    def save(self, *args, **kwargs):
        # La matrícula se genera automáticamente solo en la creación; si ya existe no
        # se sobreescribe, preservando el identificador institucional del alumno.
        if not self.pk and not self.matricula:
            from apps.school.services.matricula import generate_matricula
            self.matricula = generate_matricula()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.matricula} - {self.nombre_completo}"


class AlumnoDomicilio(models.Model):
    """Domicilio complementario del alumno (relación 1:1 con Alumno)."""

    alumno = models.OneToOneField(
        "Alumno",
        on_delete=models.RESTRICT,
        related_name="domicilio",
        verbose_name="alumno",
    )
    calle = models.CharField(
        max_length=150, blank=True, default="", verbose_name="calle"
    )
    numero = models.CharField(
        max_length=20, blank=True, default="", verbose_name="número"
    )
    colonia = models.CharField(
        max_length=120, blank=True, default="", verbose_name="colonia"
    )
    codigo_postal = models.CharField(
        max_length=5,
        blank=True,
        default="",
        verbose_name="código postal",
        validators=[validate_codigo_postal],
    )
    estado = models.CharField(
        max_length=120, blank=True, default="", verbose_name="estado"
    )
    pais = models.CharField(
        max_length=120, blank=True, default="México", verbose_name="país"
    )
    actualizado_en = models.DateTimeField(
        auto_now=True, verbose_name="actualizado en"
    )

    class Meta:
        verbose_name = "Domicilio de alumno"
        verbose_name_plural = "Domicilios de alumnos"

    def __str__(self):
        partes = [self.calle, self.numero, self.colonia, self.codigo_postal]
        resumen = ", ".join(p for p in partes if p) or "sin dirección"
        return f"Domicilio de {self.alumno.matricula}: {resumen}"


class Periodo(models.Model):
    codigo = models.CharField(max_length=30, unique=True)  # ej. 2026-01
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Periodo"
        verbose_name_plural = "Periodos"
        ordering = ["-fecha_inicio", "codigo"]

    @staticmethod
    def defaults_for(codigo: str):
        year, month = codigo.split("-", 1)
        year_i = int(year)
        month_i = int(month)
        _, last_day = calendar.monthrange(year_i, month_i)
        return {
            "fecha_inicio": date(year_i, month_i, 1),
            "fecha_fin": date(year_i, month_i, last_day),
            "activo": True,
        }

    def __str__(self):
        return self.codigo


class Curso(models.Model):
    codigo = models.CharField(max_length=40, unique=True)  # ej. ELEC-BAS
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True, default="")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Aula(models.Model):
    clave = models.CharField(max_length=20, unique=True)   # AULA-1
    nombre = models.CharField(max_length=80)              # Aula 1
    capacidad = models.PositiveIntegerField(default=0)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Aula"
        verbose_name_plural = "Aulas"
        ordering = ["clave"]

    def __str__(self):
        return self.nombre


class Docente(models.Model):
    # nombre atómico (regla del comité)
    nombres = models.CharField(max_length=120)
    apellido_paterno = models.CharField(max_length=80)
    apellido_materno = models.CharField(max_length=80, default="NO CAPTURADO")
    correo = models.EmailField(unique=True)
    telefono = models.CharField(max_length=32, blank=True, default="")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Docente"
        verbose_name_plural = "Docentes"
        ordering = ["apellido_paterno", "apellido_materno", "nombres"]

    @property
    def nombre_completo(self):
        partes = [self.nombres, self.apellido_paterno, self.apellido_materno]
        return " ".join([p for p in partes if p]).strip()

    def __str__(self):
        return self.nombre_completo


class Grupo(models.Model):
    HORARIO_SAB = "SAB"
    HORARIO_SEM = "SEM"
    HORARIO_CHOICES = [
        (HORARIO_SAB, "Sabatino"),
        (HORARIO_SEM, "Entre semana"),
    ]

    TURNO_AM = "AM"
    TURNO_PM = "PM"
    TURNO_SAB = "SAB"
    TURNO_CHOICES = [
        (TURNO_AM, "Matutino"),
        (TURNO_PM, "Vespertino"),
        (TURNO_SAB, "Sabatino"),
    ]

    ESTADO_INACTIVO = 0
    ESTADO_ACTIVO = 1
    ESTADO_CHOICES = (
        (ESTADO_INACTIVO, "Inactivo"),
        (ESTADO_ACTIVO, "Activo"),
    )

    # ====== Normalización 3FN ======
    curso_ref = models.ForeignKey(
        "school.Curso",
        on_delete=models.PROTECT,
        related_name="grupos",
    )
    periodo_ref = models.ForeignKey(
        "school.Periodo",
        on_delete=models.PROTECT,
        related_name="grupos",
    )

    # ====== Operación del grupo ======
    tipo_horario = models.CharField(max_length=3, choices=HORARIO_CHOICES)
    turno = models.CharField(
        max_length=3,
        choices=TURNO_CHOICES,
        default=TURNO_PM,
        db_index=True,
    )
    cupo = models.PositiveIntegerField()
    estado = models.SmallIntegerField(
        choices=ESTADO_CHOICES,
        default=ESTADO_ACTIVO,
        db_index=True,
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Grupo"
        verbose_name_plural = "Grupos"
        ordering = ["-creado_en", "periodo_ref__codigo", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["curso_ref", "periodo_ref", "tipo_horario", "turno"],
                name="uq_grupo_cursoref_periodoref_tipo_turno",
            ),
            models.CheckConstraint(
                check=(
                    (models.Q(tipo_horario="SAB") & models.Q(turno="SAB"))
                    |
                    (models.Q(tipo_horario="SEM") &
                     models.Q(turno__in=["AM", "PM"]))
                ),
                name="ck_grupo_tipo_turno_consistente",
            ),
        ]

    def __init__(self, *args, **kwargs):
        self._legacy_curso_slug = (kwargs.pop("curso_slug", "") or "").strip()
        self._legacy_periodo = (kwargs.pop("periodo", "") or "").strip()
        super().__init__(*args, **kwargs)

    @property
    def curso_slug(self):
        if self.curso_ref_id and self.curso_ref:
            return self.curso_ref.codigo
        return self._legacy_curso_slug

    @curso_slug.setter
    def curso_slug(self, value):
        self._legacy_curso_slug = (value or "").strip()

    @property
    def periodo(self):
        if self.periodo_ref_id and self.periodo_ref:
            return self.periodo_ref.codigo
        return self._legacy_periodo

    @periodo.setter
    def periodo(self, value):
        self._legacy_periodo = (value or "").strip()

    @staticmethod
    def _ensure_periodo(periodo_codigo: str):
        if not periodo_codigo:
            return None
        return Periodo.objects.get_or_create(
            codigo=periodo_codigo,
            defaults=Periodo.defaults_for(periodo_codigo),
        )[0]

    @staticmethod
    def _ensure_curso(curso_codigo: str):
        if not curso_codigo:
            return None
        return Curso.objects.get_or_create(
            codigo=curso_codigo,
            defaults={
                "nombre": curso_codigo.replace("-", " ").strip()[:120] or curso_codigo,
                "activo": True,
            },
        )[0]

    def save(self, *args, **kwargs):
        if not self.curso_ref_id:
            self.curso_ref = self._ensure_curso(self._legacy_curso_slug)
        if not self.periodo_ref_id:
            self.periodo_ref = self._ensure_periodo(self._legacy_periodo)

        if self.tipo_horario == self.HORARIO_SAB:
            self.turno = self.TURNO_SAB
        elif self.turno not in {self.TURNO_AM, self.TURNO_PM}:
            self.turno = self.TURNO_PM

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Grupo {self.periodo}-{self.id} ({self.turno})"


class GrupoHorario(models.Model):
    """
    Horario normalizado de un Grupo.
    Reemplaza: dias/hora_inicio/hora_fin que antes vivían en Grupo.
    """
    DIAS = [
        ("LUN", "Lunes"),
        ("MAR", "Martes"),
        ("MIE", "Miércoles"),
        ("JUE", "Jueves"),
        ("VIE", "Viernes"),
        ("SAB", "Sábado"),
        ("DOM", "Domingo"),
    ]

    grupo = models.ForeignKey(
        "Grupo", on_delete=models.CASCADE, related_name="horarios")
    dia = models.CharField(max_length=3, choices=DIAS, db_index=True)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    # Aula opcional por ahora (para que no reviente si aún no se asigna)
    aula_ref = models.ForeignKey(
        "Aula",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="horarios",
    )

    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(hora_fin__gt=models.F("hora_inicio")),
                name="ck_grupohorario_fin_mayor_inicio",
            ),
            models.UniqueConstraint(
                fields=["grupo", "dia", "hora_inicio", "hora_fin"],
                name="uq_grupohorario_grupo_dia_rango",
            ),
        ]
        ordering = ["grupo_id", "dia", "hora_inicio"]

    def __str__(self):
        return f"{self.grupo_id} {self.dia} {self.hora_inicio}-{self.hora_fin}"


class DocenteGrupo(models.Model):
    """
    Relación Docente <-> Grupo (muchos a muchos) con metadatos.
    """
    ROLES = [
        ("TIT", "Titular"),
        ("AUX", "Auxiliar"),
    ]

    docente = models.ForeignKey(
        "Docente", on_delete=models.CASCADE, related_name="asignaciones")
    grupo = models.ForeignKey(
        "Grupo", on_delete=models.CASCADE, related_name="asignaciones_docentes")
    rol = models.CharField(max_length=3, choices=ROLES, default="TIT")

    activo = models.BooleanField(default=True)
    asignado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["docente", "grupo"],
                name="uq_docente_grupo",
            )
        ]
        ordering = ["-asignado_en"]

    def __str__(self):
        return f"{self.docente_id} -> {self.grupo_id} ({self.rol})"


class Inscripcion(models.Model):
    ESTADO_ACTIVA = "activa"
    ESTADO_BAJA = "baja"
    ESTADO_FINALIZADA = "finalizada"
    ESTADO_CHOICES = (
        (ESTADO_ACTIVA, "Activa"),
        (ESTADO_BAJA, "Baja"),
        (ESTADO_FINALIZADA, "Finalizada"),
    )

    alumno = models.ForeignKey(
        Alumno,
        related_name="inscripciones",
        on_delete=models.CASCADE,
        db_index=True,
    )
    grupo = models.ForeignKey(
        Grupo,
        related_name="inscripciones",
        on_delete=models.CASCADE,
        db_index=True,
    )
    fecha_inscripcion = models.DateField(default=timezone.now)
    estado = models.CharField(
        max_length=16,
        choices=ESTADO_CHOICES,
        default=ESTADO_ACTIVA,
        db_index=True,
    )

    class Meta:
        verbose_name = "Inscripcion"
        verbose_name_plural = "Inscripciones"
        ordering = ["-fecha_inscripcion", "alumno__matricula"]
        constraints = [
            models.UniqueConstraint(
                fields=["alumno", "grupo"],
                name="uq_inscripcion_alumno_grupo",
            ),
        ]
        indexes = [
            models.Index(fields=["alumno", "estado"],
                         name="idx_insc_alumno_estado"),
            models.Index(fields=["grupo", "estado"],
                         name="idx_insc_grupo_estado"),
        ]

    def __str__(self):
        return f"Inscripcion {self.alumno_id} -> {self.grupo_id}"

    # La restricción uq_inscripcion_alumno_grupo a nivel de BD es la última línea
    # de defensa contra duplicados; la validación en serializers/servicios debe
    # anticiparse antes de llegar aquí para ofrecer un mensaje de error amigable.
    # TODO: validar cupo disponible y grupo activo antes de crear (servicio/domino).


# Relación 1:1 con Inscripcion: cada inscripción tiene como máximo una
# calificación, lo que garantiza trazabilidad académica unívoca.
class Calificacion(models.Model):
    inscripcion = models.OneToOneField(
        Inscripcion,
        related_name="calificacion",
        on_delete=models.CASCADE,
    )
    valor = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    capturado_en = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Calificacion"
        verbose_name_plural = "Calificaciones"
        ordering = ["-capturado_en"]
        indexes = [models.Index(fields=["valor"], name="idx_calif_valor")]
        constraints = [
            models.UniqueConstraint(
                fields=["inscripcion"], name="uq_calificacion_inscripcion"
            )
        ]

    def __str__(self):
        return f"Calificacion {self.inscripcion_id}"


class ActaCierre(models.Model):
    grupo = models.ForeignKey(
        Grupo,
        related_name="actas_cierre",
        on_delete=models.CASCADE,
    )
    cerrada_en = models.DateTimeField(default=timezone.now, db_index=True)
    cerrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    motivo = models.TextField(blank=True)

    class Meta:
        verbose_name = "Acta de cierre"
        verbose_name_plural = "Actas de cierre"
        ordering = ["-cerrada_en"]
        constraints = [
            # La unicidad sobre grupo impide registrar más de un acta de cierre por grupo,
            # protegiendo la inmutabilidad del historial académico del período.
            models.UniqueConstraint(
                fields=["grupo"],
                name="uq_actacierre_grupo",
            )
        ]

    @property
    def periodo(self):
        if self.grupo_id and getattr(self.grupo, "periodo_ref_id", None):
            return self.grupo.periodo_ref.codigo
        return ""

    @periodo.setter
    def periodo(self, value):
        # Compatibilidad: se acepta el valor legacy sin persistir columna.
        self._legacy_periodo = (value or "").strip()

    def __str__(self):
        return f"Acta cierre grupo {self.grupo_id} ({self.periodo})"

    @classmethod
    def existe_para(cls, grupo, periodo: str) -> bool:
        if not grupo or not periodo:
            return False
        if (grupo.periodo or "") != periodo:
            return False
        return cls.objects.filter(grupo=grupo).exists()


# --- 3FN Catalogos (lectura/escritura directa a PostgreSQL schemas) ---
class CatPais(models.Model):
    id_pais = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=120, unique=True)

    class Meta:
        managed = False
        db_table = 'catalogos"."cat_pais'  # genera "catalogos"."cat_pais"

    def __str__(self):
        return self.nombre


class CatEstado(models.Model):
    id_estado = models.BigAutoField(primary_key=True)
    pais = models.ForeignKey(
        CatPais, on_delete=models.DO_NOTHING, db_column="id_pais", related_name="estados")
    nombre = models.CharField(max_length=120)

    class Meta:
        managed = False
        db_table = 'catalogos"."cat_estado'
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "nombre"], name="uq_estado_pais_nombre_3fn")
        ]

    def __str__(self):
        return self.nombre
