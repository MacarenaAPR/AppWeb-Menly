import hashlib
import json
import logging
from urllib.parse import quote

from django.db import transaction

from menu.models import PedidoWhatsApp, Producto, ProductoVariante
from menu.services.secuencia_pedidos import obtener_siguiente_numero_pedido
from menu.utils import crear_notificacion_pedido_whatsapp

logger = logging.getLogger(__name__)


def _normalizar_entero_idempotencia(valor):
    if valor in (None, ""):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return str(valor).strip()


def calcular_hash_pedido_publico(restaurante, payload):
    productos = []
    for item in payload.get("productos") or []:
        if not isinstance(item, dict):
            productos.append(item)
            continue
        productos.append({
            "producto_id": _normalizar_entero_idempotencia(item.get("producto_id")),
            "variante_id": _normalizar_entero_idempotencia(item.get("variante_id")),
            "cantidad": _normalizar_entero_idempotencia(item.get("cantidad")),
        })

    tipo_entrega = str(payload.get("tipo_entrega") or "").strip()
    contenido = {
        "restaurante": restaurante.slug,
        "nombre_cliente": str(payload.get("nombre_cliente") or "").strip(),
        "telefono_cliente": str(payload.get("telefono_cliente") or "").strip(),
        "tipo_entrega": tipo_entrega,
        "direccion_entrega": (
            str(payload.get("direccion_entrega") or "").strip()
            if tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY
            else ""
        ),
        "metodo_pago_id": _normalizar_entero_idempotencia(payload.get("metodo_pago_id")),
        "productos": productos,
    }
    canonico = json.dumps(
        contenido,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def obtener_whatsapp_destino(restaurante):
    return (restaurante.whatsapp or restaurante.telefono or "").strip()


def normalizar_productos_pedido(restaurante, productos_solicitados):
    cantidades_por_linea = {}
    for item in productos_solicitados:
        producto_id = item["producto_id"]
        variante_id = item.get("variante_id")
        clave = (producto_id, variante_id)
        cantidades_por_linea[clave] = (
            cantidades_por_linea.get(clave, 0) + item["cantidad"]
        )

    producto_ids = {producto_id for producto_id, _ in cantidades_por_linea}
    productos = Producto.objects.filter(
        restaurante=restaurante,
        disponible=True,
        id__in=producto_ids,
    ).prefetch_related("variantes").in_bulk()

    if len(productos) != len(producto_ids):
        return None, None

    variante_ids = {variante_id for _, variante_id in cantidades_por_linea if variante_id}
    variantes = ProductoVariante.objects.filter(
        id__in=variante_ids,
        activo=True,
        producto__restaurante=restaurante,
    ).select_related("producto").in_bulk()

    if len(variantes) != len(variante_ids):
        return None, None

    snapshot = []
    total = 0

    for (producto_id, variante_id), cantidad in cantidades_por_linea.items():
        producto = productos[producto_id]
        variantes_activas = [variante for variante in producto.variantes.all() if variante.activo]

        if variantes_activas and not variante_id:
            return None, None
        if not variantes_activas and variante_id:
            return None, None

        variante = variantes.get(variante_id) if variante_id else None
        if variante and variante.producto_id != producto.id:
            return None, None

        precio_unitario = variante.precio if variante else producto.precio
        subtotal = precio_unitario * cantidad
        total += subtotal
        item_snapshot = {
            "producto_id": producto.id,
            "nombre": producto.nombre,
            "precio_unitario": int(precio_unitario),
            "cantidad": cantidad,
            "subtotal": int(subtotal),
        }
        if variante:
            item_snapshot.update({
                "variante_id": variante.id,
                "variante_nombre": variante.nombre,
            })
        snapshot.append(item_snapshot)

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
    costo_delivery = ""
    if pedido.tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY and pedido.direccion_entrega:
        direccion = f"Direccion: {pedido.direccion_entrega}\n"
    if pedido.tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY:
        costo_delivery = "Costo de delivery: por confirmar con el restaurante.\n"

    productos = "\n".join(
        (
            f"{item['nombre']} — {item['variante_nombre']} x{item['cantidad']} - ${item['subtotal']}"
            if item.get("variante_nombre")
            else f"{item['cantidad']} x {item['nombre']} - ${item['subtotal']}"
        )
        for item in pedido.productos_snapshot
    )
    metodo_pago_linea = (
        f"💳 Método de pago: {pedido.metodo_pago_nombre}\n"
        if pedido.metodo_pago_nombre
        else ""
    )

    return (
        "Hola, quiero hacer este pedido:\n\n"
        f"Pedido #{pedido.numero_pedido}\n"
        f"{productos}\n\n"
        f"{'Total productos' if costo_delivery else 'Total'}: ${int(pedido.total)}\n"
        f"{costo_delivery}"
        f"Tipo entrega: {tipo_entrega}\n"
        f"{metodo_pago_linea}"
        f"{direccion}"
        f"Cliente: {pedido.nombre_cliente}\n"
        f"Telefono: {pedido.telefono_cliente}\n\n"
        "Puedes ver el estado de tu pedido aqui:\n"
        f"{get_tracking_url(pedido, request=request)}"
    )


def generar_mensaje_legacy(pedido):
    tipo_entrega = pedido.get_tipo_entrega_display()
    direccion = ""
    costo_delivery = ""
    if pedido.tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY and pedido.direccion_entrega:
        direccion = f"Direccion:\n{pedido.direccion_entrega}\n\n"
    if pedido.tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY:
        costo_delivery = "Costo de delivery: por confirmar con el restaurante.\n\n"

    productos = "\n".join(
        (
            f"* {item['nombre']} — {item['variante_nombre']} x{item['cantidad']} - ${item['subtotal']}"
            if item.get("variante_nombre")
            else f"* {item['cantidad']} x {item['nombre']} - ${item['subtotal']}"
        )
        for item in pedido.productos_snapshot
    )
    metodo_pago_linea = (
        f"💳 Método de pago: {pedido.metodo_pago_nombre}\n\n"
        if pedido.metodo_pago_nombre
        else ""
    )

    return (
        "Hola, quiero hacer un pedido desde Menly.\n\n"
        f"Cliente: {pedido.nombre_cliente}\n"
        f"Teléfono: {pedido.telefono_cliente}\n"
        f"Tipo de entrega: {tipo_entrega}\n\n"
        f"{metodo_pago_linea}"
        f"{direccion}"
        "Productos:\n\n"
        f"{productos}\n\n"
        f"{'Total productos' if costo_delivery else 'Total'}: ${int(pedido.total)}\n\n"
        f"{costo_delivery}"
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
    datos_pedido.pop("metodo_pago_id", None)

    with transaction.atomic():
        pedido = PedidoWhatsApp.objects.create(
            restaurante=restaurante,
            numero_pedido=obtener_siguiente_numero_pedido(restaurante),
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
