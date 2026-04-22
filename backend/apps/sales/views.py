# apps/ui/views_sales.py
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from functools import wraps
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.deletion import ProtectedError
from django.db.utils import IntegrityError
from django.utils import timezone

from apps.accounts.models import Rol, UsuarioRol
from apps.governance.services.audit import log_event
from apps.school.models import Alumno, Grupo, Inscripcion
from apps.sales.services.enrollment_sales import ensure_inscripcion_sale
from apps.ui.input_validation import (
    validate_auth_code,
    validate_choice,
    validate_cp5,
    validate_curp_value,
    validate_email_value,
    validate_human_name,
    validate_matricula_value,
    validate_password_strength,
    validate_phone,
    validate_required_text,
    validate_rfc13,
    validate_text_general,
    validate_username_value,
)

# Intentamos importar modelos reales de ventas. Si cambian, no truena todo.
try:
    from apps.sales.models import AlertaStock, Concepto, CorteCaja, Existencia, OrdenPOS, Pago, Ticket
except Exception:  # pragma: no cover
    AlertaStock = None
    Concepto = None
    CorteCaja = None
    Existencia = None
    OrdenPOS = None
    Pago = None
    Ticket = None


def _corte_existente_hoy():
    if not CorteCaja:
        return None
    return CorteCaja.objects.filter(fecha_operacion=timezone.localdate()).first()


def _rol_codigo(user):
    if not user.is_authenticated:
        return None
    ur = UsuarioRol.objects.select_related("rol").filter(usuario=user).first()
    return ur.rol.codigo if ur and ur.rol else None


def _can_manage_accounts(user) -> bool:
    if user.is_superuser:
        return True
    return _rol_codigo(user) == "ADMINISTRATIVO_COMERCIAL"


def _resolve_role(code: str):
    if not code:
        return None
    return Rol.objects.filter(codigo=code, activo=True).first()


def _create_cliente_profile_if_available(user, payload):
    """Si existe modelo Cliente en el proyecto, crea perfil asociado; si no, omite."""
    try:
        from apps.sales.models import Cliente  # type: ignore
    except Exception:
        return {"cliente_profile": "not_applicable"}

    fields = {f.name for f in Cliente._meta.fields}
    kwargs = {}
    if "usuario" in fields:
        kwargs["usuario"] = user
    if "correo" in fields:
        kwargs["correo"] = payload.get("correo", "")
    if "nombre" in fields:
        kwargs["nombre"] = payload.get("nombre", "")
    if "rfc" in fields:
        kwargs["rfc"] = payload.get("rfc", "")
    if "curp" in fields:
        kwargs["curp"] = payload.get("curp", "")
    if "activo" in fields:
        kwargs["activo"] = True

    cliente = Cliente.objects.create(**kwargs)
    return {"cliente_profile": "created", "cliente_id": getattr(cliente, "pk", None)}


def role_required_codes(*allowed_codes):
    """Permite acceso por código de rol (SUPERUSUARIO siempre pasa por is_superuser)."""
    def deco(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            code = _rol_codigo(request.user)
            if code in allowed_codes:
                return view_func(request, *args, **kwargs)

            return render(
                request,
                "ui/forbidden.html",
                {"role": code or "Usuario",
                    "allowed": ", ".join(allowed_codes)},
                status=403,
            )
        return _wrapped
    return deco


def _notify_stock_alert(alerta_data: dict) -> None:
    """Envía correo de notificación activa al responsable cuando un concepto alcanza stock mínimo.

    Usa fail_silently=True para no bloquear la transacción de venta ante fallos SMTP.
    Los errores quedan en el log de Django (django.request / django.server).
    """
    from django.conf import settings
    import logging

    logger = logging.getLogger("django")

    concepto = alerta_data.get("concepto", "")
    stock_actual = alerta_data.get("stock_actual", "")
    stock_minimo = alerta_data.get("stock_minimo", "")
    destinatario = getattr(settings, "CONTACT_EMAIL", None) or getattr(
        settings, "DEFAULT_FROM_EMAIL", "noreply@joca.local"
    )
    remitente = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@joca.local")
    site_name = getattr(settings, "SITE_NAME", "CCENT")

    asunto = f"[{site_name}] Alerta de stock mínimo: {concepto}"
    cuerpo = (
        f"El concepto '{concepto}' ha alcanzado o superado su stock mínimo.\n\n"
        f"  Stock actual : {stock_actual}\n"
        f"  Stock mínimo : {stock_minimo}\n\n"
        f"Por favor revisa el inventario en el panel de ventas.\n"
        f"Este es un aviso automático del sistema {site_name}."
    )

    try:
        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=remitente,
            recipient_list=[destinatario],
            fail_silently=False,
        )
        logger.info(
            "[VENTAS][STOCK_ALERT] Correo enviado a %s — concepto: %s stock_actual=%s",
            destinatario,
            concepto,
            stock_actual,
        )
    except Exception as exc:
        logger.error(
            "[VENTAS][STOCK_ALERT] Error al enviar correo a %s: %s",
            destinatario,
            exc,
        )


@login_required(login_url="/acceso/")
@role_required_codes("ADMINISTRATIVO_COMERCIAL", "DIRECTOR_ESCOLAR", "ALUMNO", "SUPERUSUARIO")
def ventas_home(request):
    # Nota: aunque permitimos varios roles aquí, en la práctica tu NAV/Permisos decide qué ve cada quien.
    conceptos_count = Concepto.objects.count() if Concepto else 0
    ordenes_count = OrdenPOS.objects.count() if OrdenPOS else 0
    pagos_count = Pago.objects.count() if Pago else 0
    today = timezone.localdate()

    ordenes_hoy = 0
    total_ventas_hoy = Decimal("0.00")
    pagos_hoy = 0
    total_pagos_hoy = Decimal("0.00")
    alertas_stock_count = 0
    alertas_stock = []

    if OrdenPOS:
        ordenes_hoy = OrdenPOS.objects.filter(
            fecha_emision__date=today).count()
        total_expr = ExpressionWrapper(
            F("items__cantidad") * F("items__precio_unit"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        total_ventas_hoy = (
            OrdenPOS.objects.filter(fecha_emision__date=today)
            .aggregate(total=Sum(total_expr))
            .get("total")
            or Decimal("0.00")
        )

    if Pago:
        pagos_hoy = Pago.objects.filter(fecha_pago__date=today).count()
        total_pagos_hoy = (
            Pago.objects.filter(fecha_pago__date=today).aggregate(
                total=Sum("monto")).get("total")
            or Decimal("0.00")
        )

    ordenes_abiertas = 0
    if OrdenPOS:
        ordenes_abiertas = OrdenPOS.objects.filter(
            estado__in=[OrdenPOS.ESTADO_PENDIENTE, OrdenPOS.ESTADO_PARCIAL]
        ).count()

    if AlertaStock:
        alertas_stock_count = AlertaStock.objects.filter(activa=True).count()
        alertas_stock = list(
            AlertaStock.objects.select_related("existencia", "existencia__concepto").filter(
                activa=True).order_by("-generado_en")[:3]
        )

    indicadores = {
        "fecha": today,
        "ordenes_hoy": ordenes_hoy,
        "ventas_hoy": total_ventas_hoy,
        "pagos_hoy": pagos_hoy,
        "cobranza_hoy": total_pagos_hoy,
        "ordenes_abiertas": ordenes_abiertas,
        "alertas_stock": alertas_stock_count,
    }

    corte_hoy = _corte_existente_hoy()

    cards = [
        {"title": "Catálogo",
            "desc": f"Conceptos/servicios ({conceptos_count})", "href": "/panel/ventas/catalogo/"},
        {"title": "Ventas a alumnos",
            "desc": f"Ventas registradas ({ordenes_count})", "href": "/panel/ventas/pos/"},
        {"title": "Estado de cuenta",
            "desc": f"Pagos registrados ({pagos_count})", "href": "/panel/ventas/estado-cuenta/"},
        {
            "title": "Corte de caja",
            "desc": "Cierre diario con resumen y bloqueo posterior.",
            "href": "/panel/ventas/corte-caja/",
        },
        {
            "title": "Compras e inventario",
            "desc": "HU-FUT-002: captura mínima de compra para entrada de inventario.",
            "href": "/panel/ventas/inventario/compras/",
        },
        {
            "title": "Proveedores",
            "desc": "HU-FUT-003: alta rápida de proveedor para flujo de compras.",
            "href": "/panel/ventas/inventario/proveedores/",
        },
        {
            "title": "Datos fiscales",
            "desc": "HU-FUT-005: captura opcional para facturación.",
            "href": "/panel/ventas/facturacion/datos-fiscales/",
        },
    ]

    accesos = [
        {"title": "Catálogo", "href": "/panel/ventas/catalogo/"},
        {"title": "Ventas a alumnos", "href": "/panel/ventas/pos/"},
        {"title": "Estado de cuenta", "href": "/panel/ventas/estado-cuenta/"},
        {"title": "Corte de caja", "href": "/panel/ventas/corte-caja/"},
        {"title": "Compras e inventario", "href": "/panel/ventas/inventario/compras/"},
    ]

    if _can_manage_accounts(request.user):
        cards.append(
            {
                "title": "Control de cuentas",
                "desc": "Alta interna de cuentas (alumno/cliente y cuentas especiales para superuser).",
                "href": "/panel/ventas/cuentas/",
            }
        )

    if alertas_stock_count:
        cards.append(
            {
                "title": "Alertas de inventario",
                "desc": f"{alertas_stock_count} concepto(s) en stock mínimo.",
                "href": "/panel/ventas/inventario/compras/",
            }
        )

    return render(
        request,
        "ui/ventas/home.html",
        {
            "cards": cards,
            "accesos": accesos,
            "indicadores": indicadores,
            "alertas_stock": alertas_stock,
            "corte_hoy": corte_hoy,
        },
    )


@login_required(login_url="/acceso/")
@role_required_codes("ADMINISTRATIVO_COMERCIAL", "SUPERUSUARIO")
def ventas_catalogo(request):
    if not Concepto:
        messages.error(request, "El módulo de catálogo no está disponible.")
        return render(
            request,
            "ui/ventas/catalogo.html",
            {"conceptos": [], "editing_concepto": None},
        )

    if request.method == "POST":
        delete_id = (request.POST.get("delete_id") or "").strip()
        if delete_id:
            concepto = Concepto.objects.filter(pk=delete_id).first()
            if not concepto:
                messages.error(request, "Concepto no encontrado.")
                return redirect("/panel/ventas/catalogo/")

            concept_pk = concepto.pk
            concept_name = concepto.nombre
            try:
                concepto.delete()
                log_event(
                    request,
                    accion="CATALOGO::CONCEPTO_DELETE",
                    entidad="Concepto",
                    entidad_id=concept_pk,
                    resultado="ok",
                    detalle={"nombre": concept_name},
                )
                messages.success(request, "Concepto eliminado correctamente.")
            except (ProtectedError, IntegrityError):
                concepto.activo = False
                concepto.save(update_fields=["activo"])
                log_event(
                    request,
                    accion="CATALOGO::CONCEPTO_DELETE_SOFT",
                    entidad="Concepto",
                    entidad_id=concept_pk,
                    resultado="ok",
                    detalle={"nombre": concept_name, "reason": "referenced"},
                )
                messages.warning(
                    request,
                    "El concepto no puede eliminarse porque tiene movimientos; se desactivó automáticamente.",
                )
            return redirect("/panel/ventas/catalogo/")

        toggle_id = request.POST.get("toggle_id")
        if toggle_id:
            concepto = Concepto.objects.filter(pk=toggle_id).first()
            if not concepto:
                messages.error(request, "Concepto no encontrado.")
                return redirect("/panel/ventas/catalogo/")

            concepto.activo = not concepto.activo
            concepto.save(update_fields=["activo"])
            log_event(
                request,
                accion="CATALOGO::CONCEPTO_TOGGLE",
                entidad="Concepto",
                entidad_id=concepto.pk,
                resultado="ok",
                detalle={"nombre": concepto.nombre,
                         "activo": concepto.activo},
            )
            estado = "activado" if concepto.activo else "desactivado"
            messages.success(request, f"Concepto {estado} correctamente.")
            return redirect("/panel/ventas/catalogo/")

        concepto_id = (request.POST.get("concepto_id") or "").strip()
        nombre = (request.POST.get("nombre") or "").strip()
        precio_raw = (request.POST.get("precio") or "").strip()
        activo = (request.POST.get("activo") or "") == "on"
        inventario_habilitado = (request.POST.get(
            "inventario_habilitado") or "") == "on"
        stock_actual_raw = (request.POST.get("stock_actual") or "0").strip()
        stock_minimo_raw = (request.POST.get("stock_minimo") or "0").strip()

        try:
            nombre = validate_required_text(nombre, "Nombre del concepto")
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect("/panel/ventas/catalogo/")

        try:
            precio = Decimal(precio_raw)
        except (InvalidOperation, TypeError):
            messages.error(request, "El precio debe ser numérico.")
            return redirect("/panel/ventas/catalogo/")

        if precio < 0:
            messages.error(request, "El precio no puede ser negativo.")
            return redirect("/panel/ventas/catalogo/")

        try:
            stock_actual = Decimal(stock_actual_raw)
        except (InvalidOperation, TypeError):
            stock_actual = Decimal("0")

        try:
            stock_minimo = Decimal(stock_minimo_raw)
        except (InvalidOperation, TypeError):
            stock_minimo = Decimal("0")

        if stock_actual < 0:
            messages.error(request, "El stock actual no puede ser negativo.")
            return redirect("/panel/ventas/catalogo/")

        if stock_minimo < 0:
            messages.error(request, "El stock mínimo no puede ser negativo.")
            return redirect("/panel/ventas/catalogo/")

        dup_qs = Concepto.objects.filter(nombre__iexact=nombre)
        if concepto_id:
            dup_qs = dup_qs.exclude(pk=concepto_id)
        if dup_qs.exists():
            messages.error(request, "Ya existe un concepto con ese nombre.")
            return redirect("/panel/ventas/catalogo/")

        if concepto_id:
            concepto = Concepto.objects.filter(pk=concepto_id).first()
            if not concepto:
                messages.error(request, "Concepto no encontrado.")
                return redirect("/panel/ventas/catalogo/")

            concepto.nombre = nombre
            concepto.precio = precio
            concepto.activo = activo
            concepto.save(update_fields=["nombre", "precio", "activo"])
            accion = "CATALOGO::CONCEPTO_UPDATE"
            msg = "Concepto actualizado."
        else:
            concepto = Concepto.objects.create(
                nombre=nombre,
                precio=precio,
                activo=activo,
            )
            accion = "CATALOGO::CONCEPTO_CREATE"
            msg = "Concepto creado."

        if Existencia:
            Existencia.objects.update_or_create(
                concepto=concepto,
                defaults={
                    "inventario_habilitado": inventario_habilitado,
                    "stock_actual": stock_actual,
                    "stock_minimo": stock_minimo,
                },
            )

        log_event(
            request,
            accion=accion,
            entidad="Concepto",
            entidad_id=concepto.pk,
            resultado="ok",
            detalle={
                "nombre": concepto.nombre,
                "precio": str(concepto.precio),
                "activo": concepto.activo,
                "inventario_habilitado": inventario_habilitado,
            },
        )
        messages.success(request, msg)
        return redirect("/panel/ventas/catalogo/")

    edit_id = request.GET.get("edit")
    editing_concepto = (
        Concepto.objects.select_related(
            "existencia").filter(pk=edit_id).first()
        if edit_id else None
    )
    conceptos_qs = Concepto.objects.select_related(
        "existencia").order_by("-id")
    paginator = Paginator(conceptos_qs, 3)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "ui/ventas/catalogo.html",
        {
            "page_obj": page_obj,
            "editing_concepto": editing_concepto,
        },
    )


@login_required(login_url="/acceso/")
@role_required_codes("ADMINISTRATIVO_COMERCIAL", "SUPERUSUARIO")
def ventas_pos(request):
    if not (OrdenPOS and Pago and Concepto and Ticket and Inscripcion):
        messages.error(
            request, "El módulo de ventas a alumnos no está disponible.")
        return render(
            request,
            "ui/ventas/pos.html",
            {"page_obj": None, "inscripciones": [], "conceptos": []},
        )

    if request.method == "POST":
        corte_hoy = _corte_existente_hoy()
        if corte_hoy and not request.user.is_superuser:
            log_event(
                request,
                accion="VENTAS::MOVIMIENTO_DENEGADO_POST_CORTE",
                entidad="CorteCaja",
                entidad_id=corte_hoy.pk,
                resultado="denied",
                detalle={"modulo": "pos", "fecha_operacion": str(
                    corte_hoy.fecha_operacion)},
            )
            messages.error(
                request, "Caja ya cerrada para hoy. No se permiten nuevas ventas.")
            return redirect("/panel/ventas/pos/")

        inscripcion_id = (request.POST.get("inscripcion_id") or "").strip()
        concepto_id = (request.POST.get("concepto_id") or "").strip()
        cantidad_raw = (request.POST.get("cantidad") or "1").strip()
        metodo = (request.POST.get("metodo") or "EFECTIVO").strip().upper()
        descuento_pct_raw = (request.POST.get("descuento_pct") or "0").strip()
        descuento_motivo = (request.POST.get("descuento_motivo") or "").strip()
        autoriza_username = (request.POST.get(
            "autoriza_username") or "").strip()

        inscripcion = Inscripcion.objects.select_related("grupo", "alumno").filter(
            pk=inscripcion_id).first() if inscripcion_id else None
        concepto = Concepto.objects.filter(
            pk=concepto_id, activo=True).first() if concepto_id else None

        if not inscripcion:
            messages.error(request, "Selecciona una inscripción válida.")
            return redirect("/panel/ventas/pos/")
        if not concepto:
            messages.error(request, "Selecciona un concepto activo.")
            return redirect("/panel/ventas/pos/")

        try:
            metodo = validate_choice(
                metodo,
                {"EFECTIVO", "TARJETA", "TRANSFERENCIA"},
                "Método de pago",
            )
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect("/panel/ventas/pos/")

        try:
            cantidad = int(cantidad_raw)
        except ValueError:
            cantidad = 0
        if cantidad <= 0:
            messages.error(request, "La cantidad debe ser mayor a 0.")
            return redirect("/panel/ventas/pos/")

        try:
            descuento_pct = Decimal(descuento_pct_raw)
        except (InvalidOperation, TypeError):
            messages.error(request, "El descuento debe ser numérico.")
            return redirect("/panel/ventas/pos/")

        if descuento_pct < 0 or descuento_pct > 100:
            messages.error(request, "El descuento debe estar entre 0 y 100.")
            return redirect("/panel/ventas/pos/")

        autoriza_user = None
        if descuento_pct > 0:
            try:
                descuento_motivo = validate_text_general(
                    descuento_motivo,
                    "Motivo del descuento",
                    min_length=3,
                    max_length=300,
                )
            except Exception as exc:
                messages.error(request, str(exc))
                return redirect("/panel/ventas/pos/")

            if not autoriza_username and request.user.is_superuser:
                autoriza_username = request.user.username

            if not autoriza_username:
                messages.error(
                    request, "Indica usuario que autoriza el descuento.")
                return redirect("/panel/ventas/pos/")

            try:
                autoriza_username = validate_username_value(autoriza_username)
            except Exception as exc:
                messages.error(request, str(exc))
                return redirect("/panel/ventas/pos/")

            autoriza_user = get_user_model().objects.filter(
                username=autoriza_username, is_active=True).first()
            if not autoriza_user:
                messages.error(
                    request, "No existe el usuario autorizador del descuento.")
                return redirect("/panel/ventas/pos/")

            rol_autoriza = _rol_codigo(autoriza_user)
            if not (autoriza_user.is_superuser or rol_autoriza == "DIRECTOR_ESCOLAR"):
                messages.error(
                    request, "El descuento requiere autorización de Director Escolar o Superusuario.")
                return redirect("/panel/ventas/pos/")

            if not request.user.is_superuser and descuento_pct > Decimal("30.00"):
                messages.error(
                    request, "El descuento supera el tope autorizado para este rol (30%).")
                return redirect("/panel/ventas/pos/")

        periodo = (inscripcion.grupo.periodo or "").strip()
        if not periodo:
            messages.error(request, "La inscripción no tiene período válido.")
            return redirect("/panel/ventas/pos/")

        precio_unit = Decimal(concepto.precio)
        cantidad_decimal = Decimal(cantidad)
        subtotal = (precio_unit * Decimal(cantidad)).quantize(Decimal("0.01"))
        descuento_monto = (subtotal * (descuento_pct /
                           Decimal("100"))).quantize(Decimal("0.01"))
        total = (subtotal - descuento_monto).quantize(Decimal("0.01"))
        if total <= 0:
            messages.error(
                request, "El total de la venta debe ser mayor a 0 tras descuento.")
            return redirect("/panel/ventas/pos/")

        alerta_stock_data = None
        try:
            with transaction.atomic():
                existencia = None
                if Existencia:
                    existencia = Existencia.objects.select_for_update().filter(
                        concepto=concepto,
                        inventario_habilitado=True,
                    ).first()
                    if existencia and existencia.stock_actual < cantidad_decimal:
                        raise ValueError("stock_insuficiente")

                orden, _ = OrdenPOS.objects.get_or_create(
                    inscripcion=inscripcion,
                    defaults={"estado": OrdenPOS.ESTADO_PAGADA},
                )
                precio_unit_final = (
                    total / cantidad_decimal).quantize(Decimal("0.01"))
                item_existente = orden.items.filter(concepto=concepto).first()
                if item_existente:
                    item_existente.cantidad += cantidad
                    item_existente.precio_unit = precio_unit_final
                    item_existente.save(
                        update_fields=["cantidad", "precio_unit"])
                else:
                    orden.items.create(
                        concepto=concepto,
                        cantidad=cantidad,
                        precio_unit=precio_unit_final,
                    )
                pago = Pago.objects.create(
                    orden=orden,
                    monto=total,
                    metodo=metodo or "EFECTIVO",
                    auth_code="",
                )
                ticket = Ticket.objects.create(
                    pago=pago,
                    ruta_pdf=f"/panel/ventas/ticket/{pago.pk}.pdf",
                )
                if existencia:
                    existencia.stock_actual = (
                        existencia.stock_actual - cantidad_decimal).quantize(Decimal("0.01"))
                    existencia.save(
                        update_fields=["stock_actual", "actualizado_en"])
                    if existencia.stock_actual <= existencia.stock_minimo:
                        alerta, _ = AlertaStock.objects.update_or_create(
                            existencia=existencia,
                            activa=True,
                            defaults={
                                "stock_actual": existencia.stock_actual,
                                "stock_minimo": existencia.stock_minimo,
                            },
                        )
                        alerta_stock_data = {
                            "alerta_id": alerta.pk,
                            "concepto": concepto.nombre,
                            "stock_actual": str(existencia.stock_actual),
                            "stock_minimo": str(existencia.stock_minimo),
                        }
        except ValueError as exc:
            if str(exc) == "stock_insuficiente":
                messages.error(
                    request, "Stock insuficiente para completar la venta.")
                return redirect("/panel/ventas/pos/")
            raise

        log_event(
            request,
            accion="VENTAS::ORDEN_CREATE",
            entidad="OrdenPOS",
            entidad_id=orden.pk,
            resultado="ok",
            detalle={
                "inscripcion": inscripcion.pk,
                "periodo": periodo,
                "concepto": concepto.nombre,
                "cantidad": cantidad,
                "subtotal": str(subtotal),
                "descuento_pct": str(descuento_pct),
                "descuento_monto": str(descuento_monto),
                "monto": str(total),
            },
        )
        if descuento_pct > 0:
            log_event(
                request,
                accion="VENTAS::DESCUENTO_APLICADO",
                entidad="OrdenPOS",
                entidad_id=orden.pk,
                resultado="ok",
                detalle={
                    "descuento_pct": str(descuento_pct),
                    "descuento_monto": str(descuento_monto),
                    "motivo": descuento_motivo,
                    "autoriza": autoriza_user.username if autoriza_user else autoriza_username,
                },
            )
        if alerta_stock_data:
            log_event(
                request,
                accion="INVENTARIO::STOCK_MINIMO_ALERTA",
                entidad="AlertaStock",
                entidad_id=alerta_stock_data["alerta_id"],
                resultado="ok",
                detalle={
                    "concepto": alerta_stock_data["concepto"],
                    "stock_actual": alerta_stock_data["stock_actual"],
                    "stock_minimo": alerta_stock_data["stock_minimo"],
                },
            )
            messages.warning(
                request,
                f"Alerta de inventario: {alerta_stock_data['concepto']} llegó a stock mínimo.",
            )
            _notify_stock_alert(alerta_stock_data)
        log_event(
            request,
            accion="VENTAS::TICKET_EMIT",
            entidad="Ticket",
            entidad_id=ticket.pk,
            resultado="ok",
            detalle={
                "orden": orden.pk,
                "pago": pago.pk,
                "ruta_pdf": ticket.ruta_pdf,
            },
        )
        messages.success(
            request,
            f"Venta registrada y ticket emitido (orden #{orden.pk}).",
        )
        return redirect(f"/panel/ventas/ticket/{ticket.pk}/")

    inscripciones = Inscripcion.objects.select_related("alumno", "grupo").filter(
        estado="activa").order_by("-fecha_inscripcion")[:200]
    conceptos_activos = Concepto.objects.filter(
        activo=True).order_by("nombre")[:200]
    ordenes_qs = OrdenPOS.objects.select_related(
        "inscripcion", "inscripcion__alumno").order_by("-id")
    page_obj = Paginator(ordenes_qs, 3).get_page(request.GET.get("page", 1))

    return render(
        request,
        "ui/ventas/pos.html",
        {
            "page_obj": page_obj,
            "inscripciones": inscripciones,
            "conceptos": conceptos_activos,
        },
    )


@login_required(login_url="/acceso/")
@role_required_codes("ADMINISTRATIVO_COMERCIAL", "SUPERUSUARIO")
def ventas_estado_cuenta(request):
    if not (Pago and OrdenPOS):
        messages.error(request, "El módulo de pagos no está disponible.")
        return render(
            request,
            "ui/ventas/estado_cuenta.html",
            {"pagos": [], "ordenes": []},
        )

    if request.method == "POST":
        corte_hoy = _corte_existente_hoy()
        if corte_hoy and not request.user.is_superuser:
            log_event(
                request,
                accion="VENTAS::MOVIMIENTO_DENEGADO_POST_CORTE",
                entidad="CorteCaja",
                entidad_id=corte_hoy.pk,
                resultado="denied",
                detalle={"modulo": "estado_cuenta",
                         "fecha_operacion": str(corte_hoy.fecha_operacion)},
            )
            messages.error(
                request, "Caja ya cerrada para hoy. No se permiten nuevos pagos.")
            return redirect("/panel/ventas/estado-cuenta/")

        orden_id = (request.POST.get("orden_id") or "").strip()
        monto_raw = (request.POST.get("monto") or "").strip()
        metodo = (request.POST.get("metodo") or "EFECTIVO").strip().upper()
        auth_code = (request.POST.get("auth_code") or "").strip()

        orden = OrdenPOS.objects.select_related(
            "inscripcion", "inscripcion__alumno").filter(pk=orden_id).first()
        if not orden:
            messages.error(request, "Selecciona una orden válida.")
            return redirect("/panel/ventas/estado-cuenta/")

        try:
            monto = Decimal(monto_raw)
        except (InvalidOperation, TypeError):
            messages.error(request, "El monto del pago debe ser numérico.")
            return redirect("/panel/ventas/estado-cuenta/")

        if monto <= 0:
            messages.error(request, "El monto del pago debe ser mayor a 0.")
            return redirect("/panel/ventas/estado-cuenta/")

        try:
            metodo = validate_choice(
                metodo,
                {"EFECTIVO", "TARJETA", "TRANSFERENCIA", "OTRO"},
                "Método de pago",
            )
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect("/panel/ventas/estado-cuenta/")

        if auth_code:
            try:
                auth_code = validate_auth_code(auth_code, "Referencia de pago")
            except Exception as exc:
                messages.error(request, str(exc))
                return redirect("/panel/ventas/estado-cuenta/")

        if orden.estado == OrdenPOS.ESTADO_CANCELADA:
            messages.error(
                request, "No se pueden registrar pagos en órdenes canceladas.")
            return redirect("/panel/ventas/estado-cuenta/")

        pagado = orden.pagos.aggregate(
            total=Sum("monto")).get("total") or Decimal("0.00")
        saldo = (Decimal(orden.total_calculado) - Decimal(pagado)
                 ).quantize(Decimal("0.01"))
        if monto > saldo:
            messages.error(
                request, "El pago excede el saldo pendiente de la orden.")
            return redirect("/panel/ventas/estado-cuenta/")

        with transaction.atomic():
            pago = Pago.objects.create(
                orden=orden,
                monto=monto,
                metodo=metodo or "EFECTIVO",
                auth_code=auth_code,
            )
            if Ticket:
                Ticket.objects.get_or_create(
                    pago=pago,
                    defaults={
                        "ruta_pdf": f"/panel/ventas/ticket/{pago.pk}.pdf"},
                )

            nuevo_pagado = orden.pagos.aggregate(
                total=Sum("monto")).get("total") or Decimal("0.00")
            if Decimal(nuevo_pagado) >= Decimal(orden.total_calculado):
                orden.estado = OrdenPOS.ESTADO_PAGADA
            elif Decimal(nuevo_pagado) > 0:
                orden.estado = OrdenPOS.ESTADO_PARCIAL
            else:
                orden.estado = OrdenPOS.ESTADO_PENDIENTE
            orden.save(update_fields=["estado"])

        log_event(
            request,
            accion="VENTAS::PAGO_CREATE",
            entidad="Pago",
            entidad_id=pago.pk,
            resultado="ok",
            detalle={
                "orden": orden.pk,
                "monto": str(pago.monto),
                "metodo": pago.metodo,
            },
        )
        messages.success(request, f"Pago registrado para orden #{orden.pk}.")
        ticket_obj = getattr(pago, "ticket", None)
        if ticket_obj:
            return redirect(f"/panel/ventas/ticket/{ticket_obj.pk}/")
        return redirect("/panel/ventas/estado-cuenta/")

    # Ordenes anotadas con total pagado (evita N+1)
    ordenes_ann_qs = (
        OrdenPOS.objects.select_related("inscripcion", "inscripcion__alumno")
        .annotate(pagado_total=Sum("pagos__monto"))
        .order_by("-id")
    )
    # Pre-computar filas completas para paginación
    ordenes_all = []
    for orden in ordenes_ann_qs:
        pagado = Decimal(orden.pagado_total or 0).quantize(Decimal("0.01"))
        saldo = (Decimal(orden.total_calculado) -
                 pagado).quantize(Decimal("0.01"))
        ordenes_all.append({"obj": orden, "pagado": pagado, "saldo": saldo})

    ordenes_page = Paginator(ordenes_all, 3).get_page(
        request.GET.get("opage", 1))

    # Dropdown de órdenes abiertas (no canceladas y con saldo > 0)
    ordenes_abiertas = [row for row in ordenes_all
                        if row["obj"].estado != OrdenPOS.ESTADO_CANCELADA
                        and row["saldo"] > 0]

    pagos_qs = Pago.objects.select_related(
        "orden", "orden__inscripcion", "orden__inscripcion__alumno"
    ).order_by("-id")
    pagos_page = Paginator(pagos_qs, 3).get_page(request.GET.get("ppage", 1))

    log_event(
        request,
        accion="VENTAS::ESTADO_CUENTA_CONSULTA",
        entidad="Pago",
        resultado="ok",
        detalle={"ordenes_visibles": len(ordenes_all)},
    )

    return render(
        request,
        "ui/ventas/estado_cuenta.html",
        {
            "ordenes_page": ordenes_page,
            "ordenes_abiertas": ordenes_abiertas,
            "pagos_page": pagos_page,
        },
    )


@login_required(login_url="/acceso/")
@role_required_codes("ADMINISTRATIVO_COMERCIAL", "SUPERUSUARIO")
def ventas_corte_caja(request):
    if not (CorteCaja and OrdenPOS and Pago):
        messages.error(
            request, "El módulo de corte de caja no está disponible.")
        return render(
            request,
            "ui/ventas/corte_caja.html",
            {
                "fecha": timezone.localdate(),
                "resumen": {
                    "ordenes": 0,
                    "monto_ordenes": Decimal("0.00"),
                    "pagos": 0,
                    "monto_pagos": Decimal("0.00"),
                },
                "corte_hoy": None,
                "cortes": [],
            },
        )

    hoy = timezone.localdate()
    corte_hoy = CorteCaja.objects.filter(fecha_operacion=hoy).first()
    ordenes_hoy_qs = OrdenPOS.objects.filter(fecha_emision__date=hoy)
    pagos_hoy_qs = Pago.objects.filter(fecha_pago__date=hoy)
    resumen_calc = CorteCaja.resumen_calculado(hoy)

    resumen = {
        "ordenes": ordenes_hoy_qs.count(),
        "monto_ordenes": resumen_calc["monto_ordenes"],
        "pagos": pagos_hoy_qs.count(),
        "monto_pagos": resumen_calc["monto_pagos"],
    }

    if request.method == "POST":
        confirm = (request.POST.get("confirmar") or "").strip().upper()
        notas = (request.POST.get("notas") or "").strip()

        try:
            notas = validate_text_general(
                notas,
                "Notas",
                allow_blank=True,
                min_length=0,
                max_length=400,
            )
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect("/panel/ventas/corte-caja/")

        if corte_hoy:
            messages.error(request, "Ya existe corte de caja para hoy.")
            return redirect("/panel/ventas/corte-caja/")

        if confirm != "SI":
            messages.error(request, "Confirma el corte escribiendo SI.")
            return redirect("/panel/ventas/corte-caja/")

        corte = CorteCaja.objects.create(
            fecha_operacion=hoy,
            total_ordenes=resumen["ordenes"],
            total_pagos=resumen["pagos"],
            notas=notas,
            realizado_por=request.user,
        )
        log_event(
            request,
            accion="VENTAS::CORTE_CAJA",
            entidad="CorteCaja",
            entidad_id=corte.pk,
            resultado="ok",
            detalle={
                "fecha_operacion": str(corte.fecha_operacion),
                "total_ordenes": corte.total_ordenes,
                "monto_ordenes": str(resumen["monto_ordenes"]),
                "total_pagos": corte.total_pagos,
                "monto_pagos": str(resumen["monto_pagos"]),
            },
        )
        messages.success(request, "Corte de caja registrado correctamente.")
        return redirect("/panel/ventas/corte-caja/")

    cortes_qs = CorteCaja.objects.select_related("realizado_por").order_by(
        "-fecha_operacion", "-cerrado_en")
    cortes_page = Paginator(cortes_qs, 3).get_page(request.GET.get("cpage", 1))
    for corte in cortes_page:
        corte_resumen = CorteCaja.resumen_calculado(corte.fecha_operacion)
        corte.monto_ordenes_calc = corte_resumen["monto_ordenes"]
        corte.monto_pagos_calc = corte_resumen["monto_pagos"]
    return render(
        request,
        "ui/ventas/corte_caja.html",
        {
            "fecha": hoy,
            "resumen": resumen,
            "corte_hoy": corte_hoy,
            "cortes_page": cortes_page,
        },
    )


@login_required(login_url="/acceso/")
@role_required_codes("ADMINISTRATIVO_COMERCIAL", "SUPERUSUARIO")
def ventas_inventario_compras(request):
    compras = request.session.get("inv_compras_demo", [])

    if any("id" not in item for item in compras):
        normalized = []
        for idx, item in enumerate(compras, start=1):
            normalized.append(
                {
                    "id": str(item.get("id") or idx),
                    "proveedor": item.get("proveedor", ""),
                    "referencia": item.get("referencia", ""),
                    "total": item.get("total", "0.00"),
                }
            )
        compras = normalized
        request.session["inv_compras_demo"] = compras

    edit_id = (request.GET.get("edit") or "").strip()
    editing_compra = next(
        (item for item in compras if str(item.get("id")) == edit_id), None)

    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip().lower()
        item_id = (request.POST.get("item_id") or "").strip()

        if action == "delete":
            before = len(compras)
            compras = [item for item in compras if str(
                item.get("id")) != item_id]
            if len(compras) == before:
                messages.error(request, "Compra no encontrada.")
            else:
                request.session["inv_compras_demo"] = compras
                log_event(
                    request,
                    accion="INVENTARIO::COMPRA_PRECAPTURA_DELETE",
                    entidad="CompraInventario",
                    entidad_id=item_id,
                    resultado="ok",
                    detalle={"item_id": item_id},
                )
                messages.success(request, "Compra eliminada correctamente.")
            return redirect("/panel/ventas/inventario/compras/")

        proveedor = (request.POST.get("proveedor") or "").strip()
        referencia = (request.POST.get("referencia") or "").strip()
        total_raw = (request.POST.get("total") or "").strip()

        try:
            total_val = Decimal(total_raw)
        except Exception:
            total_val = Decimal("-1")

        try:
            proveedor = validate_text_general(
                proveedor,
                "Proveedor",
                min_length=2,
                max_length=120,
            )
            referencia = validate_auth_code(referencia, "Referencia")
        except Exception as exc:
            messages.error(request, str(exc))
            return render(
                request,
                "ui/ventas/inventario_compras.html",
                {"compras": compras, "editing_compra": editing_compra},
            )

        if total_val <= Decimal("0"):
            messages.error(
                request,
                "Captura proveedor, referencia y total mayor a 0 para pre-registrar la compra.",
            )
        else:
            payload = {
                "proveedor": proveedor,
                "referencia": referencia,
                "total": f"{total_val:.2f}",
            }

            existing = next((item for item in compras if str(
                item.get("id")) == item_id), None)
            if existing:
                existing.update(payload)
                accion = "INVENTARIO::COMPRA_PRECAPTURA_UPDATE"
                success_msg = "Compra actualizada correctamente."
                entidad_id = existing.get("id")
            else:
                payload["id"] = str(int(timezone.now().timestamp() * 1000000))
                compras.append(payload)
                compras = compras[-50:]
                accion = "INVENTARIO::COMPRA_PRECAPTURA"
                success_msg = "Compra pre-registrada (MVP incremental)."
                entidad_id = payload.get("id")

            request.session["inv_compras_demo"] = compras
            log_event(
                request,
                accion=accion,
                entidad="CompraInventario",
                entidad_id=entidad_id,
                resultado="ok",
                detalle=payload,
            )
            messages.success(request, success_msg)
            return redirect("/panel/ventas/inventario/compras/")

    # Existencias de materiales para consulta
    existencias_page = None
    if Existencia:
        existencias_qs = (
            Existencia.objects.select_related("concepto")
            .filter(inventario_habilitado=True)
            .order_by("concepto__nombre")
        )
        epage_number = request.GET.get("epage", 1)
        existencias_page = Paginator(existencias_qs, 3).get_page(epage_number)

    return render(
        request,
        "ui/ventas/inventario_compras.html",
        {
            "compras": compras,
            "editing_compra": editing_compra,
            "existencias_page": existencias_page,
        },
    )


@login_required(login_url="/acceso/")
@role_required_codes("ADMINISTRATIVO_COMERCIAL", "SUPERUSUARIO")
def ventas_inventario_proveedores(request):
    proveedores = request.session.get("inv_proveedores_demo", [])
    if any("id" not in item for item in proveedores):
        normalized = []
        for idx, item in enumerate(proveedores, start=1):
            normalized.append(
                {
                    "id": str(item.get("id") or idx),
                    "nombre": item.get("nombre", ""),
                    "rfc": item.get("rfc", ""),
                    "curp": item.get("curp", ""),
                    "contacto": item.get("contacto", ""),
                }
            )
        proveedores = normalized
        request.session["inv_proveedores_demo"] = proveedores

    edit_id = (request.GET.get("edit") or "").strip()
    editing_proveedor = next(
        (item for item in proveedores if str(item.get("id")) == edit_id), None)

    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip().lower()
        item_id = (request.POST.get("item_id") or "").strip()

        if action == "delete":
            before = len(proveedores)
            proveedores = [item for item in proveedores if str(
                item.get("id")) != item_id]
            if len(proveedores) == before:
                messages.error(request, "Proveedor no encontrado.")
            else:
                request.session["inv_proveedores_demo"] = proveedores
                log_event(
                    request,
                    accion="INVENTARIO::PROVEEDOR_PREALTA_DELETE",
                    entidad="Proveedor",
                    entidad_id=item_id,
                    resultado="ok",
                    detalle={"item_id": item_id},
                )
                messages.success(request, "Proveedor eliminado correctamente.")
            return redirect("/panel/ventas/inventario/proveedores/")

        nombre = (request.POST.get("nombre") or "").strip()
        rfc = (request.POST.get("rfc") or "").strip().upper()
        curp = (request.POST.get("curp") or "").strip().upper()
        contacto = (request.POST.get("contacto") or "").strip()

        try:
            nombre = validate_text_general(
                nombre,
                "Nombre del proveedor",
                min_length=2,
                max_length=120,
            )
            if rfc:
                rfc = validate_rfc13(rfc)
            if curp:
                curp = validate_curp_value(curp, "CURP")
            contacto = validate_text_general(
                contacto,
                "Contacto",
                allow_blank=True,
                min_length=0,
                max_length=120,
            )
        except Exception as exc:
            messages.error(request, str(exc))
            return render(
                request,
                "ui/ventas/inventario_proveedores.html",
                {"proveedores": proveedores, "editing_proveedor": editing_proveedor},
            )

        item = {"nombre": nombre, "rfc": rfc,
                "curp": curp, "contacto": contacto}
        existing = next((provider for provider in proveedores if str(
            provider.get("id")) == item_id), None)
        if existing:
            existing.update(item)
            accion = "INVENTARIO::PROVEEDOR_PREALTA_UPDATE"
            success_msg = "Proveedor actualizado correctamente."
            entidad_id = existing.get("id")
        else:
            item["id"] = str(int(timezone.now().timestamp() * 1000000))
            proveedores.append(item)
            proveedores = proveedores[-50:]
            accion = "INVENTARIO::PROVEEDOR_PREALTA"
            success_msg = "Proveedor pre-registrado (MVP incremental)."
            entidad_id = item.get("id")

        request.session["inv_proveedores_demo"] = proveedores
        log_event(
            request,
            accion=accion,
            entidad="Proveedor",
            entidad_id=entidad_id,
            resultado="ok",
            detalle=item,
        )
        messages.success(request, success_msg)
        return redirect("/panel/ventas/inventario/proveedores/")

    return render(
        request,
        "ui/ventas/inventario_proveedores.html",
        {"proveedores": proveedores, "editing_proveedor": editing_proveedor},
    )


@login_required(login_url="/acceso/")
@role_required_codes("ADMINISTRATIVO_COMERCIAL", "SUPERUSUARIO")
def ventas_datos_fiscales(request):
    if request.method == "POST":
        requiere_factura = (request.POST.get("requiere_factura") or "") == "on"
        razon_social = (request.POST.get("razon_social") or "").strip()
        rfc = (request.POST.get("rfc") or "").strip().upper()
        cp_fiscal = (request.POST.get("cp_fiscal") or "").strip()

        if requiere_factura:
            try:
                razon_social = validate_text_general(
                    razon_social,
                    "Razón social",
                    min_length=2,
                    max_length=180,
                )
                rfc = validate_rfc13(rfc, "RFC")
                cp_fiscal = validate_cp5(cp_fiscal, "CP fiscal")
            except Exception as exc:
                messages.error(request, str(exc))
                return render(request, "ui/ventas/datos_fiscales.html")

        log_event(
            request,
            accion="FACTURACION::DATOS_FISCALES_PRECAPTURA",
            entidad="DatosFiscales",
            resultado="ok",
            detalle={
                "requiere_factura": requiere_factura,
                "razon_social": razon_social,
                "rfc": rfc,
                "cp_fiscal": cp_fiscal,
            },
        )
        messages.success(
            request, "Datos fiscales capturados (MVP incremental).")
        return redirect("/panel/ventas/facturacion/datos-fiscales/")

    return render(request, "ui/ventas/datos_fiscales.html")


@login_required(login_url="/acceso/")
@role_required_codes("ADMINISTRATIVO_COMERCIAL", "SUPERUSUARIO")
def ventas_cuentas(request):
    if not _can_manage_accounts(request.user):
        return render(
            request,
            "ui/forbidden.html",
            {"role": _rol_codigo(request.user) or "Usuario",
             "allowed": "SUPERUSUARIO, ADMINISTRATIVO_COMERCIAL"},
            status=403,
        )

    roles = Rol.objects.filter(activo=True).order_by("nombre")
    grupos_escolares = (
        Grupo.objects.select_related("curso_ref", "periodo_ref")
        .filter(estado=Grupo.ESTADO_ACTIVO)
        .order_by("periodo_ref__codigo", "curso_ref__codigo", "turno", "id")
    )
    cupo_disponible_por_grupo = {}
    for g in grupos_escolares:
        ocupados = Inscripcion.objects.filter(
            grupo=g,
            estado=Inscripcion.ESTADO_ACTIVA,
        ).count()
        cupo_disponible = max(int(g.cupo) - int(ocupados), 0)
        cupo_disponible_por_grupo[g.pk] = cupo_disponible
        g.cupo_disponible = cupo_disponible

    def _render_cuentas(status=200):
        return render(
            request,
            "ui/ventas/cuentas.html",
            {
                "roles": roles,
                "grupos_escolares": grupos_escolares,
            },
            status=status,
        )

    if request.method == "POST":
        tipo = (request.POST.get("tipo") or "").strip().lower()
        username = (request.POST.get("username") or "").strip()
        correo = (request.POST.get("correo") or "").strip().lower()
        password = request.POST.get("password") or ""
        role_code = (request.POST.get("role_code") or "").strip().upper()

        if tipo not in {"alumno", "cliente", "usuario"}:
            messages.error(request, "Tipo de cuenta inválido.")
            return _render_cuentas()

        if not request.user.is_superuser and tipo not in {"alumno", "cliente"}:
            log_event(
                request,
                accion="CUENTAS::CREAR_DENEGADO",
                entidad="Usuario",
                resultado="denied",
                detalle={
                    "tipo": tipo,
                    "username": username,
                    "correo": correo,
                    "reason": "non_superuser_tipo_no_permitido",
                },
            )
            messages.error(
                request, "Solo superuser puede crear cuentas generales.")
            return _render_cuentas(status=403)

        if not username or not correo or not password:
            messages.error(
                request, "Usuario, correo y contraseña son obligatorios.")
            return _render_cuentas()

        try:
            username = validate_username_value(username)
            correo = validate_email_value(correo, "Correo")
            validate_password_strength(password, min_length=8)
        except Exception as exc:
            messages.error(request, str(exc))
            return _render_cuentas()

        User = get_user_model()
        if User.objects.filter(username=username).exists() or User.objects.filter(email=correo).exists():
            messages.error(
                request, "Ya existe una cuenta con ese usuario o correo.")
            return _render_cuentas()

        if request.user.is_superuser:
            target_role = _resolve_role(role_code) if role_code else None
            is_staff = (request.POST.get("is_staff") or "") == "on"
            is_superuser = (request.POST.get("is_superuser") or "") == "on"
        else:
            forced_role = "ALUMNO" if tipo == "alumno" else "CLIENTE"
            target_role = _resolve_role(forced_role)
            is_staff = False
            is_superuser = False

        if tipo in {"alumno", "cliente"} and not target_role:
            messages.error(
                request, "No existe rol activo para el tipo de cuenta solicitado.")
            return _render_cuentas()

        if tipo == "alumno":
            grupo_id = (request.POST.get("grupo_id") or "").strip()
            requiere_factura = (request.POST.get(
                "requiere_factura_alumno") or "") == "on"
            nombres = (request.POST.get("nombres") or "").strip()
            apellido_paterno = (request.POST.get(
                "apellido_paterno") or "").strip()
            curp = (request.POST.get("curp") or "").strip().upper()
            rfc = (request.POST.get("rfc") or "").strip().upper()
            try:
                validate_human_name(nombres, "Nombres")
                validate_human_name(apellido_paterno, "Apellido paterno")
                validate_human_name(
                    (request.POST.get("apellido_materno") or "").strip(),
                    "Apellido materno",
                    allow_blank=True,
                )
                validate_phone((request.POST.get("telefono")
                               or "").strip(), "Teléfono", allow_blank=True)
                matricula_candidate = (request.POST.get(
                    "matricula") or "").strip() or username
                validate_matricula_value(matricula_candidate)
                if curp:
                    curp = validate_curp_value(curp, "CURP")
                if rfc:
                    rfc = validate_rfc13(rfc, "RFC")
            except Exception as exc:
                messages.error(request, str(exc))
                return _render_cuentas()

            if not nombres or not apellido_paterno:
                messages.error(
                    request, "Para alumno, nombres y apellido paterno son obligatorios.")
                return _render_cuentas()

            if not grupo_id:
                messages.error(
                    request, "Para alumno debes seleccionar un grupo para registrar su inscripción inicial.")
                return _render_cuentas()

            grupo = Grupo.objects.filter(pk=grupo_id).first()
            if not grupo:
                messages.error(request, "Grupo inválido para inscripción.")
                return _render_cuentas()

            if grupo.estado != Grupo.ESTADO_ACTIVO:
                messages.error(request, "El grupo seleccionado está inactivo.")
                return _render_cuentas()

            ocupados = Inscripcion.objects.filter(
                grupo=grupo,
                estado=Inscripcion.ESTADO_ACTIVA,
            ).count()
            if ocupados >= grupo.cupo:
                messages.error(
                    request, "El grupo seleccionado ya no tiene cupo disponible.")
                return _render_cuentas()

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=correo,
                    password=password,
                )
                user.is_staff = bool(is_staff)
                user.is_superuser = bool(is_superuser)
                user.save(update_fields=["is_staff", "is_superuser"])

                if target_role:
                    UsuarioRol.objects.update_or_create(
                        usuario=user, defaults={"rol": target_role})

                detalle = {
                    "tipo": tipo,
                    "username": username,
                    "correo": correo,
                    "rol": target_role.codigo if target_role else None,
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                }

                if tipo == "alumno":
                    matricula = validate_matricula_value(
                        (request.POST.get("matricula") or "").strip() or username)
                    curp = (request.POST.get("curp") or "").strip().upper()
                    rfc = (request.POST.get("rfc") or "").strip().upper()
                    alumno = Alumno.objects.create(
                        matricula=matricula,
                        nombres=validate_human_name(
                            (request.POST.get("nombres") or "").strip(), "Nombres"),
                        apellido_paterno=validate_human_name(
                            (request.POST.get("apellido_paterno") or "").strip(), "Apellido paterno"),
                        apellido_materno=validate_human_name((request.POST.get(
                            "apellido_materno") or "").strip(), "Apellido materno", allow_blank=True),
                        correo=correo,
                        telefono=validate_phone(
                            (request.POST.get("telefono") or "").strip(), "Teléfono", allow_blank=True),
                        curp=validate_curp_value(
                            curp, "CURP") if curp else None,
                        rfc=validate_rfc13(rfc, "RFC") if rfc else None,
                    )
                    detalle.update(
                        {
                            "alumno_id": alumno.pk,
                            "matricula": matricula,
                            "curp": alumno.curp,
                            "rfc": alumno.rfc,
                        }
                    )

                    inscripcion = Inscripcion.objects.create(
                        alumno=alumno,
                        grupo=grupo,
                        estado=Inscripcion.ESTADO_ACTIVA,
                        fecha_inscripcion=timezone.now().date(),
                    )
                    venta = ensure_inscripcion_sale(
                        inscripcion,
                        requiere_factura=requiere_factura,
                    )
                    detalle.update(
                        {
                            "inscripcion_id": inscripcion.pk,
                            "grupo_id": grupo.pk,
                            "grupo_turno": grupo.turno,
                            "grupo_periodo": grupo.periodo,
                            "orden_venta_id": venta["orden_id"],
                            "inscripcion_precio_base": str(venta["monto_base"]),
                            "inscripcion_iva": str(venta["monto_iva"]),
                            "inscripcion_total": str(venta["total"]),
                            "requiere_factura": venta["requiere_factura"],
                        }
                    )

                if tipo == "cliente":
                    cliente_rfc = (request.POST.get(
                        "cliente_rfc") or "").strip().upper()
                    cliente_curp = (request.POST.get(
                        "cliente_curp") or "").strip().upper()
                    if cliente_rfc:
                        cliente_rfc = validate_rfc13(
                            cliente_rfc, "RFC cliente")
                    if cliente_curp:
                        cliente_curp = validate_curp_value(
                            cliente_curp, "CURP cliente")
                    detalle.update(_create_cliente_profile_if_available(
                        user,
                        {
                            "correo": correo,
                            "nombre": username,
                            "rfc": cliente_rfc,
                            "curp": cliente_curp,
                        },
                    ))
                    detalle.update({"cliente_rfc": cliente_rfc,
                                   "cliente_curp": cliente_curp})

                log_event(
                    request,
                    accion="CUENTAS::CREAR",
                    entidad="Usuario",
                    entidad_id=user.pk,
                    resultado="ok",
                    detalle=detalle,
                )
        except IntegrityError:
            messages.error(
                request, "No fue posible crear la cuenta por conflicto de datos.")
            return _render_cuentas()

        messages.success(request, "Cuenta creada correctamente.")
        return redirect("/panel/ventas/cuentas/")

    return _render_cuentas()


@login_required(login_url="/acceso/")
@role_required_codes("ADMINISTRATIVO_COMERCIAL", "SUPERUSUARIO", "ALUMNO", "DIRECTOR_ESCOLAR")
def ventas_ticket(request, ticket_id):
    if not (Ticket and Pago and OrdenPOS):
        messages.error(
            request, "El módulo de comprobantes no está disponible.")
        return redirect("/panel/ventas/estado-cuenta/")

    ticket = (
        Ticket.objects.select_related(
            "pago",
            "pago__orden",
            "pago__orden__inscripcion",
            "pago__orden__inscripcion__alumno",
            "pago__orden__inscripcion__grupo",
        )
        .filter(pk=ticket_id)
        .first()
    )
    if not ticket:
        messages.error(request, "Comprobante no encontrado.")
        return redirect("/panel/ventas/estado-cuenta/")

    pago = ticket.pago
    orden = pago.orden
    inscripcion = orden.inscripcion
    alumno = inscripcion.alumno

    items = orden.items.select_related("concepto").all()

    log_event(
        request,
        accion="VENTAS::TICKET_VIEW",
        entidad="Ticket",
        entidad_id=ticket.pk,
        resultado="ok",
        detalle={"pago": pago.pk, "orden": orden.pk},
    )

    return render(
        request,
        "ui/ventas/ticket.html",
        {
            "ticket": ticket,
            "pago": pago,
            "orden": orden,
            "inscripcion": inscripcion,
            "alumno": alumno,
            "items": items,
        },
    )
