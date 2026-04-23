from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from apps.sales.models import Concepto, OrdenItem, OrdenPOS

INSCRIPCION_PRECIO_BASE = Decimal("1000.00")
IVA_RATE = Decimal("0.16")
INSCRIPCION_IVA = (INSCRIPCION_PRECIO_BASE *
                   IVA_RATE).quantize(Decimal("0.01"))

CONCEPTO_INSCRIPCION = "Inscripcion escolar"
CONCEPTO_IVA_INSCRIPCION = "IVA inscripcion 16%"


def ensure_inscripcion_sale(inscripcion, requiere_factura: bool = False) -> dict:
    """
    Garantiza que cada inscripcion tenga su orden de venta y sus partidas.
    - Base: 1000.00 MXN
    - Si requiere factura: agrega IVA 16%
    """
    # Función idempotente: puede invocarse múltiples veces para la misma inscripción
    # sin duplicar la orden ni sus partidas; get_or_create garantiza unicidad.
    orden, _ = OrdenPOS.objects.get_or_create(
        inscripcion=inscripcion,
        defaults={
            "fecha_emision": timezone.now(),
            "estado": OrdenPOS.ESTADO_PENDIENTE,
        },
    )

    concepto_base, _ = Concepto.objects.get_or_create(
        nombre=CONCEPTO_INSCRIPCION,
        defaults={
            "precio": INSCRIPCION_PRECIO_BASE,
            "activo": True,
        },
    )

    OrdenItem.objects.update_or_create(
        orden=orden,
        concepto=concepto_base,
        defaults={
            "cantidad": 1,
            "precio_unit": INSCRIPCION_PRECIO_BASE,
        },
    )

    concepto_iva, _ = Concepto.objects.get_or_create(
        nombre=CONCEPTO_IVA_INSCRIPCION,
        defaults={
            "precio": INSCRIPCION_IVA,
            "activo": True,
        },
    )

    # La partida de IVA se agrega o elimina según el indicador de facturación;
    # evita cobros fiscales incorrectos si el alumno cambia de modalidad de pago.
    if requiere_factura:
        OrdenItem.objects.update_or_create(
            orden=orden,
            concepto=concepto_iva,
            defaults={
                "cantidad": 1,
                "precio_unit": INSCRIPCION_IVA,
            },
        )
    else:
        OrdenItem.objects.filter(orden=orden, concepto=concepto_iva).delete()

    total = orden.total_calculado
    return {
        "orden_id": orden.pk,
        "monto_base": INSCRIPCION_PRECIO_BASE,
        "monto_iva": INSCRIPCION_IVA if requiere_factura else Decimal("0.00"),
        "total": total,
        "requiere_factura": bool(requiere_factura),
    }
