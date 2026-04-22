from django.urls import path

from . import views
from .views import curso_detalle, historias, portal_home, portal_mision_vision


app_name = "public_portal"

urlpatterns = [
    path("", portal_home, name="portal-home"),
    path("mision-vision/", portal_mision_vision, name="mision-vision"),
    path("historias/", historias, name="historias"),
    path("cursos/<slug:slug>/", curso_detalle, name="curso-detalle"),
    path("grupos/", views.portal_grupos, name="portal-grupos"),
    path("avisos/", views.portal_avisos, name="portal-avisos"),
    path("faqs/", views.portal_faqs, name="portal-faqs"),
    path("contacto/", views.portal_contacto, name="portal-contacto"),
]
