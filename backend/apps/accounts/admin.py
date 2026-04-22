import logging
from typing import Dict

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.sessions.models import Session
from django.utils import timezone

from apps.accounts.forms import UsuarioChangeForm, UsuarioCreateForm
from apps.accounts.models import Rol, UsuarioRol
from apps.governance.models import EventoAuditoria, Permiso, RolPermiso

logger = logging.getLogger("bitacora")
User = get_user_model()

# Asegura registrar nuestro UserAdmin personalizado
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or ""


def log_event(request, accion: str, entidad: str, entidad_id: str, resultado: str, detalle: Dict):
    actor = request.user if request and request.user.is_authenticated else None
    ip = get_client_ip(request) if request else ""
    try:
        EventoAuditoria.objects.create(
            actor=actor,
            ip=ip,
            accion=accion,
            entidad=entidad,
            entidad_id=str(entidad_id) if entidad_id is not None else None,
            resultado=resultado,
            detalle=detalle,
        )
    except Exception:  # pragma: no cover - fallback
        logger.info("[AUDIT][%s] %s", accion, detalle)


def revoke_sessions(user):
    now = timezone.now()
    for session in Session.objects.filter(expire_date__gte=now):
        data = session.get_decoded()
        if data.get("_auth_user_id") == str(user.pk):
            session.delete()


class UsuarioRolInline(admin.TabularInline):
    model = UsuarioRol
    extra = 0


class UserActionForm(admin.helpers.ActionForm):
    motivo = forms.CharField(required=False, label="Motivo")


class RolPermisosForm(forms.ModelForm):
    permisos = forms.ModelMultipleChoiceField(
        queryset=Permiso.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Permisos",
    )

    class Meta:
        model = Rol
        fields = ["nombre", "codigo", "activo", "permisos"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            actuales = Permiso.objects.filter(rolpermiso__rol=self.instance)
            self.fields["permisos"].initial = actuales

    def save(self, commit=True):
        rol = super().save(commit)
        if rol.pk:
            nuevos = set(self.cleaned_data.get("permisos") or [])
            previos = set(Permiso.objects.filter(rolpermiso__rol=rol))

            # Elimina los que ya no están
            RolPermiso.objects.filter(rol=rol).exclude(
                permiso__in=nuevos).delete()

            # Agrega los nuevos
            faltantes = nuevos - previos
            RolPermiso.objects.bulk_create(
                [RolPermiso(rol=rol, permiso=p) for p in faltantes]
            )

            self._perm_diff = {
                "antes": [p.codigo for p in previos],
                "despues": [p.codigo for p in nuevos],
            }
        return rol


@admin.register(User)
class UsuarioAdmin(UserAdmin):
    add_form = UsuarioCreateForm
    form = UsuarioChangeForm
    inlines = [UsuarioRolInline]
    list_display = ("username", "email", "is_active",
                    "is_staff", "date_joined", "last_login")
    search_fields = ("username", "email", "first_name", "last_name")
    list_filter = ("is_active", "is_staff", "date_joined", "usuariorol__rol")
    ordering = ("-date_joined",)
    list_per_page = 50
    action_form = UserActionForm
    actions = ["activar", "desactivar"]

    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        ("Información personal", {"fields": ("first_name", "last_name")}),
        (
            "Permisos",
            {"fields": ("is_active", "is_staff", "is_superuser",
                        "groups", "user_permissions")},
        ),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            "Datos de acceso",
            {
                "classes": ("wide",),
                "description": (
                    "El correo es obligatorio para la recuperación de acceso. "
                    "El nombre de usuario se genera automáticamente para roles institucionales "
                    "(Superusuario, Director Escolar, Administrativo Comercial); "
                    "para el rol Alumno ingresa la matrícula del alumno."
                ),
                "fields": ("email", "first_name", "last_name", "username", "password1", "password2"),
            },
        ),
    )

    readonly_fields = ("last_login", "date_joined")

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if obj:
            ro.extend(["username", "email"])
        return ro

    def save_model(self, request, obj, form, change):
        detalle = {}
        if change:
            original = User.objects.get(pk=obj.pk)
            changed = {}
            for field in form.changed_data:
                changed[field] = {"antes": getattr(
                    original, field), "despues": form.cleaned_data.get(field)}
            detalle["cambios"] = changed
            accion = "USER_UPDATE"
        else:
            accion = "USER_CREATE"
            detalle["usuario"] = obj.username

        super().save_model(request, obj, form, change)
        log_event(request, accion, "User", obj.pk, "OK", detalle)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        roles = list(Rol.objects.filter(
            usuariorol__usuario=form.instance).values_list("codigo", flat=True))
        log_event(
            request,
            "USER_ROLES_UPDATE",
            "User",
            form.instance.pk,
            "OK",
            {"roles": roles},
        )
        # Para usuarios nuevos (alta): generar username institucional si aplica
        if not change and roles:
            from apps.accounts.services.username_generator import (
                generate_institutional_username,
                get_institutional_prefix,
            )
            user = form.instance
            new_username = None
            for rol_codigo in roles:
                prefix = get_institutional_prefix(rol_codigo)
                if prefix:
                    new_username = generate_institutional_username(rol_codigo)
                    break
            if new_username and user.username != new_username:
                user.username = new_username
                user.save(update_fields=["username"])
                messages.success(
                    request,
                    f"Nombre de usuario generado automáticamente: \"{user.username}\". "
                    "Comunícalo al usuario junto con su contraseña.",
                )
            elif "ALUMNO" in roles and not any(
                get_institutional_prefix(r) for r in roles
            ):
                # Rol Alumno: el username debe ser la matrícula ingresada por el operador.
                # Si quedó vacío o con valor por defecto, notificar.
                if not user.username or user.username.startswith("_tmp_"):
                    messages.warning(
                        request,
                        "El usuario tiene rol Alumno pero no se ingresó la matrícula como nombre "
                        "de usuario. Edita el registro y corrígelo.",
                    )

    def activar(self, request, queryset):
        motivo = request.POST.get("motivo", "")
        updated = 0
        for user in queryset:
            if not user.is_active:
                user.is_active = True
                user.save(update_fields=["is_active"])
                updated += 1
                log_event(request, "USER_ACTIVATE", "User",
                          user.pk, "OK", {"motivo": motivo})
        if updated:
            messages.success(request, f"Se reactivaron {updated} usuario(s).")

    activar.short_description = "Reactivar usuarios seleccionados"

    def desactivar(self, request, queryset):
        motivo = request.POST.get("motivo", "")
        updated = 0
        for user in queryset:
            if user.is_active:
                user.is_active = False
                user.save(update_fields=["is_active"])
                revoke_sessions(user)
                updated += 1
                log_event(
                    request,
                    "USER_DEACTIVATE",
                    "User",
                    user.pk,
                    "OK",
                    {"motivo": motivo},
                )
        if updated:
            messages.success(request, f"Se desactivaron {updated} usuario(s).")

    desactivar.short_description = "Desactivar usuarios seleccionados"


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    form = RolPermisosForm
    list_display = ("nombre", "codigo", "activo", "creado_en")
    search_fields = ("nombre", "codigo", "rolpermiso__permiso__nombre")
    list_filter = ("activo", "creado_en", "rolpermiso__permiso__modulo")
    ordering = ("nombre",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Registrar auditoria de cambios de permisos
        diff = getattr(form, "_perm_diff", None)
        if diff:
            log_event(
                request,
                "ROL_PERMISOS_UPDATE",
                "Rol",
                obj.pk,
                "OK",
                diff,
            )
