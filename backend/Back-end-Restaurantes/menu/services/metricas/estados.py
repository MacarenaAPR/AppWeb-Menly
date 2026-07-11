from menu.models import PedidoEspecial, PedidoManual, PedidoWhatsApp


WHATSAPP_FINALIZADOS = (PedidoWhatsApp.ESTADO_ENTREGADO,)
ESPECIALES_FINALIZADOS = (
    PedidoEspecial.ESTADO_ENTREGADO,
    "completado",
)

WHATSAPP_CANCELADOS = (PedidoWhatsApp.ESTADO_CANCELADO,)
ESPECIALES_CANCELADOS = (PedidoEspecial.ESTADO_CANCELADO,)

WHATSAPP_ACTIVOS = tuple(
    estado for estado, _ in PedidoWhatsApp.ESTADOS
    if estado not in WHATSAPP_FINALIZADOS and estado not in WHATSAPP_CANCELADOS
)
ESPECIALES_ACTIVOS = tuple(
    estado for estado, _ in PedidoEspecial.ESTADOS
    if estado not in ESPECIALES_FINALIZADOS and estado not in ESPECIALES_CANCELADOS
)

MANUALES_FINALIZADOS = (PedidoManual.ESTADO_ENTREGADO,)
MANUALES_CANCELADOS = (PedidoManual.ESTADO_CANCELADO,)
MANUALES_ACTIVOS = tuple(
    estado for estado, _ in PedidoManual.ESTADOS
    if estado not in MANUALES_FINALIZADOS and estado not in MANUALES_CANCELADOS
)

RESERVA_PENDIENTE = "pendiente"
RESERVA_CANCELADA = "cancelada"
