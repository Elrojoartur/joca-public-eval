from django import template
from apps.accounts.models import UsuarioRol

register = template.Library()

ROLE_BY_CODE = {
    "SUPERUSUARIO": "Superusuario",
    "DIRECTOR_ESCOLAR": "Director Escolar",
    "ADMINISTRATIVO_COMERCIAL": "Administrativo Comercial",
    "ALUMNO": "Alumno",
}

def _get_user_role(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return "Invitado"
    if getattr(user, "is_superuser", False):
        return "Superusuario"

    ur = UsuarioRol.objects.select_related("rol").filter(usuario=user).first()
    if not ur or not ur.rol:
        return "Usuario"

    codigo = getattr(ur.rol, "codigo", None)
    if codigo:
        return ROLE_BY_CODE.get(codigo, ur.rol.nombre or "Usuario")
    return ur.rol.nombre or "Usuario"


@register.filter
def user_role(user) -> str:
    return _get_user_role(user)


@register.simple_tag
def has_role(user, role_name: str) -> bool:
    """
    Uso típico:
      {% has_role request.user "Director Escolar" as ok %}
      {% if ok %} ... {% endif %}

    Si lo usan sin 'as', imprimirá True/False (pero ya no truena el template).
    """
    role = _get_user_role(user)
    return role == "Superusuario" or role == role_name


@register.simple_tag
def role_in(user, *roles) -> bool:
    role = _get_user_role(user)
    return role == "Superusuario" or role in set(roles)
