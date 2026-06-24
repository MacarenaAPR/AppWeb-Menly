from menu.models import PedidoEspecial, PedidoWhatsApp


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

RESERVA_PENDIENTE = "pendiente"
RESERVA_CANCELADA = "cancelada"
