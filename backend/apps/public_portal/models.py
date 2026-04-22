from django.db import models


class MensajeContacto(models.Model):
    """Almacena mensajes enviados desde el formulario de contacto del portal público."""

    nombre = models.CharField(max_length=150)
    email = models.EmailField()
    telefono = models.CharField(max_length=50, blank=True, null=True)
    asunto = models.CharField(max_length=150, blank=True)
    mensaje = models.TextField()
    ip_origen = models.GenericIPAddressField(null=True, blank=True)
    enviado_en = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)

    class Meta:
        ordering = ["-enviado_en"]
        verbose_name = "Mensaje de contacto"
        verbose_name_plural = "Mensajes de contacto"

    def __str__(self):
        return f"{self.nombre} - {self.asunto} ({self.enviado_en.strftime('%Y-%m-%d')})"
