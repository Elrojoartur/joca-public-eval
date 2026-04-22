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
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .views_core import role_required, get_user_role, build_group_catalog
from apps.ui.input_validation import validate_human_name


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Administrativo Comercial")
def ventas(request):
    return render(
        request,
        "ui/stub.html",
        {"title": "Ventas",
            "msg": "Aquí vivirán Catálogo de servicios, registro de ventas y comprobantes."},
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar", "Administrativo Comercial")
def reportes(request):
    return render(
        request,
        "ui/stub.html",
        {"title": "Tableros y reportes",
            "msg": "Aquí vivirán Tablero ejecutivo, Reportes académicos y Reportes comerciales."},
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar")
def gobierno(request):
    return render(
        request,
        "ui/stub.html",
        {"title": "Configuración y gobierno",
            "msg": "Aquí vivirán Parámetros, Seguridad, Respaldos/Auditoría y Catálogos maestros."},
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Alumno")
def alumno(request):
    return render(
        request,
        "ui/stub.html",
        {"title": "Portal del alumno",
            "msg": "Aquí vivirán Mis calificaciones, Mis inscripciones, Mis pagos y Mi horario."},
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar", "Administrativo Comercial", "Alumno")
def inscripciones(request):
    role = get_user_role(request.user)
    grupos = build_group_catalog()
    periodos = sorted({g["periodo"] for g in grupos})

    return render(
        request,
        "ui/inscripciones.html",
        {
            "role": role,
            "periodos": periodos,
            "grupos": grupos,
        },
    )


@login_required(login_url="/acceso/")
@role_required("Superusuario", "Director Escolar", "Administrativo Comercial", "Alumno")
def nueva_inscripcion(request):
    role = get_user_role(request.user)
    grupos = build_group_catalog()

    selected_id = request.GET.get("id_grupo") or request.POST.get("grupo")
    grupos_by_id = {g["id"]: g for g in grupos}
    selected_group = grupos_by_id.get(selected_id)

    if request.method == "POST":
        alumno = request.POST.get("alumno") or ""
        grupo_id = request.POST.get("grupo") or request.GET.get("id_grupo")
        grupo = grupos_by_id.get(grupo_id)

        try:
            alumno = validate_human_name(alumno, "Alumno")
        except Exception as exc:
            messages.error(request, str(exc))
            alumno = ""

        if not alumno.strip():
            messages.error(request, "Indica el alumno antes de continuar.")
        elif not grupo:
            messages.error(request, "Selecciona un grupo válido.")
        elif grupo.get("disponibles", 0) <= 0:
            messages.error(
                request, "Este grupo ya no tiene cupo. Elige otro grupo disponible.")
        else:
            messages.success(
                request,
                f"Inscripción registrada (demo) para {alumno.strip()} en Grupo {grupo['grupo']} ({grupo['periodo']}).",
            )
            return redirect(f"/panel/inscripciones/nueva/?id_grupo={grupo_id}")

        selected_group = grupo

    return render(
        request,
        "ui/nueva_inscripcion.html",
        {
            "role": role,
            "grupos": grupos,
            "selected_group": selected_group,
            "selected_id": selected_id,
        },
    )
