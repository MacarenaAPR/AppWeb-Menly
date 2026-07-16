from datetime import time
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from pywebpush import WebPushException
from rest_framework import status
from rest_framework.test import APIClient

from menu.models import (
    Categoria,
    HorarioAtencion,
    PedidoWhatsApp,
    Producto,
    PushSubscription,
    Restaurante,
    UsuarioRestaurante,
)
from menu.services.webpush import (
    enviar_push_nuevo_pedido,
    enviar_push_nuevo_pedido_seguro,
    programar_push_nuevo_pedido,
)


class WebPushTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.usuario = User.objects.create_user("push@test.com", password="secreto")
        self.otro_usuario = User.objects.create_user("push-otro@test.com", password="secreto")
        self.restaurante = Restaurante.objects.create(
            nombre_empresa="Restaurante Push",
            slug="restaurante-push",
            rut="11111111-1",
            telefono="999999999",
            email_contacto="push@test.com",
            direccion="Calle Push 1",
            ciudad="Santiago",
            activo=True,
            carrito_whatsapp_activo=True,
            whatsapp="56999999999",
        )
        self.otro_restaurante = Restaurante.objects.create(
            nombre_empresa="Otro Push",
            slug="otro-push",
            rut="22222222-2",
            telefono="988888888",
            email_contacto="otro-push@test.com",
            direccion="Calle Push 2",
            ciudad="Santiago",
            activo=True,
        )
        UsuarioRestaurante.objects.create(
            user=self.usuario,
            restaurante=self.restaurante,
            rol="dueno",
            activo=True,
        )
        UsuarioRestaurante.objects.create(
            user=self.otro_usuario,
            restaurante=self.otro_restaurante,
            rol="dueno",
            activo=True,
        )
        self.endpoint = "https://push.example.test/subscription/device-a"

    def payload_suscripcion(self, endpoint=None, **cambios):
        payload = {
            "endpoint": endpoint or self.endpoint,
            "keys": {"p256dh": "A" * 87, "auth": "B" * 22},
            "tipo_dispositivo": "panel",
        }
        payload.update(cambios)
        return payload

    def crear_pedido(self, restaurante=None):
        restaurante = restaurante or self.restaurante
        return PedidoWhatsApp.objects.create(
            restaurante=restaurante,
            numero_pedido=1,
            nombre_cliente="Cliente Push",
            telefono_cliente="912345678",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[{"nombre": "Producto", "cantidad": 1}],
            total=1000,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56999999999",
        )

    def test_endpoints_requieren_autenticacion(self):
        registro = self.client.post(
            "/api/push/subscriptions/",
            self.payload_suscripcion(),
            format="json",
        )
        config = self.client.get("/api/push/config/")

        self.assertEqual(registro.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(config.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_registra_y_actualiza_sin_duplicar_para_restaurante_actual(self):
        self.client.force_authenticate(self.usuario)
        primera = self.client.post(
            "/api/push/subscriptions/",
            self.payload_suscripcion(),
            format="json",
        )
        segunda = self.client.post(
            "/api/push/subscriptions/",
            self.payload_suscripcion(keys={"p256dh": "C" * 87, "auth": "D" * 22}),
            format="json",
        )
        estado = self.client.post(
            "/api/push/subscriptions/status/",
            {"endpoint": self.endpoint},
            format="json",
        )

        self.assertEqual(primera.status_code, status.HTTP_201_CREATED)
        self.assertEqual(segunda.status_code, status.HTTP_200_OK)
        self.assertTrue(estado.data["subscribed"])
        self.assertEqual(PushSubscription.objects.count(), 1)
        suscripcion = PushSubscription.objects.get()
        self.assertEqual(suscripcion.restaurante, self.restaurante)
        self.assertEqual(suscripcion.usuario, self.usuario)
        self.assertEqual(suscripcion.p256dh, "C" * 87)

        eliminacion = self.client.delete(
            "/api/push/subscriptions/",
            {"endpoint": self.endpoint},
            format="json",
        )
        suscripcion.refresh_from_db()
        self.assertTrue(eliminacion.data["updated"])
        self.assertFalse(suscripcion.activo)

    def test_impide_reasignar_consultar_o_desactivar_suscripcion_ajena(self):
        PushSubscription.objects.create(
            restaurante=self.restaurante,
            usuario=self.usuario,
            endpoint=self.endpoint,
            p256dh="A" * 87,
            auth="B" * 22,
            tipo_dispositivo=PushSubscription.TIPO_PANEL,
        )
        self.client.force_authenticate(self.otro_usuario)

        registro = self.client.post(
            "/api/push/subscriptions/",
            self.payload_suscripcion(),
            format="json",
        )
        estado = self.client.post(
            "/api/push/subscriptions/status/",
            {"endpoint": self.endpoint},
            format="json",
        )
        eliminacion = self.client.delete(
            "/api/push/subscriptions/",
            {"endpoint": self.endpoint},
            format="json",
        )

        self.assertEqual(registro.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(estado.data["subscribed"])
        self.assertFalse(eliminacion.data["updated"])
        self.assertTrue(PushSubscription.objects.get().activo)

    @override_settings(
        WEBPUSH_VAPID_PRIVATE_KEY="private-test-key",
        WEBPUSH_VAPID_SUBJECT="mailto:test@menly.cl",
    )
    @patch("menu.services.webpush.webpush")
    def test_envia_solo_a_paneles_activos_del_restaurante_del_pedido(self, webpush_mock):
        panel = PushSubscription.objects.create(
            restaurante=self.restaurante,
            usuario=self.usuario,
            endpoint=self.endpoint,
            p256dh="A" * 87,
            auth="B" * 22,
            tipo_dispositivo=PushSubscription.TIPO_PANEL,
        )
        PushSubscription.objects.create(
            restaurante=self.restaurante,
            usuario=self.usuario,
            endpoint="https://push.example.test/subscription/kds",
            p256dh="C" * 87,
            auth="D" * 22,
            tipo_dispositivo=PushSubscription.TIPO_KDS,
        )
        PushSubscription.objects.create(
            restaurante=self.otro_restaurante,
            usuario=self.otro_usuario,
            endpoint="https://push.example.test/subscription/other",
            p256dh="E" * 87,
            auth="F" * 22,
            tipo_dispositivo=PushSubscription.TIPO_PANEL,
        )

        pedido = self.crear_pedido()
        enviar_push_nuevo_pedido(pedido)

        webpush_mock.assert_called_once()
        self.assertEqual(
            webpush_mock.call_args.kwargs["subscription_info"]["endpoint"],
            panel.endpoint,
        )

    @override_settings(
        WEBPUSH_VAPID_PRIVATE_KEY="private-test-key",
        WEBPUSH_VAPID_SUBJECT="mailto:test@menly.cl",
    )
    @patch("menu.services.webpush.webpush")
    def test_desactiva_endpoint_permanentemente_invalido(self, webpush_mock):
        suscripcion = PushSubscription.objects.create(
            restaurante=self.restaurante,
            usuario=self.usuario,
            endpoint=self.endpoint,
            p256dh="A" * 87,
            auth="B" * 22,
            tipo_dispositivo=PushSubscription.TIPO_PANEL,
        )
        webpush_mock.side_effect = WebPushException(
            "Gone",
            response=SimpleNamespace(status_code=410),
        )

        enviar_push_nuevo_pedido(self.crear_pedido())

        suscripcion.refresh_from_db()
        self.assertFalse(suscripcion.activo)

    @patch("menu.services.webpush.enviar_push_nuevo_pedido", side_effect=RuntimeError("fallo"))
    def test_fallo_push_no_se_propaga_a_creacion_del_pedido(self, _enviar_mock):
        pedido = self.crear_pedido()

        enviar_push_nuevo_pedido_seguro(pedido)

        self.assertTrue(PedidoWhatsApp.objects.filter(pk=pedido.pk).exists())

    @patch("menu.services.webpush.WEBPUSH_EXECUTOR.submit")
    def test_programacion_del_push_no_ejecuta_el_envio_en_el_request(self, submit_mock):
        programar_push_nuevo_pedido(123)

        submit_mock.assert_called_once()
        self.assertEqual(submit_mock.call_args.args[1], 123)

    @patch("menu.views.programar_push_nuevo_pedido")
    def test_creacion_publica_programa_push_una_vez_y_replay_no_duplica(self, enviar_mock):
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=timezone.localtime().isoweekday(),
            hora_apertura=time(0, 0),
            hora_cierre=time(23, 59),
            cerrado=False,
            activo=True,
        )
        categoria = Categoria.objects.create(
            restaurante=self.restaurante,
            nombre="Push",
            orden=1,
            activa=True,
        )
        producto = Producto.objects.create(
            restaurante=self.restaurante,
            categoria=categoria,
            nombre="Producto Push",
            precio=1000,
            disponible=True,
        )
        payload = {
            "nombre_cliente": "Cliente Push",
            "telefono_cliente": "912345678",
            "tipo_entrega": PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            "direccion_entrega": "",
            "metodo_pago_id": None,
            "productos": [{"producto_id": producto.id, "cantidad": 1}],
        }
        headers = {"HTTP_IDEMPOTENCY_KEY": "push-idempotente-1"}

        with self.captureOnCommitCallbacks(execute=True):
            primera = self.client.post(
                f"/api/pedidos-whatsapp/{self.restaurante.slug}/",
                payload,
                format="json",
                **headers,
            )
        with self.captureOnCommitCallbacks(execute=True):
            replay = self.client.post(
                f"/api/pedidos-whatsapp/{self.restaurante.slug}/",
                payload,
                format="json",
                **headers,
            )

        self.assertEqual(primera.status_code, status.HTTP_201_CREATED)
        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        enviar_mock.assert_called_once()
        self.assertEqual(PedidoWhatsApp.objects.count(), 1)
