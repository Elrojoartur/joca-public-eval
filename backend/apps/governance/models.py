from django.conf import settings
from django.db import models

from apps.accounts.models import Rol


class Permiso(models.Model):
    codigo = models.CharField(max_length=100, unique=True)
    nombre = models.CharField(max_length=150)
    modulo = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "permiso"
        verbose_name = "Permiso"
        verbose_name_plural = "Permisos"

    def __str__(self):
        return self.nombre


class RolPermiso(models.Model):
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE)
    permiso = models.ForeignKey(Permiso, on_delete=models.CASCADE)
    asignado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rol_permiso"
        unique_together = ("rol", "permiso")
        verbose_name = "Rol Permiso"
        verbose_name_plural = "Roles Permisos"

    def __str__(self):
        return f"{self.rol} -> {self.permiso}"


class EventoAuditoria(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,
                              on_delete=models.SET_NULL, null=True, blank=True)
    ip = models.CharField(max_length=64, blank=True)
    accion = models.CharField(max_length=100)
    entidad = models.CharField(max_length=120)
    entidad_id = models.CharField(max_length=120, null=True, blank=True)
    resultado = models.CharField(max_length=50)
    detalle = models.JSONField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evento_auditoria"
        verbose_name = "Evento de auditoria"
        verbose_name_plural = "Eventos de auditoria"

    def __str__(self):
        return f"{self.accion} {self.entidad} ({self.entidad_id})"


class ParametroSistema(models.Model):
    CATEGORIA_INSTITUCION = "INSTITUCION"
    CATEGORIA_PERIODO = "PERIODO"
    CATEGORIA_SMTP = "SMTP"
    CATEGORIA_PASARELA = "PASARELA"
    CATEGORIA_SEGURIDAD = "SEGURIDAD"
    CATEGORIA_REPORTES = "REPORTES"
    CATEGORIA_CHOICES = (
        (CATEGORIA_INSTITUCION, "Institucion"),
        (CATEGORIA_PERIODO, "Periodo"),
        (CATEGORIA_SMTP, "SMTP"),
        (CATEGORIA_PASARELA, "Pasarela"),
        (CATEGORIA_SEGURIDAD, "Seguridad"),
        (CATEGORIA_REPORTES, "Reportes"),
    )

    categoria = models.CharField(
        max_length=30, choices=CATEGORIA_CHOICES, db_index=True)
    clave = models.CharField(max_length=80, unique=True)
    valor = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "parametro_sistema"
        verbose_name = "Parametro del sistema"
        verbose_name_plural = "Parametros del sistema"
        ordering = ["categoria", "clave"]

    def __str__(self):
        return f"{self.clave}={self.valor}"


class RespaldoSistema(models.Model):
    ESTADO_GENERADO = "GENERADO"
    ESTADO_RESTAURADO = "RESTAURADO"
    ESTADO_CHOICES = (
        (ESTADO_GENERADO, "Generado"),
        (ESTADO_RESTAURADO, "Restaurado"),
    )

    nombre = models.CharField(max_length=120, unique=True)
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default=ESTADO_GENERADO)
    checksum = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    notas = models.CharField(max_length=255, blank=True)
    generado_en = models.DateTimeField(auto_now_add=True)
    restaurado_en = models.DateTimeField(null=True, blank=True)
    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respaldos_generados",
    )

    class Meta:
        db_table = "respaldo_sistema"
        verbose_name = "Respaldo del sistema"
        verbose_name_plural = "Respaldos del sistema"
        ordering = ["-generado_en"]

    def __str__(self):
        return self.nombre
