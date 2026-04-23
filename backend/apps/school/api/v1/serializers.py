from rest_framework import serializers

from apps.school.models import Alumno, Grupo, Inscripcion, Calificacion


class AlumnoSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.ReadOnlyField()

    class Meta:
        model = Alumno
        fields = ("id_alumno", "matricula", "nombres", "apellido_paterno",
                  "apellido_materno", "nombre_completo", "correo", "telefono")
        read_only_fields = ("id_alumno", "matricula")


class GrupoSerializer(serializers.ModelSerializer):
    periodo = serializers.CharField(read_only=True)
    curso_slug = serializers.CharField(read_only=True)

    class Meta:
        model = Grupo
        fields = [
            "id",
            "curso_ref",
            "periodo_ref",
            "curso_slug",
            "periodo",
            "tipo_horario",
            "turno",
            "cupo",
            "estado",
            "creado_en",
        ]
        read_only_fields = ["id", "creado_en"]


class InscripcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Inscripcion
        fields = ["id", "alumno", "grupo", "fecha_inscripcion", "estado"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        alumno = attrs.get("alumno") or getattr(self.instance, "alumno", None)
        grupo = attrs.get("grupo") or getattr(self.instance, "grupo", None)
        if alumno and grupo:
            qs = Inscripcion.objects.filter(alumno=alumno, grupo=grupo)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            # Valida duplicidad a nivel de serialización antes de que la restricción de
            # BD lo rechace, permitiendo retornar un error 400 con mensaje legible.
            if qs.exists():
                raise serializers.ValidationError(
                    {"non_field_errors": ["El alumno ya está inscrito en este grupo."]})
        return attrs


class CalificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calificacion
        fields = ["id", "inscripcion", "valor", "capturado_en"]
        read_only_fields = ["id", "capturado_en"]

    def validate(self, attrs):
        inscripcion = attrs.get("inscripcion") or getattr(
            self.instance, "inscripcion", None)
        if inscripcion:
            qs = Calificacion.objects.filter(inscripcion=inscripcion)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            # Impide registrar una segunda calificación para la misma inscripción desde
            # la API, complementando la restricción OneToOne del modelo.
            if qs.exists():
                raise serializers.ValidationError(
                    {"inscripcion": ["Esta inscripción ya tiene calificación registrada."]})
        return attrs
