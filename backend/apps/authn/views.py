import logging

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from .forms import PortalAuthForm
from django.contrib.auth import get_user_model, login
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.db import transaction
from apps.accounts.models import Rol, UsuarioRol
from apps.school.models import Alumno
from apps.governance.services.audit import log_event
from apps.governance.services.security_policy import get_password_min_length
import random


from .services import (
    get_client_ip,
    is_locked_out,
    register_failed_attempt,
    reset_attempts,
)

bitacora_logger = logging.getLogger("bitacora")


def _make_login_verification(request) -> str:
    """Genera verificación simple (suma) y la guarda en sesión."""
    a = random.randint(2, 9)
    b = random.randint(2, 9)
    q = f"¿Cuánto es {a} + {b}?"
    request.session["login_verif_question"] = q
    request.session["login_verif_answer"] = str(a + b)
    request.session.modified = True
    return q


def salir(request):
    username = getattr(request.user, "username", "")
    log_event(
        request,
        accion="AUTH::LOGOUT",
        entidad="Sesion",
        entidad_id=username or None,
        resultado="ok",
        detalle={"username": username},
    )

    for token_key in ["access_token", "refresh_token"]:
        if token_key in request.session:
            del request.session[token_key]

    logout(request)  # internamente llama session.flush()

    bitacora_logger.info(
        "[ACCESO][LOGOUT] user=%s ip=%s",
        username,
        request.META.get("REMOTE_ADDR"),
    )
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect("/acceso/")


class PortalLoginView(LoginView):
    template_name = "registration/login.html"
    form_class = PortalAuthForm

    def get(self, request, *args, **kwargs):
        # IMPORTANTE: aquí se genera la pregunta al cargar la página
        _make_login_verification(request)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        username = request.POST.get("username", "")
        ip = get_client_ip(request)
        request._skip_register_attempt = False

        # Primer filtro: campo honeypot invisible. Los agentes automatizados suelen
        # completar todos los campos del formulario; su activación descarta la petición
        # sin revelar la razón al cliente.
        # Honeypot: si viene con valor, abortar sin procesar auth
        if (request.POST.get("hp") or "").strip():
            log_event(
                request,
                accion="AUTH::LOGIN_BLOCKED",
                entidad="Sesion",
                entidad_id=username or None,
                resultado="denied",
                detalle={"username": username, "reason": "honeypot"},
            )
            messages.error(
                request, "No se pudo validar el acceso. Intenta de nuevo.")
            request._skip_register_attempt = True
            _make_login_verification(request)
            form = self.get_form()
            return self.form_invalid(form)

        # Segundo filtro: CAPTCHA aritmético generado por sesión. Mitiga ataques de
        # fuerza bruta automatizados exigiendo una respuesta válida antes de procesar credenciales.
        # Verificación (tipo CAPTCHA por suma)
        verif = (request.POST.get("verificacion") or "").strip()
        expected = request.session.get("login_verif_answer")
        if (not expected) or (verif != expected):
            log_event(
                request,
                accion="AUTH::LOGIN_BLOCKED",
                entidad="Sesion",
                entidad_id=username or None,
                resultado="denied",
                detalle={"username": username, "reason": "verification"},
            )
            messages.error(request, "Verificación de seguridad incorrecta.")
            request._skip_register_attempt = True
            _make_login_verification(request)
            form = self.get_form()
            return self.form_invalid(form)

        # Tercer filtro: bloqueo temporal por combinación IP+usuario tras superar el
        # umbral de intentos fallidos configurado en ParametroSistema (SEGURIDAD).
        # Lockout (después de pasar verificación)
        if is_locked_out(username, ip):
            log_event(
                request,
                accion="AUTH::LOGIN_BLOCKED",
                entidad="Sesion",
                entidad_id=username or None,
                resultado="denied",
                detalle={"username": username, "reason": "lockout", "ip": ip},
            )
            messages.error(
                request, "Por seguridad, intenta de nuevo en unos minutos.")
            request._skip_register_attempt = True
            _make_login_verification(request)
            form = self.get_form()
            return self.form_invalid(form)

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        username = form.cleaned_data.get("username", "")
        ip = get_client_ip(self.request)
        # Restablece el contador de intentos para no penalizar al usuario legítimo
        # en futuros intentos de acceso tras una autenticación exitosa.
        reset_attempts(username, ip)

        log_event(
            self.request,
            accion="AUTH::LOGIN",
            entidad="Sesion",
            entidad_id=username or None,
            resultado="ok",
            detalle={"username": username},
        )

        # Limpia verificación (evita reuso)
        self.request.session.pop("login_verif_answer", None)
        self.request.session.pop("login_verif_question", None)

        return super().form_valid(form)

    def form_invalid(self, form):
        username = self.request.POST.get("username", "")
        ip = get_client_ip(self.request)

        if not getattr(self.request, "_skip_register_attempt", False):
            register_failed_attempt(username, ip)
            log_event(
                self.request,
                accion="AUTH::LOGIN_FAIL",
                entidad="Sesion",
                entidad_id=username or None,
                resultado="error",
                detalle={"username": username, "ip": ip},
            )
            messages.error(self.request, "Usuario o contraseña incorrectos.")

        # Siempre regenerar para evitar automatización
        _make_login_verification(self.request)
        return super().form_invalid(form)


class AuditPasswordResetView(auth_views.PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"

    def form_valid(self, form):
        email = (form.cleaned_data.get("email") or "").strip().lower()
        response = super().form_valid(form)
        log_event(
            self.request,
            accion="AUTH::PASSWORD_RESET_REQUEST",
            entidad="Sesion",
            entidad_id=email or None,
            resultado="ok",
            detalle={"email": email},
        )
        return response


class AuditPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not getattr(self, "validlink", False):
            log_event(
                request,
                accion="AUTH::PASSWORD_RESET_CONFIRM_DENIED",
                entidad="Sesion",
                resultado="denied",
                detalle={
                    "reason": "invalid_or_expired_token",
                    "method": request.method,
                },
            )
        return response

    def form_valid(self, form):
        response = super().form_valid(form)
        user_id = getattr(getattr(self, "user", None), "pk", None)
        log_event(
            self.request,
            accion="AUTH::PASSWORD_RESET_CONFIRM",
            entidad="Sesion",
            entidad_id=user_id,
            resultado="ok",
            detalle={"user_id": user_id},
        )
        return response


User = get_user_model()


@require_http_methods(["GET", "POST"])
def registro(request):
    if request.user.is_authenticated:
        return redirect("/panel/")

    if request.method == "GET":
        return render(request, "authn/registro.html")

    matricula = (request.POST.get("matricula") or "").strip().upper()
    email = (request.POST.get("email") or "").strip()
    p1 = request.POST.get("password1") or ""
    p2 = request.POST.get("password2") or ""

    if not matricula or not email or not p1 or not p2:
        messages.error(request, "Completa todos los campos.")
        return render(request, "authn/registro.html")

    min_len = get_password_min_length()
    if p1 != p2:
        messages.error(request, "Las contraseñas no coinciden.")
        return render(request, "authn/registro.html")
    if len(p1) < min_len:
        messages.error(
            request, f"La contraseña debe tener al menos {min_len} caracteres.")
        return render(request, "authn/registro.html")

    alumno = Alumno.objects.filter(matricula=matricula).first()
    if not alumno:
        messages.error(
            request, "Matrícula no encontrada. Solicita tu alta en control escolar.")
        return render(request, "authn/registro.html")

    # Recomendado (control real): el correo debe coincidir con el del alumno
    if (alumno.correo or "").strip().lower() != email.lower():
        messages.error(
            request, "El correo no coincide con el registrado para esa matrícula.")
        return render(request, "authn/registro.html")

    if User.objects.filter(username=matricula).exists():
        messages.error(
            request, "Ya existe una cuenta con esa matrícula. Usa recuperación de acceso.")
        return render(request, "authn/registro.html")

    with transaction.atomic():
        user = User.objects.create_user(
            username=matricula, email=email, password=p1)

        rol = Rol.objects.filter(codigo="ALUMNO").first()
        if not rol:
            messages.error(
                request, "No existe el rol ALUMNO (codigo='ALUMNO').")
            return render(request, "authn/registro.html")

        UsuarioRol.objects.update_or_create(
            usuario=user, defaults={"rol": rol})

    login(request, user)
    return redirect("/panel/alumno/")


def _new_security_code(request, key="sec_code"):
    code = f"{random.randint(1000, 9999)}"
    request.session[key] = code
    return code


@require_http_methods(["GET", "POST"])
def registro_alumno(request):
    # Si ya está logueado, no tiene caso registrarse
    if request.user.is_authenticated:
        return redirect("/panel/")

    # genera/renueva código
    security_code = request.session.get(
        "reg_code") or _new_security_code(request, "reg_code")

    if request.method == "GET":
        return render(request, "registration/registro_alumno.html", {"security_code": security_code})

    # POST
    matricula = (request.POST.get("matricula") or "").strip()
    correo = (request.POST.get("correo") or "").strip().lower()
    password1 = request.POST.get("password1") or ""
    password2 = request.POST.get("password2") or ""
    security = (request.POST.get("security") or "").strip()

    # honeypot simple (si lo usas)
    if (request.POST.get("verificacion") or "").strip():
        messages.error(request, "Solicitud inválida.")
        _new_security_code(request, "reg_code")
        return redirect("/acceso/registro/")

    # verificación de seguridad (sin decir CAPTCHA)
    if security != request.session.get("reg_code"):
        messages.error(request, "Verificación de seguridad incorrecta.")
        _new_security_code(request, "reg_code")
        return redirect("/acceso/registro/")

    if not matricula or not correo:
        messages.error(request, "Matrícula y correo son obligatorios.")
        return redirect("/acceso/registro/")

    min_len = get_password_min_length()
    if password1 != password2 or len(password1) < min_len:
        messages.error(
            request, f"Revisa tus contraseñas (mínimo {min_len} caracteres y deben coincidir).")
        return redirect("/acceso/registro/")

    # Validación “real”: debe existir alumno previamente capturado
    alumno = Alumno.objects.filter(
        matricula=matricula, correo__iexact=correo).first()
    if not alumno:
        messages.error(
            request, "No se encontró un alumno con esa matrícula y correo.")
        return redirect("/acceso/registro/")

    User = get_user_model()

    # username = matrícula (para que luego el panel pueda localizar al alumno)
    if User.objects.filter(username=matricula).exists():
        messages.info(request, "Esa cuenta ya existe. Inicia sesión.")
        return redirect("/acceso/")

    user = User.objects.create_user(
        username=matricula,
        email=correo,
        password=password1,
    )

    # Asignar rol ALUMNO
    rol = Rol.objects.filter(codigo="ALUMNO").first(
    ) or Rol.objects.filter(nombre__iexact="Alumno").first()
    if rol:
        UsuarioRol.objects.get_or_create(usuario=user, defaults={"rol": rol})

    # Login inmediato
    login(request, user)
    messages.success(request, "Cuenta creada correctamente.")
    return redirect("/panel/alumno/")
