from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # OpenAPI / Swagger
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    # Módulos
    path("public/", include("apps.public_portal.api.v1.urls")),
    path("auth/", include("apps.authn.api.v1.urls")),
    path("accounts/", include("apps.accounts.api.v1.urls")),
    path("school/", include("apps.school.api.v1.urls")),
    path("sales/", include("apps.sales.api.v1.urls")),
    path("governance/", include("apps.governance.api.v1.urls")),
    path("reports/", include("apps.reports.api.v1.urls")),
]
