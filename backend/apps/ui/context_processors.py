from django.conf import settings
from django.contrib.auth.models import AnonymousUser


def site_name(request):
    """
    Expone el nombre del sitio a todas las plantillas como SITE_NAME.

    Nota:
    Aunque Django permite usar settings.SITE_NAME directamente,
    este context processor evita depender de settings en templates.
    """
    return {"SITE_NAME": getattr(settings, "SITE_NAME", "JOCA/CCENT")}


def ui_roles(request):
    """
    Flags de rol para renderizar menú lateral por perfil:
    - superuser: ve todo
    - director_escolar, administrativo_comercial, alumno: por grupos (seed_ccent)
    """
    user = getattr(request, "user", None)

    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return {
            "UI_IS_AUTH": False,
            "UI_IS_SUPER": False,
            "UI_IS_DIRECTOR": False,
            "UI_IS_COMERCIAL": False,
            "UI_IS_ALUMNO": False,
            "UI_USERNAME": "",
            "UI_ROLE_LABEL": "",
        }

    group_names = set(user.groups.values_list("name", flat=True))

    is_super = bool(getattr(user, "is_superuser", False))
    is_director = "director_escolar" in group_names
    is_comercial = "administrativo_comercial" in group_names
    is_alumno = "alumno" in group_names

    if is_super:
        role_label = "Superusuario"
    elif is_director:
        role_label = "Director Escolar"
    elif is_comercial:
        role_label = "Administrativo Comercial"
    elif is_alumno:
        role_label = "Alumno"
    else:
        role_label = "Usuario"

    return {
        "UI_IS_AUTH": True,
        "UI_IS_SUPER": is_super,
        "UI_IS_DIRECTOR": is_director,
        "UI_IS_COMERCIAL": is_comercial,
        "UI_IS_ALUMNO": is_alumno,
        "UI_USERNAME": user.get_username(),
        "UI_ROLE_LABEL": role_label,
    }
