import hashlib
import json
import logging
from urllib.parse import quote

from django.db import transaction

from menu.models import (
    GrupoOpcionesProducto,
    OpcionProducto,
    PedidoWhatsApp,
    Producto,
    ProductoVariante,
)
from menu.services.secuencia_pedidos import obtener_siguiente_numero_pedido
from menu.utils import crear_notificacion_pedido_whatsapp

logger = logging.getLogger(__name__)


class ProductosPedidoValidationError(ValueError):
    """Error de seleccion de catalogo apto para mostrarse al cliente."""


MAX_CANTIDAD_PEDIDO_WHATSAPP = 99
MAX_CANTIDAD_PEDIDO_MANUAL = 999


def clave_configuracion_producto(producto_id, variante_id=None, opciones=None):
    return (
        int(producto_id),
        int(variante_id) if variante_id not in (None, "") else None,
        tuple(sorted(int(opcion_id) for opcion_id in (opciones or []))),
    )


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
        opciones = [
            _normalizar_entero_idempotencia(opcion_id)
            for opcion_id in (item.get("opciones") or [])
        ]
        opciones.sort(key=lambda opcion_id: (str(type(opcion_id)), str(opcion_id)))
        productos.append({
            "producto_id": _normalizar_entero_idempotencia(item.get("producto_id")),
            "variante_id": _normalizar_entero_idempotencia(item.get("variante_id")),
            "cantidad": _normalizar_entero_idempotencia(item.get("cantidad")),
            "opciones": opciones,
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


def agrupar_cantidades_por_configuracion(
    productos_solicitados,
    max_cantidad_por_configuracion=MAX_CANTIDAD_PEDIDO_WHATSAPP,
):
    cantidades_por_linea = {}
    for item in productos_solicitados:
        producto_id = item["producto_id"]
        variante_id = item.get("variante_id")
        opciones_ids = item.get("opciones") or []
        if len(opciones_ids) != len(set(opciones_ids)):
            raise ProductosPedidoValidationError(
                "No puedes seleccionar la misma opcion mas de una vez."
            )
        clave = clave_configuracion_producto(producto_id, variante_id, opciones_ids)
        cantidades_por_linea[clave] = (
            cantidades_por_linea.get(clave, 0) + item["cantidad"]
        )

    for cantidad in cantidades_por_linea.values():
        if cantidad > max_cantidad_por_configuracion:
            raise ProductosPedidoValidationError(
                "La cantidad total para una misma configuracion no puede superar "
                f"{max_cantidad_por_configuracion}."
            )

    return cantidades_por_linea


def normalizar_productos_pedido(
    restaurante,
    productos_solicitados,
    max_cantidad_por_configuracion=MAX_CANTIDAD_PEDIDO_WHATSAPP,
):
    cantidades_por_linea = agrupar_cantidades_por_configuracion(
        productos_solicitados,
        max_cantidad_por_configuracion=max_cantidad_por_configuracion,
    )

    producto_ids = {producto_id for producto_id, _, _ in cantidades_por_linea}
    productos = Producto.objects.filter(
        restaurante=restaurante,
        id__in=producto_ids,
    ).prefetch_related("variantes").in_bulk()

    if len(productos) != len(producto_ids):
        raise ProductosPedidoValidationError(
            "Uno o mas productos no pertenecen a este restaurante."
        )
    if any(not producto.disponible for producto in productos.values()):
        raise ProductosPedidoValidationError(
            "Uno o mas productos seleccionados no estan disponibles."
        )

    variante_ids = {
        variante_id
        for _, variante_id, _ in cantidades_por_linea
        if variante_id
    }
    variantes = ProductoVariante.objects.filter(
        id__in=variante_ids,
        producto__restaurante=restaurante,
    ).select_related("producto").in_bulk()

    if len(variantes) != len(variante_ids):
        raise ProductosPedidoValidationError(
            "La variante seleccionada no pertenece a este restaurante."
        )

    grupos = list(
        GrupoOpcionesProducto.objects.filter(producto_id__in=producto_ids)
        .select_related("producto")
        .order_by("producto_id", "orden", "id")
    )
    grupos_por_producto = {}
    for grupo in grupos:
        grupos_por_producto.setdefault(grupo.producto_id, []).append(grupo)

    opcion_ids = {
        opcion_id
        for _, _, opciones_linea in cantidades_por_linea
        for opcion_id in opciones_linea
    }
    opciones = OpcionProducto.objects.filter(id__in=opcion_ids).select_related(
        "grupo__producto"
    ).in_bulk()
    if len(opciones) != len(opcion_ids):
        raise ProductosPedidoValidationError(
            "Una de las opciones seleccionadas no existe."
        )

    snapshot = []
    total = 0

    for (producto_id, variante_id, opciones_ids), cantidad in cantidades_por_linea.items():
        producto = productos[producto_id]
        variantes_activas = [variante for variante in producto.variantes.all() if variante.activo]

        if variantes_activas and not variante_id:
            raise ProductosPedidoValidationError(
                f"Debes seleccionar una variante de {producto.nombre}."
            )
        if not variantes_activas and variante_id:
            raise ProductosPedidoValidationError(
                "La variante seleccionada no pertenece a este producto."
            )

        variante = variantes.get(variante_id) if variante_id else None
        if variante and variante.producto_id != producto.id:
            raise ProductosPedidoValidationError(
                "La variante seleccionada no pertenece a este producto."
            )
        if variante and not variante.activo:
            raise ProductosPedidoValidationError(
                "La variante seleccionada no esta disponible."
            )

        opciones_seleccionadas = [opciones[opcion_id] for opcion_id in opciones_ids]
        opciones_por_grupo = {}
        for opcion in opciones_seleccionadas:
            if opcion.grupo.producto_id != producto.id:
                raise ProductosPedidoValidationError(
                    "La opcion seleccionada no pertenece a este producto."
                )
            if opcion.grupo.producto.restaurante_id != restaurante.id:
                raise ProductosPedidoValidationError(
                    "La opcion seleccionada no pertenece a este restaurante."
                )
            if not opcion.disponible:
                raise ProductosPedidoValidationError(
                    f"La opcion {opcion.nombre} no esta disponible."
                )
            opciones_por_grupo.setdefault(opcion.grupo_id, []).append(opcion)

        grupos_producto = grupos_por_producto.get(producto.id, [])
        for grupo in grupos_producto:
            cantidad_seleccionada = len(opciones_por_grupo.get(grupo.id, []))
            minimo = grupo.minimo_selecciones
            if grupo.obligatorio:
                minimo = max(1, minimo)
            if cantidad_seleccionada < minimo:
                raise ProductosPedidoValidationError(
                    f"Debes seleccionar al menos {minimo} opcion(es) de {grupo.nombre}."
                )
            if (
                grupo.maximo_selecciones is not None
                and cantidad_seleccionada > grupo.maximo_selecciones
            ):
                raise ProductosPedidoValidationError(
                    "Puedes seleccionar como maximo "
                    f"{grupo.maximo_selecciones} opcion(es) de {grupo.nombre}."
                )

        grupos_snapshot = []
        opciones_total = 0
        for grupo in grupos_producto:
            seleccionadas = sorted(
                opciones_por_grupo.get(grupo.id, []),
                key=lambda opcion: (opcion.orden, opcion.id),
            )
            if not seleccionadas:
                continue
            opciones_snapshot = []
            for opcion in seleccionadas:
                opciones_total += opcion.precio_adicional
                opciones_snapshot.append({
                    "opcion_id": opcion.id,
                    "nombre": opcion.nombre,
                    "precio_adicional": int(opcion.precio_adicional),
                })
            grupos_snapshot.append({
                "grupo_id": grupo.id,
                "grupo_nombre": grupo.nombre,
                "opciones": opciones_snapshot,
            })

        precio_original = variante.precio if variante else producto.precio
        detalle_precio = producto.detalle_precio(precio_original)
        precio_base = detalle_precio["precio_efectivo"]
        precio_unitario = precio_base + opciones_total
        subtotal = precio_unitario * cantidad
        total += subtotal
        item_snapshot = {
            "producto_id": producto.id,
            "nombre": producto.nombre,
            "variante_id": variante.id if variante else None,
            "variante_nombre": variante.nombre if variante else "",
            "precio_original": int(detalle_precio["precio_original"]),
            "porcentaje_descuento_aplicado": producto.porcentaje_descuento,
            "monto_descuento": int(detalle_precio["monto_descuento"]),
            "precio_base": int(precio_base),
            "opciones_total": int(opciones_total),
            "precio_unitario": int(precio_unitario),
            "cantidad": cantidad,
            "subtotal": int(subtotal),
            "grupos_opciones": grupos_snapshot,
        }
        snapshot.append(item_snapshot)

    return snapshot, total


def _formatear_precio(valor):
    return f"{int(valor or 0):,}".replace(",", ".")


def _formatear_item_whatsapp(item, prefijo=""):
    grupos = item.get("grupos_opciones") or []
    if not grupos:
        if item.get("variante_nombre"):
            return (
                f"{prefijo}{item['nombre']} — {item['variante_nombre']} "
                f"x{item['cantidad']} - ${item['subtotal']}"
            )
        return f"{prefijo}{item['cantidad']} x {item['nombre']} - ${item['subtotal']}"

    nombre = item.get("nombre", "Producto")
    if item.get("variante_nombre"):
        nombre = f"{nombre} — {item['variante_nombre']}"
    lineas = [f"{prefijo}{item.get('cantidad', 0)}x {nombre}"]
    for grupo in grupos:
        opciones_texto = []
        for opcion in grupo.get("opciones") or []:
            texto = opcion.get("nombre", "")
            adicional = int(opcion.get("precio_adicional") or 0)
            if adicional:
                texto += f" (+${_formatear_precio(adicional)})"
            opciones_texto.append(texto)
        lineas.append(
            f"{grupo.get('grupo_nombre', 'Opciones')}: {', '.join(opciones_texto)}"
        )
    lineas.append(f"${_formatear_precio(item.get('subtotal', 0))}")
    return "\n".join(lineas)


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

    productos = "\n\n".join(
        _formatear_item_whatsapp(item)
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

    productos = "\n\n".join(
        _formatear_item_whatsapp(item, prefijo="* ")
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
