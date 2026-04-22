from django.db import IntegrityError
from rest_framework import viewsets, permissions, serializers

from apps.school.models import Alumno, Grupo, Inscripcion, Calificacion
from .serializers import (
    AlumnoSerializer,
    GrupoSerializer,
    InscripcionSerializer,
    CalificacionSerializer,
)


ROLE_DIRECTOR = "Director Escolar"
ROLE_ADMIN_COM = "Administrativo Comercial"
ROLE_ALUMNO = "Alumno"


def get_user_role(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return "Superusuario"
    groups = set(user.groups.values_list("name", flat=True))
    for role in (ROLE_DIRECTOR, ROLE_ADMIN_COM, ROLE_ALUMNO):
        if role in groups:
            return role
    return None


def alumno_from_user(user):
    """Best-effort: vincula por correo; si no existe retorna None."""
    if not user or not user.email:
        return None
    try:
        return Alumno.objects.filter(correo__iexact=user.email).first()
    except Exception:
        return None


class SchoolRolePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        role = get_user_role(request.user)
        if request.user.is_superuser or role == ROLE_DIRECTOR:
            return True
        if role == ROLE_ADMIN_COM:
            return request.method in permissions.SAFE_METHODS
        if role == ROLE_ALUMNO:
            return request.method in permissions.SAFE_METHODS
        return False

    def has_object_permission(self, request, view, obj):
        role = get_user_role(request.user)
        if request.user.is_superuser or role == ROLE_DIRECTOR:
            return True
        if role in (ROLE_ADMIN_COM, ROLE_ALUMNO):
            return request.method in permissions.SAFE_METHODS
        return False


class AlumnoViewSet(viewsets.ModelViewSet):
    queryset = Alumno.objects.all().order_by("matricula")
    serializer_class = AlumnoSerializer
    permission_classes = [SchoolRolePermission]


class GrupoViewSet(viewsets.ModelViewSet):
    queryset = Grupo.objects.all().order_by("-creado_en", "periodo_ref__codigo")
    serializer_class = GrupoSerializer
    permission_classes = [SchoolRolePermission]


class InscripcionViewSet(viewsets.ModelViewSet):
    queryset = Inscripcion.objects.select_related("alumno", "grupo").all()
    serializer_class = InscripcionSerializer
    permission_classes = [SchoolRolePermission]

    def get_queryset(self):
        qs = super().get_queryset()
        role = get_user_role(self.request.user)
        if role == ROLE_ALUMNO:
            alumno = alumno_from_user(self.request.user)
            return qs.filter(alumno=alumno) if alumno else qs.none()
        if role == ROLE_ADMIN_COM:
            return qs
        if role == ROLE_DIRECTOR or self.request.user.is_superuser:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise serializers.ValidationError(
                {"non_field_errors": ["El alumno ya está inscrito en este grupo."]})


class CalificacionViewSet(viewsets.ModelViewSet):
    queryset = Calificacion.objects.select_related(
        "inscripcion", "inscripcion__alumno", "inscripcion__grupo").all()
    serializer_class = CalificacionSerializer
    permission_classes = [SchoolRolePermission]

    def get_queryset(self):
        qs = super().get_queryset()
        role = get_user_role(self.request.user)
        if role == ROLE_ALUMNO:
            alumno = alumno_from_user(self.request.user)
            return qs.filter(inscripcion__alumno=alumno) if alumno else qs.none()
        if role == ROLE_ADMIN_COM:
            return qs
        if role == ROLE_DIRECTOR or self.request.user.is_superuser:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise serializers.ValidationError(
                {"inscripcion": ["Esta inscripción ya tiene calificación registrada."]})
