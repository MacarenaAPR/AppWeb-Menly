from django.db.models import Sum

from menu.models import Producto
from menu.services.turnos_operativos import obtener_turno_operativo_actual
from .pedidos import (
    fecha_hoy,
    inicio_mes,
    pedidos_especiales_finalizados,
    pedidos_manuales_finalizados,
    pedidos_whatsapp_finalizados,
)


def _to_int(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _item_key(item):
    if not isinstance(item, dict):
        return "nombre:Producto", None

    producto_id = item.get("producto_id") or item.get("id")
    if producto_id:
        return f"producto:{producto_id}", producto_id

    nombre = (item.get("nombre") or "Producto").strip()
    return f"nombre:{nombre.lower()}", None


def _sumar_item(acumulados, item, canal):
    if not isinstance(item, dict):
        return

    nombre = (item.get("nombre") or "Producto").strip() or "Producto"
    cantidad = _to_int(item.get("cantidad"))
    precio_unitario = _to_int(item.get("precio_unitario") or item.get("precio"))
    subtotal = item.get("subtotal")
    if subtotal is None:
        subtotal = precio_unitario * cantidad
    else:
        subtotal = _to_int(subtotal)

    if cantidad <= 0:
        return

    clave, producto_id = _item_key(item)
    actual = acumulados.setdefault(
        clave,
        {
            "clave": clave,
            "producto_id": producto_id,
            "nombre": nombre,
            "cantidad": 0,
            "total_vendido": 0,
            "canales": {"whatsapp": 0, "especiales": 0, "menly": 0},
        },
    )
    actual["cantidad"] += cantidad
    actual["total_vendido"] += subtotal
    actual["canales"][canal] = actual["canales"].get(canal, 0) + cantidad


def productos_vendidos(
    restaurante,
    desde=None,
    hasta=None,
    canal=None,
    incluir_especiales_inactivos=False,
):
    """Ranking de productos vendidos usando solo pedidos finalizados."""
    acumulados = {}

    if canal in (None, "whatsapp"):
        for pedido in pedidos_whatsapp_finalizados(restaurante, desde, hasta):
            for item in pedido.productos_snapshot or []:
                _sumar_item(acumulados, item, "whatsapp")

    if (
        canal in (None, "especiales")
        and (
            restaurante.solicitudes_especiales_activas
            or incluir_especiales_inactivos
        )
    ):
        for pedido in pedidos_especiales_finalizados(restaurante, desde, hasta):
            for item in pedido.items or []:
                _sumar_item(acumulados, item, "especiales")

    if canal in (None, "menly"):
        pedidos = pedidos_manuales_finalizados(
            restaurante, desde, hasta
        ).prefetch_related("items")
        for pedido in pedidos:
            for item in pedido.items.all():
                _sumar_item(
                    acumulados,
                    {
                        "producto_id": item.producto_id,
                        "nombre": item.nombre_producto,
                        "cantidad": item.cantidad,
                        "precio_unitario": item.precio_unitario,
                        "subtotal": item.subtotal,
                    },
                    "menly",
                )

    return sorted(
        acumulados.values(),
        key=lambda item: (-item["cantidad"], -item["total_vendido"], item["nombre"]),
    )


def top_productos_por_cantidad(
    restaurante,
    desde=None,
    hasta=None,
    canal=None,
    limit=10,
    incluir_especiales_inactivos=False,
):
    return productos_vendidos(
        restaurante,
        desde,
        hasta,
        canal,
        incluir_especiales_inactivos,
    )[:limit]


def top_productos_por_ingresos(
    restaurante,
    desde=None,
    hasta=None,
    canal=None,
    limit=10,
    incluir_especiales_inactivos=False,
):
    return sorted(
        productos_vendidos(
            restaurante,
            desde,
            hasta,
            canal,
            incluir_especiales_inactivos,
        ),
        key=lambda item: (-item["total_vendido"], -item["cantidad"], item["nombre"]),
    )[:limit]


def producto_mas_vendido(
    restaurante,
    desde=None,
    hasta=None,
    canal=None,
    incluir_especiales_inactivos=False,
):
    productos = top_productos_por_cantidad(
        restaurante,
        desde,
        hasta,
        canal,
        limit=1,
        incluir_especiales_inactivos=incluir_especiales_inactivos,
    )
    return productos[0] if productos else None


def producto_menos_vendido(
    restaurante,
    desde=None,
    hasta=None,
    canal=None,
    incluir_especiales_inactivos=False,
):
    productos = productos_vendidos(
        restaurante,
        desde,
        hasta,
        canal,
        incluir_especiales_inactivos,
    )
    return min(productos, key=lambda item: (item["cantidad"], item["nombre"])) if productos else None


def productos_mas_clickeados(restaurante, limit=10):
    return [
        {
            "id": producto.id,
            "nombre": producto.nombre,
            "categoria": producto.categoria.nombre if producto.categoria_id else "",
            "clicks": producto.clicks,
        }
        for producto in Producto.objects.filter(
            restaurante=restaurante,
            clicks__gt=0,
        ).select_related("categoria").order_by("-clicks")[:limit]
    ]


def clicks_productos_total(restaurante):
    return Producto.objects.filter(restaurante=restaurante).aggregate(
        total=Sum("clicks")
    )["total"] or 0


def metricas_productos(restaurante, hoy=None):
    usar_turno_actual = hoy is None
    hoy = hoy or fecha_hoy()
    desde_mes = inicio_mes(hoy)
    turno = obtener_turno_operativo_actual(restaurante) if usar_turno_actual else None
    mas_vendido_turno = (
        producto_mas_vendido(restaurante, turno.inicio, turno.fin)
        if turno and turno.inicio and turno.fin
        else None
    )
    return {
        "mas_vendido_hoy": (
            mas_vendido_turno
            if usar_turno_actual
            else producto_mas_vendido(restaurante, hoy, hoy)
        ),
        "mas_vendido_mes": producto_mas_vendido(restaurante, desde_mes, hoy),
        "top_por_cantidad": top_productos_por_cantidad(restaurante, desde_mes, hoy),
        "top_por_ingresos": top_productos_por_ingresos(restaurante, desde_mes, hoy),
        "mas_clickeados": productos_mas_clickeados(restaurante),
        "clicks_total": clicks_productos_total(restaurante),
    }
