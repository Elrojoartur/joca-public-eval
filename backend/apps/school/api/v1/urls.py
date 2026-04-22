from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AlumnoViewSet, GrupoViewSet, InscripcionViewSet, CalificacionViewSet


router = DefaultRouter()
router.register(r"alumnos", AlumnoViewSet, basename="alumnos")
router.register(r"grupos", GrupoViewSet, basename="grupos")
router.register(r"inscripciones", InscripcionViewSet, basename="inscripciones")
router.register(r"calificaciones", CalificacionViewSet,
                basename="calificaciones")

urlpatterns = [
    path("", include(router.urls)),
]
