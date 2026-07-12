from datetime import datetime, time, timedelta

from django.conf import settings
from django.utils import timezone

from menu.models import (
    ActivacionCocina,
    HistorialEstadoPedidoWhatsApp,
    PedidoEspecial,
    PedidoManual,
    PedidoWhatsApp,
    SesionCocina,
)


COOKIE_COCINA = "menly_cocina_session"
ORIGEN_WHATSAPP = "whatsapp"
ORIGEN_MENLY = "menly"
ORIGEN_ESPECIAL = "especial"


def fin_dia_actual():
    zona = timezone.get_current_timezone()
    manana = timezone.localdate() + timedelta(days=1)
    return timezone.make_aware(datetime.combine(manana, time.min), zona)


def construir_url_activacion(request, token):
    base_url = (request.META.get("HTTP_ORIGIN") or request.build_absolute_uri("/")).rstrip("/")
    return f"{base_url}/pedidos-cocina/activar/{token}"


def crear_activacion_cocina(restaurante, usuario, request):
    expira_en = timezone.now() + timedelta(minutes=5)
    activacion, token = ActivacionCocina.crear(restaurante, usuario, expira_en)
    return {
        "activation_url": construir_url_activacion(request, token),
        "expires_at": activacion.expira_en,
    }


def consumir_activacion_cocina(token):
    token_hash = ActivacionCocina.hashear_token(token)

    activacion = (
        ActivacionCocina.objects
        .select_related("restaurante")
        .filter(token_hash=token_hash)
        .first()
    )

    if not activacion:
        print("COCINA DEBUG: activación no encontrada")
        print("Token recibido, longitud:", len(token))
        print("Hash calculado:", token_hash[:15])

        ultima = ActivacionCocina.objects.order_by("-creado_en").first()

        if ultima:
            print("Última activación ID:", ultima.id)
            print("Hash guardado:", ultima.token_hash[:15])
            print("Creada:", ultima.creado_en)
            print("Expira:", ultima.expira_en)
            print("Consumida:", ultima.consumido_en)

        return None, None, "DEBUG: activacion no encontrada"

    print("COCINA DEBUG: activación encontrada")
    print("ID:", activacion.id)
    print("Ahora:", timezone.now())
    print("Expira:", activacion.expira_en)
    print("Consumida:", activacion.consumido_en)
    print("Puede consumirse:", activacion.puede_consumirse())

    if not activacion.puede_consumirse():
        if activacion.consumido_en:
            return None, None, "DEBUG: activacion ya consumida"

        if activacion.expira_en <= timezone.now():
            return None, None, "DEBUG: activacion expirada"

        return None, None, "DEBUG: activacion rechazada por puede_consumirse"

    sesion, token_sesion = SesionCocina.crear(
        activacion.restaurante,
        expira_en=fin_dia_actual(),
    )

    activacion.consumido_en = timezone.now()
    activacion.save(update_fields=["consumido_en"])

    return sesion, token_sesion, ""


def set_cookie_cocina(response, token_sesion, expira_en):
    response.set_signed_cookie(
        COOKIE_COCINA,
        token_sesion,
        expires=expira_en,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
        path="/",
    )


def limpiar_cookie_cocina(response):
    response.delete_cookie(COOKIE_COCINA, path="/", samesite="Lax")


def obtener_sesion_cocina(request):
    try:
        token = request.get_signed_cookie(COOKIE_COCINA)
    except Exception:
        return None

    token_hash = SesionCocina.hashear_token(token)
    sesion = (
        SesionCocina.objects
        .select_related("restaurante")
        .filter(token_hash=token_hash)
        .first()
    )
    if not sesion or not sesion.esta_vigente():
        return None
    return sesion


def _items_whatsapp(pedido):
    return [
        {
            "nombre": item.get("nombre", ""),
            "cantidad": item.get("cantidad", 0),
            "observaciones": item.get("observaciones", ""),
        }
        for item in (pedido.productos_snapshot or [])
    ]


def _items_manual(pedido):
    return [
        {
            "nombre": item.nombre_producto,
            "cantidad": item.cantidad,
            "observaciones": item.observaciones,
        }
        for item in pedido.items.all()
    ]


def _items_especial(pedido):
    return [
        {
            "nombre": item.get("nombre", ""),
            "cantidad": item.get("cantidad", 0),
            "observaciones": item.get("descripcion", ""),
        }
        for item in (pedido.items or [])
    ]


def _normalizar_comanda(pedido, tipo_origen, estado, items):
    return {
        "id": f"{tipo_origen}:{pedido.id}",
        "pedido_id": pedido.id,
        "tipo_origen": tipo_origen,
        "numero": pedido.numero_pedido,
        "estado": estado,
        "estado_original": pedido.estado,
        "hora_creacion": pedido.fecha_creacion,
        "tipo_entrega": pedido.tipo_entrega if hasattr(pedido, "tipo_entrega") else "especial",
        "tipo_entrega_display": (
            pedido.get_tipo_entrega_display()
            if hasattr(pedido, "get_tipo_entrega_display")
            else "Especial"
        ),
        "numero_mesa": getattr(pedido, "numero_mesa", ""),
        "cliente_nombre": getattr(pedido, "nombre_cliente", "") or "Cliente",
        "observaciones": getattr(pedido, "observaciones", "") or getattr(pedido, "descripcion_original", ""),
        "items": items,
    }


def obtener_comandas_activas(restaurante):
    comandas = []

    pedidos_whatsapp = PedidoWhatsApp.objects.filter(
        restaurante=restaurante,
        estado__in=[PedidoWhatsApp.ESTADO_EN_PREPARACION, PedidoWhatsApp.ESTADO_LISTO],
    ).order_by("fecha_creacion", "id")
    for pedido in pedidos_whatsapp:
        comandas.append(_normalizar_comanda(pedido, ORIGEN_WHATSAPP, pedido.estado, _items_whatsapp(pedido)))

    pedidos_manuales = (
        PedidoManual.objects
        .filter(
            restaurante=restaurante,
            estado__in=[PedidoManual.ESTADO_PREPARANDO, PedidoManual.ESTADO_LISTO],
        )
        .prefetch_related("items")
        .order_by("fecha_creacion", "id")
    )
    for pedido in pedidos_manuales:
        estado = "en_preparacion" if pedido.estado == PedidoManual.ESTADO_PREPARANDO else pedido.estado
        comandas.append(_normalizar_comanda(pedido, ORIGEN_MENLY, estado, _items_manual(pedido)))

    pedidos_especiales = PedidoEspecial.objects.filter(
        restaurante=restaurante,
        estado__in=[PedidoEspecial.ESTADO_EN_PREPARACION, PedidoEspecial.ESTADO_LISTO],
    ).order_by("fecha_creacion", "id")
    for pedido in pedidos_especiales:
        comandas.append(_normalizar_comanda(pedido, ORIGEN_ESPECIAL, pedido.estado, _items_especial(pedido)))

    return sorted(comandas, key=lambda item: item["hora_creacion"])


def _obtener_pedido_cocina(restaurante, identificador):
    try:
        tipo_origen, pedido_id = str(identificador).split(":", 1)
        pedido_id = int(pedido_id)
    except (TypeError, ValueError):
        return None, None

    if tipo_origen == ORIGEN_WHATSAPP:
        return tipo_origen, PedidoWhatsApp.objects.filter(id=pedido_id, restaurante=restaurante).first()
    if tipo_origen == ORIGEN_MENLY:
        return tipo_origen, PedidoManual.objects.filter(id=pedido_id, restaurante=restaurante).first()
    if tipo_origen == ORIGEN_ESPECIAL:
        return tipo_origen, PedidoEspecial.objects.filter(id=pedido_id, restaurante=restaurante).first()
    return None, None


def cambiar_estado_comanda(restaurante, identificador, estado_nuevo):
    tipo_origen, pedido = _obtener_pedido_cocina(restaurante, identificador)
    if not pedido:
        return None, "Comanda no encontrada."

    estado_actual = pedido.estado
    transiciones = {
        ORIGEN_WHATSAPP: {
            PedidoWhatsApp.ESTADO_EN_PREPARACION: [PedidoWhatsApp.ESTADO_LISTO],
            PedidoWhatsApp.ESTADO_LISTO: [PedidoWhatsApp.ESTADO_ENTREGADO],
        },
        ORIGEN_MENLY: {
            PedidoManual.ESTADO_PREPARANDO: [PedidoManual.ESTADO_LISTO],
            PedidoManual.ESTADO_LISTO: [PedidoManual.ESTADO_ENTREGADO],
        },
        ORIGEN_ESPECIAL: {
            PedidoEspecial.ESTADO_EN_PREPARACION: [PedidoEspecial.ESTADO_LISTO],
            PedidoEspecial.ESTADO_LISTO: [PedidoEspecial.ESTADO_ENTREGADO],
        },
    }

    if estado_nuevo not in transiciones.get(tipo_origen, {}).get(estado_actual, []):
        return None, "Transicion de estado invalida para cocina."

    pedido.estado = estado_nuevo
    update_fields = ["estado"]
    if isinstance(pedido, PedidoWhatsApp):
        pedido.save(update_fields=update_fields)
        HistorialEstadoPedidoWhatsApp.objects.create(
            pedido=pedido,
            estado_anterior=estado_actual,
            estado_nuevo=estado_nuevo,
            observacion="Actualizado desde cocina",
        )
    else:
        pedido.save(update_fields=update_fields)

    return pedido, ""
