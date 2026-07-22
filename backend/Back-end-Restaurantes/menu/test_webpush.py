import socket
from datetime import time
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from pywebpush import WebPushException
from requests import Response
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
    WebPushNoRedirectSession,
    enviar_push_nuevo_pedido,
    enviar_push_nuevo_pedido_seguro,
    programar_push_nuevo_pedido,
)
from menu.services.webpush_endpoints import validate_webpush_endpoint
from menu.serializers import PushSubscriptionSerializer


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
        self.endpoint = "https://fcm.googleapis.com/fcm/send/device-a"
        self.dns_patcher = patch(
            "menu.services.webpush_endpoints.socket.getaddrinfo",
            return_value=[
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    ("142.250.72.202", 443),
                ),
            ],
        )
        self.dns_patcher.start()
        self.addCleanup(self.dns_patcher.stop)

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
            endpoint="https://fcm.googleapis.com/fcm/send/kds",
            p256dh="C" * 87,
            auth="D" * 22,
            tipo_dispositivo=PushSubscription.TIPO_KDS,
        )
        PushSubscription.objects.create(
            restaurante=self.otro_restaurante,
            usuario=self.otro_usuario,
            endpoint="https://fcm.googleapis.com/fcm/send/other",
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

    def test_validador_rechaza_destinos_ssrf_y_urls_malformadas(self):
        endpoints_invalidos = [
            "http://example.com/push",
            "https://localhost/push",
            "https://127.0.0.1/push",
            "https://[::1]/push",
            "https://10.0.0.1/push",
            "https://172.16.0.1/push",
            "https://192.168.1.1/push",
            "https://[fc00::1]/push",
            "https://[fe80::1]/push",
            "https://169.254.169.254/latest/meta-data/secret",
            "https://192.0.2.1/push",
            "https://user:password@fcm.googleapis.com/push",
            "https://fcm.googleapis.com:8443/push",
            "https://fcm.googleapis.com.attacker.test/push",
            "https://-bad.notify.windows.com/push",
            "https://bad_host.notify.windows.com/push",
            "ftp://fcm.googleapis.com/push",
            "https://2130706433/push",
            "https://0x7f000001/push",
            "https://0177.0.0.1/push",
        ]

        for endpoint in endpoints_invalidos:
            with self.subTest(endpoint=endpoint):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Endpoint Web Push no permitido.",
                ):
                    validate_webpush_endpoint(endpoint)

    def test_validador_acepta_cada_proveedor_autorizado(self):
        endpoints_validos = [
            "https://fcm.googleapis.com/fcm/send/chrome",
            "https://updates.push.services.mozilla.com/wpush/v2/firefox",
            "https://web.push.apple.com/QD-safari",
            "https://db3.notify.windows.com/?token=edge",
        ]

        for endpoint in endpoints_validos:
            with self.subTest(endpoint=endpoint):
                serializer = PushSubscriptionSerializer(
                    data=self.payload_suscripcion(endpoint=endpoint)
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_validador_rechaza_dns_privado_y_dns_mixto(self):
        respuestas = [
            [
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    ("10.0.0.5", 443),
                ),
            ],
            [
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    ("142.250.72.202", 443),
                ),
                (
                    socket.AF_INET6,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    ("fe80::1", 443, 0, 0),
                ),
            ],
        ]

        for respuesta in respuestas:
            with self.subTest(respuesta=respuesta):
                with patch(
                    "menu.services.webpush_endpoints.socket.getaddrinfo",
                    return_value=respuesta,
                ):
                    with self.assertRaises(ValidationError):
                        validate_webpush_endpoint(self.endpoint)

    def test_endpoint_invalido_no_se_guarda_y_responde_error_generico(self):
        self.client.force_authenticate(self.usuario)
        endpoint = "https://169.254.169.254/latest/meta-data/secret-token"

        response = self.client.post(
            "/api/push/subscriptions/",
            self.payload_suscripcion(endpoint=endpoint),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            str(response.data["endpoint"][0]),
            "Endpoint Web Push no permitido.",
        )
        self.assertNotIn("169.254.169.254", str(response.data))
        self.assertFalse(PushSubscription.objects.exists())

    @override_settings(
        WEBPUSH_VAPID_PRIVATE_KEY="private-test-key",
        WEBPUSH_VAPID_SUBJECT="mailto:test@menly.cl",
    )
    @patch("menu.services.webpush.webpush")
    def test_suscripcion_antigua_insegura_no_llega_a_pywebpush(self, webpush_mock):
        endpoint = "http://169.254.169.254/latest/meta-data/secret-token"
        suscripcion = PushSubscription.objects.create(
            restaurante=self.restaurante,
            usuario=self.usuario,
            endpoint=endpoint,
            p256dh="A" * 87,
            auth="B" * 22,
            tipo_dispositivo=PushSubscription.TIPO_PANEL,
        )

        with self.assertLogs("menu.services.webpush", level="WARNING") as logs:
            enviar_push_nuevo_pedido(self.crear_pedido())

        webpush_mock.assert_not_called()
        suscripcion.refresh_from_db()
        self.assertFalse(suscripcion.activo)
        self.assertNotIn(endpoint, " ".join(logs.output))
        self.assertNotIn("secret-token", " ".join(logs.output))

    @override_settings(
        WEBPUSH_VAPID_PRIVATE_KEY="private-test-key",
        WEBPUSH_VAPID_SUBJECT="mailto:test@menly.cl",
    )
    @patch("menu.services.webpush.webpush")
    def test_suscripcion_insegura_no_impide_enviar_a_la_siguiente(self, webpush_mock):
        valida = PushSubscription.objects.create(
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
            endpoint="https://localhost/private",
            p256dh="C" * 87,
            auth="D" * 22,
            tipo_dispositivo=PushSubscription.TIPO_PANEL,
        )

        enviar_push_nuevo_pedido(self.crear_pedido())

        webpush_mock.assert_called_once()
        self.assertEqual(
            webpush_mock.call_args.kwargs["subscription_info"]["endpoint"],
            valida.endpoint,
        )
        self.assertIsInstance(
            webpush_mock.call_args.kwargs["requests_session"],
            WebPushNoRedirectSession,
        )

    @patch("requests.adapters.HTTPAdapter.send")
    def test_sesion_no_sigue_redirecciones_hacia_destinos_peligrosos(self, send_mock):
        destinos = [
            "https://localhost/private",
            "https://10.0.0.5/private",
            "http://169.254.169.254/latest/meta-data/",
        ]

        with WebPushNoRedirectSession() as session:
            for destino in destinos:
                with self.subTest(destino=destino):
                    redirect = Response()
                    redirect.status_code = 307
                    redirect.headers["Location"] = destino
                    redirect._content = b""
                    send_mock.reset_mock()
                    send_mock.return_value = redirect

                    response = session.post(
                        "https://fcm.googleapis.com/redirect"
                    )

                    send_mock.assert_called_once()
                    self.assertEqual(response.status_code, 307)
                    self.assertEqual(response.history, [])
