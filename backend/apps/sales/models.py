from django.conf import settings
from django.apps import apps
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone


class Concepto(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Concepto"
        verbose_name_plural = "Conceptos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class OrdenPOS(models.Model):
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_PARCIAL = "parcial"
    ESTADO_PAGADA = "pagada"
    ESTADO_CANCELADA = "cancelada"
    ESTADO_CHOICES = (
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_PARCIAL, "Parcial"),
        (ESTADO_PAGADA, "Pagada"),
        (ESTADO_CANCELADA, "Cancelada"),
    )

    inscripcion = models.ForeignKey(
        "school.Inscripcion",
        on_delete=models.PROTECT,
        related_name="ordenes",
        db_index=True,
    )
    fecha_emision = models.DateTimeField(default=timezone.now)
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE, db_index=True)

    class Meta:
        verbose_name = "Orden"
        verbose_name_plural = "Ordenes"
        constraints = [
            models.UniqueConstraint(
                fields=["inscripcion"], name="uq_orden_inscripcion")
        ]
        ordering = ["-fecha_emision"]

    @property
    def periodo(self):
        if self.inscripcion_id and self.inscripcion.grupo_id:
            return self.inscripcion.grupo.periodo
        return ""

    @property
    def total_calculado(self):
        total_expr = ExpressionWrapper(
            F("cantidad") * F("precio_unit"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        return self.items.aggregate(total=Sum(total_expr)).get("total") or 0

    def __str__(self):
        return f"Orden {self.periodo} (insc={self.inscripcion_id})"


class OrdenItem(models.Model):
    orden = models.ForeignKey(
        OrdenPOS, on_delete=models.CASCADE, related_name="items")
    concepto = models.ForeignKey(
        Concepto, on_delete=models.PROTECT, related_name="items")
    cantidad = models.PositiveIntegerField(default=1)
    precio_unit = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Item"
        verbose_name_plural = "Items"
        constraints = [
            models.UniqueConstraint(
                fields=["orden", "concepto"], name="uq_item_orden_concepto")
        ]

    def __str__(self):
        return f"{self.concepto} x{self.cantidad}"

    @property
    def total_calculado(self):
        return self.cantidad * self.precio_unit


class Pago(models.Model):
    orden = models.ForeignKey(
        OrdenPOS, on_delete=models.PROTECT, related_name="pagos")
    fecha_pago = models.DateTimeField(default=timezone.now)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    metodo = models.CharField(max_length=20)
    auth_code = models.CharField(max_length=40, blank=True)

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["-fecha_pago"]

    def __str__(self):
        return f"Pago {self.monto} ({self.metodo})"


class Ticket(models.Model):
    pago = models.OneToOneField(
        Pago, on_delete=models.CASCADE, related_name="ticket")
    generado_en = models.DateTimeField(default=timezone.now)
    ruta_pdf = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"

    def __str__(self):
        return f"Ticket pago={self.pago_id}"


class Existencia(models.Model):
    concepto = models.OneToOneField(
        Concepto,
        on_delete=models.CASCADE,
        related_name="existencia",
    )
    inventario_habilitado = models.BooleanField(default=False)
    stock_actual = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    stock_minimo = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Existencia"
        verbose_name_plural = "Existencias"

    def __str__(self):
        return f"Existencia {self.concepto.nombre}: {self.stock_actual}"


class AlertaStock(models.Model):
    existencia = models.ForeignKey(
        Existencia,
        on_delete=models.CASCADE,
        related_name="alertas",
    )
    stock_actual = models.DecimalField(max_digits=12, decimal_places=2)
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=2)
    activa = models.BooleanField(default=True)
    generado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Alerta de stock"
        verbose_name_plural = "Alertas de stock"
        ordering = ["-generado_en"]

    def __str__(self):
        return f"Alerta {self.concepto.nombre}: {self.stock_actual} <= {self.stock_minimo}"

    @property
    def concepto(self):
        if self.existencia_id and self.existencia.concepto_id:
            return self.existencia.concepto
        return None


class CorteCaja(models.Model):
    fecha_operacion = models.DateField(unique=True, db_index=True)
    cerrado_en = models.DateTimeField(default=timezone.now)
    total_ordenes = models.PositiveIntegerField(default=0)
    total_pagos = models.PositiveIntegerField(default=0)
    notas = models.CharField(max_length=255, blank=True)
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cortes_caja",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Corte de caja"
        verbose_name_plural = "Cortes de caja"
        ordering = ["-fecha_operacion", "-cerrado_en"]

    def __str__(self):
        return f"Corte {self.fecha_operacion}"

    @classmethod
    def resumen_calculado(cls, fecha_operacion):
        orden_item_model = apps.get_model("sales", "OrdenItem")
        pago_model = apps.get_model("sales", "Pago")

        total_expr = ExpressionWrapper(
            F("cantidad") * F("precio_unit"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        monto_ordenes = (
            orden_item_model.objects.filter(
                orden__fecha_emision__date=fecha_operacion)
            .aggregate(total=Sum(total_expr))
            .get("total")
            or 0
        )
        monto_pagos = (
            pago_model.objects.filter(fecha_pago__date=fecha_operacion)
            .aggregate(total=Sum("monto"))
            .get("total")
            or 0
        )
        return {
            "monto_ordenes": monto_ordenes,
            "monto_pagos": monto_pagos,
        }
