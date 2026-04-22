from django.contrib import admin
from .models import (
    Alumno,
    Grupo,
    Inscripcion,
    ActaCierre,
    Calificacion,
    Aula,
    Curso,
    Docente,
    Periodo,
    GrupoHorario,
    DocenteGrupo,
)


@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ("matricula", "get_nombre_completo", "correo", "telefono")
    search_fields = ("matricula", "nombres", "apellido_paterno",
                     "apellido_materno", "correo")
    ordering = ("matricula",)

    @admin.display(description="Nombre completo")
    def get_nombre_completo(self, obj):
        return f"{obj.nombres} {obj.apellido_paterno} {obj.apellido_materno}".strip()


@admin.register(Grupo)
class GrupoAdmin(admin.ModelAdmin):
    list_display = ("id", "curso_slug", "periodo",
                    "tipo_horario", "turno", "cupo", "estado", "creado_en")
    search_fields = ("curso_ref__codigo", "periodo_ref__codigo")
    list_filter = ("periodo_ref", "tipo_horario", "turno", "estado")
    ordering = ("-creado_en",)


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ("id", "alumno", "grupo", "fecha_inscripcion", "estado")
    # Evita campos no garantizados como alumno__nombre (depende de tu modelo Alumno)
    search_fields = ("alumno__matricula", "alumno__correo",
                     "grupo__curso_ref__codigo", "grupo__periodo_ref__codigo")
    list_filter = ("estado", "grupo__periodo_ref", "grupo__tipo_horario")
    ordering = ("-fecha_inscripcion",)


@admin.register(Calificacion)
class CalificacionAdmin(admin.ModelAdmin):
    list_display = ("id", "inscripcion", "valor", "capturado_en")
    search_fields = ("inscripcion__alumno__matricula",
                     "inscripcion__alumno__correo")
    list_filter = ("capturado_en",)
    ordering = ("-capturado_en",)


@admin.register(ActaCierre)
class ActaCierreAdmin(admin.ModelAdmin):
    list_display = ("id", "grupo", "periodo",
                    "cerrada_en", "cerrada_por", "motivo")
    search_fields = ("grupo__curso_ref__codigo",
                     "grupo__periodo_ref__codigo", "cerrada_por")
    list_filter = ("cerrada_en",)
    ordering = ("-cerrada_en",)


@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    # Aula sí la dejaste clara, pero por seguridad no asumimos nombre/capacidad si cambian:
    list_display = ("id", "etiqueta")
    search_fields = ()
    ordering = ("id",)

    @admin.display(description="Aula")
    def etiqueta(self, obj):
        return str(obj)


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    # ✅ No inventa campos: muestra lo que __str__ devuelva
    list_display = ("id", "etiqueta")
    search_fields = ()
    ordering = ("id",)

    @admin.display(description="Curso")
    def etiqueta(self, obj):
        return str(obj)


@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):
    # ✅ No inventa campos
    list_display = ("id", "etiqueta")
    search_fields = ()
    ordering = ("id",)

    @admin.display(description="Periodo")
    def etiqueta(self, obj):
        return str(obj)


@admin.register(Docente)
class DocenteAdmin(admin.ModelAdmin):
    # ✅ No inventa campos
    list_display = ("id", "etiqueta")
    search_fields = ()
    ordering = ("id",)

    @admin.display(description="Docente")
    def etiqueta(self, obj):
        return str(obj)


@admin.register(GrupoHorario)
class GrupoHorarioAdmin(admin.ModelAdmin):
    list_display = ("id", "grupo", "dia", "hora_inicio",
                    "hora_fin", "aula_ref", "activo")
    list_filter = ("dia", "activo")
    search_fields = ("grupo__curso_ref__codigo", "grupo__periodo_ref__codigo")
    ordering = ("grupo_id", "dia", "hora_inicio")


@admin.register(DocenteGrupo)
class DocenteGrupoAdmin(admin.ModelAdmin):
    list_display = ("id", "docente", "grupo", "rol", "activo", "asignado_en")
    list_filter = ("rol", "activo")
    search_fields = ("grupo__curso_ref__codigo", "grupo__periodo_ref__codigo")
    ordering = ("-asignado_en",)
