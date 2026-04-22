from django.contrib import admin
from .models import MensajeContacto


@admin.register(MensajeContacto)
class MensajeContactoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "email", "asunto", "enviado_en", "leido")
    list_filter = ("enviado_en", "leido")
    search_fields = ("nombre", "email", "asunto", "mensaje")
    readonly_fields = ("enviado_en", "ip_origen")

    fieldsets = (
        ("Contacto", {
            "fields": ("nombre", "email", "telefono", "ip_origen")
        }),
        ("Mensaje", {
            "fields": ("asunto", "mensaje")
        }),
        ("Estado", {
            "fields": ("leido", "enviado_en")
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True
