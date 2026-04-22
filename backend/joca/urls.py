
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.http import JsonResponse
from django.contrib.auth import views as auth_views
from apps.authn import views as authn_views
from apps.authn.views import PortalLoginView, salir
from apps.authn.decorators import rate_limit
from apps.ui import views
from django.urls import path
from . import views
from apps.ui import views_auth

app_name = "ui"

# ── Error handlers ────────────────────────────────────────────────────────────
handler400 = "joca.views.handler400"
handler403 = "joca.views.handler403"
handler404 = "joca.views.handler404"
handler500 = "joca.views.handler500"
# ─────────────────────────────────────────────────────────────────────────────

urlpatterns = [
    # Público
    path("portal/", include("apps.public_portal.urls")),

    # Acceso (auth)
    path("acceso/", views_auth.acceso, name="login"),

    path(
        "acceso/registro/",
        RedirectView.as_view(url="/acceso/", permanent=False),
        name="registro_alumno",
    ),

    path("salir/", salir, name="logout"),

    # Password reset: máx 5 solicitudes por IP en 10 min (evita spam de emails)
    path(
        "acceso/recuperar/",
        rate_limit("pw_reset_req", max_calls=5, period_seconds=600)(
            authn_views.AuditPasswordResetView.as_view()
        ),
        name="password_reset",
    ),
    path("acceso/recuperar/enviado/",
         auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    # Confirm: máx 10 intentos por IP en 10 min (cada clic único consume uno)
    path(
        "acceso/recuperar/<uidb64>/<token>/",
        rate_limit("pw_reset_confirm", max_calls=10, period_seconds=600)(
            authn_views.AuditPasswordResetConfirmView.as_view()
        ),
        name="password_reset_confirm",
    ),
    path("acceso/recuperar/listo/", auth_views.PasswordResetCompleteView.as_view(),
         name="password_reset_complete"),
    path("acceso/admin/", RedirectView.as_view(url="/admin/", permanent=True)),

    # Privado (UI)
    path("panel/", include("apps.ui.urls")),

    # Admin
    path("admin/", admin.site.urls),

    # API
    path("api/health/",
         lambda r: JsonResponse({"status": "ok", "service": "CCENT Nikola Tesla API"})),
    path("api/v1/", include("joca.api.v1.urls")),

    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"),
         name="swagger-ui"),

    path("", RedirectView.as_view(url="/portal/", permanent=False))



]
