import logging
from urllib.parse import quote

from django.db import transaction
from django.db.models import Max

from menu.models import PedidoWhatsApp, Producto, Restaurante
from menu.utils import crear_notificacion_pedido_whatsapp

logger = logging.getLogger(__name__)


def obtener_whatsapp_destino(restaurante):
    return (restaurante.whatsapp or restaurante.telefono or "").strip()


def normalizar_productos_pedido(restaurante, productos_solicitados):
    cantidades_por_producto = {}
    for item in productos_solicitados:
        producto_id = item["producto_id"]
        cantidades_por_producto[producto_id] = (
            cantidades_por_producto.get(producto_id, 0) + item["cantidad"]
        )

    productos = Producto.objects.filter(
        restaurante=restaurante,
        disponible=True,
        id__in=cantidades_por_producto.keys(),
    ).in_bulk()

    if len(productos) != len(cantidades_por_producto):
        return None, None

    snapshot = []
    total = 0

    for producto_id, cantidad in cantidades_por_producto.items():
        producto = productos[producto_id]
        precio_unitario = producto.precio
        subtotal = precio_unitario * cantidad
        total += subtotal
        snapshot.append({
            "producto_id": producto.id,
            "nombre": producto.nombre,
            "precio_unitario": int(precio_unitario),
            "cantidad": cantidad,
            "subtotal": int(subtotal),
        })

    return snapshot, total


def get_tracking_url(pedido, request=None):
    base_url = ""
    if request:
        base_url = request.META.get("HTTP_ORIGIN") or request.build_absolute_uri("/")
    base_url = (base_url or "https://menly.cl").rstrip("/")
    return f"{base_url}/seguimiento/pedido/{pedido.tracking_token}"


def generar_mensaje_whatsapp(pedido, request=None):
    tipo_entrega = pedido.get_tipo_entrega_display()
    direccion = ""
    if pedido.tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY and pedido.direccion_entrega:
        direccion = f"Direccion: {pedido.direccion_entrega}\n"

    productos = "\n".join(
        f"{item['cantidad']} x {item['nombre']} - ${item['subtotal']}"
        for item in pedido.productos_snapshot
    )

    return (
        "Hola, quiero hacer este pedido:\n\n"
        f"Pedido #{pedido.numero_pedido}\n"
        f"{productos}\n\n"
        f"Total: ${int(pedido.total)}\n"
        f"Tipo entrega: {tipo_entrega}\n"
        f"{direccion}"
        f"Cliente: {pedido.nombre_cliente}\n"
        f"Telefono: {pedido.telefono_cliente}\n\n"
        "Puedes ver el estado de tu pedido aqui:\n"
        f"{get_tracking_url(pedido, request=request)}"
    )


def generar_mensaje_legacy(pedido):
    tipo_entrega = pedido.get_tipo_entrega_display()
    direccion = ""
    if pedido.tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY and pedido.direccion_entrega:
        direccion = f"Direccion:\n{pedido.direccion_entrega}\n\n"

    productos = "\n".join(
        f"* {item['cantidad']} x {item['nombre']} - ${item['subtotal']}"
        for item in pedido.productos_snapshot
    )

    return (
        "Hola, quiero hacer un pedido desde Menly.\n\n"
        f"Cliente: {pedido.nombre_cliente}\n"
        f"Teléfono: {pedido.telefono_cliente}\n"
        f"Tipo de entrega: {tipo_entrega}\n\n"
        f"{direccion}"
        "Productos:\n\n"
        f"{productos}\n\n"
        f"Total: ${int(pedido.total)}\n\n"
        f"Pedido N°: {pedido.numero_pedido}"
    )


def generar_whatsapp_url(telefono, mensaje):
    numero = "".join(ch for ch in str(telefono) if ch.isdigit())
    return f"https://wa.me/{numero}?text={quote(mensaje)}"


def crear_pedido_whatsapp(restaurante, datos_pedido, request=None):
    productos_snapshot = datos_pedido.pop("productos_snapshot")
    total = datos_pedido.pop("total")
    whatsapp_destino = datos_pedido.pop("whatsapp_destino")
    datos_pedido.pop("productos", None)

    with transaction.atomic():
        Restaurante.objects.select_for_update().get(id=restaurante.id)
        ultimo_numero = PedidoWhatsApp.objects.filter(
            restaurante=restaurante
        ).aggregate(maximo=Max("numero_pedido"))["maximo"] or 0
        numero_pedido = ultimo_numero + 1

        pedido = PedidoWhatsApp.objects.create(
            restaurante=restaurante,
            numero_pedido=numero_pedido,
            productos_snapshot=productos_snapshot,
            total=total,
            whatsapp_destino=whatsapp_destino,
            mensaje_whatsapp_generado="",
            **datos_pedido,
        )
        mensaje = generar_mensaje_whatsapp(pedido, request=request)
        pedido.mensaje_whatsapp_generado = mensaje
        pedido.save(update_fields=["mensaje_whatsapp_generado"])

        try:
            crear_notificacion_pedido_whatsapp(pedido)
        except Exception:
            logger.exception(
                "Error creando notificacion persistente de pedido WhatsApp",
                extra={"pedido_whatsapp_id": pedido.id, "restaurante_id": restaurante.id},
            )

    pedido.whatsapp_url = generar_whatsapp_url(pedido.whatsapp_destino, mensaje)
    return pedido
