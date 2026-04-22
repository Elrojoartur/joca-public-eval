# apps/ui/views_registro.py
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from apps.school.models import Alumno
from apps.accounts.models import Rol, UsuarioRol
from apps.ui.input_validation import (
    validate_email_value,
    validate_matricula_value,
    validate_password_strength,
)


@require_http_methods(["GET", "POST"])
def registro_alumno(request):
    if request.user.is_authenticated:
        return redirect("/panel/")

    if request.method == "POST":
        matricula = (request.POST.get("matricula") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        password2 = request.POST.get("password2") or ""

        try:
            matricula = validate_matricula_value(matricula)
            email = validate_email_value(email, "Correo")
        except Exception as exc:
            messages.error(request, str(exc))
            return render(request, "ui/registro_alumno.html")

        if not matricula or not email or not password:
            messages.error(request, "Completa matrícula, correo y contraseña.")
            return render(request, "ui/registro_alumno.html")

        if password != password2:
            messages.error(request, "Las contraseñas no coinciden.")
            return render(request, "ui/registro_alumno.html")

        try:
            validate_password_strength(password, min_length=8)
        except Exception as exc:
            messages.error(request, str(exc))
            return render(request, "ui/registro_alumno.html")

        # ✅ Validación REAL: solo deja registrarse si la matrícula ya existe en Alumno
        alumno = Alumno.objects.filter(matricula=matricula).first()
        if not alumno:
            messages.error(
                request, "Matrícula no encontrada. Solicita alta al administrador escolar.")
            return render(request, "ui/registro_alumno.html")

        U = get_user_model()
        username_field = getattr(U, "USERNAME_FIELD", "username")

        # Usamos matrícula como username (si tu USERNAME_FIELD es username)
        lookup_value = matricula if username_field != "email" else email

        if U.objects.filter(**{username_field: lookup_value}).exists():
            messages.error(
                request, "Esa cuenta ya existe. Intenta iniciar sesión.")
            return redirect("/acceso/")

        user_kwargs = {username_field: lookup_value, "email": email}
        user = U.objects.create_user(**user_kwargs, password=password)

        # ✅ Asignar rol ALUMNO (o por nombre si tu código difiere)
        rol = Rol.objects.filter(codigo="ALUMNO").first(
        ) or Rol.objects.filter(nombres__icontains="Alumno").first()
        if rol:
            UsuarioRol.objects.update_or_create(
                usuario=user, defaults={"rol": rol})

        # ✅ Si Alumno tiene FK a usuario, lo guardamos (si existe el campo)
        if hasattr(alumno, "usuario_id"):
            alumno.usuario = user
            alumno.save(update_fields=["usuario"])

        login(request, user)
        return redirect("/panel/alumno/")

    return render(request, "ui/registro_alumno.html")
