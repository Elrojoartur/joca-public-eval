import os
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

import environ
from django.core.exceptions import ImproperlyConfigured

# Base / env
BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend
env = environ.Env()

# Lee .env si existe (un nivel arriba de backend)
ENV_FILE = BASE_DIR.parent / ".env"
if ENV_FILE.exists():
    environ.Env.read_env(str(ENV_FILE))

# Secrets / flags
DEV_SECRET_KEY = "django-insecure-=_(v8*t41q_tfwv-*ifw+o0vt$0ea7gy+rx3sa3a1$5^(-b4j@"
SECRET_KEY = env("DJANGO_SECRET_KEY", default=env(
    "SECRET_KEY", default=DEV_SECRET_KEY))
DEBUG = env.bool("DJANGO_DEBUG", default=env.bool("DEBUG", default=True))

# CAPTCHA (fallback seguro: desactivado cuando no hay llaves)
RECAPTCHA_ENABLED = env.bool("RECAPTCHA_ENABLED", default=True)
RECAPTCHA_SITE_KEY = env("RECAPTCHA_SITE_KEY", default="")
RECAPTCHA_SECRET_KEY = env("RECAPTCHA_SECRET_KEY", default="")
RECAPTCHA_THRESHOLD = env.int("RECAPTCHA_THRESHOLD", default=1)
RECAPTCHA_MODE = env("RECAPTCHA_MODE", default="v3")
RECAPTCHA_SCORE_THRESHOLD = env.float("RECAPTCHA_SCORE_THRESHOLD", default=0.5)

# Llaves de prueba oficiales de Google para desarrollo/demo.
# Se usan como respaldo para no desactivar reCAPTCHA cuando faltan llaves reales.
RECAPTCHA_USE_TEST_KEYS = env.bool("RECAPTCHA_USE_TEST_KEYS", default=True)
if (
    RECAPTCHA_ENABLED
    and RECAPTCHA_USE_TEST_KEYS
    and not RECAPTCHA_SITE_KEY
    and not RECAPTCHA_SECRET_KEY
):
    RECAPTCHA_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
    RECAPTCHA_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"
    # Las test keys de Google son exclusivamente v2; forzar modo compatible.
    RECAPTCHA_MODE = "v2"

# Static
STATIC_URL = "/static/"
STATIC_ROOT = env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles"))

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# En pruebas se evita depender de manifest de estaticos para renderizar templates.
if "test" in sys.argv:
    STORAGES["staticfiles"] = {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    }

# Branding
SITE_NAME = "CCENT Nikola Tesla"
PORTAL_MISION = env(
    "PORTAL_MISION",
    default="Formar estudiantes con excelencia academica, tecnica y humana para su desarrollo integral.",
)
PORTAL_VISION = env(
    "PORTAL_VISION",
    default="Ser una institucion referente en educacion y formacion tecnica por su calidad, inclusion e innovacion.",
)

# Hosts / CSRF
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".github.dev",
    # Agregar aquí el dominio o IP del servidor de producción
    # Ejemplo: "mi-dominio.com", "www.mi-dominio.com"
]

CSRF_TRUSTED_ORIGINS = [
    "https://*.github.dev",
    # Agregar aquí los orígenes confiables del servidor de producción
    # Ejemplo: "https://mi-dominio.com", "https://www.mi-dominio.com"
]


# =========================
# Database (PostgreSQL)
# =========================
DB_ENGINE = env("DB_ENGINE", default="django.db.backends.postgresql")
DB_NAME = env("DB_NAME", default=env("POSTGRES_DB", default="CCENT_db"))
DB_USER = env("DB_USER", default=env("POSTGRES_USER", default="CCENT_user"))
DB_PASSWORD = env("DB_PASSWORD", default=env("POSTGRES_PASSWORD", default=""))
DB_HOST = env("DB_HOST", default=env("POSTGRES_HOST", default="127.0.0.1"))
DB_PORT = env("DB_PORT", default=env("POSTGRES_PORT", default="5432"))

DATABASES = {
    "default": {
        "ENGINE": DB_ENGINE,
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
    }
}

# Apps / middleware
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.public_portal",
    "apps.authn",
    "apps.accounts",
    "apps.school",
    "apps.sales",
    "apps.governance",
    "apps.reports",
    "apps.ui",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # debe ir justo después de AuthenticationMiddleware
    "apps.authn.middleware.GuestOnlyRedirectMiddleware",
    "apps.authn.middleware.PanelAccessMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.authn.middleware.IdleTimeoutMiddleware",
    # al final del stack personalizado: ve la respuesta ya procesada
    "apps.authn.middleware.SecurityNoCacheMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "joca.urls"

LOGIN_URL = "/acceso/"
LOGIN_REDIRECT_URL = "/panel/"
LOGOUT_REDIRECT_URL = "/acceso/"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",

                # Context processors propios
                "apps.ui.context_processors.site_name",
                "apps.ui.context_processors.ui_roles",
            ],
        },
    },
]

# Seguridad de contrasenas: hash robusto y validaciones base.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Email backend para contacto: console en dev, SMTP en producción
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend" if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=1025)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@joca.local")
CONTACT_EMAIL = env("CONTACT_EMAIL", default="contacto@joca.local")

# =========================
# Bloque 1 · Security headers
# =========================
# DJANGO_SECURE=True activa HTTPS obligatorio, cookies seguras y HSTS.
# Solo debe ser True en el VPS con TLS real. En dev/Codespaces dejar False.
DJANGO_SECURE = env.bool("DJANGO_SECURE", default=False)

# Proxy SSL: Nginx/Caddy terminan TLS y reenvían con este header
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO",
                           "https") if DJANGO_SECURE else None

# Redirigir HTTP → HTTPS solo cuando hay TLS real
SECURE_SSL_REDIRECT = DJANGO_SECURE

# Cookies solo viajan por HTTPS cuando hay TLS
SESSION_COOKIE_SECURE = DJANGO_SECURE
CSRF_COOKIE_SECURE = DJANGO_SECURE

# Siempre activos (sin riesgo en dev)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# HSTS: activo solo cuando hay TLS (no establecer en pre-producción)
SECURE_HSTS_SECONDS = 31_536_000 if DJANGO_SECURE else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = DJANGO_SECURE
SECURE_HSTS_PRELOAD = DJANGO_SECURE

# Headers de seguridad pasivos (seguros en todo entorno)
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# =========================
# Bloque 2 · Logging estructurado
# =========================
_LOG_DIR = BASE_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "archivo_bitacora": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(_LOG_DIR / "bitacora.log"),
            "maxBytes": 5 * 1024 * 1024,   # 5 MB
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "archivo_app": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(_LOG_DIR / "app.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        # Errores internos de Django (templates, ORM, etc.)
        "django": {
            "handlers": ["console", "archivo_app"],
            "level": "WARNING",
            "propagate": False,
        },
        # Violaciones CSRF, SuspiciousOperation, etc.
        "django.security": {
            "handlers": ["console", "archivo_app"],
            "level": "WARNING",
            "propagate": False,
        },
        # Bitácora de negocio (auth, audit, accesos)
        "bitacora": {
            "handlers": ["console", "archivo_bitacora"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# =========================
# Bloque 3 · Validación de env vars al arranque
# =========================
# Solo aplica cuando DEBUG=False para no bloquear el entorno de desarrollo.
if not DEBUG:
    _errores_startup: list[str] = []

    if SECRET_KEY == DEV_SECRET_KEY:
        _errores_startup.append(
            "SECRET_KEY insegura. Define DJANGO_SECRET_KEY en el entorno."
        )

    smtp_backend = "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_BACKEND == smtp_backend and not EMAIL_HOST_USER:
        _errores_startup.append(
            "EMAIL_HOST_USER vacío con backend SMTP activo. "
            "Define EMAIL_HOST_USER y EMAIL_HOST_PASSWORD."
        )

    if _errores_startup:
        raise ImproperlyConfigured(
            "Errores de configuración de producción detectados al arranque:\n  - "
            + "\n  - ".join(_errores_startup)
        )

# =========================
# Bloque 4 · API REST — permisos por defecto y CORS
# =========================
# Todos los endpoints bajo /api/v1/ requieren sesión autenticada por defecto.
# Los endpoints que necesitan acceso público (ej. portal público de grupos)
# deben declarar explícitamente AllowAny con @permission_classes.
# CORS: este proyecto no tiene frontend separado (todos los clientes son
# templates Django mismo-origen). No se instala django-cors-headers.
# Si en el futuro se agrega un frontend desacoplado, instalar corsheaders
# y configurar CORS_ALLOWED_ORIGINS con solo el dominio del front.
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Throttling DRF (independiente del rate_limit decorator de cache)
    # Aplica como segunda capa de defensa en la API REST.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/min",
        "user": "120/min",
    },
}

# =========================
# Bloque 5 · Sentry (opcional, solo producción)
# =========================
# Para activar: instalar sentry-sdk[django] en el VPS y definir SENTRY_DSN en .env
#   pip install "sentry-sdk[django]>=2.0,<3.0"
SENTRY_DSN = env("SENTRY_DSN", default="")
if not DEBUG and SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            # No enviar stack traces con datos de usuario ni variables locales
            send_default_pii=False,
            traces_sample_rate=0.05,   # 5% de transacciones para performance
        )
    except ImportError:
        pass  # sentry-sdk no instalado; continuar sin él
