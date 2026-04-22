import json
import logging
from datetime import datetime
from functools import wraps, lru_cache
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.accounts.models import UsuarioRol
from apps.governance.models import EventoAuditoria, RolPermiso
from apps.governance.services.audit import log_event
from apps.ui.catalogs.cursos import load_cursos

import json
import logging
from datetime import datetime
from functools import wraps, lru_cache
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.accounts.models import UsuarioRol
from apps.governance.models import EventoAuditoria, RolPermiso
from apps.ui.catalogs.cursos import load_cursos


ROLE_BY_CODE = {
    "SUPERUSUARIO": "Superusuario",
    "DIRECTOR_ESCOLAR": "Director Escolar",
    "ADMINISTRATIVO_COMERCIAL": "Administrativo Comercial",
    "ALUMNO": "Alumno",
}

GROUPS_UI = []


def get_user_role(user) -> str:

    if not user.is_authenticated:
        return "Invitado"
    if user.is_superuser:
        return "Superusuario"

    ur = UsuarioRol.objects.select_related("rol").filter(usuario=user).first()
    if not ur or not ur.rol:
        return "Usuario"

    codigo = getattr(ur.rol, "codigo", None)
    if codigo:
        return ROLE_BY_CODE.get(codigo, ur.rol.nombre or "Usuario")

    return ur.rol.nombre or "Usuario"


def _is_director(user) -> bool:
    return get_user_role(user) in {"Superusuario", "Director Escolar"}


def role_required(*allowed_roles):
    """Permite acceso solo a roles indicados (Superusuario siempre pasa)."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            role = get_user_role(request.user)
            if role == "Superusuario" or role in allowed_roles:
                return view_func(request, *args, **kwargs)
            return render(
                request,
                "ui/forbidden.html",
                {"role": role, "allowed": ", ".join(allowed_roles)},
                status=403,
            )
        return _wrapped
    return decorator


@lru_cache(maxsize=1)
def load_cursos_catalog():
    """Carga el catálogo de cursos desde JSON con cache simple."""
    try:
        return load_cursos()
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def get_cursos_catalog_list():
    data = load_cursos_catalog()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())
    return []


def build_group_catalog():
    catalog = get_cursos_catalog_list()
    catalog_len = len(catalog)
    grupos = []
    for idx, g in enumerate(GROUPS_UI):
        course = catalog[idx % catalog_len] if catalog_len else {}
        grupos.append({
            **g,
            "titulo": course.get("nombres", f"Grupo {g['grupo']}"),
            "descripcion": course.get("descripcion", "Descripción en preparación."),
            "imagen": course.get("imagen", "ui/brand/logo.svg"),
            "curso": course or None,
        })
    return grupos


def home(request):
    # Portal público como landing
    return redirect("/portal/")


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or ""


def registrar_auditoria(request, accion, entidad, entidad_id=None, resultado="ok", detalle=None):
    log_event(
        request,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        resultado=resultado,
        detalle=detalle,
    )


@login_required(login_url="/acceso/")
def panel(request):
    role = get_user_role(request.user)

    # Permisos NAV_* por rol (RolPermiso)
    nav = set()

    if request.user.is_superuser:
        # Superusuario ve todo aun si falta configuración
        nav = {"NAV_ESCOLAR", "NAV_VENTAS",
               "NAV_REPORTES", "NAV_GOBIERNO", "NAV_ALUMNO"}
    else:
        ur = UsuarioRol.objects.select_related(
            "rol").filter(usuario=request.user).first()
        if ur and ur.rol:
            nav = set(
                RolPermiso.objects.filter(rol=ur.rol)
                .values_list("permiso__codigo", flat=True)
            )

    cards = []

    if "NAV_ESCOLAR" in nav:
        cards.append(
            {"title": "Escolar", "desc": "Alumnos, grupos, inscripciones y calificaciones.", "href": "/panel/escolar/"})
    if "NAV_VENTAS" in nav:
        cards.append(
            {"title": "Ventas", "desc": "Catálogo, órdenes, pagos y tickets.", "href": "/panel/ventas/"})
    if "NAV_REPORTES" in nav:
        cards.append(
            {"title": "Reportes", "desc": "Reportes académicos y comerciales.", "href": "/panel/reportes/"})
    if "NAV_GOBIERNO" in nav:
        cards.append(
            {"title": "Gobierno", "desc": "Parámetros, seguridad y auditoría.", "href": "/panel/gobierno/"})
    if "NAV_ALUMNO" in nav:
        cards.append(
            {"title": "Alumno", "desc": "Vista de alumno.", "href": "/panel/alumno/"})

    if not cards:
        cards = [{"title": "Mi panel",
                  "desc": "Acceso general.", "href": "/panel/"}]

    return render(request, "ui/panel.html", {"role": role, "cards": cards})
