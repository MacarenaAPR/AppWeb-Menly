import json
import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections
from pywebpush import WebPushException, webpush

from menu.models import PedidoWhatsApp, PushSubscription


logger = logging.getLogger(__name__)
ESTADOS_SUSCRIPCION_INVALIDA = {404, 410}
WEBPUSH_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="menly-webpush")


def _desactivar_suscripcion_invalida(suscripcion, status_code):
    if status_code not in ESTADOS_SUSCRIPCION_INVALIDA:
        return

    PushSubscription.objects.filter(pk=suscripcion.pk).update(activo=False)


def enviar_push_nuevo_pedido(pedido):
    if not settings.WEBPUSH_VAPID_PRIVATE_KEY or not settings.WEBPUSH_VAPID_SUBJECT:
        logger.warning(
            "Web Push no configurado; se omite el envio",
            extra={"pedido_id": pedido.id, "restaurante_id": pedido.restaurante_id},
        )
        return

    payload = {
        "type": "nuevo_pedido",
        "title": "Nuevo pedido",
        "body": "Ha llegado un nuevo pedido de WhatsApp.",
        "pedido_id": pedido.id,
        "url": f"/dashboard/{pedido.restaurante.slug}/pedidos",
        "tag": f"pedido-whatsapp-{pedido.id}",
    }
    suscripciones = PushSubscription.objects.filter(
        restaurante_id=pedido.restaurante_id,
        tipo_dispositivo=PushSubscription.TIPO_PANEL,
        activo=True,
    ).only("id", "endpoint", "p256dh", "auth")

    for suscripcion in suscripciones.iterator():
        try:
            webpush(
                subscription_info={
                    "endpoint": suscripcion.endpoint,
                    "keys": {
                        "p256dh": suscripcion.p256dh,
                        "auth": suscripcion.auth,
                    },
                },
                data=json.dumps(payload),
                vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.WEBPUSH_VAPID_SUBJECT},
                ttl=60,
                timeout=5,
            )
        except WebPushException as error:
            status_code = getattr(getattr(error, "response", None), "status_code", None)
            _desactivar_suscripcion_invalida(suscripcion, status_code)
            logger.warning(
                "Fallo enviando Web Push",
                extra={
                    "pedido_id": pedido.id,
                    "restaurante_id": pedido.restaurante_id,
                    "suscripcion_id": suscripcion.id,
                    "push_status": status_code,
                },
            )
        except Exception:
            logger.exception(
                "Error inesperado enviando Web Push",
                extra={
                    "pedido_id": pedido.id,
                    "restaurante_id": pedido.restaurante_id,
                    "suscripcion_id": suscripcion.id,
                },
            )


def enviar_push_nuevo_pedido_seguro(pedido):
    try:
        enviar_push_nuevo_pedido(pedido)
    except Exception:
        logger.exception(
            "No se pudo ejecutar el envio Web Push del pedido",
            extra={"pedido_id": pedido.id, "restaurante_id": pedido.restaurante_id},
        )


def _enviar_push_nuevo_pedido_por_id(pedido_id):
    close_old_connections()
    try:
        pedido = (
            PedidoWhatsApp.objects
            .select_related("restaurante")
            .filter(pk=pedido_id)
            .first()
        )
        if pedido:
            enviar_push_nuevo_pedido_seguro(pedido)
    finally:
        close_old_connections()


def programar_push_nuevo_pedido(pedido_id):
    try:
        WEBPUSH_EXECUTOR.submit(_enviar_push_nuevo_pedido_por_id, pedido_id)
    except RuntimeError:
        logger.exception(
            "No se pudo programar el envio Web Push",
            extra={"pedido_id": pedido_id},
        )
