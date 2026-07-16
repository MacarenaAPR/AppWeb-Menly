from django.db import transaction
from django.db.models import Max

from menu.models import (
    PedidoEspecial,
    PedidoManual,
    PedidoWhatsApp,
    Restaurante,
    RestaurantePedidoSecuencia,
)


MAX_NUMERO_PEDIDO = 9999


def _ultimo_numero_historico(restaurante_id):
    maximos = [
        modelo.objects.filter(restaurante_id=restaurante_id).aggregate(
            maximo=Max("numero_pedido")
        )["maximo"] or 0
        for modelo in (PedidoWhatsApp, PedidoManual, PedidoEspecial)
    ]
    return min(max(maximos), MAX_NUMERO_PEDIDO)


def obtener_siguiente_numero_pedido(restaurante):
    """Reserva un correlativo operativo compartido para un restaurante."""
    with transaction.atomic():
        Restaurante.objects.select_for_update().only("id").get(id=restaurante.id)
        try:
            secuencia = RestaurantePedidoSecuencia.objects.select_for_update().get(
                restaurante_id=restaurante.id
            )
        except RestaurantePedidoSecuencia.DoesNotExist:
            secuencia = RestaurantePedidoSecuencia.objects.create(
                restaurante_id=restaurante.id,
                ultimo_numero=_ultimo_numero_historico(restaurante.id),
            )
        siguiente = 1 if secuencia.ultimo_numero >= MAX_NUMERO_PEDIDO else secuencia.ultimo_numero + 1
        secuencia.ultimo_numero = siguiente
        secuencia.save(update_fields=["ultimo_numero", "fecha_actualizacion"])
        return siguiente
