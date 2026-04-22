from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string


def home(request):
    return redirect("/portal/")


def health(request):
    return HttpResponse("ok", content_type="text/plain")


def handler400(request, exception=None):
    html = render_to_string("errors/400.html", {}, request=request)
    return HttpResponse(html, status=400, content_type="text/html; charset=utf-8")


def handler403(request, exception=None):
    html = render_to_string("errors/403.html", {}, request=request)
    return HttpResponse(html, status=403, content_type="text/html; charset=utf-8")


def handler404(request, exception=None):
    html = render_to_string("errors/404.html", {}, request=request)
    return HttpResponse(html, status=404, content_type="text/html; charset=utf-8")


def handler500(request):
    # Template autónomo para máxima seguridad ante excepciones en cadena
    try:
        html = render_to_string("errors/500.html", {})
    except Exception:
        html = (
            "<!doctype html><html lang='es'><body>"
            "<h1>Error interno del servidor</h1>"
            "<p>Algo salió mal. Intenta más tarde.</p>"
            "</body></html>"
        )
    return HttpResponse(html, status=500, content_type="text/html; charset=utf-8")
