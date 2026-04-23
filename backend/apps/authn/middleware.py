import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect, render

from apps.accounts.models import UsuarioRol
from apps.governance.services.audit import log_event
from apps.governance.services.security_policy import get_idle_timeout_seconds


class IdleTimeoutMiddleware:
    """Cierra sesión tras inactividad usando session timestamps."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        now_ts = int(time.time())
        timeout = get_idle_timeout_seconds()

        if getattr(request, "user", None) and request.user.is_authenticated:
            last_activity = request.session.get("last_activity")
            # Verifica inactividad antes de procesar la petición; si el umbral se supera,
            # invalida la sesión y redirige al login para reducir el riesgo de secuestro de sesión.
            if last_activity and now_ts - last_activity > timeout:
                username = getattr(request.user, "username", "")
                log_event(
                    request,
                    accion="AUTH::LOGOUT_IDLE",
                    entidad="Sesion",
                    entidad_id=username or None,
                    resultado="ok",
                    detalle={
                        "username": username,
                        "idle_seconds": now_ts - int(last_activity),
                        "timeout_seconds": timeout,
                    },
                )
                logout(request)  # internamente llama session.flush()
                messages.info(
                    request, "Sesión expirada por inactividad. Vuelve a ingresar.")
                return redirect("/acceso/")
            request.session["last_activity"] = now_ts

        response = self.get_response(request)
        return response


class PanelAccessMiddleware:
    """Aplica control de acceso por rol para rutas /panel/* de forma centralizada."""

    # Las reglas se evalúan en orden descendente de especificidad; la primera
    # coincidencia de prefijo determina el conjunto de roles requeridos para esa ruta.
    ROLE_RULES = (
        ("/panel/escolar/", {"SUPERUSUARIO", "DIRECTOR_ESCOLAR"}),
        ("/panel/gobierno/", {"SUPERUSUARIO", "DIRECTOR_ESCOLAR"}),
        ("/panel/reportes/academico/", {"SUPERUSUARIO", "DIRECTOR_ESCOLAR"}),
        ("/panel/reportes/comercial/",
         {"SUPERUSUARIO", "ADMINISTRATIVO_COMERCIAL"}),
        (
            "/panel/reportes/",
            {"SUPERUSUARIO", "DIRECTOR_ESCOLAR", "ADMINISTRATIVO_COMERCIAL"},
        ),
        ("/panel/ventas/catalogo/",
         {"SUPERUSUARIO", "ADMINISTRATIVO_COMERCIAL"}),
        ("/panel/ventas/pos/", {"SUPERUSUARIO", "ADMINISTRATIVO_COMERCIAL"}),
        (
            "/panel/ventas/estado-cuenta/",
            {"SUPERUSUARIO", "ADMINISTRATIVO_COMERCIAL"},
        ),
        (
            "/panel/ventas/inventario/",
            {"SUPERUSUARIO", "ADMINISTRATIVO_COMERCIAL"},
        ),
        (
            "/panel/ventas/facturacion/",
            {"SUPERUSUARIO", "ADMINISTRATIVO_COMERCIAL"},
        ),
        (
            "/panel/ventas/cuentas/",
            {"SUPERUSUARIO", "ADMINISTRATIVO_COMERCIAL"},
        ),
        (
            "/panel/ventas/",
            {
                "SUPERUSUARIO",
                "DIRECTOR_ESCOLAR",
                "ADMINISTRATIVO_COMERCIAL",
                "ALUMNO",
            },
        ),
        ("/panel/alumno/", {"SUPERUSUARIO", "ALUMNO"}),
        (
            "/panel/",
            {
                "SUPERUSUARIO",
                "DIRECTOR_ESCOLAR",
                "ADMINISTRATIVO_COMERCIAL",
                "ALUMNO",
            },
        ),
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        if not path.startswith("/panel/"):
            return self.get_response(request)

        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return redirect(f"/acceso/?next={request.get_full_path()}")

        if request.user.is_superuser:
            return self.get_response(request)

        required_codes = self._required_codes(path)
        if not required_codes:
            return self.get_response(request)

        user_role_code = self._get_role_code(request.user)
        if user_role_code in required_codes:
            return self.get_response(request)

        log_event(
            request,
            accion="PANEL::ACCESO_DENEGADO",
            entidad="Ruta",
            entidad_id=path,
            resultado="denied",
            detalle={
                "path": path,
                "role": user_role_code,
                "required": sorted(required_codes),
            },
        )

        return render(
            request,
            "ui/forbidden.html",
            {
                "role": user_role_code or "Usuario",
                "allowed": ", ".join(sorted(required_codes)),
            },
            status=403,
        )

    def _required_codes(self, path):
        for prefix, codes in self.ROLE_RULES:
            if path.startswith(prefix):
                return codes
        return None

    @staticmethod
    def _get_role_code(user):
        # Consulta el rol desde UsuarioRol (modelo propio de gobernanza) en lugar de
        # groups de Django, manteniendo una única fuente de verdad para el control de acceso.
        ur = UsuarioRol.objects.select_related(
            "rol").filter(usuario=user).first()
        if not ur or not ur.rol:
            return None
        return (ur.rol.codigo or "").strip().upper() or None


class GuestOnlyRedirectMiddleware:
    """Redirige a /panel/ a cualquier usuario autenticado que intente acceder
    a rutas exclusivas para visitantes no autenticados (/acceso/ y derivadas).

    Requiere que AuthenticationMiddleware ya haya poblado request.user,
    por lo que debe ir DESPUÉS de él en MIDDLEWARE.
    """

    # Prefijo único que cubre TODAS las rutas guest-only declaradas en joca/urls.py:
    #   name="login"                  → /acceso/
    #   name="registro_alumno"        → /acceso/registro/
    #   name="password_reset"         → /acceso/recuperar/
    #   name="password_reset_done"    → /acceso/recuperar/enviado/
    #   name="password_reset_confirm" → /acceso/recuperar/<uidb64>/<token>/
    #   name="password_reset_complete"→ /acceso/recuperar/listo/
    GUEST_ONLY_PREFIXES: tuple[str, ...] = ("/acceso/",)

    # Rutas dentro del prefijo anterior que sí pueden recibir usuarios autenticados
    # sin redirección: /acceso/admin/ es un RedirectView permanente hacia /admin/
    # que tiene su propio flujo de autenticación.
    GUEST_EXCEPTIONS: tuple[str, ...] = ("/acceso/admin/",)

    PANEL_HOME: str = "/panel/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and self._is_guest_only(request.path):
            return redirect(self.PANEL_HOME)
        return self.get_response(request)

    def _is_guest_only(self, path: str) -> bool:
        for exc in self.GUEST_EXCEPTIONS:
            if path.startswith(exc):
                return False
        for prefix in self.GUEST_ONLY_PREFIXES:
            if path.startswith(prefix):
                return True
        return False


class SecurityNoCacheMiddleware:
    """Aplica cabeceras anti-cache únicamente a respuestas HTML de rutas
    sensibles o de usuarios autenticados.

    No modifica respuestas de archivos estáticos, media, PDFs, CSVs ni
    cualquier Content-Type que no sea text/html.
    """

    SENSITIVE_BASE_PATHS: tuple[str, ...] = (
        "/panel",
        "/acceso",
        "/salir",
    )

    # Rutas cuyas respuestas nunca deben recibir no-cache forzado
    # (WhiteNoise ya gestiona su propio cache con ETags/max-age).
    SKIP_PREFIXES: tuple[str, ...] = (
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        path = request.path

        # 1. Excluir rutas de archivos estáticos/media
        if any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return response

        # 2. Solo aplicar a respuestas HTML (evita alterar PDFs, CSVs, JSON, etc.)
        content_type = response.get("Content-Type", "")
        if "text/html" not in content_type:
            return response

        # 3. Aplicar si el usuario está autenticado O si la ruta es sensible
        user = getattr(request, "user", None)
        authenticated = bool(user and user.is_authenticated)
        path_stripped = path.rstrip("/") or "/"
        sensitive_path = (
            path_stripped in self.SENSITIVE_BASE_PATHS
            or any(path.startswith(base + "/") for base in self.SENSITIVE_BASE_PATHS)
        )

        if authenticated or sensitive_path:
            response["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0, private"
            )
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        return response
