import logging

from django.db import transaction

from menu.models import (
    HistorialEstadoPedidoEspecial,
    HistorialEstadoPedidoManual,
    HistorialEstadoPedidoWhatsApp,
    PedidoEspecial,
    PedidoManual,
    PedidoWhatsApp,
    SolicitudEspecial,
)

logger = logging.getLogger(__name__)

TIPO_WHATSAPP = "whatsapp"
TIPO_MANUAL = "manual"
TIPO_ESPECIAL = "especial"

ORIGEN_PANEL = "panel"
ORIGEN_KDS = "kds"
ORIGEN_SISTEMA = "sistema"
ORIGENES_VALIDOS = {ORIGEN_PANEL, ORIGEN_KDS, ORIGEN_SISTEMA}

PENDIENTE = "pendiente"
EN_PREPARACION = "en_preparacion"
LISTO = "listo"
EN_REPARTO = "en_reparto"
ENTREGADO = "entregado"
CANCELADO = "cancelado"

TRANSICIONES_BASE = {
    PENDIENTE: (EN_PREPARACION, CANCELADO),
    EN_PREPARACION: (LISTO, CANCELADO),
    LISTO: (ENTREGADO, CANCELADO),
    EN_REPARTO: (ENTREGADO,),
    ENTREGADO: (),
    CANCELADO: (),
}

TRANSICIONES_KDS = {
    EN_PREPARACION: (LISTO,),
    LISTO: (ENTREGADO,),
}

REGISTRO_TIPOS = {
    TIPO_WHATSAPP: {
        "modelo": PedidoWhatsApp,
        "historial": HistorialEstadoPedidoWhatsApp,
        "actual_a_canonico": {
            PedidoWhatsApp.ESTADO_RECIBIDO: PENDIENTE,
            PedidoWhatsApp.ESTADO_PENDIENTE_CONFIRMACION: PENDIENTE,
            PedidoWhatsApp.ESTADO_CONFIRMADO: PENDIENTE,
            PedidoWhatsApp.ESTADO_EN_PREPARACION: EN_PREPARACION,
            PedidoWhatsApp.ESTADO_LISTO: LISTO,
            PedidoWhatsApp.ESTADO_EN_REPARTO: EN_REPARTO,
            PedidoWhatsApp.ESTADO_ENTREGADO: ENTREGADO,
            PedidoWhatsApp.ESTADO_CANCELADO: CANCELADO,
        },
        "canonico_a_actual": {
            PENDIENTE: PedidoWhatsApp.ESTADO_RECIBIDO,
            EN_PREPARACION: PedidoWhatsApp.ESTADO_EN_PREPARACION,
            LISTO: PedidoWhatsApp.ESTADO_LISTO,
            EN_REPARTO: PedidoWhatsApp.ESTADO_EN_REPARTO,
            ENTREGADO: PedidoWhatsApp.ESTADO_ENTREGADO,
            CANCELADO: PedidoWhatsApp.ESTADO_CANCELADO,
        },
        "campo_fecha": "fecha_actualizacion_estado",
    },
    TIPO_MANUAL: {
        "modelo": PedidoManual,
        "historial": HistorialEstadoPedidoManual,
        "actual_a_canonico": {
            PedidoManual.ESTADO_PENDIENTE: PENDIENTE,
            PedidoManual.ESTADO_PREPARANDO: EN_PREPARACION,
            PedidoManual.ESTADO_LISTO: LISTO,
            PedidoManual.ESTADO_EN_REPARTO: EN_REPARTO,
            PedidoManual.ESTADO_ENTREGADO: ENTREGADO,
            PedidoManual.ESTADO_CANCELADO: CANCELADO,
        },
        "canonico_a_actual": {
            PENDIENTE: PedidoManual.ESTADO_PENDIENTE,
            EN_PREPARACION: PedidoManual.ESTADO_PREPARANDO,
            LISTO: PedidoManual.ESTADO_LISTO,
            EN_REPARTO: PedidoManual.ESTADO_EN_REPARTO,
            ENTREGADO: PedidoManual.ESTADO_ENTREGADO,
            CANCELADO: PedidoManual.ESTADO_CANCELADO,
        },
        "campo_fecha": "fecha_actualizacion",
    },
    TIPO_ESPECIAL: {
        "modelo": PedidoEspecial,
        "historial": HistorialEstadoPedidoEspecial,
        "actual_a_canonico": {
            PedidoEspecial.ESTADO_PENDIENTE: PENDIENTE,
            PedidoEspecial.ESTADO_CONFIRMADO: PENDIENTE,
            PedidoEspecial.ESTADO_EN_PREPARACION: EN_PREPARACION,
            PedidoEspecial.ESTADO_LISTO: LISTO,
            PedidoEspecial.ESTADO_ENTREGADO: ENTREGADO,
            PedidoEspecial.ESTADO_CANCELADO: CANCELADO,
        },
        "canonico_a_actual": {
            PENDIENTE: PedidoEspecial.ESTADO_PENDIENTE,
            EN_PREPARACION: PedidoEspecial.ESTADO_EN_PREPARACION,
            LISTO: PedidoEspecial.ESTADO_LISTO,
            ENTREGADO: PedidoEspecial.ESTADO_ENTREGADO,
            CANCELADO: PedidoEspecial.ESTADO_CANCELADO,
        },
        "campo_fecha": "fecha_actualizacion",
    },
}


class EstadoPedidoInvalido(Exception):
    pass


class TransicionEstadoInvalida(Exception):
    def __init__(self, estado_actual, estado_solicitado, estados_permitidos):
        self.estado_actual = estado_actual
        self.estado_solicitado = estado_solicitado
        self.estados_permitidos = estados_permitidos
        super().__init__(
            f"No se puede cambiar el pedido de '{estado_actual}' a '{estado_solicitado}'."
        )


def normalizar_tipo_pedido(tipo):
    tipo_normalizado = "manual" if tipo == "menly" else str(tipo or "").lower()
    if tipo_normalizado not in REGISTRO_TIPOS:
        raise EstadoPedidoInvalido("Tipo de pedido no válido.")
    return tipo_normalizado


def obtener_tipo_pedido(pedido):
    for tipo, config in REGISTRO_TIPOS.items():
        if isinstance(pedido, config["modelo"]):
            return tipo
    raise EstadoPedidoInvalido("Tipo de pedido no válido.")


def _configuracion(tipo):
    return REGISTRO_TIPOS[normalizar_tipo_pedido(tipo)]


def normalizar_estado_actual(pedido, tipo=None):
    tipo = normalizar_tipo_pedido(tipo or obtener_tipo_pedido(pedido))
    return _configuracion(tipo)["actual_a_canonico"].get(pedido.estado)


def _normalizar_estado_solicitado(config, estado):
    estado = str(estado or "").strip().lower()
    if estado in config["actual_a_canonico"]:
        return config["actual_a_canonico"][estado]
    if estado in config["canonico_a_actual"]:
        return estado
    raise EstadoPedidoInvalido("El estado solicitado no es válido.")


def _admite_reparto(pedido, tipo):
    if tipo == TIPO_WHATSAPP:
        return (
            pedido.tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY
            and pedido.restaurante.delivery_activo
        )
    if tipo == TIPO_MANUAL:
        return pedido.tipo_entrega == PedidoManual.TIPO_DELIVERY
    return False


def _transiciones_canonicas(pedido, tipo, origen):
    actual = normalizar_estado_actual(pedido, tipo)
    if actual is None:
        return ()
    if actual == LISTO and _admite_reparto(pedido, tipo):
        permitidas = [EN_REPARTO] if origen == ORIGEN_KDS else [EN_REPARTO, CANCELADO]
    else:
        permitidas = list(
            TRANSICIONES_KDS.get(actual, ())
            if origen == ORIGEN_KDS
            else TRANSICIONES_BASE.get(actual, ())
        )
    return tuple(permitidas)


def obtener_transiciones_permitidas(pedido, tipo=None, origen=ORIGEN_PANEL):
    tipo = normalizar_tipo_pedido(tipo or obtener_tipo_pedido(pedido))
    if origen not in ORIGENES_VALIDOS:
        raise ValueError("Origen de transición no válido.")
    config = _configuracion(tipo)
    return [
        config["canonico_a_actual"][estado]
        for estado in _transiciones_canonicas(pedido, tipo, origen)
        if estado in config["canonico_a_actual"]
    ]


def _completar_solicitud_especial(pedido):
    solicitud = pedido.solicitud_especial
    if not solicitud:
        solicitud = SolicitudEspecial.objects.filter(
            restaurante=pedido.restaurante,
            estado="aceptada",
            fecha_evento=pedido.fecha_entrega,
            telefono_contacto=pedido.telefono_cliente,
            email_contacto=pedido.email_cliente,
            descripcion_solicitud=pedido.descripcion_original,
        ).order_by("-fecha_creacion", "-id").first()
        if solicitud:
            pedido.solicitud_especial = solicitud
            pedido.save(update_fields=["solicitud_especial", "fecha_actualizacion"])
    if solicitud and solicitud.estado != "completada":
        solicitud.estado = "completada"
        solicitud.save(update_fields=["estado", "fecha_actualizacion"])


def cambiar_estado_pedido(pedido, nuevo_estado, tipo=None, actor=None, origen=ORIGEN_PANEL):
    tipo = normalizar_tipo_pedido(tipo or obtener_tipo_pedido(pedido))
    if origen not in ORIGENES_VALIDOS:
        raise ValueError("Origen de transición no válido.")
    config = _configuracion(tipo)
    if not isinstance(pedido, config["modelo"]):
        raise EstadoPedidoInvalido("El pedido no corresponde al tipo indicado.")

    with transaction.atomic():
        pedido_bloqueado = (
            config["modelo"].objects
            .select_for_update()
            .select_related("restaurante")
            .filter(pk=pedido.pk, restaurante_id=pedido.restaurante_id)
            .first()
        )
        if not pedido_bloqueado:
            raise config["modelo"].DoesNotExist

        estado_actual_canonico = normalizar_estado_actual(pedido_bloqueado, tipo)
        estado_solicitado_canonico = _normalizar_estado_solicitado(config, nuevo_estado)
        if estado_actual_canonico is None:
            raise TransicionEstadoInvalida(
                pedido_bloqueado.estado,
                str(nuevo_estado),
                [],
            )
        if estado_actual_canonico == estado_solicitado_canonico:
            return pedido_bloqueado, True

        permitidas_canonicas = _transiciones_canonicas(pedido_bloqueado, tipo, origen)
        if estado_solicitado_canonico not in permitidas_canonicas:
            raise TransicionEstadoInvalida(
                pedido_bloqueado.estado,
                str(nuevo_estado),
                obtener_transiciones_permitidas(pedido_bloqueado, tipo, origen),
            )

        estado_anterior = pedido_bloqueado.estado
        estado_nuevo_real = config["canonico_a_actual"][estado_solicitado_canonico]
        pedido_bloqueado.estado = estado_nuevo_real
        update_fields = ["estado", config["campo_fecha"]]
        pedido_bloqueado.save(update_fields=update_fields)

        usuario = actor if getattr(actor, "is_authenticated", False) else None
        historial_kwargs = {
            "pedido": pedido_bloqueado,
            "estado_anterior": estado_anterior,
            "estado_nuevo": estado_nuevo_real,
            "usuario": usuario,
            "origen": origen,
        }
        if config["historial"] is HistorialEstadoPedidoWhatsApp:
            historial_kwargs["observacion"] = f"Actualizado desde {origen}"
        config["historial"].objects.create(**historial_kwargs)

        if tipo == TIPO_ESPECIAL and estado_solicitado_canonico == ENTREGADO:
            _completar_solicitud_especial(pedido_bloqueado)

    logger.info(
        "Estado de pedido actualizado",
        extra={
            "tipo_pedido": tipo,
            "pedido_id": pedido_bloqueado.id,
            "estado_anterior": estado_anterior,
            "estado_nuevo": estado_nuevo_real,
            "origen": origen,
        },
    )
    return pedido_bloqueado, False
