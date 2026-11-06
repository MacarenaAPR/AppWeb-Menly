from collections import Counter
from datetime import datetime, time

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from menu.models import (
    PedidoEspecial,
    PedidoManual,
    PedidoManualItem,
    PedidoWhatsApp,
    ReporteMetrica,
)


ESTADOS_CANONICOS = {
    PedidoWhatsApp: {
        PedidoWhatsApp.ESTADO_RECIBIDO: "pendiente",
        PedidoWhatsApp.ESTADO_PENDIENTE_CONFIRMACION: "pendiente",
        PedidoWhatsApp.ESTADO_CONFIRMADO: "pendiente",
        PedidoWhatsApp.ESTADO_EN_PREPARACION: "en_preparacion",
        PedidoWhatsApp.ESTADO_LISTO: "listo",
        PedidoWhatsApp.ESTADO_EN_REPARTO: "en_reparto",
        PedidoWhatsApp.ESTADO_ENTREGADO: "entregado",
        PedidoWhatsApp.ESTADO_CANCELADO: "cancelado",
    },
    PedidoManual: {
        PedidoManual.ESTADO_PENDIENTE: "pendiente",
        PedidoManual.ESTADO_PREPARANDO: "en_preparacion",
        PedidoManual.ESTADO_LISTO: "listo",
        PedidoManual.ESTADO_EN_REPARTO: "en_reparto",
        PedidoManual.ESTADO_ENTREGADO: "entregado",
        PedidoManual.ESTADO_CANCELADO: "cancelado",
    },
    PedidoEspecial: {
        PedidoEspecial.ESTADO_PENDIENTE: "pendiente",
        PedidoEspecial.ESTADO_CONFIRMADO: "pendiente",
        PedidoEspecial.ESTADO_EN_PREPARACION: "en_preparacion",
        PedidoEspecial.ESTADO_LISTO: "listo",
        PedidoEspecial.ESTADO_ENTREGADO: "entregado",
        PedidoEspecial.ESTADO_CANCELADO: "cancelado",
    },
}


def _limites_mes(anio, mes):
    inicio = datetime.combine(datetime(anio, mes, 1).date(), time.min)
    if mes == 12:
        siguiente = datetime.combine(datetime(anio + 1, 1, 1).date(), time.min)
    else:
        siguiente = datetime.combine(datetime(anio, mes + 1, 1).date(), time.min)
    zona = timezone.get_current_timezone()
    return timezone.make_aware(inicio, zona), timezone.make_aware(siguiente, zona)


def _cantidad(valor):
    try:
        return max(int(valor or 0), 0)
    except (TypeError, ValueError):
        return 0


def _sumar_estados(destino, modelo, queryset):
    mapa = ESTADOS_CANONICOS[modelo]
    for fila in queryset.values("estado").annotate(total=Count("id")):
        estado = mapa.get(fila["estado"], fila["estado"])
        destino[estado] += fila["total"]


def construir_snapshot_mensual(restaurante, anio, mes):
    inicio, siguiente = _limites_mes(int(anio), int(mes))
    periodo = f"{int(anio):04d}-{int(mes):02d}"

    whatsapp = PedidoWhatsApp.objects.filter(
        restaurante=restaurante,
        fecha_creacion__gte=inicio,
        fecha_creacion__lt=siguiente,
    )
    manuales = PedidoManual.objects.filter(
        restaurante=restaurante,
        fecha_creacion__gte=inicio,
        fecha_creacion__lt=siguiente,
    )
    especiales = PedidoEspecial.objects.filter(
        restaurante=restaurante,
        fecha_creacion__gte=inicio,
        fecha_creacion__lt=siguiente,
    )

    estados = Counter()
    for modelo, queryset in (
        (PedidoWhatsApp, whatsapp),
        (PedidoManual, manuales),
        (PedidoEspecial, especiales),
    ):
        _sumar_estados(estados, modelo, queryset)

    tipos_entrega = Counter()
    for queryset in (whatsapp, manuales):
        for fila in queryset.values("tipo_entrega").annotate(total=Count("id")):
            tipos_entrega[fila["tipo_entrega"]] += fila["total"]
    cantidad_especiales = especiales.count()
    if cantidad_especiales:
        tipos_entrega["especial"] = cantidad_especiales

    whatsapp_comerciales = whatsapp.exclude(estado=PedidoWhatsApp.ESTADO_CANCELADO)
    manuales_comerciales = manuales.exclude(estado=PedidoManual.ESTADO_CANCELADO)
    especiales_comerciales = especiales.exclude(estado=PedidoEspecial.ESTADO_CANCELADO)
    monto = sum(
        int(queryset.aggregate(total=Sum("total"))["total"] or 0)
        for queryset in (whatsapp_comerciales, manuales_comerciales, especiales_comerciales)
    )
    pedidos_comerciales = sum(
        queryset.count()
        for queryset in (whatsapp_comerciales, manuales_comerciales, especiales_comerciales)
    )

    productos = Counter()
    for pedido in whatsapp_comerciales.only("productos_snapshot"):
        for item in pedido.productos_snapshot or []:
            if isinstance(item, dict):
                productos[str(item.get("nombre") or "Producto sin nombre")] += _cantidad(item.get("cantidad"))

    ids_manuales = manuales_comerciales.values("id")
    for fila in (
        PedidoManualItem.objects.filter(pedido_id__in=ids_manuales)
        .values("nombre_producto")
        .annotate(cantidad_total=Sum("cantidad"))
    ):
        productos[fila["nombre_producto"]] += _cantidad(fila["cantidad_total"])

    for pedido in especiales_comerciales.only("items"):
        for item in pedido.items or []:
            if isinstance(item, dict):
                productos[str(item.get("nombre") or "Producto sin nombre")] += _cantidad(item.get("cantidad"))

    total_pedidos = whatsapp.count() + manuales.count() + cantidad_especiales
    cancelados = estados["cancelado"]
    generado = timezone.localtime(timezone.now()).isoformat()
    resumen = {
        "total_pedidos": total_pedidos,
        "pedidos_cancelados": cancelados,
        "monto_pedidos_no_cancelados": monto,
        "ticket_promedio_pedidos_no_cancelados": (
            round(monto / pedidos_comerciales) if pedidos_comerciales else 0
        ),
    }
    datos = {
        "version": 1,
        "restaurante": {
            "id": restaurante.id,
            "nombre": restaurante.nombre_empresa,
            "slug": restaurante.slug,
            "activo_al_generar": restaurante.activo,
        },
        "periodo": periodo,
        "fecha_generacion": generado,
        "zona_horaria": str(timezone.get_current_timezone()),
        "criterio_monetario": (
            "Montos brutos de pedidos no cancelados. El sistema no registra un "
            "estado de pago verificable; estas cifras no representan ingresos cobrados."
        ),
        "resumen": resumen,
        "pedidos_por_estado": dict(sorted(estados.items())),
        "pedidos_por_tipo_entrega": dict(sorted(tipos_entrega.items())),
        "pedidos_por_origen": {
            "whatsapp": whatsapp.count(),
            "menly": manuales.count(),
            "especial": cantidad_especiales,
        },
        "productos_mas_solicitados": [
            {"producto": nombre, "cantidad": cantidad}
            for nombre, cantidad in sorted(
                productos.items(), key=lambda item: (-item[1], item[0].casefold())
            )[:20]
        ],
    }
    return resumen, datos


def guardar_reporte_mensual(restaurante, anio, mes, regenerar=False):
    periodo = f"{int(anio):04d}-{int(mes):02d}"
    filtros = {
        "restaurante": restaurante,
        "tipo": ReporteMetrica.TIPO_MENSUAL,
        "periodo_mes": periodo,
        "activo": True,
    }
    with transaction.atomic():
        existente = ReporteMetrica.objects.select_for_update().filter(**filtros).first()
        if existente and not regenerar:
            return existente, False

        resumen, datos = construir_snapshot_mensual(restaurante, anio, mes)
        defaults = {
            "periodo_anio": f"{int(anio):04d}",
            "titulo": f"Reporte mensual Menly {periodo}",
            "resumen": resumen,
            "datos": datos,
            "generado_por": None,
        }
        if existente:
            for campo, valor in defaults.items():
                setattr(existente, campo, valor)
            existente.fecha_generacion = timezone.now()
            existente.save(update_fields=[*defaults, "fecha_generacion"])
            return existente, True

        return ReporteMetrica.objects.get_or_create(defaults=defaults, **filtros)
