
from django.test import TestCase, TransactionTestCase
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from importlib import import_module
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections

from .models import Restaurante, UsuarioRestaurante, Categoria, Producto, ProductoVariante, GrupoOpcionesProducto, OpcionProducto, Reserva, Mesa, RespaldoRestaurante, HorarioAtencion, MetodoPago, BitacoraProducto, SolicitudEspecial, Notificacion, PedidoWhatsApp, PedidoIdempotencia, HistorialEstadoPedidoWhatsApp, HistorialEstadoPedidoManual, HistorialEstadoPedidoEspecial, PedidoEspecial, PedidoManual, PedidoManualItem, RestaurantePedidoSecuencia, ActivacionCocina, SesionCocina, Plan
from .views import CrearReservaPublicaView, PublicReservaRateThrottle, ProductoClickRateThrottle, ProductoClickView, PasswordResetRequestView, PasswordResetRateThrottle, CrearSolicitudEspecialPublicaView, PublicSolicitudEspecialRateThrottle
from .cache_utils import invalidate_menu_cache, menu_cache_key
from .utils import get_slug_from_host, validar_horario_reserva
from .services.estado_restaurante import calcular_estado_abierto, calcular_estado_restaurante
from .services.estados_pedidos import TransicionEstadoInvalida, cambiar_estado_pedido
from .services.cocina import obtener_comandas_activas
from .services.pedidos_whatsapp import (
    MAX_CANTIDAD_PEDIDO_MANUAL,
    MAX_CANTIDAD_PEDIDO_WHATSAPP,
    ProductosPedidoValidationError,
    calcular_hash_pedido_publico,
    generar_mensaje_whatsapp,
    normalizar_productos_pedido,
)
from .services.metricas.pedidos import pedidos_manuales_activos, pedidos_manuales_finalizados
from .serializers import PedidoWhatsAppCreateSerializer, PedidoWhatsAppDashboardSerializer
from django.core.cache import cache


class TenantHostTests(TestCase):
    def test_get_slug_from_host_soporta_produccion_y_local(self):
        self.assertEqual(get_slug_from_host("lamechada.menly.cl"), "lamechada")
        self.assertEqual(get_slug_from_host("demo.menly.localhost:5173"), "demo")
        self.assertEqual(get_slug_from_host("lamechada.lvh.me:5173"), "lamechada")

    def test_get_slug_from_host_ignora_hosts_raiz_y_subdominios_reservados(self):
        self.assertIsNone(get_slug_from_host("localhost:5173"))
        self.assertIsNone(get_slug_from_host("menly.cl"))
        self.assertIsNone(get_slug_from_host("api.menly.cl"))


class BaseTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.dueno = User.objects.create_user(
            username="dueno@test.com",
            email="dueno@test.com",
            password="123456"
        )

        self.admin = User.objects.create_user(
            username="admin@test.com",
            email="admin@test.com",
            password="123456"
        )

        self.empleado = User.objects.create_user(
            username="empleado@test.com",
            email="empleado@test.com",
            password="123456"
        )

        self.restaurante = Restaurante.objects.create(
            nombre_empresa="Restaurante Test",
            slug="restaurante-test",
            rut="11111111-1",
            telefono="999999999",
            email_contacto="test@test.com",
            direccion="Calle Test 123",
            ciudad="Antofagasta",
            activo=True,
        )

        self.otro_restaurante = Restaurante.objects.create(
            nombre_empresa="Otro Restaurante",
            slug="otro-restaurante",
            rut="22222222-2",
            telefono="888888888",
            email_contacto="otro@test.com",
            direccion="Otra Calle 123",
            ciudad="Santiago",
            activo=True,
        )

        self.perfil_dueno = UsuarioRestaurante.objects.create(
            user=self.dueno,
            restaurante=self.restaurante,
            rol="dueno",
            activo=True,
        )

        self.perfil_admin = UsuarioRestaurante.objects.create(
            user=self.admin,
            restaurante=self.restaurante,
            rol="admin",
            activo=True,
        )

        self.perfil_empleado = UsuarioRestaurante.objects.create(
            user=self.empleado,
            restaurante=self.restaurante,
            rol="empleado",
            activo=True,
        )

        self.categoria = Categoria.objects.create(
            restaurante=self.restaurante,
            nombre="Bebidas",
            orden=1,
            activa=True,
        )

        self.categoria_otro_restaurante = Categoria.objects.create(
            restaurante=self.otro_restaurante,
            nombre="Comida",
            orden=1,
            activa=True,
        )

        self.producto = Producto.objects.create(
            restaurante=self.restaurante,
            categoria=self.categoria,
            nombre="Coca Cola",
            descripcion="Bebida",
            precio=1500,
            disponible=True,
            destacado=False,
            orden=1,
        )


class OfertasProductoTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.dueno)

    def test_calculo_sin_oferta_y_ofertas_limite(self):
        self.assertFalse(self.producto.en_oferta)
        self.assertEqual(self.producto.precio_efectivo, Decimal("1500"))
        self.assertIsNone(self.producto.precio_oferta)

        casos = [(1, 1485), (20, 1200), (99, 15)]
        for porcentaje, esperado in casos:
            with self.subTest(porcentaje=porcentaje):
                self.producto.porcentaje_descuento = porcentaje
                self.assertEqual(self.producto.precio_efectivo, Decimal(esperado))

    def test_redondeo_half_up(self):
        self.producto.precio = 9990
        self.producto.porcentaje_descuento = 15
        self.assertEqual(self.producto.precio_efectivo, Decimal("8492"))
        self.assertEqual(self.producto.monto_descuento, Decimal("1498"))

    def test_api_rechaza_porcentajes_invalidos_y_precio_negativo(self):
        endpoint = "/api/mi-restaurante/productos/agregar/"
        invalidos = [0, 100, -1, 101, 1.5]
        for indice, porcentaje in enumerate(invalidos, start=2):
            response = self.client.post(endpoint, {
                "categoria": self.categoria.id,
                "nombre": f"Oferta invalida {indice}",
                "precio": 10000,
                "porcentaje_descuento": porcentaje,
                "orden": indice,
            }, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(endpoint, {
            "categoria": self.categoria.id,
            "nombre": "Precio negativo",
            "precio": -1,
            "orden": 9,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_actualizar_y_desactivar_oferta_usa_datos_validados(self):
        endpoint = f"/api/mi-restaurante/productos/{self.producto.id}/actualizar/"
        activar = self.client.patch(endpoint, {
            "porcentaje_descuento": 20,
            "precio": 10000,
        }, format="json")
        self.assertEqual(activar.status_code, status.HTTP_200_OK)
        self.assertEqual(activar.data["precio_oferta"], "8000")

        invalido = self.client.patch(endpoint, {"precio": -100}, format="json")
        self.assertEqual(invalido.status_code, status.HTTP_400_BAD_REQUEST)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.precio, Decimal("10000"))

        desactivar = self.client.patch(
            endpoint,
            {"porcentaje_descuento": ""},
            format="multipart",
        )
        self.assertEqual(desactivar.status_code, status.HTTP_200_OK)
        self.assertFalse(desactivar.data["en_oferta"])
        self.assertEqual(desactivar.data["precio_efectivo"], "10000")

    def test_api_publica_y_privada_exponen_contrato_oferta(self):
        self.producto.porcentaje_descuento = 20
        self.producto.save(update_fields=["porcentaje_descuento"])
        invalidate_menu_cache(self.restaurante)

        publico = self.client.get(f"/api/menu/{self.restaurante.slug}/")
        producto_publico = publico.json()["categorias"][0]["productos"][0]
        self.assertEqual(producto_publico["precio"], "1500")
        self.assertTrue(producto_publico["en_oferta"])
        self.assertEqual(producto_publico["precio_oferta"], "1200")
        self.assertEqual(producto_publico["precio_efectivo"], "1200")

        privado = self.client.get("/api/mi-restaurante/")
        producto_privado = next(
            item for item in privado.data["productos"] if item["id"] == self.producto.id
        )
        self.assertEqual(producto_privado["porcentaje_descuento"], 20)
        self.assertEqual(producto_privado["precio_efectivo"], "1200")

    def test_actualizar_oferta_invalida_cache_del_menu(self):
        inicial = self.client.get(f"/api/menu/{self.restaurante.slug}/")
        self.assertFalse(
            inicial.json()["categorias"][0]["productos"][0]["en_oferta"]
        )

        actualizar = self.client.patch(
            f"/api/mi-restaurante/productos/{self.producto.id}/actualizar/",
            {"porcentaje_descuento": 20},
            format="json",
        )
        self.assertEqual(actualizar.status_code, status.HTTP_200_OK)

        refrescado = self.client.get(f"/api/menu/{self.restaurante.slug}/")
        producto = refrescado.json()["categorias"][0]["productos"][0]
        self.assertTrue(producto["en_oferta"])
        self.assertEqual(producto["precio_efectivo"], "1200")

    def test_variante_y_extras_descuentan_solo_precio_base(self):
        self.producto.porcentaje_descuento = 20
        self.producto.save(update_fields=["porcentaje_descuento"])
        variante = ProductoVariante.objects.create(
            producto=self.producto,
            nombre="Grande",
            precio=10000,
            activo=True,
        )
        grupo = GrupoOpcionesProducto.objects.create(
            producto=self.producto,
            nombre="Extras",
            maximo_selecciones=1,
        )
        extra = OpcionProducto.objects.create(
            grupo=grupo,
            nombre="Queso",
            precio_adicional=1500,
        )
        snapshot, total = normalizar_productos_pedido(self.restaurante, [{
            "producto_id": self.producto.id,
            "variante_id": variante.id,
            "cantidad": 2,
            "opciones": [extra.id],
        }])
        item = snapshot[0]
        self.assertEqual(item["precio_original"], 10000)
        self.assertEqual(item["monto_descuento"], 2000)
        self.assertEqual(item["precio_base"], 8000)
        self.assertEqual(item["opciones_total"], 1500)
        self.assertEqual(item["precio_unitario"], 9500)
        self.assertEqual(total, 19000)

    def test_api_variante_expone_precio_original_y_efectivo(self):
        self.producto.porcentaje_descuento = 20
        self.producto.save(update_fields=["porcentaje_descuento"])
        ProductoVariante.objects.create(
            producto=self.producto,
            nombre="Familiar",
            precio=12000,
            activo=True,
        )
        invalidate_menu_cache(self.restaurante)

        response = self.client.get(f"/api/menu/{self.restaurante.slug}/")
        variante = response.json()["categorias"][0]["productos"][0]["variantes"][0]
        self.assertEqual(variante["precio"], "12000")
        self.assertEqual(variante["precio_oferta"], "9600")
        self.assertEqual(variante["precio_efectivo"], "9600")

    def test_pedido_whatsapp_y_manual_guardan_snapshot_de_oferta(self):
        self.producto.porcentaje_descuento = 20
        self.producto.save(update_fields=["porcentaje_descuento"])
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.pedidos_pos = True
        self.restaurante.whatsapp = "56911111111"
        self.restaurante.save(update_fields=[
            "carrito_whatsapp_activo", "pedidos_pos", "whatsapp"
        ])

        whatsapp = PedidoWhatsAppCreateSerializer(
            data={
                "nombre_cliente": "Cliente",
                "telefono_cliente": "56922222222",
                "tipo_entrega": PedidoWhatsApp.TIPO_RETIRO_LOCAL,
                "productos": [{"producto_id": self.producto.id, "cantidad": 1}],
            },
            context={"restaurante": self.restaurante},
        )
        self.assertTrue(whatsapp.is_valid(), whatsapp.errors)
        pedido_whatsapp = whatsapp.save()
        self.assertEqual(pedido_whatsapp.productos_snapshot[0]["precio_base"], 1200)
        self.assertEqual(
            pedido_whatsapp.productos_snapshot[0]["porcentaje_descuento_aplicado"],
            20,
        )

        manual = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            {
                "tipo_entrega": PedidoManual.TIPO_RETIRO,
                "items": [{"producto_id": self.producto.id, "cantidad": 1}],
            },
            format="json",
        )
        self.assertEqual(manual.status_code, status.HTTP_201_CREATED)
        item_manual = PedidoManualItem.objects.get(pedido_id=manual.data["pedido"]["id"])
        self.assertEqual(item_manual.precio_original, Decimal("1500"))
        self.assertEqual(item_manual.porcentaje_descuento_aplicado, 20)
        self.assertEqual(item_manual.monto_descuento, Decimal("300"))
        self.assertEqual(item_manual.precio_unitario, Decimal("1200"))

    def test_snapshot_no_cambia_y_edicion_conserva_linea_existente(self):
        self.restaurante.pedidos_pos = True
        self.restaurante.save(update_fields=["pedidos_pos"])
        self.producto.porcentaje_descuento = 20
        self.producto.save(update_fields=["porcentaje_descuento"])
        crear = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            {
                "tipo_entrega": PedidoManual.TIPO_RETIRO,
                "items": [{"producto_id": self.producto.id, "cantidad": 1}],
            },
            format="json",
        )
        pedido = PedidoManual.objects.get(id=crear.data["pedido"]["id"])

        self.producto.precio = 5000
        self.producto.porcentaje_descuento = 50
        self.producto.save(update_fields=["precio", "porcentaje_descuento"])
        editar = self.client.patch(
            f"/api/mi-restaurante/pedidos/manuales/{pedido.id}/",
            {
                "items": [{"producto_id": self.producto.id, "cantidad": 2}],
            },
            format="json",
        )
        self.assertEqual(editar.status_code, status.HTTP_200_OK)
        item = pedido.items.get()
        self.assertEqual(item.precio_unitario, Decimal("1200"))
        self.assertEqual(item.subtotal, Decimal("2400"))
        self.assertEqual(item.porcentaje_descuento_aplicado, 20)

    def test_edicion_whatsapp_conserva_precio_de_linea_existente(self):
        self.producto.porcentaje_descuento = 20
        self.producto.save(update_fields=["porcentaje_descuento"])
        pedido = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Cliente",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=normalizar_productos_pedido(
                self.restaurante,
                [{"producto_id": self.producto.id, "cantidad": 1}],
            )[0],
            total=1200,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )
        self.producto.precio = 5000
        self.producto.porcentaje_descuento = 50
        self.producto.save(update_fields=["precio", "porcentaje_descuento"])

        serializer = PedidoWhatsAppDashboardSerializer(
            pedido,
            data={
                "productos": [{"producto_id": self.producto.id, "cantidad": 2}],
            },
            partial=True,
            context={"restaurante": self.restaurante},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        actualizado = serializer.save()
        self.assertEqual(actualizado.total, 2400)
        self.assertEqual(actualizado.productos_snapshot[0]["precio_unitario"], 1200)
        self.assertEqual(
            actualizado.productos_snapshot[0]["porcentaje_descuento_aplicado"],
            20,
        )


class DashboardMetricasResilienciaTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.dueno)

    def test_ultimos_pedidos_sin_datos_devuelve_lista_vacia(self):
        response = self.client.get("/api/dashboard/ultimos-pedidos/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    def test_ultimos_pedidos_identifica_cada_origen_e_incluye_especiales_activos(self):
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.save(update_fields=["solicitudes_especiales_activas"])
        pedido_whatsapp = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="WhatsApp",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=1000,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )
        pedido_manual = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Manual",
            tipo_entrega=PedidoManual.TIPO_MESA,
            subtotal=2000,
            total=2000,
        )
        pedido_especial = PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Especial",
            telefono_cliente="56911111111",
            items=[],
            total=3000,
            fecha_entrega=timezone.localdate(),
        )

        response = self.client.get("/api/dashboard/ultimos-pedidos/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pedidos = response.json()
        referencias = {(pedido["tipo"], pedido["id"]) for pedido in pedidos}
        self.assertIn(("whatsapp", pedido_whatsapp.id), referencias)
        self.assertIn(("manual", pedido_manual.id), referencias)
        self.assertIn(("especial", pedido_especial.id), referencias)
        self.assertTrue(all("estado" in pedido for pedido in pedidos))

    def test_ultimos_pedidos_respeta_tenant_y_modulo_especiales(self):
        PedidoWhatsApp.objects.create(
            restaurante=self.otro_restaurante,
            numero_pedido=1,
            nombre_cliente="Cliente ajeno",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=1000,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )
        PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Especial inactivo",
            telefono_cliente="56911111111",
            items=[],
            total=3000,
            fecha_entrega=timezone.localdate(),
        )

        response = self.client.get("/api/dashboard/ultimos-pedidos/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    def test_metricas_resumen_sin_datos_devuelve_payload_vacio(self):
        response = self.client.get("/api/mi-restaurante/metricas/resumen/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["ventas"]["venta_real_mes"], 0)
        self.assertEqual(data["venta_total_diaria_operativa"], 0)
        self.assertEqual(data["reservas"]["reservas_hoy"], 0)
        self.assertEqual(data["productos"]["top_por_cantidad"], [])
        self.assertIsNone(data["productos"]["mas_vendido_mes"])

    @patch("menu.services.metricas.pedidos.metricas_canal_especiales")
    @patch("menu.services.metricas.productos.pedidos_especiales_finalizados")
    @patch("menu.services.metricas.resumen.metricas_reservas")
    def test_metricas_no_consulta_modulos_inactivos(
        self,
        mock_reservas,
        mock_productos_especiales,
        mock_metricas_especiales,
    ):
        self.restaurante.reservas_activas = False
        self.restaurante.solicitudes_especiales_activas = False
        self.restaurante.save(update_fields=["reservas_activas", "solicitudes_especiales_activas"])

        response = self.client.get("/api/mi-restaurante/metricas/resumen/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_reservas.assert_not_called()
        mock_productos_especiales.assert_not_called()
        mock_metricas_especiales.assert_not_called()
        self.assertEqual(response.json()["reservas"]["reservas_hoy"], 0)
        self.assertEqual(response.json()["canales"]["especiales"]["venta_real_hoy"], 0)

    def test_metricas_resumen_tolera_items_snapshot_invalidos(self):
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Cliente",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[
                "item-antiguo-invalido",
                {"nombre": "Completo", "cantidad": "abc", "precio": "1000"},
                {"nombre": "Bebida", "cantidad": "2", "precio": "bad", "subtotal": "bad"},
            ],
            total=0,
            estado=PedidoWhatsApp.ESTADO_ENTREGADO,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            nombre_cliente="Cancelado",
            telefono_cliente="999999999",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=4000,
            estado=PedidoWhatsApp.ESTADO_CANCELADO,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )
        PedidoWhatsApp.objects.create(
            restaurante=self.otro_restaurante,
            numero_pedido=1,
            nombre_cliente="Otro restaurante",
            telefono_cliente="999999999",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=7000,
            estado=PedidoWhatsApp.ESTADO_ENTREGADO,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )

        response = self.client.get("/api/mi-restaurante/metricas/resumen/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["ventas"]["venta_real_mes"], 0)
        self.assertEqual(data["venta_total_diaria_operativa"], 0)
        self.assertEqual(data["productos"]["top_por_cantidad"][0]["nombre"], "Bebida")
        self.assertEqual(data["productos"]["top_por_cantidad"][0]["cantidad"], 2)


class PedidoManualDashboardTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.restaurante.pedidos_pos = True
        self.restaurante.save(update_fields=["pedidos_pos"])
        self.client.force_authenticate(user=self.dueno)
        self.otro_producto = Producto.objects.create(
            restaurante=self.otro_restaurante,
            categoria=self.categoria_otro_restaurante,
            nombre="Producto externo",
            descripcion="No permitido",
            precio=9990,
            disponible=True,
            destacado=False,
            orden=1,
        )

    def payload_valido(self, **overrides):
        payload = {
            "nombre_cliente": "Camila",
            "telefono_cliente": "+56912345678",
            "tipo_entrega": "delivery",
            "direccion": "Los Robles 123",
            "numero_mesa": "",
            "observaciones": "Tocar el timbre",
            "items": [
                {
                    "producto_id": self.producto.id,
                    "cantidad": 2,
                    "observaciones": "Una sin cebolla",
                }
            ],
        }
        payload.update(overrides)
        return payload

    def test_crear_pedido_manual_valido_calcula_total_y_origen_menly(self):
        self.restaurante.slug = "laasesina-matatuhambre"
        self.restaurante.save(update_fields=["slug"])
        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            self.payload_valido(),
            format="json",
            HTTP_ORIGIN="https://www.menly.cl",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pedido = PedidoManual.objects.get()
        self.assertEqual(pedido.restaurante, self.restaurante)
        self.assertEqual(pedido.origen, PedidoManual.ORIGEN_MENLY)
        self.assertEqual(pedido.creado_por, self.dueno)
        self.assertEqual(int(pedido.total), 3000)
        self.assertEqual(pedido.items.count(), 1)
        item = pedido.items.first()
        self.assertEqual(item.nombre_producto, self.producto.nombre)
        self.assertEqual(int(item.precio_unitario), 1500)
        self.assertEqual(int(item.subtotal), 3000)
        data = response.json()["pedido"]
        self.assertEqual(data["items"][0]["nombre_producto"], self.producto.nombre)
        self.assertTrue(data["tracking_token"])
        self.assertEqual(
            data["tracking_url"],
            f"https://{self.restaurante.slug}.menly.cl/seguimiento/pedido/{data['tracking_token']}",
        )
        self.assertNotIn("https://www.menly.cl/", data["tracking_url"])
        self.assertEqual(data["cliente_nombre"], "Camila")
        self.assertEqual(data["cliente_telefono"], "+56912345678")

    def test_pedido_manual_variante_usa_precio_backend_y_guarda_snapshot(self):
        variante = ProductoVariante.objects.create(
            producto=self.producto,
            nombre="Familiar",
            descripcion="Para 4 personas",
            precio=6000,
            activo=True,
        )

        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            self.payload_valido(items=[{
                "producto_id": self.producto.id,
                "variante_id": variante.id,
                "cantidad": 2,
                "precio_unitario": 1,
            }]),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pedido = PedidoManual.objects.get()
        item = pedido.items.get()
        self.assertEqual(item.variante_id, variante.id)
        self.assertEqual(item.variante_nombre, "Familiar")
        self.assertEqual(int(item.precio_unitario), 6000)
        self.assertEqual(int(item.subtotal), 12000)
        self.assertEqual(int(pedido.total), 12000)
        self.assertEqual(response.json()["pedido"]["items"][0]["variante_id"], variante.id)

    def test_pedido_manual_exige_variante_activa_si_producto_tiene_variantes(self):
        ProductoVariante.objects.create(
            producto=self.producto,
            nombre="Individual",
            precio=2500,
            activo=True,
        )

        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            self.payload_valido(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items", response.json())
        self.assertFalse(PedidoManual.objects.exists())

    def test_pedido_manual_rechaza_variante_de_otro_producto_o_tenant(self):
        variante_externa = ProductoVariante.objects.create(
            producto=self.otro_producto,
            nombre="Externa",
            precio=1,
            activo=True,
        )

        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            self.payload_valido(items=[{
                "producto_id": self.producto.id,
                "variante_id": variante_externa.id,
                "cantidad": 1,
            }]),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(PedidoManual.objects.exists())

    def test_editar_items_pedido_manual_actualiza_variante_y_precio(self):
        individual = ProductoVariante.objects.create(
            producto=self.producto,
            nombre="Individual",
            precio=2500,
            activo=True,
        )
        familiar = ProductoVariante.objects.create(
            producto=self.producto,
            nombre="Familiar",
            precio=6000,
            activo=True,
        )
        crear = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            self.payload_valido(items=[{
                "producto_id": self.producto.id,
                "variante_id": individual.id,
                "cantidad": 1,
            }]),
            format="json",
        )
        pedido_id = crear.json()["pedido"]["id"]

        response = self.client.patch(
            f"/api/mi-restaurante/pedidos/manuales/{pedido_id}/",
            {"items": [{
                "producto_id": self.producto.id,
                "variante_id": familiar.id,
                "cantidad": 3,
                "precio_unitario": 1,
            }]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pedido = PedidoManual.objects.get(id=pedido_id)
        item = pedido.items.get()
        self.assertEqual(item.variante_id, familiar.id)
        self.assertEqual(item.variante_nombre, "Familiar")
        self.assertEqual(int(item.precio_unitario), 6000)
        self.assertEqual(int(pedido.total), 18000)

    def test_seguimiento_publico_manual_reutiliza_token_y_expone_payload_seguro(self):
        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            self.payload_valido(tipo_entrega="mesa", direccion="", numero_mesa="7"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pedido_data = response.json()["pedido"]
        token = pedido_data["tracking_token"]

        response = self.client.get(f"/api/public/pedidos/seguimiento/{token}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["numero_pedido"], pedido_data["numero_pedido"])
        self.assertEqual(data["restaurante_nombre"], self.restaurante.nombre_empresa)
        self.assertEqual(data["estado"], PedidoManual.ESTADO_PENDIENTE)
        self.assertEqual(data["tipo_entrega"], PedidoManual.TIPO_MESA)
        self.assertEqual(data["observaciones_cliente"], "Mesa 7")
        self.assertEqual(data["items"][0]["nombre"], self.producto.nombre)
        self.assertNotIn("id", data)
        self.assertNotIn("tracking_token", data)

        pedido_id = pedido_data["id"]
        response = self.client.patch(
            f"/api/mi-restaurante/pedidos/manuales/{pedido_id}/estado/",
            {"estado": PedidoManual.ESTADO_PREPARANDO},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["pedido"]["tracking_token"], token)

        response = self.client.get(f"/api/public/pedidos/seguimiento/{token}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["estado"], PedidoManual.ESTADO_PREPARANDO)

    def test_rechaza_pedido_manual_sin_items(self):
        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            self.payload_valido(items=[]),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(PedidoManual.objects.exists())

    def test_rechaza_delivery_sin_direccion(self):
        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            self.payload_valido(direccion=""),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("direccion", response.json())

    def test_rechaza_mesa_sin_numero_mesa(self):
        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            self.payload_valido(tipo_entrega="mesa", direccion="", numero_mesa=""),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("numero_mesa", response.json())

    def test_rechaza_producto_de_otro_restaurante(self):
        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            self.payload_valido(items=[{"producto_id": self.otro_producto.id, "cantidad": 1}]),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(PedidoManual.objects.exists())

    def test_listado_manual_es_tenant_safe(self):
        pedido_propio = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            total=1500,
            subtotal=1500,
            creado_por=self.dueno,
        )
        PedidoManual.objects.create(
            restaurante=self.otro_restaurante,
            numero_pedido=1,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            total=9990,
            subtotal=9990,
        )

        response = self.client.get("/api/mi-restaurante/pedidos/manuales/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], pedido_propio.id)

    def test_cambio_estado_manual_respeta_flujo(self):
        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            self.payload_valido(tipo_entrega="retiro", direccion=""),
            format="json",
        )
        pedido_id = response.json()["pedido"]["id"]

        response = self.client.patch(
            f"/api/mi-restaurante/pedidos/manuales/{pedido_id}/estado/",
            {"estado": PedidoManual.ESTADO_PREPARANDO},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(
            f"/api/mi-restaurante/pedidos/manuales/{pedido_id}/estado/",
            {"estado": PedidoManual.ESTADO_PENDIENTE},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        response = self.client.patch(
            f"/api/mi-restaurante/pedidos/manuales/{pedido_id}/estado/",
            {"estado": PedidoManual.ESTADO_CANCELADO},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(
            f"/api/mi-restaurante/pedidos/manuales/{pedido_id}/estado/",
            {"estado": PedidoManual.ESTADO_LISTO},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_metricas_pedidos_calcula_venta_diaria_menly_solo_hoy_no_cancelados(self):
        hoy = timezone.localtime(timezone.now())
        ayer = hoy - timedelta(days=1)

        PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            origen=PedidoManual.ORIGEN_MENLY,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=1500,
            total=1500,
            estado=PedidoManual.ESTADO_PENDIENTE,
            creado_por=self.dueno,
        )
        PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            origen=PedidoManual.ORIGEN_MENLY,
            tipo_entrega=PedidoManual.TIPO_MESA,
            numero_mesa="3",
            subtotal=3000,
            total=3000,
            estado=PedidoManual.ESTADO_ENTREGADO,
            creado_por=self.dueno,
        )
        PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=3,
            origen=PedidoManual.ORIGEN_MENLY,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=9990,
            total=9990,
            estado=PedidoManual.ESTADO_CANCELADO,
            creado_por=self.dueno,
        )
        pedido_ayer = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=4,
            origen=PedidoManual.ORIGEN_MENLY,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=7000,
            total=7000,
            estado=PedidoManual.ESTADO_PENDIENTE,
            creado_por=self.dueno,
        )
        PedidoManual.objects.filter(id=pedido_ayer.id).update(fecha_creacion=ayer)
        PedidoManual.objects.create(
            restaurante=self.otro_restaurante,
            numero_pedido=1,
            origen=PedidoManual.ORIGEN_MENLY,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=8000,
            total=8000,
            estado=PedidoManual.ESTADO_PENDIENTE,
        )
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="WhatsApp",
            telefono_cliente="999999999",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=5000,
            estado=PedidoWhatsApp.ESTADO_ENTREGADO,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )
        pedido_especial = PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Especial",
            telefono_cliente="999999999",
            items=[],
            total=6000,
            fecha_entrega=timezone.localdate(),
            estado=PedidoEspecial.ESTADO_ENTREGADO,
        )

        response = self.client.get("/api/mi-restaurante/pedidos/metricas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["venta_diaria_menly"], 4500)
        self.assertEqual(data["cantidad_pedidos_menly_hoy"], 2)
        self.assertEqual(data["canales"]["menly"]["venta_diaria_menly"], 4500)
        self.assertEqual(data["canales"]["menly"]["cantidad_pedidos_menly_hoy"], 2)
        self.assertEqual(data["canales"]["whatsapp"]["venta_diaria_whatsapp"], 5000)
        self.assertEqual(data["venta_total_diaria_operativa"], 9500)


class PedidosCancelacionIrreversibleTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.dueno)
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.pedidos_pos = True
        self.restaurante.save(update_fields=[
            "carrito_whatsapp_activo",
            "solicitudes_especiales_activas",
            "pedidos_pos",
        ])

    def test_pedidos_cancelados_no_pueden_volver_a_otro_estado(self):
        pedido_whatsapp = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="WhatsApp",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=1000,
            estado=PedidoWhatsApp.ESTADO_CANCELADO,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )
        pedido_manual = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=1000,
            total=1000,
            estado=PedidoManual.ESTADO_CANCELADO,
        )
        pedido_especial = PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Especial",
            telefono_cliente="56911111111",
            items=[],
            total=1000,
            fecha_entrega=timezone.localdate(),
            estado=PedidoEspecial.ESTADO_CANCELADO,
        )

        casos = [
            (
                f"/api/mi-restaurante/pedidos/whatsapp/{pedido_whatsapp.id}/estado/",
                PedidoWhatsApp.ESTADO_CONFIRMADO,
                pedido_whatsapp,
            ),
            (
                f"/api/mi-restaurante/pedidos/manuales/{pedido_manual.id}/estado/",
                PedidoManual.ESTADO_LISTO,
                pedido_manual,
            ),
            (
                f"/api/mi-restaurante/pedidos/especiales/{pedido_especial.id}/estado/",
                PedidoEspecial.ESTADO_LISTO,
                pedido_especial,
            ),
        ]

        for endpoint, estado_nuevo, pedido in casos:
            with self.subTest(endpoint=endpoint):
                response = self.client.patch(endpoint, {"estado": estado_nuevo}, format="json")
                self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
                self.assertEqual(response.data["error"], "transicion_estado_invalida")
                pedido.refresh_from_db()
                self.assertEqual(pedido.estado, "cancelado")


class CocinaComandasTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.restaurante.pedidos_pos = True
        self.restaurante.save(update_fields=["pedidos_pos"])

    def activar_cocina(self, usuario=None):
        self.client.force_authenticate(user=usuario or self.dueno)
        response = self.client.post("/api/mi-restaurante/cocina/activacion/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        token = response.json()["activation_url"].rstrip("/").split("/")[-1]
        self.client.force_authenticate(user=None)
        response = self.client.post(f"/api/cocina/activar/{token}/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return token

    def test_dueno_y_admin_generan_activacion_empleado_no(self):
        self.client.force_authenticate(user=self.dueno)
        response = self.client.post("/api/mi-restaurante/cocina/activacion/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("activation_url", response.json())

        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/mi-restaurante/cocina/activacion/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(user=self.empleado)
        response = self.client.post("/api/mi-restaurante/cocina/activacion/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_token_activacion_se_consume_una_sola_vez_y_crea_sesion(self):
        token = self.activar_cocina()

        self.assertEqual(ActivacionCocina.objects.count(), 1)
        self.assertEqual(SesionCocina.objects.count(), 1)
        self.assertIsNotNone(ActivacionCocina.objects.first().consumido_en)

        response = self.client.post(f"/api/cocina/activar/{token}/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_comandas_filtra_estados_y_solo_restaurante_de_la_sesion(self):
        self.activar_cocina()
        pedido_wsp = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="WhatsApp",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[{"nombre": "Completo", "cantidad": 2}],
            total=3000,
            estado=PedidoWhatsApp.ESTADO_EN_PREPARACION,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )
        pedido_manual = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            tipo_entrega=PedidoManual.TIPO_MESA,
            numero_mesa="4",
            subtotal=1500,
            total=1500,
            estado=PedidoManual.ESTADO_PREPARANDO,
        )
        pedido_manual.items.create(
            nombre_producto=self.producto.nombre,
            precio_unitario=1500,
            cantidad=1,
            subtotal=1500,
            observaciones="Sin hielo",
        )
        pedido_especial = PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Especial",
            telefono_cliente="56911111111",
            items=[{"nombre": "Torta", "cantidad": 1}],
            total=10000,
            fecha_entrega=timezone.localdate(),
            estado=PedidoEspecial.ESTADO_LISTO,
        )
        PedidoWhatsApp.objects.create(
            restaurante=self.otro_restaurante,
            numero_pedido=1,
            nombre_cliente="Otro",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[{"nombre": "Ajeno", "cantidad": 1}],
            total=1000,
            estado=PedidoWhatsApp.ESTADO_EN_PREPARACION,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            nombre_cliente="Pendiente",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[{"nombre": "Pendiente", "cantidad": 1}],
            total=1000,
            estado=PedidoWhatsApp.ESTADO_RECIBIDO,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )

        response = self.client.get("/api/cocina/comandas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.json()["comandas"]}
        self.assertEqual(ids, {f"whatsapp:{pedido_wsp.id}", f"menly:{pedido_manual.id}", f"especial:{pedido_especial.id}"})

    def test_cocina_cambia_estado_listo_y_entregado(self):
        self.activar_cocina()
        pedido = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=1500,
            total=1500,
            estado=PedidoManual.ESTADO_PREPARANDO,
        )

        response = self.client.patch(
            f"/api/cocina/comandas/menly:{pedido.id}/estado/",
            {"estado": "listo"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoManual.ESTADO_LISTO)

        response = self.client.patch(
            f"/api/cocina/comandas/menly:{pedido.id}/estado/",
            {"estado": "entregado"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoManual.ESTADO_ENTREGADO)
        historiales = HistorialEstadoPedidoManual.objects.filter(pedido=pedido).order_by("fecha", "id")
        self.assertEqual(historiales.count(), 2)
        self.assertTrue(all(item.origen == "kds" for item in historiales))
        self.assertEqual(historiales[0].estado_anterior, PedidoManual.ESTADO_PREPARANDO)
        self.assertEqual(historiales[0].estado_nuevo, PedidoManual.ESTADO_LISTO)

    def test_cocina_delivery_manual_entrega_al_repartidor_y_sale_del_kds(self):
        self.activar_cocina()
        pedido = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            tipo_entrega=PedidoManual.TIPO_DELIVERY,
            direccion="Calle delivery 123",
            subtotal=1500,
            total=1500,
            estado=PedidoManual.ESTADO_LISTO,
        )

        comandas = self.client.get("/api/cocina/comandas/")
        comanda = next(item for item in comandas.data["comandas"] if item["id"] == f"menly:{pedido.id}")
        self.assertEqual(comanda["transiciones_permitidas"], [PedidoManual.ESTADO_EN_REPARTO])

        response = self.client.patch(
            f"/api/cocina/comandas/menly:{pedido.id}/estado/",
            {"estado": PedidoManual.ESTADO_EN_REPARTO},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoManual.ESTADO_EN_REPARTO)
        historial = HistorialEstadoPedidoManual.objects.get(pedido=pedido)
        self.assertEqual(historial.estado_anterior, PedidoManual.ESTADO_LISTO)
        self.assertEqual(historial.estado_nuevo, PedidoManual.ESTADO_EN_REPARTO)
        self.assertEqual(historial.origen, "kds")

        comandas = self.client.get("/api/cocina/comandas/")
        self.assertNotIn(f"menly:{pedido.id}", {item["id"] for item in comandas.data["comandas"]})

        response = self.client.patch(
            f"/api/cocina/comandas/menly:{pedido.id}/estado/",
            {"estado": PedidoManual.ESTADO_ENTREGADO},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_cocina_delivery_whatsapp_entrega_al_repartidor(self):
        self.activar_cocina()
        self.restaurante.delivery_activo = True
        self.restaurante.save(update_fields=["delivery_activo"])
        pedido = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Delivery WhatsApp",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_DELIVERY,
            direccion_entrega="Calle delivery 456",
            productos_snapshot=[],
            total=1500,
            estado=PedidoWhatsApp.ESTADO_LISTO,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )

        comandas = self.client.get("/api/cocina/comandas/")
        comanda = next(item for item in comandas.data["comandas"] if item["id"] == f"whatsapp:{pedido.id}")
        self.assertEqual(comanda["transiciones_permitidas"], [PedidoWhatsApp.ESTADO_EN_REPARTO])

        response = self.client.patch(
            f"/api/cocina/comandas/whatsapp:{pedido.id}/estado/",
            {"estado": PedidoWhatsApp.ESTADO_EN_REPARTO},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoWhatsApp.ESTADO_EN_REPARTO)
        historial = HistorialEstadoPedidoWhatsApp.objects.get(pedido=pedido)
        self.assertEqual(historial.origen, "kds")

        response = self.client.patch(
            f"/api/cocina/comandas/whatsapp:{pedido.id}/estado/",
            {"estado": PedidoWhatsApp.ESTADO_ENTREGADO},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(HistorialEstadoPedidoWhatsApp.objects.filter(pedido=pedido).count(), 1)

    def test_cocina_rechaza_misma_transicion_invalida_que_panel(self):
        self.activar_cocina()
        pedido = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=1500,
            total=1500,
            estado=PedidoManual.ESTADO_PREPARANDO,
        )

        response = self.client.patch(
            f"/api/cocina/comandas/menly:{pedido.id}/estado/",
            {"estado": "entregado"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"], "transicion_estado_invalida")
        self.assertEqual(HistorialEstadoPedidoManual.objects.filter(pedido=pedido).count(), 0)

    def test_cocina_no_accede_a_pedido_de_otro_restaurante(self):
        self.activar_cocina()
        pedido = PedidoManual.objects.create(
            restaurante=self.otro_restaurante,
            numero_pedido=1,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=1500,
            total=1500,
            estado=PedidoManual.ESTADO_PREPARANDO,
        )

        response = self.client.patch(
            f"/api/cocina/comandas/menly:{pedido.id}/estado/",
            {"estado": "listo"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(HistorialEstadoPedidoManual.objects.filter(pedido=pedido).count(), 0)

    def test_cerrar_cocina_invalida_sesion(self):
        self.activar_cocina()
        response = self.client.post("/api/cocina/cerrar/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get("/api/cocina/comandas/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sesion_cocina_persiste_entre_jornadas_y_al_recargar(self):
        self.activar_cocina()
        sesion = SesionCocina.objects.get()
        sesion.fecha_operativa = timezone.localdate() - timedelta(days=1)
        sesion.expira_en = timezone.now() + timedelta(days=20)
        sesion.save(update_fields=["fecha_operativa", "expira_en"])

        response = self.client.get("/api/cocina/comandas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["restaurante"]["slug"], self.restaurante.slug)

    def test_polling_renueva_sesion_cocina_cercana_a_expirar(self):
        self.activar_cocina()
        sesion = SesionCocina.objects.get()
        expiracion_anterior = timezone.now() + timedelta(hours=1)
        sesion.expira_en = expiracion_anterior
        sesion.save(update_fields=["expira_en"])

        response = self.client.get("/api/cocina/comandas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sesion.refresh_from_db()
        self.assertGreater(sesion.expira_en, expiracion_anterior)
        self.assertIn("menly_cocina_session", response.cookies)
        self.assertTrue(response.cookies["menly_cocina_session"]["httponly"])

    def test_cierre_manual_detiene_comandas_sin_cerrar_sesion_cocina(self):
        self.activar_cocina()
        pedido = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=1500,
            total=1500,
            estado=PedidoManual.ESTADO_PREPARANDO,
        )
        self.restaurante.abierto = False
        self.restaurante.save(update_fields=["abierto"])

        response = self.client.get("/api/cocina/comandas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["estado_local"]["abierto"])
        self.assertEqual(response.data["estado_local"]["motivo"], "cierre_manual")
        self.assertEqual(response.data["comandas"], [])
        self.assertTrue(SesionCocina.objects.get().activa)
        self.assertTrue(PedidoManual.objects.filter(pk=pedido.pk).exists())

    def test_cocina_cerrada_rechaza_gestion_sin_confundirla_con_logout(self):
        self.activar_cocina()
        pedido = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=1500,
            total=1500,
            estado=PedidoManual.ESTADO_PREPARANDO,
        )
        self.restaurante.abierto = False
        self.restaurante.save(update_fields=["abierto"])

        response = self.client.patch(
            f"/api/cocina/comandas/menly:{pedido.id}/estado/",
            {"estado": PedidoManual.ESTADO_LISTO},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"], "local_cerrado")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoManual.ESTADO_PREPARANDO)
        self.assertTrue(SesionCocina.objects.get().esta_vigente())

    def test_apertura_excepcional_reactiva_kds_sin_nueva_sesion(self):
        self.activar_cocina()
        sesion_id = SesionCocina.objects.get().id
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=timezone.localtime().isoweekday(),
            cerrado=True,
            activo=True,
        )

        cerrado = self.client.get("/api/cocina/estado/")
        self.assertFalse(cerrado.data["estado_local"]["abierto"])

        self.restaurante.apertura_excepcional_hasta = timezone.now() + timedelta(hours=2)
        self.restaurante.save(update_fields=["apertura_excepcional_hasta"])
        abierto = self.client.get("/api/cocina/estado/")

        self.assertEqual(abierto.status_code, status.HTTP_200_OK)
        self.assertTrue(abierto.data["estado_local"]["abierto"])
        self.assertEqual(abierto.data["estado_local"]["motivo"], "apertura_excepcional")
        self.assertEqual(SesionCocina.objects.get().id, sesion_id)

    def test_reapertura_por_horario_reactiva_kds_sin_nueva_sesion(self):
        self.activar_cocina()
        sesion_id = SesionCocina.objects.get().id
        horario = HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=timezone.localtime().isoweekday(),
            cerrado=True,
            activo=True,
        )
        self.assertFalse(
            self.client.get("/api/cocina/estado/").data["estado_local"]["abierto"]
        )

        horario.cerrado = False
        horario.hora_apertura = time(0, 0)
        horario.hora_cierre = time(23, 59, 59)
        horario.save(update_fields=["cerrado", "hora_apertura", "hora_cierre"])
        abierto = self.client.get("/api/cocina/estado/")

        self.assertTrue(abierto.data["estado_local"]["abierto"])
        self.assertEqual(abierto.data["estado_local"]["motivo"], "dentro_de_horario")
        self.assertEqual(SesionCocina.objects.get().id, sesion_id)

    def test_dos_clientes_kds_reflejan_el_mismo_estado_del_backend(self):
        self.activar_cocina()
        segundo_cliente = APIClient()
        segundo_cliente.cookies = self.client.cookies.copy()
        self.restaurante.abierto = False
        self.restaurante.save(update_fields=["abierto"])

        estado_primero = self.client.get("/api/cocina/estado/")
        estado_segundo = segundo_cliente.get("/api/cocina/estado/")

        self.assertFalse(estado_primero.data["estado_local"]["abierto"])
        self.assertFalse(estado_segundo.data["estado_local"]["abierto"])

    def test_estado_cocina_con_sesion_invalida_responde_401(self):
        self.activar_cocina()
        sesion = SesionCocina.objects.get()
        sesion.activa = False
        sesion.save(update_fields=["activa"])

        response = self.client.get("/api/cocina/estado/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_desactivar_acceso_pos_revoca_sesion_cocina(self):
        self.activar_cocina()
        self.restaurante.pedidos_pos = False
        self.restaurante.save(update_fields=["pedidos_pos"])

        response = self.client.get("/api/cocina/comandas/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminCookieSessionTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def login(self, remember_me=False):
        return self.client.post(
            "/api/login/",
            {
                "email": self.dueno.email,
                "password": "123456",
                "remember_me": remember_me,
            },
            format="json",
        )

    def test_login_guarda_refresh_httponly_y_no_lo_expone_en_json(self):
        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        cookie = response.cookies[settings.ADMIN_REFRESH_COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["path"], "/api/")
        self.assertEqual(cookie["max-age"], "")
        self.assertEqual(
            response.cookies[settings.ADMIN_REMEMBER_COOKIE_NAME].value,
            "0",
        )

    def test_login_recordarme_crea_cookie_persistente_por_siete_dias(self):
        response = self.login(remember_me=True)

        refresh_cookie = response.cookies[settings.ADMIN_REFRESH_COOKIE_NAME]
        remember_cookie = response.cookies[settings.ADMIN_REMEMBER_COOKIE_NAME]
        expected_max_age = int(
            settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()
        )
        self.assertEqual(int(refresh_cookie["max-age"]), expected_max_age)
        self.assertEqual(int(remember_cookie["max-age"]), expected_max_age)
        self.assertEqual(remember_cookie.value, "1")
        self.assertTrue(refresh_cookie["httponly"])
        self.assertTrue(remember_cookie["httponly"])

    def test_refresh_desde_cookie_rota_token_y_entrega_solo_access(self):
        self.login()
        refresh_anterior = self.client.cookies[settings.ADMIN_REFRESH_COOKIE_NAME].value

        response = self.client.post("/api/token/refresh/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        refresh_nuevo = response.cookies[settings.ADMIN_REFRESH_COOKIE_NAME].value
        self.assertNotEqual(refresh_nuevo, refresh_anterior)

    def test_refresh_conserva_persistencia_recordarme(self):
        self.login(remember_me=True)

        response = self.client.post("/api/token/refresh/", {}, format="json")

        expected_max_age = int(
            settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()
        )
        self.assertEqual(
            int(response.cookies[settings.ADMIN_REFRESH_COOKIE_NAME]["max-age"]),
            expected_max_age,
        )
        self.assertEqual(
            response.cookies[settings.ADMIN_REMEMBER_COOKIE_NAME].value,
            "1",
        )

    def test_refresh_conserva_cookie_de_sesion_sin_recordarme(self):
        self.login(remember_me=False)

        response = self.client.post("/api/token/refresh/", {}, format="json")

        self.assertEqual(
            response.cookies[settings.ADMIN_REFRESH_COOKIE_NAME]["max-age"],
            "",
        )
        self.assertEqual(
            response.cookies[settings.ADMIN_REMEMBER_COOKIE_NAME].value,
            "0",
        )

    def test_logout_revoca_refresh_y_elimina_cookie(self):
        self.login()
        response = self.client.post("/api/logout/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        self.assertEqual(response.cookies[settings.ADMIN_REFRESH_COOKIE_NAME]["max-age"], 0)
        self.assertEqual(response.cookies[settings.ADMIN_REMEMBER_COOKIE_NAME]["max-age"], 0)

        refresh_response = self.client.post("/api/token/refresh/", {}, format="json")
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)


class ConfiguracionRestauranteOperacionTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.dueno)

    def crear_pedido_delivery(self):
        return PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Cliente Delivery",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_DELIVERY,
            direccion_entrega="Calle 123",
            productos_snapshot=[
                {
                    "producto_id": self.producto.id,
                    "nombre": self.producto.nombre,
                    "cantidad": 1,
                    "precio_unitario": 1500,
                    "subtotal": 1500,
                }
            ],
            total=1500,
            estado=PedidoWhatsApp.ESTADO_CONFIRMADO,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )

    def test_mensaje_delivery_aclara_costo_sin_modificar_total_productos(self):
        pedido = self.crear_pedido_delivery()

        mensaje = generar_mensaje_whatsapp(pedido)

        self.assertEqual(pedido.total, 1500)
        self.assertIn("Total productos: $1500", mensaje)
        self.assertIn(
            "Costo de delivery: por confirmar con el restaurante.",
            mensaje,
        )

    def test_mensaje_retiro_no_incluye_aviso_de_delivery(self):
        pedido = self.crear_pedido_delivery()
        pedido.tipo_entrega = PedidoWhatsApp.TIPO_RETIRO_LOCAL
        pedido.direccion_entrega = None

        mensaje = generar_mensaje_whatsapp(pedido)

        self.assertIn("Total: $1500", mensaje)
        self.assertNotIn("Costo de delivery: por confirmar", mensaje)

    def test_configuracion_guarda_delivery_activo_y_abierto(self):
        response = self.client.patch(
            "/api/mi-restaurante/configuracion/",
            {"delivery_activo": True, "abierto": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.restaurante.refresh_from_db()
        self.assertTrue(self.restaurante.delivery_activo)
        self.assertFalse(self.restaurante.abierto)
        data = response.json()
        self.assertTrue(data["delivery_activo"])
        self.assertFalse(data["abierto"])

    def test_landing_publica_devuelve_estado_abierto_cerrado(self):
        self.restaurante.abierto = False
        self.restaurante.save(update_fields=["abierto"])

        response = self.client.get(f"/api/restaurantes/{self.restaurante.slug}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertFalse(data["abierto"])
        self.assertFalse(data["abierto_ahora"])

    def test_dashboard_cambia_estado_abierto_del_restaurante_autenticado(self):
        response = self.client.patch(
            "/api/mi-restaurante/estado-apertura/",
            {"abierto": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.restaurante.refresh_from_db()
        self.assertFalse(self.restaurante.abierto)
        self.assertFalse(response.json()["abierto"])

    def test_estado_apertura_no_modifica_otro_restaurante(self):
        user_otro = User.objects.create_user(
            username="dueno-otro@test.com",
            email="dueno-otro@test.com",
            password="123456",
        )
        UsuarioRestaurante.objects.create(
            user=user_otro,
            restaurante=self.otro_restaurante,
            rol="dueno",
            activo=True,
        )

        self.client.force_authenticate(user=user_otro)
        response = self.client.patch(
            "/api/mi-restaurante/estado-apertura/",
            {"abierto": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.restaurante.refresh_from_db()
        self.otro_restaurante.refresh_from_db()
        self.assertTrue(self.restaurante.abierto)
        self.assertFalse(self.otro_restaurante.abierto)

    def test_delivery_desactivado_rechaza_estado_en_reparto(self):
        pedido = self.crear_pedido_delivery()

        response = self.client.patch(
            f"/api/mi-restaurante/pedidos/whatsapp/{pedido.id}/estado/",
            {"estado": PedidoWhatsApp.ESTADO_EN_REPARTO},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoWhatsApp.ESTADO_CONFIRMADO)

    def test_delivery_activado_permite_estado_en_reparto(self):
        self.restaurante.delivery_activo = True
        self.restaurante.save(update_fields=["delivery_activo"])
        pedido = self.crear_pedido_delivery()

        response = self.client.patch(
            f"/api/mi-restaurante/pedidos/whatsapp/{pedido.id}/estado/",
            {"estado": PedidoWhatsApp.ESTADO_EN_REPARTO},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoWhatsApp.ESTADO_EN_REPARTO)


class MigracionPedidoWhatsAppTrackingTests(TestCase):
    def test_poblar_tracking_y_estados_respeta_largos_de_campos(self):
        migracion = import_module("menu.migrations.0034_pedido_whatsapp_tracking")

        class PedidoAntiguo:
            tracking_token = ""
            fecha_actualizacion_estado = None
            fecha_creacion = timezone.now()
            estado = "pendiente"
            update_fields = None

            def save(self, update_fields=None):
                self.update_fields = update_fields
                self.estado_max_length = 30
                self.tracking_token_max_length = 32
                if len(self.estado) > self.estado_max_length:
                    raise AssertionError("estado supera max_length")
                if len(self.tracking_token) > self.tracking_token_max_length:
                    raise AssertionError("tracking_token supera max_length")

        pedido = PedidoAntiguo()

        class FakeQuerySet:
            def order_by(self, *_args):
                return [pedido]

            def exists(self):
                return False

        class FakeManager:
            def all(self):
                return FakeQuerySet()

            def filter(self, **_kwargs):
                return FakeQuerySet()

        class FakePedidoWhatsApp:
            objects = FakeManager()

        testcase = self

        class FakeApps:
            def get_model(self, app_label, model_name):
                testcase.assertEqual(app_label, "menu")
                testcase.assertEqual(model_name, "PedidoWhatsApp")
                return FakePedidoWhatsApp

        with patch.object(migracion, "generar_token_unico", return_value="token-seguro-123"):
            migracion.poblar_tracking_y_estados(FakeApps(), None)

        self.assertEqual(pedido.estado, "pendiente_confirmacion")
        self.assertLessEqual(len(pedido.estado), 30)
        self.assertEqual(pedido.tracking_token, "token-seguro-123")
        self.assertLessEqual(len(pedido.tracking_token), 32)
        self.assertEqual(
            pedido.update_fields,
            ["tracking_token", "fecha_actualizacion_estado", "estado"],
        )


class SuscripcionDashboardTests(BaseTestCase):

    def set_fecha_creacion_restaurante(self, fecha):
        Restaurante.objects.filter(id=self.restaurante.id).update(
            fecha_creacion=timezone.make_aware(datetime.combine(fecha, time(9, 0)))
        )

    def get_suscripcion(self, hoy):
        self.client.force_authenticate(user=self.dueno)
        with patch("menu.views.now") as now_mock:
            now_mock.return_value = timezone.make_aware(
                datetime.combine(hoy, time(12, 0))
            )
            response = self.client.get("/api/mi-restaurante/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data["suscripcion"]

    def test_suscripcion_sin_alerta_si_faltan_mas_de_tres_dias(self):
        self.set_fecha_creacion_restaurante(date(2026, 1, 1))

        suscripcion = self.get_suscripcion(date(2026, 1, 15))

        self.assertEqual(suscripcion["fecha_vencimiento"], "2026-02-01")
        self.assertEqual(suscripcion["dias_restantes"], 17)
        self.assertFalse(suscripcion["por_vencer"])
        self.assertFalse(suscripcion["vencida"])

    def test_suscripcion_por_vencer_si_faltan_exactamente_tres_dias(self):
        self.set_fecha_creacion_restaurante(date(2026, 1, 10))

        suscripcion = self.get_suscripcion(date(2026, 2, 7))

        self.assertEqual(suscripcion["fecha_vencimiento"], "2026-02-10")
        self.assertEqual(suscripcion["dias_restantes"], 3)
        self.assertTrue(suscripcion["por_vencer"])
        self.assertFalse(suscripcion["vencida"])

    def test_suscripcion_por_vencer_si_falta_un_dia(self):
        self.set_fecha_creacion_restaurante(date(2026, 1, 10))

        suscripcion = self.get_suscripcion(date(2026, 2, 9))

        self.assertEqual(suscripcion["dias_restantes"], 1)
        self.assertTrue(suscripcion["por_vencer"])
        self.assertFalse(suscripcion["vencida"])

    def test_suscripcion_dia_de_vencimiento_avisa_sin_marcar_vencida(self):
        self.set_fecha_creacion_restaurante(date(2026, 1, 10))

        suscripcion = self.get_suscripcion(date(2026, 2, 10))

        self.assertEqual(suscripcion["dias_restantes"], 0)
        self.assertTrue(suscripcion["por_vencer"])
        self.assertFalse(suscripcion["vencida"])

    def test_suscripcion_vencida_despues_del_vencimiento(self):
        self.set_fecha_creacion_restaurante(date(2026, 1, 10))

        suscripcion = self.get_suscripcion(date(2026, 2, 11))

        self.assertEqual(suscripcion["dias_restantes"], -1)
        self.assertFalse(suscripcion["por_vencer"])
        self.assertTrue(suscripcion["vencida"])

    def test_suscripcion_calcula_fin_de_mes_correctamente(self):
        self.set_fecha_creacion_restaurante(date(2026, 1, 31))

        suscripcion = self.get_suscripcion(date(2026, 2, 25))

        self.assertEqual(suscripcion["fecha_vencimiento"], "2026-02-28")
        self.assertEqual(suscripcion["dias_restantes"], 3)
        self.assertTrue(suscripcion["por_vencer"])
        self.assertFalse(suscripcion["vencida"])


class RestauranteInactivoTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.mensaje_inactivo = (
            "La cuenta del restaurante está inactiva. Contacta al soporte de Menly para reactivar tu cuenta."
        )
        self.reserva = Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Inactivo",
            telefono="900000000",
            email="cliente-inactivo@test.com",
            fecha=date.today() + timedelta(days=2),
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )
        self.dueno_b = User.objects.create_user(
            username="dueno-activo-b@test.com",
            email="dueno-activo-b@test.com",
            password="123456"
        )
        self.perfil_dueno_b = UsuarioRestaurante.objects.create(
            user=self.dueno_b,
            restaurante=self.otro_restaurante,
            rol="dueno",
            activo=True,
        )

    def desactivar_restaurante(self):
        self.restaurante.activo = False
        self.restaurante.save(update_fields=["activo"])

    def assert_bloqueo_inactivo(self, response):
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("inactiva", str(response.data))

    def test_landing_restaurante_activo_devuelve_menu_normal(self):
        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_landing_restaurante_inactivo_devuelve_403_controlado(self):
        self.desactivar_restaurante()

        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["estado"], "inactivo")

    def test_landing_slug_inexistente_devuelve_404(self):
        response = self.client.get("/api/menu/slug-inexistente/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_usuario_de_restaurante_inactivo_puede_hacer_login(self):
        self.desactivar_restaurante()

        response = self.client.post(
            "/api/login/",
            {
                "email": "dueno@test.com",
                "password": "123456",
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["restaurante"]["activo"])

    @patch("menu.views.send_mail")
    def test_password_reset_request_responde_generico_y_notifica_admin(self, send_mail_mock):
        response = self.client.post(
            "/api/password-reset-request/",
            {"email": "DUENO@test.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "Si el correo está registrado, el administrador será notificado.",
        )
        send_mail_mock.assert_called_once()
        self.assertIn("Usuario encontrado:\nSí", send_mail_mock.call_args.kwargs["message"])
        self.assertIn("dueno@test.com", send_mail_mock.call_args.kwargs["message"])

    @patch("menu.views.send_mail")
    def test_password_reset_request_no_revela_email_inexistente(self, send_mail_mock):
        response = self.client.post(
            "/api/password-reset-request/",
            {"email": "noexiste@test.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "Si el correo está registrado, el administrador será notificado.",
        )
        send_mail_mock.assert_called_once()
        self.assertIn("Usuario encontrado:\nNo", send_mail_mock.call_args.kwargs["message"])

    def test_restaurante_inactivo_puede_ver_mi_restaurante(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.dueno)

        response = self.client.get("/api/mi-restaurante/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["restaurante"]["activo"])
        self.assertTrue(response.data["cuenta_inactiva"])
        self.assertIn("Cuenta inactiva", response.data["mensaje_cuenta"])

    def test_dueno_inactivo_no_puede_crear_producto(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/productos/agregar/",
            {
                "categoria": self.categoria.id,
                "nombre": "Producto bloqueado",
                "descripcion": "No debe crearse",
                "precio": 3000,
                "orden": 2,
            },
            format="json"
        )

        self.assert_bloqueo_inactivo(response)
        self.assertFalse(Producto.objects.filter(nombre="Producto bloqueado").exists())

    def test_admin_inactivo_no_puede_editar_producto(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f"/api/mi-restaurante/productos/{self.producto.id}/actualizar/",
            {
                "categoria": self.categoria.id,
                "nombre": "Producto editado",
                "precio": self.producto.precio,
                "orden": self.producto.orden,
            },
            format="json"
        )

        self.assert_bloqueo_inactivo(response)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.nombre, "Coca Cola")

    def test_admin_inactivo_no_puede_editar_reserva(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f"/api/mi-restaurante/reservas/{self.reserva.id}/",
            {"estado": "confirmada"},
            format="json"
        )

        self.assert_bloqueo_inactivo(response)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, "pendiente")

    def test_empleado_inactivo_no_puede_gestionar_reserva(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.empleado)

        response = self.client.patch(
            f"/api/mi-restaurante/reservas/{self.reserva.id}/",
            {"estado": "rechazada"},
            format="json"
        )

        self.assert_bloqueo_inactivo(response)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, "pendiente")

    def test_dueno_inactivo_no_puede_editar_configuracion(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.dueno)

        response = self.client.patch(
            "/api/mi-restaurante/configuracion/",
            {"nombre_empresa": "Nombre bloqueado"},
            format="json"
        )

        self.assert_bloqueo_inactivo(response)
        self.restaurante.refresh_from_db()
        self.assertEqual(self.restaurante.nombre_empresa, "Restaurante Test")

    def test_dueno_inactivo_no_puede_crear_usuario(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/usuarios/",
            {
                "username": "nuevo-inactivo@test.com",
                "email": "nuevo-inactivo@test.com",
                "password": "123456",
                "rol": "empleado",
            },
            format="json"
        )

        self.assert_bloqueo_inactivo(response)
        self.assertFalse(User.objects.filter(username="nuevo-inactivo@test.com").exists())

    def test_restaurante_activo_mantiene_comportamiento_normal(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/productos/agregar/",
            {
                "categoria": self.categoria.id,
                "nombre": "Producto activo",
                "descripcion": "Debe crearse",
                "precio": 3000,
                "orden": 2,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_restaurante_inactivo_no_afecta_otro_restaurante_activo(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.dueno_b)

        response = self.client.post(
            "/api/mi-restaurante/productos/agregar/",
            {
                "categoria": self.categoria_otro_restaurante.id,
                "nombre": "Producto restaurante B",
                "descripcion": "B sigue activo",
                "precio": 4000,
                "orden": 2,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Producto.objects.filter(
                restaurante=self.otro_restaurante,
                nombre="Producto restaurante B",
            ).exists()
        )


class CategoriaTests(BaseTestCase):

    def test_dueno_puede_crear_categoria(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/categorias/",
            {
                "nombre": "Promociones",
                "orden": 2,
                "activa": True,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Categoria.objects.filter(
                restaurante=self.restaurante,
                nombre="Promociones"
            ).exists()
        )

    def test_admin_no_puede_crear_categoria(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            "/api/mi-restaurante/categorias/",
            {
                "nombre": "Postres",
                "orden": 3,
                "activa": True,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_permite_categoria_duplicada(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/categorias/",
            {
                "nombre": "Bebidas",
                "orden": 2,
                "activa": True,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lista_solo_categorias_del_restaurante_actual(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.get("/api/mi-restaurante/categorias/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        nombres = [cat["nombre"] for cat in response.data]

        self.assertIn("Bebidas", nombres)
        self.assertNotIn("Comida", nombres)


class ProductoTests(BaseTestCase):

    def test_crud_variante_valida_precio_y_nombre_duplicado(self):
        self.client.force_authenticate(user=self.dueno)
        url = f"/api/mi-restaurante/productos/{self.producto.id}/variantes/"

        response = self.client.post(url, {
            "nombre": "Familiar", "descripcion": "Para compartir",
            "precio": 6000, "activo": True, "orden": 1,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        variante_id = response.data["id"]

        duplicada = self.client.post(url, {"nombre": "familiar", "precio": 7000}, format="json")
        self.assertEqual(duplicada.status_code, status.HTTP_400_BAD_REQUEST)

        negativa = self.client.post(url, {"nombre": "Mediana", "precio": -1}, format="json")
        self.assertEqual(negativa.status_code, status.HTTP_400_BAD_REQUEST)

        detalle = f"{url}{variante_id}/"
        desactivar = self.client.patch(detalle, {"activo": False}, format="json")
        self.assertEqual(desactivar.status_code, status.HTTP_200_OK)
        self.assertFalse(desactivar.data["activo"])

        eliminar = self.client.delete(detalle)
        self.assertEqual(eliminar.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProductoVariante.objects.filter(id=variante_id).exists())

    def test_crud_variante_aisla_restaurantes(self):
        variante = ProductoVariante.objects.create(producto=self.producto, nombre="Individual", precio=2000)
        usuario_otro = User.objects.create_user(username="otro-dueno", password="test")
        UsuarioRestaurante.objects.create(
            user=usuario_otro, restaurante=self.otro_restaurante, rol="dueno", activo=True
        )
        self.client.force_authenticate(user=usuario_otro)

        response = self.client.patch(
            f"/api/mi-restaurante/productos/{self.producto.id}/variantes/{variante.id}/",
            {"precio": 1}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        variante.refresh_from_db()
        self.assertEqual(variante.precio, 2000)

    def test_pedido_variante_usa_precio_backend_y_guarda_snapshot(self):
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.whatsapp = "56999999999"
        self.restaurante.save(update_fields=["carrito_whatsapp_activo", "whatsapp"])
        variante = ProductoVariante.objects.create(
            producto=self.producto, nombre="Familiar", descripcion="Para 4", precio=6000, activo=True
        )

        response = self.client.post(
            f"/api/pedidos-whatsapp/{self.restaurante.slug}/",
            {
                "nombre_cliente": "Cliente", "telefono_cliente": "912345678",
                "tipo_entrega": PedidoWhatsApp.TIPO_RETIRO_LOCAL,
                "productos": [{
                    "producto_id": self.producto.id, "variante_id": variante.id,
                    "cantidad": 2, "precio_unitario": 1,
                }],
            }, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pedido = PedidoWhatsApp.objects.get(id=response.data["pedido_id"])
        self.assertEqual(pedido.total, 12000)
        self.assertEqual(pedido.productos_snapshot[0]["variante_id"], variante.id)
        self.assertEqual(pedido.productos_snapshot[0]["variante_nombre"], "Familiar")
        self.assertEqual(pedido.productos_snapshot[0]["precio_unitario"], 6000)
        self.assertIn("Coca Cola — Familiar x2", pedido.mensaje_whatsapp_generado)

    def test_pedido_exige_variante_activa_del_producto(self):
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.whatsapp = "56999999999"
        self.restaurante.save(update_fields=["carrito_whatsapp_activo", "whatsapp"])
        ProductoVariante.objects.create(producto=self.producto, nombre="Individual", precio=2000, activo=True)

        response = self.client.post(
            f"/api/pedidos-whatsapp/{self.restaurante.slug}/",
            {
                "nombre_cliente": "Cliente", "telefono_cliente": "912345678",
                "tipo_entrega": PedidoWhatsApp.TIPO_RETIRO_LOCAL,
                "productos": [{"producto_id": self.producto.id, "cantidad": 1}],
            }, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("productos", response.data)

    def test_no_permite_cambiar_producto_a_categoria_de_otro_restaurante(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.patch(
            f"/api/mi-restaurante/productos/{self.producto.id}/",
            {
                "categoria": self.categoria_otro_restaurante.id,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.categoria, self.categoria)

    def test_crear_producto_en_orden_ocupado_reordena(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/productos/agregar/",
            {
                "categoria": self.categoria.id,
                "nombre": "Jugo Natural",
                "descripcion": "Jugo",
                "precio": 2500,
                "disponible": True,
                "destacado": False,
                "orden": 1,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        producto_nuevo = Producto.objects.get(nombre="Jugo Natural")
        self.producto.refresh_from_db()

        self.assertEqual(producto_nuevo.orden, 1)
        self.assertEqual(self.producto.orden, 2)

    def test_editar_producto_cambiando_orden_reordena(self):
        self.client.force_authenticate(user=self.dueno)

        segundo = Producto.objects.create(
            restaurante=self.restaurante,
            categoria=self.categoria,
            nombre="Sprite",
            descripcion="Bebida",
            precio=1500,
            disponible=True,
            destacado=False,
            orden=2,
        )

        response = self.client.patch(
            f"/api/mi-restaurante/productos/{segundo.id}/actualizar/",
            {
                "categoria": self.categoria.id,
                "nombre": segundo.nombre,
                "precio": segundo.precio,
                "descripcion": segundo.descripcion,
                "condiciones": segundo.condiciones,
                "disponible": segundo.disponible,
                "destacado": segundo.destacado,
                "orden": 1,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        segundo.refresh_from_db()
        self.producto.refresh_from_db()

        self.assertEqual(segundo.orden, 1)
        self.assertEqual(self.producto.orden, 2)


class UsuariosTests(BaseTestCase):

    def test_crear_usuario_con_email_global_existente_falla_claro(self):
        self.client.force_authenticate(user=self.dueno)
        User.objects.create_superuser(
            username="superuser@test.com",
            email="correoexistente@test.com",
            password="123456"
        )

        response = self.client.post(
            "/api/mi-restaurante/usuarios/",
            {
                "username": "empleado-nuevo",
                "email": "correoexistente@test.com",
                "password": "12345678",
                "rol": "empleado",
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("superuser", response.data["error"])

    def test_editar_usuario_funciona(self):
        self.client.force_authenticate(user=self.dueno)
        empleado_user = User.objects.create_user(
            username="empleado-original",
            email="empleado-original@test.com",
            password="12345678"
        )
        empleado = UsuarioRestaurante.objects.create(
            user=empleado_user,
            restaurante=self.restaurante,
            rol="empleado",
            activo=True,
        )

        response = self.client.patch(
            f"/api/mi-restaurante/usuarios/{empleado.id}/",
            {
                "username": "empleado-editado",
                "email": "empleado-editado@test.com",
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        empleado_user.refresh_from_db()
        self.assertEqual(empleado_user.username, "empleado-editado")
        self.assertEqual(empleado_user.email, "empleado-editado@test.com")

    def test_desactivar_usuario_bloquea_login(self):
        self.client.force_authenticate(user=self.dueno)
        empleado_user = User.objects.create_user(
            username="empleado-login",
            email="empleado-login@test.com",
            password="12345678"
        )
        empleado = UsuarioRestaurante.objects.create(
            user=empleado_user,
            restaurante=self.restaurante,
            rol="empleado",
            activo=True,
        )

        response = self.client.patch(f"/api/mi-restaurante/usuarios/{empleado.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        empleado.refresh_from_db()
        empleado_user.refresh_from_db()
        self.assertFalse(empleado.activo)
        self.assertFalse(empleado_user.is_active)

        self.client.force_authenticate(user=None)
        login_response = self.client.post(
            "/api/login/",
            {
                "email": "empleado-login@test.com",
                "password": "12345678",
            },
            format="json"
        )

        self.assertNotEqual(login_response.status_code, status.HTTP_200_OK)


class RespaldosTests(BaseTestCase):

    def test_dueno_puede_crear_listar_y_ver_ultimo_respaldo(self):
        self.client.force_authenticate(user=self.dueno)

        crear_response = self.client.post("/api/mi-restaurante/respaldos/")

        self.assertEqual(crear_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RespaldoRestaurante.objects.count(), 1)
        self.assertEqual(crear_response.data["nombre_restaurante"], self.restaurante.nombre_empresa)
        self.assertIn("productos", crear_response.data["datos_json"])
        self.assertIn("reservas", crear_response.data["datos_json"])

        listar_response = self.client.get("/api/mi-restaurante/respaldos/")

        self.assertEqual(listar_response.status_code, status.HTTP_200_OK)
        self.assertEqual(listar_response.data["count"], 1)
        self.assertEqual(len(listar_response.data["results"]), 1)

        ultimo_response = self.client.get("/api/mi-restaurante/respaldos/ultimo/")

        self.assertEqual(ultimo_response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(ultimo_response.data["ultimo_respaldo"])

    def test_admin_puede_crear_respaldo(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post("/api/mi-restaurante/respaldos/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_empleado_no_puede_acceder_respaldos(self):
        self.client.force_authenticate(user=self.empleado)

        crear_response = self.client.post("/api/mi-restaurante/respaldos/")
        listar_response = self.client.get("/api/mi-restaurante/respaldos/")
        ultimo_response = self.client.get("/api/mi-restaurante/respaldos/ultimo/")

        self.assertEqual(crear_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(listar_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ultimo_response.status_code, status.HTTP_403_FORBIDDEN)


class ReservaManualMesaTests(BaseTestCase):

    def reserva_manual_payload(self, mesa):
        return {
            "nombre_cliente": "Cliente Manual",
            "telefono": "999999999",
            "email": "cliente.manual@test.com",
            "fecha": (date.today() + timedelta(days=2)).isoformat(),
            "hora": "12:00",
            "cantidad_personas": 2,
            "mensaje": "Reserva creada desde dashboard",
            "mesa_asignada": mesa.id,
            "observacion_admin": "Mesa elegida manualmente",
        }

    def test_restaurante_puede_asignar_su_propia_mesa_activa(self):
        self.client.force_authenticate(user=self.dueno)
        mesa = Mesa.objects.create(
            restaurante=self.restaurante,
            numero=1,
            nombre="Mesa terraza",
            activa=True,
        )

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            self.reserva_manual_payload(mesa),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Reserva.objects.filter(
                restaurante=self.restaurante,
                nombre_cliente="Cliente Manual",
            ).exists()
        )

    def test_restaurante_no_puede_asignar_mesa_de_otro_restaurante(self):
        self.client.force_authenticate(user=self.dueno)
        mesa_externa = Mesa.objects.create(
            restaurante=self.otro_restaurante,
            numero=1,
            nombre="Mesa externa",
            activa=True,
        )

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            self.reserva_manual_payload(mesa_externa),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("mesa_asignada", response.data)
        self.assertFalse(
            Reserva.objects.filter(
                restaurante=self.restaurante,
                nombre_cliente="Cliente Manual",
            ).exists()
        )

    def test_restaurante_no_puede_asignar_mesa_inactiva(self):
        self.client.force_authenticate(user=self.dueno)
        mesa_inactiva = Mesa.objects.create(
            restaurante=self.restaurante,
            numero=2,
            nombre="Mesa inactiva",
            activa=False,
        )

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            self.reserva_manual_payload(mesa_inactiva),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("mesa_asignada", response.data)
        self.assertFalse(
            Reserva.objects.filter(
                restaurante=self.restaurante,
                nombre_cliente="Cliente Manual",
            ).exists()
        )

    def test_rechaza_mesa_ocupada_misma_fecha_y_hora(self):
        self.client.force_authenticate(user=self.dueno)
        mesa = Mesa.objects.create(
            restaurante=self.restaurante,
            numero=3,
            nombre="Mesa ocupada",
            activa=True,
        )
        fecha_reserva = date.today() + timedelta(days=2)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="111111111",
            email="original@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            mesa_asignada=str(mesa.id),
            estado="pendiente",
        )

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            self.reserva_manual_payload(mesa),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"],
            "La mesa ya tiene una reserva para esa fecha y hora."
        )

    def test_permite_mesa_si_reserva_anterior_esta_cancelada(self):
        self.client.force_authenticate(user=self.dueno)
        mesa = Mesa.objects.create(
            restaurante=self.restaurante,
            numero=4,
            nombre="Mesa liberada",
            activa=True,
        )
        fecha_reserva = date.today() + timedelta(days=2)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="111111111",
            email="original@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            mesa_asignada=str(mesa.id),
            estado="cancelada",
        )

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            self.reserva_manual_payload(mesa),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_permite_mesa_si_reserva_anterior_esta_rechazada(self):
        self.client.force_authenticate(user=self.dueno)
        mesa = Mesa.objects.create(
            restaurante=self.restaurante,
            numero=5,
            nombre="Mesa disponible",
            activa=True,
        )
        fecha_reserva = date.today() + timedelta(days=2)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="111111111",
            email="original@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            mesa_asignada=str(mesa.id),
            estado="rechazada",
        )

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            self.reserva_manual_payload(mesa),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class PaginacionTests(BaseTestCase):

    def test_configuracion_global_paginacion_drf(self):
        self.assertNotIn("PAGE_SIZE", settings.REST_FRAMEWORK)
        self.assertNotIn("DEFAULT_PAGINATION_CLASS", settings.REST_FRAMEWORK)

    def test_reservas_dashboard_paginadas_y_multi_tenant(self):
        self.client.force_authenticate(user=self.dueno)

        for i in range(25):
            Reserva.objects.create(
                restaurante=self.restaurante,
                nombre_cliente=f"Cliente {i}",
                telefono="999999999",
                fecha=date.today() + timedelta(days=2),
                hora=time(12, 0),
                cantidad_personas=2,
                estado="pendiente",
            )

        Reserva.objects.create(
            restaurante=self.otro_restaurante,
            nombre_cliente="Cliente externo",
            telefono="999999999",
            fecha=date.today() + timedelta(days=2),
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )

        response = self.client.get("/api/mi-restaurante/reservas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["next"])
        nombres = [reserva["nombre_cliente"] for reserva in response.data["results"]]
        self.assertNotIn("Cliente externo", nombres)

    def test_historial_paginado_y_multi_tenant(self):
        self.client.force_authenticate(user=self.dueno)

        for i in range(25):
            BitacoraProducto.objects.create(
                restaurante=self.restaurante,
                producto_id=self.producto.id,
                producto_nombre=f"Producto {i}",
                usuario=self.dueno,
                accion="CREADO",
                descripcion="Producto creado",
            )

        BitacoraProducto.objects.create(
            restaurante=self.otro_restaurante,
            producto_id=999,
            producto_nombre="Producto externo",
            usuario=self.dueno,
            accion="CREADO",
            descripcion="No debe verse",
        )

        response = self.client.get("/api/historial/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])
        productos = [item["producto"] for item in response.data["results"]]
        self.assertNotIn("Producto externo", productos)

    def test_productos_paginados_y_multi_tenant(self):
        self.client.force_authenticate(user=self.dueno)

        for i in range(2, 14):
            Producto.objects.create(
                restaurante=self.restaurante,
                categoria=self.categoria,
                nombre=f"Producto {i}",
                descripcion="Producto paginado",
                precio=1000 + i,
                disponible=True,
                destacado=False,
                orden=i,
            )

        Producto.objects.create(
            restaurante=self.otro_restaurante,
            categoria=self.categoria_otro_restaurante,
            nombre="Producto externo",
            descripcion="No debe verse",
            precio=9999,
            disponible=True,
            destacado=False,
            orden=1,
        )

        response = self.client.get("/api/mi-restaurante/productos/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 13)
        self.assertEqual(len(response.data["results"]), 8)
        nombres = [producto["nombre"] for producto in response.data["results"]]
        self.assertIn("Coca Cola", nombres)
        self.assertNotIn("Producto externo", nombres)

    def test_respaldos_paginados_y_multi_tenant(self):
        self.client.force_authenticate(user=self.dueno)

        for i in range(12):
            RespaldoRestaurante.objects.create(
                restaurante=self.restaurante,
                responsable=self.perfil_dueno,
                nombre_responsable=f"Responsable {i}",
                nombre_restaurante=self.restaurante.nombre_empresa,
                datos_json={"indice": i},
            )

        RespaldoRestaurante.objects.create(
            restaurante=self.otro_restaurante,
            responsable=None,
            nombre_responsable="Externo",
            nombre_restaurante=self.otro_restaurante.nombre_empresa,
            datos_json={"externo": True},
        )

        response = self.client.get("/api/mi-restaurante/respaldos/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 12)
        self.assertEqual(len(response.data["results"]), 10)
        restaurantes = [item["nombre_restaurante"] for item in response.data["results"]]
        self.assertNotIn(self.otro_restaurante.nombre_empresa, restaurantes)

    def test_usuarios_paginados_y_filtrados_por_restaurante(self):
        self.client.force_authenticate(user=self.dueno)

        otro_user = User.objects.create_user(
            username="otro-user@test.com",
            email="otro-user@test.com",
            password="12345678"
        )
        UsuarioRestaurante.objects.create(
            user=otro_user,
            restaurante=self.otro_restaurante,
            rol="dueno",
            activo=True,
        )

        response = self.client.get("/api/mi-restaurante/usuarios/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        usernames = [usuario["username"] for usuario in response.data["results"]]
        self.assertIn(self.dueno.username, usernames)
        self.assertNotIn("otro-user@test.com", usernames)


class ProductoClickTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_click_valido_incrementa_contador(self):
        response = self.client.post(f"/api/productos/{self.producto.id}/click/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"mensaje": "Click registrado"})

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.clicks, 1)

    def test_producto_inexistente_devuelve_404(self):
        response = self.client.post("/api/productos/999999/click/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_producto_no_disponible_no_incrementa_clicks(self):
        self.producto.disponible = False
        self.producto.clicks = 5
        self.producto.save(update_fields=["disponible", "clicks"])

        response = self.client.post(f"/api/productos/{self.producto.id}/click/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.clicks, 5)

    def test_click_solo_incrementa_clicks_y_no_expone_datos_sensibles(self):
        nombre = self.producto.nombre
        precio = self.producto.precio
        categoria_id = self.producto.categoria_id
        restaurante_id = self.producto.restaurante_id

        response = self.client.post(f"/api/productos/{self.producto.id}/click/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(response.data.keys()), ["mensaje"])

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.clicks, 1)
        self.assertEqual(self.producto.nombre, nombre)
        self.assertEqual(self.producto.precio, precio)
        self.assertEqual(self.producto.categoria_id, categoria_id)
        self.assertEqual(self.producto.restaurante_id, restaurante_id)

    def test_throttle_bloquea_exceso_de_clicks(self):
        for _ in range(30):
            response = self.client.post(f"/api/productos/{self.producto.id}/click/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(f"/api/productos/{self.producto.id}/click/")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_rate_producto_click_existe_y_no_afecta_otros_rates(self):
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})

        self.assertEqual(rates["producto_click"], "30/min")
        self.assertEqual(rates["login"], "5/min")
        self.assertEqual(rates["password_reset"], "3/hour")
        self.assertEqual(rates["public_reservas"], "20/hour")
        self.assertIn(ProductoClickRateThrottle, ProductoClickView.throttle_classes)
        self.assertIn(PublicReservaRateThrottle, CrearReservaPublicaView.throttle_classes)
        self.assertIn(PasswordResetRateThrottle, PasswordResetRequestView.throttle_classes)


class MultiTenantIsolationTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        self.dueno_b = User.objects.create_user(
            username="dueno-b@test.com",
            email="dueno-b@test.com",
            password="123456"
        )
        self.admin_b = User.objects.create_user(
            username="admin-b@test.com",
            email="admin-b@test.com",
            password="123456"
        )
        self.empleado_b = User.objects.create_user(
            username="empleado-b@test.com",
            email="empleado-b@test.com",
            password="123456"
        )
        self.perfil_dueno_b = UsuarioRestaurante.objects.create(
            user=self.dueno_b,
            restaurante=self.otro_restaurante,
            rol="dueno",
            activo=True,
        )
        self.perfil_admin_b = UsuarioRestaurante.objects.create(
            user=self.admin_b,
            restaurante=self.otro_restaurante,
            rol="admin",
            activo=True,
        )
        self.perfil_empleado_b = UsuarioRestaurante.objects.create(
            user=self.empleado_b,
            restaurante=self.otro_restaurante,
            rol="empleado",
            activo=True,
        )
        self.producto_b = Producto.objects.create(
            restaurante=self.otro_restaurante,
            categoria=self.categoria_otro_restaurante,
            nombre="Producto B",
            descripcion="Producto de otro restaurante",
            precio=2500,
            disponible=True,
            destacado=False,
            orden=1,
        )
        self.mesa_a = Mesa.objects.create(
            restaurante=self.restaurante,
            numero=1,
            nombre="Mesa A",
            activa=True,
        )
        self.mesa_b = Mesa.objects.create(
            restaurante=self.otro_restaurante,
            numero=1,
            nombre="Mesa B",
            activa=True,
        )
        self.reserva_b = Reserva.objects.create(
            restaurante=self.otro_restaurante,
            nombre_cliente="Cliente B",
            telefono="911111111",
            email="cliente-b@test.com",
            fecha=date.today() + timedelta(days=2),
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )
        self.horario_b = HorarioAtencion.objects.create(
            restaurante=self.otro_restaurante,
            dia=1,
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )
        self.metodo_b = MetodoPago.objects.create(
            restaurante=self.otro_restaurante,
            nombre="Pago B",
            activo=True,
        )
        self.bitacora_b = BitacoraProducto.objects.create(
            restaurante=self.otro_restaurante,
            producto_id=self.producto_b.id,
            producto_nombre=self.producto_b.nombre,
            usuario=self.dueno_b,
            accion="CREADO",
            descripcion="Accion de B",
        )
        self.respaldo_b = RespaldoRestaurante.objects.create(
            restaurante=self.otro_restaurante,
            responsable=self.perfil_dueno_b,
            nombre_responsable="Dueno B",
            nombre_restaurante=self.otro_restaurante.nombre_empresa,
            datos_json={"restaurante": "B"},
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def assert_forbidden_or_not_found(self, response):
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
        )

    def test_usuarios_de_a_no_ven_usuarios_de_b(self):
        for user in [self.dueno, self.admin]:
            self.client.force_authenticate(user=user)
            response = self.client.get("/api/mi-restaurante/usuarios/")

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            emails = [item["email"] for item in response.data["results"]]
            self.assertIn(self.dueno.email, emails)
            self.assertNotIn(self.dueno_b.email, emails)

        self.client.force_authenticate(user=self.empleado)
        response = self.client.get("/api/mi-restaurante/usuarios/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dueno_a_no_modifica_ni_elimina_usuario_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        patch_response = self.client.patch(
            f"/api/mi-restaurante/usuarios/{self.perfil_admin_b.id}/",
            {"username": "admin-b-editado@test.com"},
            format="json"
        )
        delete_response = self.client.delete(
            f"/api/mi-restaurante/usuarios/{self.perfil_admin_b.id}/"
        )

        self.assert_forbidden_or_not_found(patch_response)
        self.assert_forbidden_or_not_found(delete_response)
        self.admin_b.refresh_from_db()
        self.perfil_admin_b.refresh_from_db()
        self.assertEqual(self.admin_b.username, "admin-b@test.com")
        self.assertTrue(self.perfil_admin_b.activo)

    def test_productos_de_a_no_ven_ni_modifican_productos_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/productos/")
        nombres = [item["nombre"] for item in listar_response.data["results"]]
        self.assertIn(self.producto.nombre, nombres)
        self.assertNotIn(self.producto_b.nombre, nombres)

        editar_response = self.client.patch(
            f"/api/mi-restaurante/productos/{self.producto_b.id}/actualizar/",
            {
                "nombre": "Producto B editado",
                "categoria": self.categoria_otro_restaurante.id,
                "orden": 2,
                "precio": 9999,
            },
            format="json"
        )
        disponibilidad_response = self.client.patch(
            f"/api/mi-restaurante/productos/{self.producto_b.id}/",
            {"disponible": False},
            format="json"
        )
        eliminar_response = self.client.delete(
            f"/api/mi-restaurante/productos/{self.producto_b.id}/eliminar/"
        )

        self.assert_forbidden_or_not_found(editar_response)
        self.assert_forbidden_or_not_found(disponibilidad_response)
        self.assert_forbidden_or_not_found(eliminar_response)
        self.producto_b.refresh_from_db()
        self.assertEqual(self.producto_b.nombre, "Producto B")
        self.assertTrue(self.producto_b.disponible)
        self.assertEqual(self.producto_b.orden, 1)

    def test_producto_de_a_no_puede_usar_categoria_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/productos/agregar/",
            {
                "categoria": self.categoria_otro_restaurante.id,
                "nombre": "Producto cruzado",
                "descripcion": "No debe crearse",
                "precio": 3000,
                "orden": 2,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            Producto.objects.filter(
                restaurante=self.restaurante,
                nombre="Producto cruzado",
            ).exists()
        )

    def test_categorias_de_a_no_ven_ni_modifican_categorias_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/categorias/")
        nombres = [item["nombre"] for item in listar_response.data]
        self.assertIn(self.categoria.nombre, nombres)
        self.assertNotIn(self.categoria_otro_restaurante.nombre, nombres)

        patch_response = self.client.patch(
            f"/api/mi-restaurante/categorias/{self.categoria_otro_restaurante.id}/",
            {"nombre": "Categoria B editada"},
            format="json"
        )
        delete_response = self.client.delete(
            f"/api/mi-restaurante/categorias/{self.categoria_otro_restaurante.id}/"
        )

        self.assert_forbidden_or_not_found(patch_response)
        self.assert_forbidden_or_not_found(delete_response)
        self.categoria_otro_restaurante.refresh_from_db()
        self.assertEqual(self.categoria_otro_restaurante.nombre, "Comida")

    def test_reservas_de_a_no_ven_ni_gestionan_reservas_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/reservas/")
        ids = [item["id"] for item in listar_response.data["results"]]
        self.assertNotIn(self.reserva_b.id, ids)

        patch_response = self.client.patch(
            f"/api/mi-restaurante/reservas/{self.reserva_b.id}/",
            {"estado": "confirmada"},
            format="json"
        )

        self.assert_forbidden_or_not_found(patch_response)
        self.reserva_b.refresh_from_db()
        self.assertEqual(self.reserva_b.estado, "pendiente")

    def test_reserva_manual_de_a_no_usa_mesa_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            {
                "nombre_cliente": "Cliente A",
                "telefono": "922222222",
                "email": "cliente-a@test.com",
                "fecha": (date.today() + timedelta(days=2)).isoformat(),
                "hora": "12:00",
                "cantidad_personas": 2,
                "mesa_asignada": self.mesa_b.id,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("mesa_asignada", response.data)

    def test_reserva_publica_slug_a_crea_en_a_y_no_en_b(self):
        fecha_reserva = date.today() + timedelta(days=3)
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=fecha_reserva.isoweekday(),
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            {
                "nombre_cliente": "Publico A",
                "telefono": "933333333",
                "email": "publico-a@test.com",
                "fecha": fecha_reserva.isoformat(),
                "hora": "12:00",
                "cantidad_personas": 2,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Reserva.objects.filter(
                restaurante=self.restaurante,
                email="publico-a@test.com",
            ).exists()
        )
        self.assertFalse(
            Reserva.objects.filter(
                restaurante=self.otro_restaurante,
                email="publico-a@test.com",
            ).exists()
        )

    def test_mesas_de_a_no_ven_ni_modifican_mesas_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/mesas/")
        nombres = [item["nombre"] for item in listar_response.data]
        self.assertIn(self.mesa_a.nombre, nombres)
        self.assertNotIn(self.mesa_b.nombre, nombres)

        patch_response = self.client.patch(
            f"/api/mi-restaurante/mesas/{self.mesa_b.id}/",
            {"nombre": "Mesa B editada", "numero": 9},
            format="json"
        )
        delete_response = self.client.delete(
            f"/api/mi-restaurante/mesas/{self.mesa_b.id}/"
        )

        self.assert_forbidden_or_not_found(patch_response)
        self.assert_forbidden_or_not_found(delete_response)
        self.mesa_b.refresh_from_db()
        self.assertEqual(self.mesa_b.nombre, "Mesa B")

    def test_horarios_de_a_no_ven_ni_modifican_horarios_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/horarios/")
        ids = [item["id"] for item in listar_response.data]
        self.assertNotIn(self.horario_b.id, ids)

        patch_response = self.client.patch(
            f"/api/mi-restaurante/horarios/{self.horario_b.id}/",
            {"cerrado": True},
            format="json"
        )

        self.assert_forbidden_or_not_found(patch_response)
        self.horario_b.refresh_from_db()
        self.assertFalse(self.horario_b.cerrado)

    def test_metodos_pago_de_a_no_ven_ni_modifican_metodos_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/metodos-pago/")
        nombres = [item["nombre"] for item in listar_response.data]
        self.assertNotIn(self.metodo_b.nombre, nombres)

        patch_response = self.client.patch(
            f"/api/mi-restaurante/metodos-pago/{self.metodo_b.id}/",
            {"nombre": "Pago B editado"},
            format="json"
        )
        delete_response = self.client.delete(
            f"/api/mi-restaurante/metodos-pago/{self.metodo_b.id}/"
        )

        self.assert_forbidden_or_not_found(patch_response)
        self.assert_forbidden_or_not_found(delete_response)
        self.metodo_b.refresh_from_db()
        self.assertEqual(self.metodo_b.nombre, "Pago B")

    def test_historial_de_a_no_incluye_acciones_de_b_y_escribe_en_a(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/historial/")
        productos = [item["producto"] for item in listar_response.data["results"]]
        self.assertNotIn(self.producto_b.nombre, productos)

        self.client.patch(
            f"/api/mi-restaurante/productos/{self.producto.id}/actualizar/",
            {
                "nombre": "Coca Cola Zero",
                "categoria": self.categoria.id,
                "orden": self.producto.orden,
                "precio": self.producto.precio,
            },
            format="json"
        )

        self.assertTrue(
            BitacoraProducto.objects.filter(
                restaurante=self.restaurante,
                producto_id=self.producto.id,
                accion="EDITADO",
            ).exists()
        )
        self.assertFalse(
            BitacoraProducto.objects.filter(
                restaurante=self.otro_restaurante,
                producto_id=self.producto.id,
            ).exists()
        )

    def test_respaldos_de_a_no_ven_respaldos_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/respaldos/")
        ids = [item["id"] for item in listar_response.data["results"]]
        self.assertNotIn(self.respaldo_b.id, ids)

        ultimo_response = self.client.get("/api/mi-restaurante/respaldos/ultimo/")
        ultimo = ultimo_response.data["ultimo_respaldo"]
        if ultimo:
            self.assertNotEqual(ultimo["id"], self.respaldo_b.id)

    def test_menu_publico_por_slug_no_mezcla_productos(self):
        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        categorias = response.json()["categorias"]
        productos = [
            producto["nombre"]
            for categoria in categorias
            for producto in categoria["productos"]
        ]
        self.assertIn(self.producto.nombre, productos)
        self.assertNotIn(self.producto_b.nombre, productos)

    def test_detalle_publico_por_slug_no_expone_otro_restaurante(self):
        response = self.client.get("/api/restaurantes/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "restaurante-test")
        self.assertEqual(response.data["nombre_empresa"], self.restaurante.nombre_empresa)
        self.assertNotEqual(response.data["slug"], "otro-restaurante")

    def test_click_producto_solo_afecta_producto_indicado(self):
        response = self.client.post(f"/api/productos/{self.producto.id}/click/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.producto.refresh_from_db()
        self.producto_b.refresh_from_db()
        self.assertEqual(self.producto.clicks, 1)
        self.assertEqual(self.producto_b.clicks, 0)

    def test_slugs_publicos_inexistentes_devuelven_404(self):
        menu_response = self.client.get("/api/menu/no-existe/")
        detalle_response = self.client.get("/api/restaurantes/no-existe/")

        self.assertEqual(menu_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(detalle_response.status_code, status.HTTP_404_NOT_FOUND)


class MenuPublicoTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()

    def test_menu_publico_responde_por_slug(self):
        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_menu_publico_no_requiere_login(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_menu_publico_no_muestra_restaurante_inactivo(self):
        self.restaurante.activo = False
        self.restaurante.save()

        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["estado"], "inactivo")

    def test_menu_publico_usa_cache_por_slug(self):
        cache.set(
            menu_cache_key("restaurante-test"),
            {
                "restaurante": {"reservas_activas": True},
                "categorias": [{"id": 999, "nombre": "Cacheado", "icono": None, "productos": []}],
            },
            timeout=300,
        )

        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["categorias"][0]["nombre"], "Cacheado")

    def test_cambio_producto_invalida_cache_menu_publico(self):
        cache.set(
            menu_cache_key("restaurante-test"),
            {
                "restaurante": {"reservas_activas": True},
                "categorias": [{"id": 999, "nombre": "Cache viejo", "icono": None, "productos": []}],
            },
            timeout=300,
        )

        self.producto.nombre = "Producto cache actualizado"
        self.producto.save(update_fields=["nombre"])

        response = self.client.get("/api/menu/restaurante-test/")
        nombres = [
            producto["nombre"]
            for categoria in response.json()["categorias"]
            for producto in categoria["productos"]
        ]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Producto cache actualizado", nombres)
        self.assertNotEqual(response.json()["categorias"][0]["nombre"], "Cache viejo")

    def test_menu_publico_devuelve_flags_del_restaurante(self):
        self.restaurante.reservas_activas = False
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.metricas_activas = False
        self.restaurante.save(update_fields=[
            "reservas_activas",
            "solicitudes_especiales_activas",
            "carrito_whatsapp_activo",
            "metricas_activas",
        ])

        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json()["restaurante"]["reservas_activas"])
        self.assertTrue(response.json()["restaurante"]["solicitudes_especiales_activas"])
        self.assertTrue(response.json()["restaurante"]["carrito_whatsapp_activo"])
        self.assertFalse(response.json()["restaurante"]["metricas_activas"])


class RestaurantePublicoDetalleTests(BaseTestCase):

    def test_detalle_publico_responde_por_slug(self):
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=1,
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )
        MetodoPago.objects.create(
            restaurante=self.restaurante,
            nombre="Transferencia",
            activo=True,
        )
        MetodoPago.objects.create(
            restaurante=self.restaurante,
            nombre="Cheque",
            activo=False,
        )

        response = self.client.get("/api/restaurantes/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "restaurante-test")
        self.assertEqual(response.data["nombre_empresa"], "Restaurante Test")
        self.assertEqual(len(response.data["horarios"]), 1)
        self.assertEqual(
            [metodo["nombre"] for metodo in response.data["metodos_pago"]],
            ["Transferencia"]
        )
        self.assertNotIn("notificar_reservas", response.data)
        self.assertNotIn("email_notificacion", response.data)
        self.assertIn("reservas_activas", response.data)
        self.assertIn("solicitudes_especiales_activas", response.data)
        self.assertIn("carrito_whatsapp_activo", response.data)
        self.assertIn("metricas_activas", response.data)

    def test_detalle_publico_no_requiere_login(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/restaurantes/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_detalle_publico_no_muestra_restaurante_inactivo(self):
        self.restaurante.activo = False
        self.restaurante.save()

        response = self.client.get("/api/restaurantes/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["estado"], "inactivo")


class RestauranteFeatureFlagsTests(BaseTestCase):

    def test_restaurante_feature_flags_tienen_defaults_correctos(self):
        restaurante = Restaurante.objects.get(id=self.restaurante.id)

        self.assertTrue(restaurante.reservas_activas)
        self.assertFalse(restaurante.solicitudes_especiales_activas)
        self.assertFalse(restaurante.carrito_whatsapp_activo)
        self.assertTrue(restaurante.metricas_activas)

    def test_mi_restaurante_devuelve_flags_para_lectura(self):
        self.client.force_authenticate(user=self.dueno)
        self.restaurante.reservas_activas = False
        self.restaurante.save(update_fields=["reservas_activas"])

        response = self.client.get("/api/mi-restaurante/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["restaurante"]["reservas_activas"])
        self.assertIn("metricas_activas", response.data["restaurante"])

    def test_configuracion_devuelve_flags_pero_patch_no_los_modifica(self):
        self.client.force_authenticate(user=self.dueno)

        get_response = self.client.get("/api/mi-restaurante/configuracion/")
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertIn("reservas_activas", get_response.data["restaurante"])

        patch_response = self.client.patch(
            "/api/mi-restaurante/configuracion/",
            {
                "nombre_empresa": "Nombre editado",
                "reservas_activas": False,
                "solicitudes_especiales_activas": True,
                "carrito_whatsapp_activo": True,
                "metricas_activas": False,
            },
            format="json",
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.restaurante.refresh_from_db()
        self.assertEqual(self.restaurante.nombre_empresa, "Nombre editado")
        self.assertTrue(self.restaurante.reservas_activas)
        self.assertFalse(self.restaurante.solicitudes_especiales_activas)
        self.assertFalse(self.restaurante.carrito_whatsapp_activo)
        self.assertTrue(self.restaurante.metricas_activas)

    def test_admin_puede_ver_configuracion_pero_no_modificar_flags_por_api(self):
        self.client.force_authenticate(user=self.admin)

        get_response = self.client.get("/api/mi-restaurante/configuracion/")
        patch_response = self.client.patch(
            "/api/mi-restaurante/configuracion/",
            {"reservas_activas": False},
            format="json",
        )

        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertIn("reservas_activas", get_response.data["restaurante"])
        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)


class SeguridadCriticaTests(BaseTestCase):

    def crear_horario_para_reserva(self, restaurante, fecha_reserva):
        return HorarioAtencion.objects.create(
            restaurante=restaurante,
            dia=fecha_reserva.isoweekday(),
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )

    def payload_reserva_publica(self, fecha_reserva, **overrides):
        data = {
            "nombre_cliente": "Cliente Reserva",
            "telefono": "999999999",
            "email": "cliente@test.com",
            "fecha": fecha_reserva.isoformat(),
            "hora": "12:00",
            "cantidad_personas": 2,
            "mensaje": "",
        }
        data.update(overrides)
        return data

    def payload_solicitud_especial(self, **overrides):
        data = {
            "restaurante_id": self.restaurante.id,
            "nombre": "Cliente",
            "apellido": "Especial",
            "fecha_evento": (date.today() + timedelta(days=10)).isoformat(),
            "telefono_contacto": "999999999",
            "email_contacto": "cliente.especial@test.com",
            "descripcion_solicitud": "Necesito un pedido especial para un evento.",
        }
        data.update(overrides)
        return data

    def test_solicitud_especial_publica_crea_en_restaurante_del_slug(self):
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.save(update_fields=["solicitudes_especiales_activas"])

        response = self.client.post(
            "/api/solicitudes-especiales/restaurante-test/",
            self.payload_solicitud_especial(),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        solicitud = SolicitudEspecial.objects.get(email_contacto="cliente.especial@test.com")
        self.assertEqual(solicitud.restaurante, self.restaurante)

    def test_solicitud_especial_rechaza_restaurante_id_distinto_al_slug(self):
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.save(update_fields=["solicitudes_especiales_activas"])

        response = self.client.post(
            "/api/solicitudes-especiales/restaurante-test/",
            self.payload_solicitud_especial(restaurante_id=self.otro_restaurante.id),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(SolicitudEspecial.objects.exists())

    def test_solicitud_especial_rechaza_modulo_inactivo(self):
        response = self.client.post(
            "/api/solicitudes-especiales/restaurante-test/",
            self.payload_solicitud_especial(),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(SolicitudEspecial.objects.exists())

    @patch("menu.utils.send_mail")
    def test_solicitud_especial_publica_envia_notificacion_si_esta_configurado(self, send_mail_mock):
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.notificar_reservas = True
        self.restaurante.email_notificacion = " solicitudes@test.com "
        self.restaurante.save(update_fields=[
            "solicitudes_especiales_activas",
            "notificar_reservas",
            "email_notificacion",
        ])

        response = self.client.post(
            "/api/solicitudes-especiales/restaurante-test/",
            self.payload_solicitud_especial(),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        send_mail_mock.assert_called_once()
        kwargs = send_mail_mock.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], ["solicitudes@test.com"])
        self.assertIn("Cliente Especial", kwargs["message"])

    def test_solicitud_especial_publica_tiene_throttle_configurado(self):
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})

        self.assertIn("public_solicitudes_especiales", rates)
        self.assertEqual(rates["public_solicitudes_especiales"], "20/hour")
        self.assertIn(
            PublicSolicitudEspecialRateThrottle,
            CrearSolicitudEspecialPublicaView.throttle_classes
        )

    def test_dashboard_solicitudes_lista_solo_restaurante_autenticado(self):
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.save(update_fields=["solicitudes_especiales_activas"])
        SolicitudEspecial.objects.create(
            restaurante=self.restaurante,
            nombre="Cliente",
            apellido="Propio",
            fecha_evento=date.today() + timedelta(days=10),
            telefono_contacto="999999999",
            email_contacto="propio@test.com",
            descripcion_solicitud="Solicitud propia",
        )
        SolicitudEspecial.objects.create(
            restaurante=self.otro_restaurante,
            nombre="Cliente",
            apellido="Externo",
            fecha_evento=date.today() + timedelta(days=10),
            telefono_contacto="888888888",
            email_contacto="externo@test.com",
            descripcion_solicitud="Solicitud externa",
        )

        self.client.force_authenticate(user=self.dueno)
        response = self.client.get("/api/mi-restaurante/solicitudes-especiales/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [item["email_contacto"] for item in response.data["results"]]
        self.assertIn("propio@test.com", emails)
        self.assertNotIn("externo@test.com", emails)

    def test_empleado_puede_gestionar_solicitudes_especiales(self):
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.save(update_fields=["solicitudes_especiales_activas"])

        self.client.force_authenticate(user=self.empleado)
        response = self.client.post(
            "/api/mi-restaurante/solicitudes-especiales/",
            self.payload_solicitud_especial(),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            SolicitudEspecial.objects.filter(
                restaurante=self.restaurante,
                email_contacto="cliente.especial@test.com",
            ).exists()
        )

    def test_dashboard_solicitudes_rechaza_modulo_inactivo(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.get("/api/mi-restaurante/solicitudes-especiales/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_solicitudes_no_actualiza_otro_restaurante(self):
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.save(update_fields=["solicitudes_especiales_activas"])
        solicitud_externa = SolicitudEspecial.objects.create(
            restaurante=self.otro_restaurante,
            nombre="Cliente",
            apellido="Externo",
            fecha_evento=date.today() + timedelta(days=10),
            telefono_contacto="888888888",
            email_contacto="externo@test.com",
            descripcion_solicitud="Solicitud externa",
        )

        self.client.force_authenticate(user=self.dueno)
        response = self.client.patch(
            f"/api/mi-restaurante/solicitudes-especiales/{solicitud_externa.id}/",
            {"estado": "aceptada"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        solicitud_externa.refresh_from_db()
        self.assertEqual(solicitud_externa.estado, "pendiente")

    def test_pedido_especial_entregado_completa_solicitud_y_sale_del_listado_activo(self):
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.save(update_fields=["solicitudes_especiales_activas"])
        solicitud = SolicitudEspecial.objects.create(
            restaurante=self.restaurante,
            nombre="Cliente",
            apellido="Especial",
            fecha_evento=date.today() + timedelta(days=10),
            telefono_contacto="999999999",
            email_contacto="especial@test.com",
            descripcion_solicitud="Solicitud aceptada",
            estado="aceptada",
        )

        self.client.force_authenticate(user=self.dueno)
        crear_response = self.client.post(
            "/api/mi-restaurante/pedidos/especiales/",
            {
                "solicitud_especial_id": solicitud.id,
                "fecha_entrega": str(solicitud.fecha_evento),
                "items": [
                    {
                        "nombre": "Pedido especial",
                        "descripcion": "Item principal",
                        "cantidad": 1,
                        "precio_unitario": 15000,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(crear_response.status_code, status.HTTP_201_CREATED)
        pedido_id = crear_response.data["pedido"]["id"]

        actualizar_response = None
        for estado in [
            PedidoEspecial.ESTADO_EN_PREPARACION,
            PedidoEspecial.ESTADO_LISTO,
            PedidoEspecial.ESTADO_ENTREGADO,
        ]:
            actualizar_response = self.client.patch(
                f"/api/mi-restaurante/pedidos/especiales/{pedido_id}/estado/",
                {"estado": estado},
                format="json",
            )
            self.assertEqual(actualizar_response.status_code, status.HTTP_200_OK)

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, "completada")

        listado_response = self.client.get("/api/mi-restaurante/pedidos/especiales/")

        self.assertEqual(listado_response.status_code, status.HTTP_200_OK)
        ids_listado = [pedido["id"] for pedido in listado_response.data["results"]]
        self.assertNotIn(pedido_id, ids_listado)
        self.assertTrue(
            PedidoEspecial.objects.filter(
                id=pedido_id,
                estado=PedidoEspecial.ESTADO_ENTREGADO,
            ).exists()
        )

    def test_pedido_especial_entregado_con_fk_nulo_vincula_y_completa_solicitud_original(self):
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.save(update_fields=["solicitudes_especiales_activas"])
        solicitud = SolicitudEspecial.objects.create(
            restaurante=self.restaurante,
            nombre="Cliente",
            apellido="Especial",
            fecha_evento=date.today() + timedelta(days=10),
            telefono_contacto="999999999",
            email_contacto="especial@test.com",
            descripcion_solicitud="Solicitud aceptada",
            estado="aceptada",
        )
        pedido = PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            solicitud_especial=None,
            numero_pedido=1,
            nombre_cliente=solicitud.nombre,
            telefono_cliente=solicitud.telefono_contacto,
            email_cliente=solicitud.email_contacto,
            descripcion_original=solicitud.descripcion_solicitud,
            items=[
                {
                    "nombre": "Pedido especial",
                    "descripcion": "Item principal",
                    "cantidad": 1,
                    "precio_unitario": 15000,
                    "subtotal": 15000,
                }
            ],
            total=15000,
            fecha_entrega=solicitud.fecha_evento,
            estado=PedidoEspecial.ESTADO_CONFIRMADO,
        )

        self.client.force_authenticate(user=self.dueno)
        response = None
        for estado in [
            PedidoEspecial.ESTADO_EN_PREPARACION,
            PedidoEspecial.ESTADO_LISTO,
            PedidoEspecial.ESTADO_ENTREGADO,
        ]:
            response = self.client.patch(
                f"/api/mi-restaurante/pedidos/especiales/{pedido.id}/estado/",
                {"estado": estado},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        solicitud.refresh_from_db()
        pedido.refresh_from_db()
        self.assertEqual(solicitud.estado, "completada")
        self.assertEqual(pedido.solicitud_especial_id, solicitud.id)

    def test_pedidos_whatsapp_dashboard_lista_solo_pedidos_de_hoy(self):
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.save(update_fields=["carrito_whatsapp_activo"])
        hoy = timezone.localtime(timezone.now())
        ayer = hoy - timedelta(days=1)
        pedido_hoy = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Cliente Hoy",
            telefono_cliente="999999999",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[
                {
                    "nombre": "Hamburguesa",
                    "cantidad": 2,
                    "precio_unitario": 5000,
                    "subtotal": 10000,
                }
            ],
            total=10000,
            mensaje_whatsapp_generado="Pedido hoy",
            whatsapp_destino="999999999",
        )
        pedido_ayer = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            nombre_cliente="Cliente Ayer",
            telefono_cliente="888888888",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[
                {
                    "nombre": "Bebida",
                    "cantidad": 1,
                    "precio_unitario": 2000,
                    "subtotal": 2000,
                }
            ],
            total=2000,
            mensaje_whatsapp_generado="Pedido ayer",
            whatsapp_destino="888888888",
        )
        PedidoWhatsApp.objects.filter(id=pedido_ayer.id).update(fecha_creacion=ayer)

        self.client.force_authenticate(user=self.dueno)
        response = self.client.get("/api/mi-restaurante/pedidos/whatsapp/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [pedido["id"] for pedido in response.data["results"]]
        self.assertIn(pedido_hoy.id, ids)
        self.assertNotIn(pedido_ayer.id, ids)

    def test_pedido_whatsapp_publico_crea_tracking_y_link_en_mensaje(self):
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.whatsapp = "56999999999"
        self.restaurante.save(update_fields=["carrito_whatsapp_activo", "whatsapp"])

        response = self.client.post(
            f"/api/pedidos-whatsapp/{self.restaurante.slug}/",
            {
                "nombre_cliente": "Cliente Tracking",
                "telefono_cliente": "912345678",
                "tipo_entrega": PedidoWhatsApp.TIPO_RETIRO_LOCAL,
                "productos": [
                    {"producto_id": self.producto.id, "cantidad": 2},
                ],
            },
            format="json",
            HTTP_ORIGIN="http://localhost:5173",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("tracking_token", response.data)
        self.assertIn("tracking_url", response.data)
        self.assertEqual(response.data["total"], 3000)
        self.assertIn(
            f"http://localhost:5173/seguimiento/pedido/{response.data['tracking_token']}",
            response.data["mensaje_whatsapp"],
        )
        expected_message = (
            "Hola, quiero hacer este pedido:\n\n"
            f"Pedido #{response.data['numero_pedido']}\n"
            "2 x Coca Cola - $3000\n\n"
            "Total: $3000\n"
            "Tipo entrega: Retiro en local\n"
            "Cliente: Cliente Tracking\n"
            "Telefono: 912345678\n\n"
            "Puedes ver el estado de tu pedido aqui:\n"
            f"http://localhost:5173/seguimiento/pedido/{response.data['tracking_token']}"
        )
        self.assertEqual(response.data["mensaje_whatsapp"], expected_message)

        pedido = PedidoWhatsApp.objects.get(tracking_token=response.data["tracking_token"])
        self.assertEqual(pedido.restaurante, self.restaurante)
        self.assertEqual(pedido.total, 3000)
        self.assertTrue(pedido.tracking_token)
        self.assertEqual(
            pedido.productos_snapshot,
            [
                {
                    "producto_id": self.producto.id,
                    "nombre": "Coca Cola",
                    "variante_id": None,
                    "variante_nombre": "",
                    "precio_original": 1500,
                    "porcentaje_descuento_aplicado": None,
                    "monto_descuento": 0,
                    "precio_base": 1500,
                    "opciones_total": 0,
                    "precio_unitario": 1500,
                    "cantidad": 2,
                    "subtotal": 3000,
                    "grupos_opciones": [],
                }
            ],
        )
        self.assertEqual(pedido.mensaje_whatsapp_generado, expected_message)
        self.assertTrue(
            Notificacion.objects.filter(
                restaurante=self.restaurante,
                referencia_modelo=Notificacion.MODELO_PEDIDO_WHATSAPP,
                referencia_id=pedido.id,
            ).exists()
        )
        self.assertFalse(
            PedidoWhatsApp.objects.filter(
                restaurante=self.otro_restaurante,
                tracking_token=response.data["tracking_token"],
            ).exists()
        )

    def test_pedido_whatsapp_publico_rechaza_producto_de_otro_restaurante(self):
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.whatsapp = "56999999999"
        self.restaurante.save(update_fields=["carrito_whatsapp_activo", "whatsapp"])
        producto_otro = Producto.objects.create(
            restaurante=self.otro_restaurante,
            categoria=self.categoria_otro_restaurante,
            nombre="Producto ajeno",
            descripcion="No pertenece",
            precio=9990,
            disponible=True,
            destacado=False,
            orden=1,
        )

        response = self.client.post(
            f"/api/pedidos-whatsapp/{self.restaurante.slug}/",
            {
                "nombre_cliente": "Cliente Aislado",
                "telefono_cliente": "912345678",
                "tipo_entrega": PedidoWhatsApp.TIPO_RETIRO_LOCAL,
                "productos": [
                    {"producto_id": producto_otro.id, "cantidad": 1},
                ],
            },
            format="json",
            HTTP_ORIGIN="http://localhost:5173",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("productos", response.data)
        self.assertFalse(PedidoWhatsApp.objects.filter(restaurante=self.restaurante).exists())

    def test_seguimiento_publico_devuelve_solo_payload_seguro(self):
        pedido = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Cliente Publico",
            telefono_cliente="999999999",
            tipo_entrega=PedidoWhatsApp.TIPO_DELIVERY,
            direccion_entrega="Calle segura 123",
            productos_snapshot=[
                {
                    "producto_id": self.producto.id,
                    "nombre": "Coca Cola",
                    "cantidad": 1,
                    "precio_unitario": 1500,
                    "subtotal": 1500,
                }
            ],
            total=1500,
            mensaje_whatsapp_generado="Pedido publico",
            whatsapp_destino="56999999999",
        )

        response = self.client.get(
            f"/api/public/pedidos/seguimiento/{pedido.tracking_token}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["numero_pedido"], pedido.numero_pedido)
        self.assertEqual(response.data["estado"], PedidoWhatsApp.ESTADO_RECIBIDO)
        self.assertEqual(response.data["items"][0]["nombre"], "Coca Cola")
        self.assertNotIn("id", response.data)
        self.assertNotIn("nombre_cliente", response.data)
        self.assertNotIn("telefono_cliente", response.data)
        self.assertNotIn("tracking_token", response.data)

    def test_estado_pedido_whatsapp_se_actualiza_con_historial_y_tenant(self):
        pedido = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Cliente Estado",
            telefono_cliente="999999999",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=3000,
            mensaje_whatsapp_generado="Pedido estado",
            whatsapp_destino="56999999999",
        )
        dueno_otro = User.objects.create_user(
            username="dueno-otro@test.com",
            email="dueno-otro@test.com",
            password="123456",
        )
        UsuarioRestaurante.objects.create(
            user=dueno_otro,
            restaurante=self.otro_restaurante,
            rol="dueno",
            activo=True,
        )

        self.client.force_authenticate(user=dueno_otro)
        response_otro = self.client.patch(
            f"/api/pedidos-whatsapp/{pedido.id}/estado/",
            {"estado": PedidoWhatsApp.ESTADO_EN_PREPARACION},
            format="json",
        )
        self.assertEqual(response_otro.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(user=self.dueno)
        response = self.client.patch(
            f"/api/pedidos-whatsapp/{pedido.id}/estado/",
            {"estado": PedidoWhatsApp.ESTADO_EN_PREPARACION},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoWhatsApp.ESTADO_EN_PREPARACION)
        self.assertEqual(
            HistorialEstadoPedidoWhatsApp.objects.filter(
                pedido=pedido,
                estado_anterior=PedidoWhatsApp.ESTADO_RECIBIDO,
                estado_nuevo=PedidoWhatsApp.ESTADO_EN_PREPARACION,
                usuario=self.dueno,
            ).count(),
            1,
        )

    def test_historial_pedidos_whatsapp_lista_solo_pedidos_anteriores(self):
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.save(update_fields=["carrito_whatsapp_activo"])
        hoy = timezone.localtime(timezone.now())
        ayer = hoy - timedelta(days=1)
        pedido_hoy = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Cliente Hoy",
            telefono_cliente="999999999",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=10000,
            mensaje_whatsapp_generado="Pedido hoy",
            whatsapp_destino="999999999",
        )
        pedido_ayer = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            nombre_cliente="Cliente Ayer",
            telefono_cliente="888888888",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=2000,
            mensaje_whatsapp_generado="Pedido ayer",
            whatsapp_destino="888888888",
        )
        PedidoWhatsApp.objects.filter(id=pedido_ayer.id).update(fecha_creacion=ayer)

        self.client.force_authenticate(user=self.dueno)
        response = self.client.get("/api/historial/pedidos/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [pedido["id"] for pedido in response.data["results"]]
        self.assertIn(pedido_ayer.id, ids)
        self.assertNotIn(pedido_hoy.id, ids)

    def test_metricas_pedidos_resumen_diario_y_mensual(self):
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.save(update_fields=[
            "carrito_whatsapp_activo",
            "solicitudes_especiales_activas",
        ])
        hoy = timezone.localtime(timezone.now())
        ayer = hoy - timedelta(days=1)
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Cliente WSP Hoy",
            telefono_cliente="999999999",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[
                {
                    "producto_id": self.producto.id,
                    "nombre": "Hamburguesa",
                    "cantidad": 2,
                    "precio_unitario": 5000,
                    "subtotal": 10000,
                }
            ],
            total=10000,
            estado=PedidoWhatsApp.ESTADO_ENTREGADO,
            mensaje_whatsapp_generado="Pedido hoy",
            whatsapp_destino="999999999",
        )
        pedido_wsp_ayer = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            nombre_cliente="Cliente WSP Ayer",
            telefono_cliente="888888888",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[
                {
                    "nombre": "Bebida",
                    "cantidad": 1,
                    "precio_unitario": 2000,
                    "subtotal": 2000,
                }
            ],
            total=2000,
            mensaje_whatsapp_generado="Pedido ayer",
            whatsapp_destino="888888888",
        )
        pedido_wsp_cancelado = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=3,
            nombre_cliente="Cliente Cancelado",
            telefono_cliente="777777777",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=4000,
            estado=PedidoWhatsApp.ESTADO_CANCELADO,
            mensaje_whatsapp_generado="Pedido cancelado",
            whatsapp_destino="777777777",
        )
        pedido_especial = PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Cliente Especial",
            telefono_cliente="666666666",
            email_cliente="especial@test.com",
            descripcion_original="Pedido especial",
            items=[
                {
                    "nombre": "Torta",
                    "descripcion": "",
                    "cantidad": 1,
                    "precio_unitario": 20000,
                    "subtotal": 20000,
                }
            ],
            total=20000,
            fecha_entrega=hoy.date(),
            estado=PedidoEspecial.ESTADO_ENTREGADO,
        )
        pedido_especial_cancelado = PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            nombre_cliente="Cliente Especial Cancelado",
            telefono_cliente="555555555",
            email_cliente="cancelado@test.com",
            descripcion_original="Pedido especial cancelado",
            items=[],
            total=3000,
            fecha_entrega=hoy.date(),
            estado=PedidoEspecial.ESTADO_CANCELADO,
        )
        PedidoWhatsApp.objects.filter(id=pedido_wsp_ayer.id).update(fecha_creacion=ayer)

        self.client.force_authenticate(user=self.dueno)
        response = self.client.get("/api/mi-restaurante/pedidos/metricas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resumen = response.data["resumen"]
        self.assertEqual(resumen["venta_diaria_wsp"], 10000)
        self.assertEqual(resumen["pedidos_wsp_hoy"], 2)
        self.assertEqual(resumen["venta_especiales_mes"], int(pedido_especial.total))
        self.assertEqual(resumen["pedidos_especiales_mes"], 2)
        self.assertEqual(resumen["venta_total_mes"], 30000)
        self.assertEqual(resumen["pedidos_total_mes"], 2)
        self.assertEqual(resumen["pedidos_creados_mes"], 5)
        self.assertEqual(resumen["pedidos_finalizados_mes"], 2)
        self.assertEqual(resumen["pedidos_cancelados_mes"], 2)
        self.assertEqual(response.data["ventas"]["venta_real_mes"], 30000)
        self.assertEqual(response.data["pedidos"]["pedidos_activos"], 1)
        self.assertEqual(response.data["productos"]["mas_vendido_mes"]["producto_id"], self.producto.id)

    def test_metricas_resumen_venta_real_excluye_pendientes_y_cancelados(self):
        hoy = timezone.localtime(timezone.now()).date()
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Pendiente",
            telefono_cliente="111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=5000,
            estado=PedidoWhatsApp.ESTADO_PENDIENTE,
            mensaje_whatsapp_generado="Pendiente",
            whatsapp_destino="111",
        )
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            nombre_cliente="Cancelado",
            telefono_cliente="222",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=7000,
            estado=PedidoWhatsApp.ESTADO_CANCELADO,
            mensaje_whatsapp_generado="Cancelado",
            whatsapp_destino="222",
        )
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=3,
            nombre_cliente="Entregado",
            telefono_cliente="333",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=10000,
            estado=PedidoWhatsApp.ESTADO_ENTREGADO,
            mensaje_whatsapp_generado="Entregado",
            whatsapp_destino="333",
        )
        PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Especial completado",
            telefono_cliente="444",
            email_cliente="especial@test.com",
            descripcion_original="Especial",
            items=[],
            total=20000,
            fecha_entrega=hoy,
            estado="completado",
        )

        self.client.force_authenticate(user=self.dueno)
        response = self.client.get("/api/mi-restaurante/metricas/resumen/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ventas"]["venta_real_mes"], 30000)
        self.assertEqual(response.data["pedidos"]["pedidos_creados_mes"], 4)
        self.assertEqual(response.data["pedidos"]["pedidos_finalizados_mes"], 2)
        self.assertEqual(response.data["pedidos"]["pedidos_cancelados_mes"], 1)

    def test_reportes_mensual_y_anual_incluyen_whatsapp_y_especiales_finalizados(self):
        plan, _ = Plan.objects.get_or_create(
            slug="pro",
            defaults={"nombre": "Pro"},
        )
        self.restaurante.plan = plan
        self.restaurante.save(update_fields=["plan"])
        hoy = timezone.localtime(timezone.now()).date()
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="WSP",
            telefono_cliente="111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[{
                "producto_id": self.producto.id,
                "nombre": self.producto.nombre,
                "cantidad": 2,
                "precio_unitario": 5000,
                "subtotal": 10000,
            }],
            total=10000,
            estado=PedidoWhatsApp.ESTADO_ENTREGADO,
            mensaje_whatsapp_generado="WSP",
            whatsapp_destino="111",
        )
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            nombre_cliente="WSP Pendiente",
            telefono_cliente="333",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[{
                "nombre": "Producto pendiente",
                "cantidad": 99,
                "precio_unitario": 100,
                "subtotal": 9900,
            }],
            total=9900,
            estado=PedidoWhatsApp.ESTADO_PENDIENTE,
            mensaje_whatsapp_generado="WSP pendiente",
            whatsapp_destino="333",
        )
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=3,
            nombre_cliente="WSP Cancelado",
            telefono_cliente="444",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[{
                "nombre": "Producto cancelado",
                "cantidad": 88,
                "precio_unitario": 100,
                "subtotal": 8800,
            }],
            total=8800,
            estado=PedidoWhatsApp.ESTADO_CANCELADO,
            mensaje_whatsapp_generado="WSP cancelado",
            whatsapp_destino="444",
        )
        PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Especial",
            telefono_cliente="222",
            email_cliente="especial@test.com",
            descripcion_original="Especial",
            items=[],
            total=20000,
            fecha_entrega=hoy,
            estado=PedidoEspecial.ESTADO_ENTREGADO,
        )
        PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            nombre_cliente="Especial completado",
            telefono_cliente="555",
            email_cliente="especial-completado@test.com",
            descripcion_original="Especial completado",
            items=[{
                "nombre": "Torta completada",
                "descripcion": "",
                "cantidad": 1,
                "precio_unitario": 5000,
                "subtotal": 5000,
            }],
            total=5000,
            fecha_entrega=hoy,
            estado="completado",
        )

        self.client.force_authenticate(user=self.dueno)
        mensual = self.client.get("/api/metricas/reporte-mensual/")
        anual = self.client.get("/api/metricas/reporte-anual/")

        self.assertEqual(mensual.status_code, status.HTTP_200_OK)
        self.assertEqual(anual.status_code, status.HTTP_200_OK)
        self.assertEqual(mensual.data["venta_total"], 35000)
        self.assertEqual(mensual.data["venta_whatsapp"], 10000)
        self.assertEqual(mensual.data["venta_especiales"], 25000)
        self.assertEqual(mensual.data["pedidos_creados"], 5)
        self.assertEqual(mensual.data["pedidos_finalizados"], 3)
        self.assertEqual(mensual.data["pedidos_cancelados"], 1)
        self.assertEqual(mensual.data["pedidos_creados_whatsapp"], 3)
        self.assertEqual(mensual.data["pedidos_creados_especiales"], 2)
        self.assertEqual(mensual.data["pedidos_finalizados_whatsapp"], 1)
        self.assertEqual(mensual.data["pedidos_finalizados_especiales"], 2)
        self.assertEqual(mensual.data["pedidos_cancelados_whatsapp"], 1)
        self.assertEqual(mensual.data["pedidos_cancelados_especiales"], 0)
        self.assertEqual(mensual.data["desglose_por_canal"]["whatsapp"]["venta_real"], 10000)
        self.assertEqual(mensual.data["desglose_por_canal"]["especiales"]["venta_real"], 25000)
        self.assertIn("venta_total", mensual.data)
        self.assertIn("pedidos_total", mensual.data)
        self.assertIn("pedidos_cancelados", mensual.data)
        self.assertIn("producto_mas_vendido", mensual.data)
        self.assertIn("producto_menos_vendido", mensual.data)
        self.assertIn("productos_vendidos", mensual.data)
        self.assertIn("productos_por_canal", mensual.data)
        self.assertIn("resumen_canales", mensual.data)
        nombres_vendidos = [producto["nombre"] for producto in mensual.data["productos_vendidos"]]
        self.assertIn(self.producto.nombre, nombres_vendidos)
        self.assertIn("Torta completada", nombres_vendidos)
        self.assertNotIn("Producto pendiente", nombres_vendidos)
        self.assertNotIn("Producto cancelado", nombres_vendidos)

        self.assertEqual(anual.data["venta_total_anual"], 35000)
        self.assertEqual(anual.data["venta_whatsapp"], 10000)
        self.assertEqual(anual.data["venta_especiales"], 25000)
        self.assertEqual(anual.data["pedidos_creados"], 5)
        self.assertEqual(anual.data["pedidos_finalizados"], 3)
        self.assertEqual(anual.data["pedidos_cancelados"], 1)
        self.assertEqual(anual.data["desglose_por_canal"]["whatsapp"]["venta_real"], 10000)
        self.assertEqual(anual.data["desglose_por_canal"]["especiales"]["venta_real"], 25000)
        self.assertIn("venta_total_anual", anual.data)
        self.assertIn("pedidos_total_anual", anual.data)
        self.assertIn("ventas_por_mes", anual.data)
        self.assertIn("productos_vendidos", anual.data)
        self.assertIn("productos_por_canal", anual.data)
        self.assertIn("resumen_canales", anual.data)

    def test_productos_vendidos_salen_solo_de_pedidos_finalizados(self):
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Entregado",
            telefono_cliente="111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[{
                "producto_id": self.producto.id,
                "nombre": self.producto.nombre,
                "cantidad": 2,
                "precio_unitario": 1500,
                "subtotal": 3000,
            }],
            total=3000,
            estado=PedidoWhatsApp.ESTADO_ENTREGADO,
            mensaje_whatsapp_generado="Entregado",
            whatsapp_destino="111",
        )
        PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            nombre_cliente="Pendiente",
            telefono_cliente="222",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[{
                "nombre": "Producto pendiente",
                "cantidad": 99,
                "precio_unitario": 100,
                "subtotal": 9900,
            }],
            total=9900,
            estado=PedidoWhatsApp.ESTADO_PENDIENTE,
            mensaje_whatsapp_generado="Pendiente",
            whatsapp_destino="222",
        )

        self.client.force_authenticate(user=self.dueno)
        response = self.client.get("/api/mi-restaurante/metricas/resumen/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        top = response.data["productos"]["top_por_cantidad"]
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0]["producto_id"], self.producto.id)
        self.assertEqual(top[0]["cantidad"], 2)

    def test_reservas_creadas_y_programadas_se_calculan_distinto(self):
        hoy = timezone.localtime(timezone.now()).date()
        proximo_mes = (hoy.replace(day=28) + timedelta(days=8)).replace(day=5)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Creada este mes programada futuro",
            telefono="111",
            email="cliente@test.com",
            fecha=proximo_mes,
            hora=time(20, 0),
            cantidad_personas=2,
            estado="pendiente",
        )
        reserva_programada_mes = Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Programada este mes creada antes",
            telefono="222",
            email="cliente2@test.com",
            fecha=hoy,
            hora=time(21, 0),
            cantidad_personas=2,
            estado="pendiente",
        )
        mes_anterior = hoy.replace(day=1) - timedelta(days=1)
        Reserva.objects.filter(id=reserva_programada_mes.id).update(
            fecha_creacion=timezone.make_aware(datetime.combine(mes_anterior, time(12, 0)))
        )

        self.client.force_authenticate(user=self.dueno)
        response = self.client.get("/api/mi-restaurante/metricas/resumen/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["reservas"]["reservas_creadas_mes"], 1)
        self.assertEqual(response.data["reservas"]["reservas_programadas_mes"], 1)

    def test_reserva_publica_rechaza_modulo_reservas_inactivo(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.restaurante.reservas_activas = False
        self.restaurante.save(update_fields=["reservas_activas"])

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data["error"],
            "Las reservas no están disponibles para este restaurante."
        )

    def test_login_usuario_sin_perfil_falla(self):
        User.objects.create_user(
            username="sinperfil@test.com",
            email="sinperfil@test.com",
            password="123456"
        )

        response = self.client.post(
            "/api/login/",
            {
                "email": "sinperfil@test.com",
                "password": "123456",
            },
            format="json"
        )

        self.assertNotEqual(response.status_code, status.HTTP_200_OK)

    def test_reserva_publica_tiene_throttle_configurado(self):
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})

        self.assertIn("public_reservas", rates)
        self.assertEqual(rates["public_reservas"], "20/hour")
        self.assertIn(PublicReservaRateThrottle, CrearReservaPublicaView.throttle_classes)

    def test_no_permite_duplicar_reserva_publica_por_email_misma_fecha(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="111111111",
            email="cliente@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(
                fecha_reserva,
                telefono="222222222",
                hora="15:00",
            ),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"],
            "Ya existe una reserva registrada para este cliente en esa fecha."
        )

    def test_no_permite_duplicar_reserva_publica_por_telefono_misma_fecha(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="999999999",
            email="otro@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="confirmada",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(
                fecha_reserva,
                email="cliente-nuevo@test.com",
                hora="16:00",
            ),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"],
            "Ya existe una reserva registrada para este cliente en esa fecha."
        )

    def test_permite_mismo_email_en_otra_fecha(self):
        fecha_reserva = date.today() + timedelta(days=2)
        nueva_fecha = fecha_reserva + timedelta(days=1)
        self.crear_horario_para_reserva(self.restaurante, nueva_fecha)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="111111111",
            email="cliente@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(nueva_fecha, telefono="222222222"),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_permite_mismo_telefono_en_otra_fecha(self):
        fecha_reserva = date.today() + timedelta(days=2)
        nueva_fecha = fecha_reserva + timedelta(days=1)
        self.crear_horario_para_reserva(self.restaurante, nueva_fecha)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="999999999",
            email="otro@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="confirmada",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(nueva_fecha, email="cliente-nuevo@test.com"),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_permite_reserva_publica_si_anterior_esta_cancelada(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="999999999",
            email="cliente@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="cancelada",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_permite_reserva_publica_si_anterior_esta_rechazada(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="999999999",
            email="cliente@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="rechazada",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_duplicado_publico_no_se_mezcla_entre_restaurantes(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)
        Reserva.objects.create(
            restaurante=self.otro_restaurante,
            nombre_cliente="Cliente Otro Restaurante",
            telefono="999999999",
            email="cliente@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_reserva_publica_rechaza_dia_cerrado(self):
        fecha_reserva = date.today() + timedelta(days=2)
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=fecha_reserva.isoweekday(),
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=True,
            activo=True,
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reserva_publica_rechaza_antes_de_apertura(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva, hora="09:59"),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reserva_publica_rechaza_despues_de_cierre(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva, hora="22:01"),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reserva_publica_permite_dentro_del_horario(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva, hora="12:00"),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch("menu.utils.send_mail")
    def test_reserva_publica_envia_notificacion_si_esta_configurado(self, send_mail_mock):
        fecha_reserva = date.today() + timedelta(days=2)
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=fecha_reserva.isoweekday(),
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )
        self.restaurante.notificar_reservas = True
        self.restaurante.email_notificacion = " reservas@test.com "
        self.restaurante.save(update_fields=["notificar_reservas", "email_notificacion"])

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            {
                "nombre_cliente": "Cliente Correo",
                "telefono": "999999999",
                "email": "cliente@test.com",
                "fecha": fecha_reserva.isoformat(),
                "hora": "12:00",
                "cantidad_personas": 2,
                "mensaje": "Mesa tranquila",
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        send_mail_mock.assert_called_once()
        kwargs = send_mail_mock.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], ["reservas@test.com"])
        self.assertIn(fecha_reserva.strftime("%d-%m-%Y"), kwargs["message"])
        self.assertIn("Hora: 12:00", kwargs["message"])

    @patch("menu.utils.send_mail", side_effect=Exception("SMTP caido"))
    def test_fallo_email_no_bloquea_reserva_publica(self, send_mail_mock):
        fecha_reserva = date.today() + timedelta(days=2)
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=fecha_reserva.isoweekday(),
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )
        self.restaurante.notificar_reservas = True
        self.restaurante.email_notificacion = "reservas@test.com"
        self.restaurante.save(update_fields=["notificar_reservas", "email_notificacion"])

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            {
                "nombre_cliente": "Cliente Sin Bloqueo",
                "telefono": "999999999",
                "email": "cliente@test.com",
                "fecha": fecha_reserva.isoformat(),
                "hora": "12:00",
                "cantidad_personas": 2,
                "mensaje": "",
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        send_mail_mock.assert_called_once()

    @patch("menu.utils.send_mail")
    def test_no_envia_email_si_notificaciones_desactivadas(self, send_mail_mock):
        fecha_reserva = date.today() + timedelta(days=2)
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=fecha_reserva.isoweekday(),
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )
        self.restaurante.notificar_reservas = False
        self.restaurante.email_notificacion = "reservas@test.com"
        self.restaurante.save(update_fields=["notificar_reservas", "email_notificacion"])

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            {
                "nombre_cliente": "Cliente No Email",
                "telefono": "999999999",
                "fecha": fecha_reserva.isoformat(),
                "hora": "12:00",
                "cantidad_personas": 2,
                "mensaje": "",
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        send_mail_mock.assert_not_called()

    def test_estado_invalido_de_reserva_devuelve_400(self):
        self.client.force_authenticate(user=self.dueno)

        reserva = Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Test",
            telefono="999999999",
            fecha=date.today() + timedelta(days=2),
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )

        response = self.client.patch(
            f"/api/mi-restaurante/reservas/{reserva.id}/",
            {"estado": "estado_invalido"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_puede_asignar_mesa_de_otro_restaurante(self):
        self.client.force_authenticate(user=self.dueno)

        Mesa.objects.create(
            restaurante=self.otro_restaurante,
            numero=99,
            nombre="Mesa externa",
            activa=True,
        )
        reserva = Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Test",
            telefono="999999999",
            fecha=date.today() + timedelta(days=2),
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )

        response = self.client.patch(
            f"/api/mi-restaurante/reservas/{reserva.id}/",
            {"mesa_asignada": "99"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
class HorariosNocturnosTests(BaseTestCase):
    def crear_horario(self, dia, apertura, cierre):
        return HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=dia,
            hora_apertura=apertura,
            hora_cierre=cierre,
            cerrado=False,
            activo=True,
        )

    def momento(self, anio, mes, dia, hora, minuto=0):
        return timezone.make_aware(datetime(anio, mes, dia, hora, minuto))

    def test_api_acepta_cierre_al_dia_siguiente_y_lo_muestra_sin_anotaciones(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/horarios/",
            {
                "dia": 1,
                "hora_apertura": "18:00",
                "hora_cierre": "01:00",
                "cerrado": False,
                "activo": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["hora_apertura"], "18:00:00")
        self.assertEqual(response.data["hora_cierre"], "01:00:00")

    def test_api_rechaza_apertura_y_cierre_iguales(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/horarios/",
            {
                "dia": 1,
                "hora_apertura": "18:00",
                "hora_cierre": "18:00",
                "cerrado": False,
                "activo": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("distinta", response.data["hora_cierre"][0])

    def test_estado_abierto_cubre_ambos_tramos_del_horario_nocturno(self):
        self.crear_horario(1, time(18, 0), time(1, 0))

        casos = [
            (self.momento(2026, 7, 13, 17, 0), False),
            (self.momento(2026, 7, 13, 19, 0), True),
            (self.momento(2026, 7, 13, 23, 30), True),
            (self.momento(2026, 7, 14, 0, 45), True),
            (self.momento(2026, 7, 14, 1, 10), False),
        ]

        for momento, esperado in casos:
            with self.subTest(momento=momento):
                self.assertEqual(
                    calcular_estado_abierto(self.restaurante, ahora=momento),
                    esperado,
                )

    def test_estado_abierto_tradicional_mantiene_comportamiento(self):
        self.crear_horario(1, time(9, 0), time(18, 0))

        self.assertTrue(
            calcular_estado_abierto(
                self.restaurante,
                ahora=self.momento(2026, 7, 13, 12, 0),
            )
        )
        self.assertFalse(
            calcular_estado_abierto(
                self.restaurante,
                ahora=self.momento(2026, 7, 13, 18, 1),
            )
        )

    def test_madrugada_del_lunes_consulta_horario_del_domingo(self):
        self.crear_horario(7, time(20, 0), time(2, 0))

        self.assertTrue(
            calcular_estado_abierto(
                self.restaurante,
                ahora=self.momento(2026, 7, 13, 1, 30),
            )
        )

    def test_reserva_de_madrugada_pertenece_al_horario_anterior(self):
        fecha_lunes = date(2026, 7, 13)
        fecha_martes = date(2026, 7, 14)
        self.crear_horario(fecha_lunes.isoweekday(), time(18, 0), time(1, 0))

        self.assertTrue(
            validar_horario_reserva(
                self.restaurante,
                fecha_martes,
                time(0, 45),
            )
        )
        self.assertFalse(
            validar_horario_reserva(
                self.restaurante,
                fecha_martes,
                time(1, 10),
            )
        )


class EstadoAperturaExcepcionalTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.dueno)
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=timezone.localtime().isoweekday(),
            cerrado=True,
            activo=True,
        )

    def test_dashboard_y_landing_comparten_apertura_excepcional_persistida(self):
        dashboard_cerrado = self.client.get("/api/mi-restaurante/")
        publico_cerrado = self.client.get(f"/api/restaurantes/{self.restaurante.slug}/")

        self.assertFalse(dashboard_cerrado.data["restaurante"]["abierto_ahora"])
        self.assertFalse(publico_cerrado.data["abierto_ahora"])
        self.assertEqual(
            dashboard_cerrado.data["restaurante"]["motivo_estado"],
            "fuera_de_horario",
        )

        sin_confirmar = self.client.patch(
            "/api/mi-restaurante/estado-apertura/",
            {"abierto": True},
            format="json",
        )
        self.assertEqual(sin_confirmar.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(sin_confirmar.data["requiere_confirmacion"])

        confirmar = self.client.patch(
            "/api/mi-restaurante/estado-apertura/",
            {"abierto": True, "forzar_fuera_de_horario": True},
            format="json",
        )
        self.assertEqual(confirmar.status_code, status.HTTP_200_OK)
        self.assertTrue(confirmar.data["abierto_ahora"])
        self.assertEqual(confirmar.data["motivo_estado"], "apertura_excepcional")
        self.assertTrue(confirmar.data["apertura_excepcional_activa"])

        self.restaurante.refresh_from_db()
        self.assertIsNotNone(self.restaurante.apertura_excepcional_hasta)
        self.assertTrue(calcular_estado_abierto(self.restaurante))
        self.assertTrue(
            self.client.get("/api/mi-restaurante/").data["restaurante"]["abierto_ahora"]
        )
        self.assertTrue(
            self.client.get(f"/api/restaurantes/{self.restaurante.slug}/").data["abierto_ahora"]
        )

    def test_cierre_manual_desactiva_excepcion_y_tiene_prioridad(self):
        self.restaurante.apertura_excepcional_hasta = timezone.now() + timedelta(hours=2)
        self.restaurante.save(update_fields=["apertura_excepcional_hasta"])

        response = self.client.patch(
            "/api/mi-restaurante/estado-apertura/",
            {"abierto": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["abierto_ahora"])
        self.assertEqual(response.data["motivo_estado"], "cierre_manual")
        self.restaurante.refresh_from_db()
        self.assertIsNone(self.restaurante.apertura_excepcional_hasta)

    def test_excepcion_vencida_se_ignora(self):
        self.restaurante.apertura_excepcional_hasta = timezone.now() - timedelta(minutes=1)
        self.restaurante.save(update_fields=["apertura_excepcional_hasta"])

        estado = calcular_estado_restaurante(self.restaurante)

        self.assertFalse(estado["abierto_ahora"])
        self.assertFalse(estado["apertura_excepcional_activa"])
        self.assertEqual(estado["motivo"], "fuera_de_horario")

    def test_reapertura_dentro_de_horario_no_crea_excepcion(self):
        self.restaurante.horarios.all().delete()
        self.restaurante.abierto = False
        self.restaurante.save(update_fields=["abierto"])

        response = self.client.patch(
            "/api/mi-restaurante/estado-apertura/",
            {"abierto": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["abierto_ahora"])
        self.assertEqual(response.data["motivo_estado"], "dentro_de_horario")
        self.restaurante.refresh_from_db()
        self.assertIsNone(self.restaurante.apertura_excepcional_hasta)

    def test_usuario_sin_permiso_no_puede_forzar_apertura(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            "/api/mi-restaurante/estado-apertura/",
            {"abierto": True, "forzar_fuera_de_horario": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.restaurante.refresh_from_db()
        self.assertIsNone(self.restaurante.apertura_excepcional_hasta)


class PedidosPublicosEstadoRestauranteTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.send_mail_patcher = patch("menu.utils.send_mail")
        self.send_mail_mock = self.send_mail_patcher.start()
        self.addCleanup(self.send_mail_patcher.stop)
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.whatsapp = "56999999999"
        self.restaurante.save(update_fields=["carrito_whatsapp_activo", "whatsapp"])

    def payload(self):
        return {
            "nombre_cliente": "Cliente Público",
            "telefono_cliente": "912345678",
            "tipo_entrega": PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            "productos": [{"producto_id": self.producto.id, "cantidad": 1}],
        }

    def crear_pedido_publico(self):
        return self.client.post(
            f"/api/pedidos-whatsapp/{self.restaurante.slug}/",
            self.payload(),
            format="json",
        )

    def crear_horario_cerrado_hoy(self):
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=timezone.localtime().isoweekday(),
            cerrado=True,
            activo=True,
        )

    def assert_bloqueo_sin_efectos(self, response, status_esperado=status.HTTP_409_CONFLICT):
        self.assertEqual(response.status_code, status_esperado)
        self.assertEqual(PedidoWhatsApp.objects.count(), 1)
        self.assertEqual(
            PedidoWhatsApp.objects.filter(restaurante=self.restaurante).latest("id").numero_pedido,
            7,
        )
        self.assertEqual(Notificacion.objects.count(), 0)
        self.assertEqual(
            obtener_comandas_activas(self.restaurante),
            self.comandas_antes,
        )
        self.send_mail_mock.assert_not_called()

    def crear_pedido_base(self):
        self.pedido_base = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=7,
            nombre_cliente="Pedido previo",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=1000,
            mensaje_whatsapp_generado="Pedido previo",
            whatsapp_destino="56999999999",
        )
        self.comandas_antes = obtener_comandas_activas(self.restaurante)
        return self.pedido_base

    def test_crea_pedido_abierto_por_horario(self):
        ahora = timezone.localtime()
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=ahora.isoweekday(),
            hora_apertura=time(0, 0),
            hora_cierre=time(23, 59),
            cerrado=False,
            activo=True,
        )

        response = self.crear_pedido_publico()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PedidoWhatsApp.objects.count(), 1)

    def test_crea_pedido_tras_reapertura_manual_dentro_de_horario(self):
        self.restaurante.abierto = False
        self.restaurante.save(update_fields=["abierto"])
        self.client.force_authenticate(user=self.dueno)
        reapertura = self.client.patch(
            "/api/mi-restaurante/estado-apertura/",
            {"abierto": True},
            format="json",
        )
        self.client.force_authenticate(user=None)

        response = self.crear_pedido_publico()

        self.assertEqual(reapertura.status_code, status.HTTP_200_OK)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_crea_pedido_con_apertura_excepcional_fuera_de_horario(self):
        self.crear_horario_cerrado_hoy()
        self.restaurante.apertura_excepcional_hasta = timezone.now() + timedelta(hours=2)
        self.restaurante.save(update_fields=["apertura_excepcional_hasta"])

        response = self.crear_pedido_publico()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_bloquea_cierre_manual_sin_efectos_secundarios(self):
        pedido_base = self.crear_pedido_base()
        tokens_antes = set(PedidoWhatsApp.objects.values_list("tracking_token", flat=True))
        self.restaurante.abierto = False
        self.restaurante.save(update_fields=["abierto"])

        response = self.crear_pedido_publico()

        self.assert_bloqueo_sin_efectos(response)
        self.assertEqual(response.data, {
            "error": "restaurante_cerrado",
            "message": "Este restaurante no está aceptando pedidos en este momento.",
            "abierto": False,
        })
        self.assertEqual(
            set(PedidoWhatsApp.objects.values_list("tracking_token", flat=True)),
            tokens_antes,
        )
        self.assertTrue(PedidoWhatsApp.objects.filter(id=pedido_base.id).exists())

    def test_bloquea_fuera_de_horario_sin_excepcion(self):
        self.crear_pedido_base()
        self.crear_horario_cerrado_hoy()

        response = self.crear_pedido_publico()

        self.assert_bloqueo_sin_efectos(response)

    def test_bloquea_carrito_deshabilitado(self):
        self.crear_pedido_base()
        self.restaurante.carrito_whatsapp_activo = False
        self.restaurante.save(update_fields=["carrito_whatsapp_activo"])

        response = self.crear_pedido_publico()

        self.assert_bloqueo_sin_efectos(response, status.HTTP_400_BAD_REQUEST)

    def test_bloquea_restaurante_inactivo(self):
        self.crear_pedido_base()
        self.restaurante.activo = False
        self.restaurante.save(update_fields=["activo"])

        response = self.crear_pedido_publico()

        self.assert_bloqueo_sin_efectos(response, status.HTTP_403_FORBIDDEN)


class PedidosPublicosIdempotenciaTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.whatsapp = "56999999999"
        self.restaurante.save(update_fields=["carrito_whatsapp_activo", "whatsapp"])
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=timezone.localtime().isoweekday(),
            hora_apertura=time(0, 0),
            hora_cierre=time(23, 59),
            cerrado=False,
            activo=True,
        )
        self.send_mail_patcher = patch("menu.utils.send_mail")
        self.send_mail_mock = self.send_mail_patcher.start()
        self.addCleanup(self.send_mail_patcher.stop)

    def payload(self, **cambios):
        payload = {
            "nombre_cliente": "Cliente Idempotente",
            "telefono_cliente": "912345678",
            "tipo_entrega": PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            "direccion_entrega": "",
            "metodo_pago_id": None,
            "productos": [{"producto_id": self.producto.id, "cantidad": 1}],
        }
        payload.update(cambios)
        return payload

    def post(self, clave, payload=None, slug=None):
        return self.client.post(
            f"/api/pedidos-whatsapp/{slug or self.restaurante.slug}/",
            payload or self.payload(),
            format="json",
            HTTP_IDEMPOTENCY_KEY=clave,
        )

    def test_misma_clave_y_payload_reproduce_el_pedido_sin_duplicar(self):
        clave = "550e8400-e29b-41d4-a716-446655440000"

        primera = self.post(clave)
        segunda = self.post(clave)

        self.assertEqual(primera.status_code, status.HTTP_201_CREATED)
        self.assertEqual(segunda.status_code, status.HTTP_200_OK)
        for campo in ["pedido_id", "numero_pedido", "tracking_token", "tracking_url", "total", "whatsapp_url"]:
            self.assertEqual(segunda.data[campo], primera.data[campo])
        self.assertTrue(segunda.data["idempotent_replay"])
        self.assertEqual(PedidoWhatsApp.objects.count(), 1)
        self.assertEqual(PedidoWhatsApp.objects.get().numero_pedido, 1)
        self.assertEqual(
            RestaurantePedidoSecuencia.objects.get(restaurante=self.restaurante).ultimo_numero,
            1,
        )
        self.assertEqual(PedidoIdempotencia.objects.count(), 1)
        idempotencia = PedidoIdempotencia.objects.get()
        self.assertEqual(idempotencia.estado, PedidoIdempotencia.ESTADO_COMPLETADO)
        self.assertEqual(idempotencia.status_code, status.HTTP_201_CREATED)
        self.assertEqual(idempotencia.pedido_whatsapp_id, primera.data["pedido_id"])
        self.assertEqual(Notificacion.objects.count(), 1)
        self.assertEqual(obtener_comandas_activas(self.restaurante), [])
        self.send_mail_mock.assert_not_called()

    def test_replay_completado_no_depende_del_estado_posterior_del_restaurante(self):
        clave = "550e8400-e29b-41d4-a716-446655440005"
        primera = self.post(clave)
        self.restaurante.activo = False
        self.restaurante.abierto = False
        self.restaurante.save(update_fields=["activo", "abierto"])

        replay = self.post(clave)

        self.assertEqual(primera.status_code, status.HTTP_201_CREATED)
        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        self.assertEqual(replay.data["pedido_id"], primera.data["pedido_id"])
        self.assertEqual(PedidoWhatsApp.objects.count(), 1)
        self.assertEqual(Notificacion.objects.count(), 1)

    def test_misma_clave_con_payload_distinto_devuelve_conflicto(self):
        clave = "550e8400-e29b-41d4-a716-446655440001"
        primera = self.post(clave)
        tokens_antes = set(PedidoWhatsApp.objects.values_list("tracking_token", flat=True))

        conflicto = self.post(clave, self.payload(nombre_cliente="Otro cliente"))

        self.assertEqual(primera.status_code, status.HTTP_201_CREATED)
        self.assertEqual(conflicto.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(conflicto.data, {
            "error": "idempotency_key_reused",
            "message": "La clave de idempotencia ya fue utilizada con un pedido diferente.",
        })
        self.assertEqual(PedidoWhatsApp.objects.count(), 1)
        self.assertEqual(PedidoWhatsApp.objects.get().numero_pedido, 1)
        self.assertEqual(
            set(PedidoWhatsApp.objects.values_list("tracking_token", flat=True)),
            tokens_antes,
        )
        self.assertEqual(Notificacion.objects.count(), 1)
        self.assertEqual(obtener_comandas_activas(self.restaurante), [])
        self.send_mail_mock.assert_not_called()

    def test_hash_normaliza_espacios_y_enteros_equivalentes(self):
        clave = "550e8400-e29b-41d4-a716-446655440002"
        primera = self.post(clave)
        equivalente = self.payload(
            nombre_cliente="  Cliente Idempotente  ",
            productos=[{"producto_id": str(self.producto.id), "cantidad": "1"}],
        )

        segunda = self.post(clave, equivalente)

        self.assertEqual(primera.status_code, status.HTTP_201_CREATED)
        self.assertEqual(segunda.status_code, status.HTTP_200_OK)
        self.assertEqual(PedidoWhatsApp.objects.count(), 1)

    def test_payload_invalido_no_reserva_la_clave(self):
        clave = "550e8400-e29b-41d4-a716-446655440003"

        invalida = self.post(clave, self.payload(productos=[]))
        valida = self.post(clave)

        self.assertEqual(invalida.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(valida.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PedidoWhatsApp.objects.count(), 1)
        self.assertEqual(PedidoIdempotencia.objects.count(), 1)

    def test_clave_se_aisla_por_restaurante(self):
        clave = "550e8400-e29b-41d4-a716-446655440004"
        self.otro_restaurante.carrito_whatsapp_activo = True
        self.otro_restaurante.whatsapp = "56888888888"
        self.otro_restaurante.save(update_fields=["carrito_whatsapp_activo", "whatsapp"])
        HorarioAtencion.objects.create(
            restaurante=self.otro_restaurante,
            dia=timezone.localtime().isoweekday(),
            hora_apertura=time(0, 0),
            hora_cierre=time(23, 59),
            cerrado=False,
            activo=True,
        )
        otro_producto = Producto.objects.create(
            restaurante=self.otro_restaurante,
            categoria=self.categoria_otro_restaurante,
            nombre="Producto ajeno",
            precio=2000,
            disponible=True,
        )

        primero = self.post(clave)
        segundo = self.post(
            clave,
            self.payload(productos=[{"producto_id": otro_producto.id, "cantidad": 1}]),
            slug=self.otro_restaurante.slug,
        )

        self.assertEqual(primero.status_code, status.HTTP_201_CREATED)
        self.assertEqual(segundo.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PedidoWhatsApp.objects.count(), 2)
        self.assertEqual(PedidoIdempotencia.objects.count(), 2)


class EstadosPedidosCentralizadosTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.restaurante.pedidos_pos = True
        self.restaurante.delivery_activo = True
        self.restaurante.save(update_fields=["pedidos_pos", "delivery_activo"])
        self.client.force_authenticate(user=self.dueno)

    def crear_whatsapp(self, estado=PedidoWhatsApp.ESTADO_RECIBIDO, delivery=False, restaurante=None):
        restaurante = restaurante or self.restaurante
        return PedidoWhatsApp.objects.create(
            restaurante=restaurante,
            numero_pedido=PedidoWhatsApp.objects.filter(restaurante=restaurante).count() + 1,
            nombre_cliente="Cliente",
            telefono_cliente="56911111111",
            tipo_entrega=(
                PedidoWhatsApp.TIPO_DELIVERY
                if delivery else PedidoWhatsApp.TIPO_RETIRO_LOCAL
            ),
            direccion_entrega="Calle 1" if delivery else None,
            productos_snapshot=[],
            total=1000,
            estado=estado,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )

    def crear_manual(
        self,
        estado=PedidoManual.ESTADO_PENDIENTE,
        restaurante=None,
        tipo_entrega=PedidoManual.TIPO_RETIRO,
    ):
        restaurante = restaurante or self.restaurante
        return PedidoManual.objects.create(
            restaurante=restaurante,
            numero_pedido=PedidoManual.objects.filter(restaurante=restaurante).count() + 1,
            tipo_entrega=tipo_entrega,
            direccion="Calle delivery 123" if tipo_entrega == PedidoManual.TIPO_DELIVERY else "",
            numero_mesa="8" if tipo_entrega == PedidoManual.TIPO_MESA else "",
            subtotal=1000,
            total=1000,
            estado=estado,
        )

    def crear_especial(self, estado=PedidoEspecial.ESTADO_PENDIENTE, restaurante=None):
        restaurante = restaurante or self.restaurante
        return PedidoEspecial.objects.create(
            restaurante=restaurante,
            numero_pedido=PedidoEspecial.objects.filter(restaurante=restaurante).count() + 1,
            nombre_cliente="Cliente especial",
            telefono_cliente="56911111111",
            items=[],
            total=1000,
            fecha_entrega=timezone.localdate(),
            estado=estado,
        )

    def endpoint(self, tipo, pedido):
        return f"/api/mi-restaurante/pedidos/{tipo}/{pedido.id}/estado/"

    def test_panel_aplica_flujo_completo_y_crea_historial_por_tipo(self):
        casos = [
            (
                "whatsapp",
                self.crear_whatsapp(),
                ["en_preparacion", "listo", "entregado"],
                HistorialEstadoPedidoWhatsApp,
            ),
            (
                "manuales",
                self.crear_manual(),
                ["preparando", "listo", "entregado"],
                HistorialEstadoPedidoManual,
            ),
            (
                "especiales",
                self.crear_especial(),
                ["en_preparacion", "listo", "entregado"],
                HistorialEstadoPedidoEspecial,
            ),
        ]

        for tipo_url, pedido, estados, historial_modelo in casos:
            with self.subTest(tipo=tipo_url):
                for estado in estados:
                    response = self.client.patch(
                        self.endpoint(tipo_url, pedido),
                        {"estado": estado},
                        format="json",
                    )
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                pedido.refresh_from_db()
                self.assertEqual(pedido.estado, "entregado")
                historiales = historial_modelo.objects.filter(pedido=pedido).order_by("fecha", "id")
                self.assertEqual(historiales.count(), 3)
                self.assertTrue(all(item.origen == "panel" for item in historiales))

    def test_delivery_whatsapp_pasa_de_listo_a_reparto_y_entregado(self):
        pedido = self.crear_whatsapp(estado=PedidoWhatsApp.ESTADO_LISTO, delivery=True)

        reparto = self.client.patch(
            self.endpoint("whatsapp", pedido),
            {"estado": "en_reparto"},
            format="json",
        )
        entregado = self.client.patch(
            self.endpoint("whatsapp", pedido),
            {"estado": "entregado"},
            format="json",
        )

        self.assertEqual(reparto.status_code, status.HTTP_200_OK)
        self.assertEqual(entregado.status_code, status.HTTP_200_OK)
        self.assertEqual(HistorialEstadoPedidoWhatsApp.objects.filter(pedido=pedido).count(), 2)

    def test_delivery_manual_pasa_de_listo_a_reparto_y_panel_lo_entrega(self):
        pedido = self.crear_manual(
            estado=PedidoManual.ESTADO_LISTO,
            tipo_entrega=PedidoManual.TIPO_DELIVERY,
        )

        reparto = self.client.patch(
            self.endpoint("manuales", pedido),
            {"estado": PedidoManual.ESTADO_EN_REPARTO},
            format="json",
        )
        self.assertEqual(reparto.status_code, status.HTTP_200_OK)
        self.assertEqual(reparto.data["pedido"]["estado_display"], "En reparto")
        self.assertEqual(
            reparto.data["pedido"]["transiciones_permitidas"],
            [PedidoManual.ESTADO_ENTREGADO],
        )

        entregado = self.client.patch(
            self.endpoint("manuales", pedido),
            {"estado": PedidoManual.ESTADO_ENTREGADO},
            format="json",
        )
        self.assertEqual(entregado.status_code, status.HTTP_200_OK)

        historiales = list(
            HistorialEstadoPedidoManual.objects.filter(pedido=pedido).order_by("fecha", "id")
        )
        self.assertEqual(len(historiales), 2)
        self.assertEqual(historiales[0].estado_anterior, PedidoManual.ESTADO_LISTO)
        self.assertEqual(historiales[0].estado_nuevo, PedidoManual.ESTADO_EN_REPARTO)
        self.assertEqual(historiales[1].estado_anterior, PedidoManual.ESTADO_EN_REPARTO)
        self.assertEqual(historiales[1].estado_nuevo, PedidoManual.ESTADO_ENTREGADO)
        self.assertTrue(all(item.origen == "panel" for item in historiales))

    def test_manual_no_delivery_rechaza_reparto_y_reparto_no_retrocede_ni_cancela(self):
        for tipo_entrega in [PedidoManual.TIPO_RETIRO, PedidoManual.TIPO_MESA]:
            with self.subTest(tipo_entrega=tipo_entrega):
                pedido = self.crear_manual(
                    estado=PedidoManual.ESTADO_LISTO,
                    tipo_entrega=tipo_entrega,
                )
                response = self.client.patch(
                    self.endpoint("manuales", pedido),
                    {"estado": PedidoManual.ESTADO_EN_REPARTO},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        for estado in [PedidoManual.ESTADO_LISTO, PedidoManual.ESTADO_PREPARANDO, PedidoManual.ESTADO_CANCELADO]:
            with self.subTest(estado=estado):
                pedido = self.crear_manual(
                    estado=PedidoManual.ESTADO_EN_REPARTO,
                    tipo_entrega=PedidoManual.TIPO_DELIVERY,
                )
                response = self.client.patch(
                    self.endpoint("manuales", pedido),
                    {"estado": estado},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_delivery_listo_no_puede_saltar_directamente_a_entregado(self):
        casos = [
            ("manuales", self.crear_manual(
                estado=PedidoManual.ESTADO_LISTO,
                tipo_entrega=PedidoManual.TIPO_DELIVERY,
            )),
            ("whatsapp", self.crear_whatsapp(
                estado=PedidoWhatsApp.ESTADO_LISTO,
                delivery=True,
            )),
        ]
        for tipo, pedido in casos:
            with self.subTest(tipo=tipo):
                response = self.client.patch(
                    self.endpoint(tipo, pedido),
                    {"estado": "entregado"},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_tracking_y_metricas_tratan_manual_en_reparto_como_activo(self):
        pedido = self.crear_manual(
            estado=PedidoManual.ESTADO_EN_REPARTO,
            tipo_entrega=PedidoManual.TIPO_DELIVERY,
        )

        tracking = self.client.get(f"/api/public/pedidos/seguimiento/{pedido.tracking_token}/")
        self.assertEqual(tracking.status_code, status.HTTP_200_OK)
        self.assertEqual(tracking.data["estado"], PedidoManual.ESTADO_EN_REPARTO)
        self.assertEqual(tracking.data["estado_display"], "En reparto")
        self.assertTrue(pedidos_manuales_activos(self.restaurante).filter(pk=pedido.pk).exists())
        self.assertFalse(pedidos_manuales_finalizados(self.restaurante).filter(pk=pedido.pk).exists())

    def test_reparto_se_rechaza_para_pedido_no_delivery(self):
        pedido = self.crear_whatsapp(estado=PedidoWhatsApp.ESTADO_LISTO)

        response = self.client.patch(
            self.endpoint("whatsapp", pedido),
            {"estado": "en_reparto"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"], "transicion_estado_invalida")
        self.assertEqual(HistorialEstadoPedidoWhatsApp.objects.filter(pedido=pedido).count(), 0)

    def test_transiciones_invalidas_y_terminales_se_rechazan_sin_historial(self):
        casos = [
            ("whatsapp", self.crear_whatsapp(), "listo", HistorialEstadoPedidoWhatsApp),
            ("manuales", self.crear_manual(), "entregado", HistorialEstadoPedidoManual),
            ("especiales", self.crear_especial(estado="entregado"), "cancelado", HistorialEstadoPedidoEspecial),
            ("whatsapp", self.crear_whatsapp(estado="cancelado"), "en_preparacion", HistorialEstadoPedidoWhatsApp),
        ]

        for tipo_url, pedido, solicitado, historial_modelo in casos:
            with self.subTest(tipo=tipo_url, solicitado=solicitado):
                response = self.client.patch(
                    self.endpoint(tipo_url, pedido),
                    {"estado": solicitado},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
                self.assertEqual(response.data["error"], "transicion_estado_invalida")
                self.assertEqual(historial_modelo.objects.filter(pedido=pedido).count(), 0)

    def test_cancelacion_desde_pendiente_preparacion_y_listo(self):
        fabricas = [
            (
                "whatsapp",
                self.crear_whatsapp,
                ["recibido", "en_preparacion", "listo"],
                HistorialEstadoPedidoWhatsApp,
            ),
            (
                "manuales",
                self.crear_manual,
                ["pendiente", "preparando", "listo"],
                HistorialEstadoPedidoManual,
            ),
            (
                "especiales",
                self.crear_especial,
                ["pendiente", "en_preparacion", "listo"],
                HistorialEstadoPedidoEspecial,
            ),
        ]

        for tipo_url, fabrica, estados, historial_modelo in fabricas:
            for estado_actual in estados:
                with self.subTest(tipo=tipo_url, estado=estado_actual):
                    pedido = fabrica(estado=estado_actual)
                    response = self.client.patch(
                        self.endpoint(tipo_url, pedido),
                        {"estado": "cancelado"},
                        format="json",
                    )
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    pedido.refresh_from_db()
                    self.assertEqual(pedido.estado, "cancelado")
                    historial = historial_modelo.objects.get(pedido=pedido)
                    self.assertEqual(historial.estado_anterior, estado_actual)
                    self.assertEqual(historial.estado_nuevo, "cancelado")

    def test_estado_inexistente_devuelve_400(self):
        pedido = self.crear_manual()

        response = self.client.patch(
            self.endpoint("manuales", pedido),
            {"estado": "teletransportado"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "estado_invalido")

    def test_estado_repetido_es_idempotente_y_no_crea_historial(self):
        pedido = self.crear_especial(estado="listo")

        response = self.client.patch(
            self.endpoint("especiales", pedido),
            {"estado": "listo"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["estado_sin_cambios"])
        self.assertEqual(HistorialEstadoPedidoEspecial.objects.filter(pedido=pedido).count(), 0)

    def test_patch_generico_no_puede_cambiar_estado(self):
        casos = [
            ("whatsapp", self.crear_whatsapp()),
            ("manuales", self.crear_manual()),
            ("especiales", self.crear_especial()),
        ]

        for tipo_url, pedido in casos:
            with self.subTest(tipo=tipo_url):
                response = self.client.patch(
                    f"/api/mi-restaurante/pedidos/{tipo_url}/{pedido.id}/",
                    {"estado": "listo"},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                pedido.refresh_from_db()
                self.assertNotEqual(pedido.estado, "listo")

    def test_panel_no_accede_a_pedido_de_otro_restaurante(self):
        pedidos = [
            ("whatsapp", self.crear_whatsapp(restaurante=self.otro_restaurante)),
            ("manuales", self.crear_manual(restaurante=self.otro_restaurante)),
            ("especiales", self.crear_especial(restaurante=self.otro_restaurante)),
        ]

        for tipo_url, pedido in pedidos:
            with self.subTest(tipo=tipo_url):
                response = self.client.patch(
                    self.endpoint(tipo_url, pedido),
                    {"estado": "en_preparacion"},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class EstadosPedidosConcurrenciaTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.restaurante = Restaurante.objects.create(
            nombre_empresa="Restaurante concurrencia",
            slug="restaurante-concurrencia",
            rut="33333333-3",
            telefono="56933333333",
            email_contacto="concurrencia@test.com",
            direccion="Calle 3",
            ciudad="Santiago",
            activo=True,
        )
        self.pedido = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            estado=PedidoManual.ESTADO_PREPARANDO,
            subtotal=1000,
            total=1000,
        )

    def test_dos_transiciones_concurrentes_releen_estado_bajo_lock(self):
        barrera = Barrier(2)

        def intentar(nuevo_estado):
            close_old_connections()
            pedido = PedidoManual.objects.get(pk=self.pedido.pk)
            barrera.wait(timeout=10)
            try:
                cambiar_estado_pedido(
                    pedido,
                    nuevo_estado,
                    tipo="manual",
                    origen="panel",
                )
                return "ok"
            except TransicionEstadoInvalida:
                return "conflicto"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(intentar, ["listo", "cancelado"]))

        self.pedido.refresh_from_db()
        historiales = list(
            HistorialEstadoPedidoManual.objects
            .filter(pedido=self.pedido)
            .order_by("fecha", "id")
        )
        self.assertIn("ok", resultados)
        self.assertEqual(
            sum(item.estado_anterior == PedidoManual.ESTADO_PREPARANDO for item in historiales),
            1,
        )
        for anterior, siguiente in zip(historiales, historiales[1:]):
            self.assertEqual(siguiente.estado_anterior, anterior.estado_nuevo)
        self.assertEqual(self.pedido.estado, PedidoManual.ESTADO_CANCELADO)


class MetodosPagoPedidosTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.whatsapp = "56999999999"
        self.restaurante.save(update_fields=["carrito_whatsapp_activo", "whatsapp"])

    def crear_metodo(self, restaurante, nombre, activo=True, orden=0):
        return MetodoPago.objects.create(
            restaurante=restaurante,
            nombre=nombre,
            activo=activo,
            orden=orden,
        )

    def payload_pedido(self, metodo_pago_id=None):
        payload = {
            "nombre_cliente": "Cliente Pago",
            "telefono_cliente": "912345678",
            "tipo_entrega": PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            "productos": [{"producto_id": self.producto.id, "cantidad": 1}],
        }
        if metodo_pago_id is not None:
            payload["metodo_pago_id"] = metodo_pago_id
        return payload

    def crear_pedido_publico(self, payload):
        return self.client.post(
            f"/api/pedidos-whatsapp/{self.restaurante.slug}/",
            payload,
            format="json",
        )

    def test_endpoint_publico_devuelve_solo_activos_en_orden(self):
        self.crear_metodo(self.restaurante, "Efectivo", activo=True, orden=2)
        transferencia = self.crear_metodo(
            self.restaurante, "Transferencia", activo=True, orden=1
        )
        self.crear_metodo(self.restaurante, "Cheque", activo=False, orden=0)

        response = self.client.get(
            f"/api/public/restaurantes/{self.restaurante.slug}/metodos-pago/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [metodo["nombre"] for metodo in response.data],
            ["Transferencia", "Efectivo"],
        )
        self.assertEqual(
            set(response.data[0]),
            {"id", "codigo", "nombre"},
        )
        self.assertEqual(response.data[0]["id"], transferencia.id)

    def test_endpoint_publico_no_mezcla_metodos_entre_restaurantes(self):
        self.crear_metodo(self.restaurante, "Efectivo")
        self.crear_metodo(self.otro_restaurante, "Tarjeta")

        response = self.client.get(
            f"/api/public/restaurantes/{self.restaurante.slug}/metodos-pago/"
        )

        self.assertEqual(
            [metodo["nombre"] for metodo in response.data],
            ["Efectivo"],
        )

    def test_pedido_guarda_referencia_nombre_historico_y_mensaje(self):
        metodo = self.crear_metodo(self.restaurante, "Transferencia")

        response = self.crear_pedido_publico(self.payload_pedido(metodo.id))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pedido = PedidoWhatsApp.objects.get(id=response.data["pedido_id"])
        self.assertEqual(pedido.metodo_pago_id, metodo.id)
        self.assertEqual(pedido.metodo_pago_nombre, "Transferencia")
        self.assertIn("💳 Método de pago: Transferencia", pedido.mensaje_whatsapp_generado)

        metodo.delete()
        pedido.refresh_from_db()
        self.assertIsNone(pedido.metodo_pago_id)
        self.assertEqual(pedido.metodo_pago_nombre, "Transferencia")

    def test_pedido_rechaza_metodo_de_otro_restaurante(self):
        metodo_ajeno = self.crear_metodo(self.otro_restaurante, "Tarjeta")

        response = self.crear_pedido_publico(self.payload_pedido(metodo_ajeno.id))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("metodo_pago_id", response.data)

    def test_pedido_rechaza_metodo_inactivo(self):
        inactivo = self.crear_metodo(self.restaurante, "Cheque", activo=False)

        response = self.crear_pedido_publico(self.payload_pedido(inactivo.id))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("metodo_pago_id", response.data)

    def test_pedido_exige_metodo_si_hay_opciones_activas(self):
        self.crear_metodo(self.restaurante, "Efectivo")

        response = self.crear_pedido_publico(self.payload_pedido())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("metodo_pago_id", response.data)

    def test_pedido_sin_metodos_configurados_mantiene_compatibilidad(self):
        response = self.crear_pedido_publico(self.payload_pedido())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pedido = PedidoWhatsApp.objects.get(id=response.data["pedido_id"])
        self.assertIsNone(pedido.metodo_pago_id)
        self.assertEqual(pedido.metodo_pago_nombre, "")

    def test_pedido_antiguo_sin_metodo_serializa_como_no_informado_en_ui(self):
        response = self.crear_pedido_publico(self.payload_pedido())
        pedido = PedidoWhatsApp.objects.get(id=response.data["pedido_id"])

        data = PedidoWhatsAppDashboardSerializer(pedido).data

        self.assertIsNone(data["metodo_pago"])
        self.assertEqual(data["metodo_pago_nombre"], "")

    def test_no_permite_desactivar_el_ultimo_metodo_activo(self):
        metodo = self.crear_metodo(self.restaurante, "Efectivo")
        self.client.force_authenticate(user=self.dueno)

        response = self.client.patch(
            f"/api/mi-restaurante/metodos-pago/{metodo.id}/",
            {"activo": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("al menos un metodo", response.data["error"])


class ProductoOpcionesBackendTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.dueno)
        self.grupos_url = (
            f"/api/mi-restaurante/productos/{self.producto.id}/grupos-opciones/"
        )

    def crear_grupo(self, **overrides):
        payload = {
            "nombre": "Proteina",
            "obligatorio": True,
            "minimo_selecciones": 1,
            "maximo_selecciones": 2,
            "orden": 1,
        }
        payload.update(overrides)
        return self.client.post(self.grupos_url, payload, format="json")

    def crear_opcion_api(self, grupo_id, nombre, disponible=True):
        return self.client.post(
            f"{self.grupos_url}{grupo_id}/opciones/",
            {
                "nombre": nombre,
                "precio_adicional": 0,
                "disponible": disponible,
                "orden": 0,
            },
            format="json",
        )

    def test_crud_grupos_y_opciones_con_validaciones(self):
        grupo_response = self.crear_grupo(
            obligatorio=False,
            minimo_selecciones=0,
        )
        self.assertEqual(grupo_response.status_code, status.HTTP_201_CREATED)
        grupo_id = grupo_response.data["id"]

        opciones_url = f"{self.grupos_url}{grupo_id}/opciones/"
        opcion_response = self.client.post(
            opciones_url,
            {
                "nombre": "Pollo",
                "precio_adicional": 1500,
                "disponible": True,
                "orden": 1,
            },
            format="json",
        )
        self.assertEqual(opcion_response.status_code, status.HTTP_201_CREATED)
        opcion_id = opcion_response.data["id"]

        negativa = self.client.post(
            opciones_url,
            {"nombre": "Invalida", "precio_adicional": -1},
            format="json",
        )
        self.assertEqual(negativa.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("precio_adicional", negativa.data)

        desactivar = self.client.patch(
            f"{opciones_url}{opcion_id}/",
            {"disponible": False},
            format="json",
        )
        self.assertEqual(desactivar.status_code, status.HTTP_200_OK)
        self.assertFalse(desactivar.data["disponible"])

        detalle_grupo = self.client.get(f"{self.grupos_url}{grupo_id}/")
        self.assertEqual(detalle_grupo.status_code, status.HTTP_200_OK)
        self.assertEqual(len(detalle_grupo.data["opciones"]), 1)

        eliminar_opcion = self.client.delete(f"{opciones_url}{opcion_id}/")
        self.assertEqual(eliminar_opcion.status_code, status.HTTP_204_NO_CONTENT)
        eliminar_grupo = self.client.delete(f"{self.grupos_url}{grupo_id}/")
        self.assertEqual(eliminar_grupo.status_code, status.HTTP_204_NO_CONTENT)

    def test_desactivar_opcion_permitido_si_quedan_suficientes_disponibles(self):
        grupo = self.crear_grupo(minimo_selecciones=2, maximo_selecciones=3)
        grupo_id = grupo.data["id"]
        opciones = [
            self.crear_opcion_api(grupo_id, nombre).data
            for nombre in ["Carne", "Pollo", "Camaron"]
        ]

        response = self.client.patch(
            f"{self.grupos_url}{grupo_id}/opciones/{opciones[-1]['id']}/",
            {"disponible": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["disponible"])

    def test_desactivar_opcion_rechazado_si_deja_grupo_inviable(self):
        grupo = self.crear_grupo(minimo_selecciones=2, maximo_selecciones=2)
        grupo_id = grupo.data["id"]
        self.crear_opcion_api(grupo_id, "Carne")
        pollo = self.crear_opcion_api(grupo_id, "Pollo").data

        response = self.client.patch(
            f"{self.grupos_url}{grupo_id}/opciones/{pollo['id']}/",
            {"disponible": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            str(response.data["detail"][0]),
            "No puedes desactivar esta opcion porque el grupo Proteina requiere "
            "al menos 2 opciones disponibles.",
        )
        self.assertTrue(OpcionProducto.objects.get(pk=pollo["id"]).disponible)

    def test_eliminar_opcion_rechazado_si_deja_grupo_inviable(self):
        grupo = self.crear_grupo(minimo_selecciones=2, maximo_selecciones=2)
        grupo_id = grupo.data["id"]
        self.crear_opcion_api(grupo_id, "Carne")
        pollo = self.crear_opcion_api(grupo_id, "Pollo").data

        response = self.client.delete(
            f"{self.grupos_url}{grupo_id}/opciones/{pollo['id']}/"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "requiere al menos 2 opciones disponibles",
            str(response.data["detail"]),
        )
        self.assertTrue(OpcionProducto.objects.filter(pk=pollo["id"]).exists())

    def test_reducir_minimo_permite_desactivar_opcion(self):
        grupo = self.crear_grupo(minimo_selecciones=2, maximo_selecciones=2)
        grupo_id = grupo.data["id"]
        self.crear_opcion_api(grupo_id, "Carne")
        pollo = self.crear_opcion_api(grupo_id, "Pollo").data

        reducir = self.client.patch(
            f"{self.grupos_url}{grupo_id}/",
            {"minimo_selecciones": 1},
            format="json",
        )
        desactivar = self.client.patch(
            f"{self.grupos_url}{grupo_id}/opciones/{pollo['id']}/",
            {"disponible": False},
            format="json",
        )

        self.assertEqual(reducir.status_code, status.HTTP_200_OK)
        self.assertEqual(desactivar.status_code, status.HTTP_200_OK)

    def test_grupo_opcional_sin_minimo_permite_desactivar_y_eliminar(self):
        grupo = self.crear_grupo(
            obligatorio=False,
            minimo_selecciones=0,
            maximo_selecciones=1,
        )
        grupo_id = grupo.data["id"]
        opcion = self.crear_opcion_api(grupo_id, "Sin cebolla").data
        opcion_url = f"{self.grupos_url}{grupo_id}/opciones/{opcion['id']}/"

        desactivar = self.client.patch(
            opcion_url,
            {"disponible": False},
            format="json",
        )
        eliminar = self.client.delete(opcion_url)

        self.assertEqual(desactivar.status_code, status.HTTP_200_OK)
        self.assertEqual(eliminar.status_code, status.HTTP_204_NO_CONTENT)

    def test_no_permite_aumentar_minimo_sobre_opciones_disponibles(self):
        grupo = self.crear_grupo(minimo_selecciones=1, maximo_selecciones=3)
        grupo_id = grupo.data["id"]
        self.crear_opcion_api(grupo_id, "Carne")

        response = self.client.patch(
            f"{self.grupos_url}{grupo_id}/",
            {"minimo_selecciones": 2},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "requiere al menos 2 opciones disponibles",
            str(response.data["detail"][0]),
        )

    def test_no_permite_hacer_obligatorio_un_grupo_vacio(self):
        grupo = self.crear_grupo(
            obligatorio=False,
            minimo_selecciones=0,
            maximo_selecciones=1,
        )

        response = self.client.patch(
            f"{self.grupos_url}{grupo.data['id']}/",
            {"obligatorio": True, "minimo_selecciones": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "requiere al menos 1 opcion disponible",
            str(response.data["detail"][0]),
        )

    def test_creacion_progresiva_de_grupo_y_opciones_sigue_permitida(self):
        grupo = self.crear_grupo(minimo_selecciones=2, maximo_selecciones=2)
        self.assertEqual(grupo.status_code, status.HTTP_201_CREATED)
        self.assertEqual(grupo.data["opciones"], [])

        primera = self.crear_opcion_api(grupo.data["id"], "Carne")
        segunda = self.crear_opcion_api(grupo.data["id"], "Pollo")

        self.assertEqual(primera.status_code, status.HTTP_201_CREATED)
        self.assertEqual(segunda.status_code, status.HTTP_201_CREATED)

    def test_valida_obligatorio_minimo_maximo_y_nombres_duplicados(self):
        obligatorio_sin_minimo = self.crear_grupo(minimo_selecciones=0)
        self.assertEqual(obligatorio_sin_minimo.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("minimo_selecciones", obligatorio_sin_minimo.data)

        maximo_menor = self.crear_grupo(
            nombre="Rellenos",
            minimo_selecciones=2,
            maximo_selecciones=1,
        )
        self.assertEqual(maximo_menor.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("maximo_selecciones", maximo_menor.data)

        creado = self.crear_grupo()
        self.assertEqual(creado.status_code, status.HTTP_201_CREATED)
        duplicado = self.crear_grupo(nombre="proteina")
        self.assertEqual(duplicado.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nombre", duplicado.data)

    def test_crud_aisla_restaurante_producto_grupo_y_opcion(self):
        grupo = GrupoOpcionesProducto.objects.create(
            producto=self.producto,
            nombre="Extras",
            obligatorio=False,
            minimo_selecciones=0,
            maximo_selecciones=None,
        )
        opcion = OpcionProducto.objects.create(
            grupo=grupo,
            nombre="Queso",
            precio_adicional=1000,
        )
        producto_otro = Producto.objects.create(
            restaurante=self.otro_restaurante,
            categoria=self.categoria_otro_restaurante,
            nombre="Producto externo",
            precio=5000,
            orden=1,
        )

        usuario_otro = User.objects.create_user(
            username="opciones-otro@test.com",
            password="test",
        )
        UsuarioRestaurante.objects.create(
            user=usuario_otro,
            restaurante=self.otro_restaurante,
            rol="dueno",
            activo=True,
        )
        self.client.force_authenticate(user=usuario_otro)

        grupo_ajeno = self.client.patch(
            f"{self.grupos_url}{grupo.id}/",
            {"nombre": "Alterado"},
            format="json",
        )
        self.assertEqual(grupo_ajeno.status_code, status.HTTP_404_NOT_FOUND)

        opcion_producto_incorrecto = self.client.patch(
            (
                f"/api/mi-restaurante/productos/{producto_otro.id}/grupos-opciones/"
                f"{grupo.id}/opciones/{opcion.id}/"
            ),
            {"precio_adicional": 1},
            format="json",
        )
        self.assertEqual(
            opcion_producto_incorrecto.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        opcion.refresh_from_db()
        self.assertEqual(int(opcion.precio_adicional), 1000)

    def test_menu_publico_filtra_opciones_no_disponibles_y_producto_antiguo_usa_lista_vacia(self):
        grupo = GrupoOpcionesProducto.objects.create(
            producto=self.producto,
            nombre="Extras",
            minimo_selecciones=0,
            maximo_selecciones=2,
        )
        OpcionProducto.objects.create(
            grupo=grupo,
            nombre="Queso",
            precio_adicional=1000,
            disponible=True,
        )
        OpcionProducto.objects.create(
            grupo=grupo,
            nombre="Agotada",
            precio_adicional=2000,
            disponible=False,
        )
        producto_antiguo = Producto.objects.create(
            restaurante=self.restaurante,
            categoria=self.categoria,
            nombre="Producto antiguo",
            precio=2000,
            orden=2,
        )

        response = self.client.get(f"/api/menu/{self.restaurante.slug}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        productos = response.json()["categorias"][0]["productos"]
        producto_json = next(item for item in productos if item["id"] == self.producto.id)
        antiguo_json = next(item for item in productos if item["id"] == producto_antiguo.id)

        self.assertEqual(len(producto_json["grupos_opciones"]), 1)
        self.assertEqual(
            [item["nombre"] for item in producto_json["grupos_opciones"][0]["opciones"]],
            ["Queso"],
        )
        self.assertEqual(antiguo_json["grupos_opciones"], [])

        privado = self.client.get("/api/mi-restaurante/")
        privado_producto = next(
            item for item in privado.data["productos"] if item["id"] == self.producto.id
        )
        self.assertEqual(len(privado_producto["grupos_opciones"][0]["opciones"]), 2)

    def test_cambios_de_grupos_y_opciones_invalidan_cache_menu(self):
        cache.set(menu_cache_key(self.restaurante.slug), {"cached": True}, 300)
        grupo = GrupoOpcionesProducto.objects.create(
            producto=self.producto,
            nombre="Salsas",
        )
        self.assertIsNone(cache.get(menu_cache_key(self.restaurante.slug)))

        cache.set(menu_cache_key(self.restaurante.slug), {"cached": True}, 300)
        opcion = OpcionProducto.objects.create(
            grupo=grupo,
            nombre="Mostaza",
            precio_adicional=0,
        )
        self.assertIsNone(cache.get(menu_cache_key(self.restaurante.slug)))

        cache.set(menu_cache_key(self.restaurante.slug), {"cached": True}, 300)
        opcion.disponible = False
        opcion.save(update_fields=["disponible"])
        self.assertIsNone(cache.get(menu_cache_key(self.restaurante.slug)))

        cache.set(menu_cache_key(self.restaurante.slug), {"cached": True}, 300)
        opcion.delete()
        self.assertIsNone(cache.get(menu_cache_key(self.restaurante.slug)))

    def test_pedido_manual_item_existente_usa_snapshot_vacio_por_defecto(self):
        pedido = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=999,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
        )
        item = PedidoManualItem.objects.create(
            pedido=pedido,
            producto=self.producto,
            nombre_producto=self.producto.nombre,
            precio_unitario=1500,
            cantidad=1,
            subtotal=1500,
        )
        self.assertEqual(item.opciones_snapshot, [])


class PersonalizacionPedidosBackendTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.whatsapp = "56999999999"
        self.restaurante.pedidos_pos = True
        self.restaurante.save(update_fields=[
            "carrito_whatsapp_activo",
            "whatsapp",
            "pedidos_pos",
        ])

    def crear_grupo(
        self,
        producto=None,
        nombre="Proteinas",
        obligatorio=True,
        minimo=1,
        maximo=2,
        orden=1,
    ):
        return GrupoOpcionesProducto.objects.create(
            producto=producto or self.producto,
            nombre=nombre,
            obligatorio=obligatorio,
            minimo_selecciones=minimo,
            maximo_selecciones=maximo,
            orden=orden,
        )

    def crear_opcion(
        self,
        grupo,
        nombre,
        precio=0,
        disponible=True,
        orden=0,
    ):
        return OpcionProducto.objects.create(
            grupo=grupo,
            nombre=nombre,
            precio_adicional=precio,
            disponible=disponible,
            orden=orden,
        )

    def linea(self, producto=None, opciones=None, variante=None, cantidad=1):
        return {
            "producto_id": (producto or self.producto).id,
            "variante_id": variante.id if variante else None,
            "cantidad": cantidad,
            "opciones": opciones or [],
        }

    def payload_whatsapp(self, lineas):
        return {
            "nombre_cliente": "Cliente",
            "telefono_cliente": "912345678",
            "tipo_entrega": PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            "productos": lineas,
        }

    def crear_pedido_whatsapp(self, lineas, headers=None):
        return self.client.post(
            f"/api/pedidos-whatsapp/{self.restaurante.slug}/",
            self.payload_whatsapp(lineas),
            format="json",
            **(headers or {}),
        )

    def test_producto_sin_opciones_mantiene_compatibilidad(self):
        snapshot, total = normalizar_productos_pedido(
            self.restaurante,
            [self.linea(cantidad=2)],
        )
        self.assertEqual(total, 3000)
        self.assertEqual(snapshot[0]["grupos_opciones"], [])
        self.assertEqual(snapshot[0]["precio_base"], 1500)
        self.assertEqual(snapshot[0]["opciones_total"], 0)

    def test_grupo_obligatorio_rechaza_falta_de_seleccion(self):
        self.crear_grupo()
        with self.assertRaisesMessage(
            ProductosPedidoValidationError,
            "Debes seleccionar al menos 1 opcion(es) de Proteinas.",
        ):
            normalizar_productos_pedido(self.restaurante, [self.linea()])

    def test_minimo_valido(self):
        grupo = self.crear_grupo(minimo=2, maximo=3)
        pollo = self.crear_opcion(grupo, "Pollo")
        carne = self.crear_opcion(grupo, "Carne")
        snapshot, _ = normalizar_productos_pedido(
            self.restaurante,
            [self.linea(opciones=[pollo.id, carne.id])],
        )
        self.assertEqual(len(snapshot[0]["grupos_opciones"][0]["opciones"]), 2)

    def test_maximo_valido(self):
        grupo = self.crear_grupo(maximo=2)
        pollo = self.crear_opcion(grupo, "Pollo")
        carne = self.crear_opcion(grupo, "Carne")
        snapshot, _ = normalizar_productos_pedido(
            self.restaurante,
            [self.linea(opciones=[pollo.id, carne.id])],
        )
        self.assertEqual(len(snapshot), 1)

    def test_exceso_del_maximo_es_rechazado(self):
        grupo = self.crear_grupo(maximo=2)
        opciones = [
            self.crear_opcion(grupo, "Pollo"),
            self.crear_opcion(grupo, "Carne"),
            self.crear_opcion(grupo, "Camaron"),
        ]
        with self.assertRaisesMessage(
            ProductosPedidoValidationError,
            "Puedes seleccionar como maximo 2 opcion(es) de Proteinas.",
        ):
            normalizar_productos_pedido(
                self.restaurante,
                [self.linea(opciones=[opcion.id for opcion in opciones])],
            )

    def test_grupo_opcional_puede_quedar_vacio(self):
        self.crear_grupo(
            nombre="Salsas",
            obligatorio=False,
            minimo=0,
            maximo=3,
        )
        snapshot, total = normalizar_productos_pedido(
            self.restaurante,
            [self.linea()],
        )
        self.assertEqual(total, 1500)
        self.assertEqual(snapshot[0]["grupos_opciones"], [])

    def test_opcion_con_precio_adicional(self):
        grupo = self.crear_grupo()
        queso = self.crear_opcion(grupo, "Queso extra", precio=1500)
        snapshot, total = normalizar_productos_pedido(
            self.restaurante,
            [self.linea(opciones=[queso.id])],
        )
        self.assertEqual(snapshot[0]["opciones_total"], 1500)
        self.assertEqual(snapshot[0]["precio_unitario"], 3000)
        self.assertEqual(total, 3000)

    def test_varias_opciones_suman_sus_precios(self):
        grupo = self.crear_grupo()
        queso = self.crear_opcion(grupo, "Queso", precio=1500)
        camaron = self.crear_opcion(grupo, "Camaron", precio=2000)
        snapshot, total = normalizar_productos_pedido(
            self.restaurante,
            [self.linea(opciones=[queso.id, camaron.id], cantidad=2)],
        )
        self.assertEqual(snapshot[0]["opciones_total"], 3500)
        self.assertEqual(snapshot[0]["precio_unitario"], 5000)
        self.assertEqual(total, 10000)

    def test_producto_con_variante_y_opciones_respeta_precio_variante(self):
        variante = ProductoVariante.objects.create(
            producto=self.producto,
            nombre="XL",
            precio=9990,
        )
        grupo = self.crear_grupo()
        queso = self.crear_opcion(grupo, "Queso extra", precio=1500)
        snapshot, total = normalizar_productos_pedido(
            self.restaurante,
            [self.linea(variante=variante, opciones=[queso.id])],
        )
        self.assertEqual(snapshot[0]["precio_base"], 9990)
        self.assertEqual(snapshot[0]["precio_unitario"], 11490)
        self.assertEqual(total, 11490)

    def test_opcion_desactivada_es_rechazada(self):
        grupo = self.crear_grupo()
        opcion = self.crear_opcion(grupo, "Agotada", disponible=False)
        with self.assertRaisesMessage(
            ProductosPedidoValidationError,
            "La opcion Agotada no esta disponible.",
        ):
            normalizar_productos_pedido(
                self.restaurante,
                [self.linea(opciones=[opcion.id])],
            )

    def test_opcion_de_otro_producto_es_rechazada(self):
        otro_producto = Producto.objects.create(
            restaurante=self.restaurante,
            categoria=self.categoria,
            nombre="Otro producto",
            precio=2000,
            orden=2,
        )
        otro_grupo = self.crear_grupo(producto=otro_producto)
        opcion = self.crear_opcion(otro_grupo, "Ajena")
        with self.assertRaisesMessage(
            ProductosPedidoValidationError,
            "La opcion seleccionada no pertenece a este producto.",
        ):
            normalizar_productos_pedido(
                self.restaurante,
                [self.linea(opciones=[opcion.id])],
            )

    def test_opcion_de_otro_restaurante_es_rechazada(self):
        producto_externo = Producto.objects.create(
            restaurante=self.otro_restaurante,
            categoria=self.categoria_otro_restaurante,
            nombre="Externo",
            precio=2000,
            orden=1,
        )
        grupo_externo = self.crear_grupo(producto=producto_externo)
        opcion = self.crear_opcion(grupo_externo, "Externa")
        with self.assertRaisesMessage(
            ProductosPedidoValidationError,
            "La opcion seleccionada no pertenece a este producto.",
        ):
            normalizar_productos_pedido(
                self.restaurante,
                [self.linea(opciones=[opcion.id])],
            )

    def test_ids_de_opciones_duplicados_son_rechazados(self):
        grupo = self.crear_grupo()
        opcion = self.crear_opcion(grupo, "Pollo")
        with self.assertRaisesMessage(
            ProductosPedidoValidationError,
            "No puedes seleccionar la misma opcion mas de una vez.",
        ):
            normalizar_productos_pedido(
                self.restaurante,
                [self.linea(opciones=[opcion.id, opcion.id])],
            )

    def test_configuraciones_diferentes_no_se_fusionan(self):
        grupo = self.crear_grupo(maximo=1)
        pollo = self.crear_opcion(grupo, "Pollo")
        carne = self.crear_opcion(grupo, "Carne")
        snapshot, _ = normalizar_productos_pedido(
            self.restaurante,
            [
                self.linea(opciones=[pollo.id]),
                self.linea(opciones=[carne.id]),
            ],
        )
        self.assertEqual(len(snapshot), 2)

    def test_misma_configuracion_en_otro_orden_se_fusiona(self):
        grupo = self.crear_grupo(maximo=2)
        pollo = self.crear_opcion(grupo, "Pollo")
        carne = self.crear_opcion(grupo, "Carne")
        snapshot, _ = normalizar_productos_pedido(
            self.restaurante,
            [
                self.linea(opciones=[pollo.id, carne.id], cantidad=1),
                self.linea(opciones=[carne.id, pollo.id], cantidad=2),
            ],
        )
        self.assertEqual(len(snapshot), 1)
        self.assertEqual(snapshot[0]["cantidad"], 3)

    def test_cantidad_whatsapp_en_el_maximo_es_valida(self):
        response = self.crear_pedido_whatsapp([
            self.linea(cantidad=MAX_CANTIDAD_PEDIDO_WHATSAPP)
        ])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_lineas_identicas_dentro_del_maximo_se_fusionan(self):
        response = self.crear_pedido_whatsapp([
            self.linea(cantidad=40),
            self.linea(cantidad=50),
        ])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pedido = PedidoWhatsApp.objects.get(pk=response.data["pedido_id"])
        self.assertEqual(len(pedido.productos_snapshot), 1)
        self.assertEqual(pedido.productos_snapshot[0]["cantidad"], 90)

    def test_lineas_identicas_sobre_maximo_whatsapp_son_rechazadas(self):
        response = self.crear_pedido_whatsapp([
            self.linea(cantidad=50),
            self.linea(cantidad=50),
        ])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "no puede superar 99",
            str(response.data["productos"][0]),
        )

    def test_opciones_en_distinto_orden_tambien_suman_antes_del_limite(self):
        grupo = self.crear_grupo(minimo=2, maximo=2)
        pollo = self.crear_opcion(grupo, "Pollo")
        carne = self.crear_opcion(grupo, "Carne")

        response = self.crear_pedido_whatsapp([
            self.linea(opciones=[pollo.id, carne.id], cantidad=50),
            self.linea(opciones=[carne.id, pollo.id], cantidad=50),
        ])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no puede superar 99", str(response.data["productos"][0]))

    def test_configuraciones_diferentes_tienen_limites_independientes(self):
        grupo = self.crear_grupo(maximo=1)
        pollo = self.crear_opcion(grupo, "Pollo")
        carne = self.crear_opcion(grupo, "Carne")

        snapshot, _ = normalizar_productos_pedido(
            self.restaurante,
            [
                self.linea(opciones=[pollo.id], cantidad=99),
                self.linea(opciones=[carne.id], cantidad=99),
            ],
        )

        self.assertEqual(len(snapshot), 2)
        self.assertEqual([item["cantidad"] for item in snapshot], [99, 99])

    def test_variantes_diferentes_tienen_limites_independientes(self):
        normal = ProductoVariante.objects.create(
            producto=self.producto,
            nombre="Normal",
            precio=1500,
        )
        xl = ProductoVariante.objects.create(
            producto=self.producto,
            nombre="XL",
            precio=2500,
        )

        snapshot, _ = normalizar_productos_pedido(
            self.restaurante,
            [
                self.linea(variante=normal, cantidad=99),
                self.linea(variante=xl, cantidad=99),
            ],
        )

        self.assertEqual(len(snapshot), 2)

    def test_productos_diferentes_tienen_limites_independientes(self):
        otro_producto = Producto.objects.create(
            restaurante=self.restaurante,
            categoria=self.categoria,
            nombre="Segundo producto",
            precio=2000,
            orden=2,
        )

        snapshot, _ = normalizar_productos_pedido(
            self.restaurante,
            [
                self.linea(cantidad=99),
                self.linea(producto=otro_producto, cantidad=99),
            ],
        )

        self.assertEqual(len(snapshot), 2)

    def test_pedido_normal_del_frontend_sigue_funcionando(self):
        response = self.crear_pedido_whatsapp([self.linea(cantidad=1)])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_pedido_manual_rechaza_suma_sobre_su_maximo(self):
        self.client.force_authenticate(user=self.dueno)
        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            {
                "tipo_entrega": PedidoManual.TIPO_RETIRO,
                "items": [
                    self.linea(cantidad=500),
                    self.linea(cantidad=500),
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            f"no puede superar {MAX_CANTIDAD_PEDIDO_MANUAL}",
            str(response.data["items"]),
        )

    def test_pedido_manual_acepta_suma_en_su_maximo(self):
        self.client.force_authenticate(user=self.dueno)
        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            {
                "tipo_entrega": PedidoManual.TIPO_RETIRO,
                "items": [
                    self.linea(cantidad=500),
                    self.linea(cantidad=499),
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pedido = PedidoManual.objects.get(pk=response.data["pedido"]["id"])
        self.assertEqual(pedido.items.get().cantidad, MAX_CANTIDAD_PEDIDO_MANUAL)

    def test_edicion_manual_historica_tambien_respeta_cantidad_acumulada(self):
        grupo = self.crear_grupo(maximo=1)
        queso = self.crear_opcion(grupo, "Queso")
        self.client.force_authenticate(user=self.dueno)
        crear = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            {
                "tipo_entrega": PedidoManual.TIPO_RETIRO,
                "items": [self.linea(opciones=[queso.id])],
            },
            format="json",
        )
        pedido_id = crear.data["pedido"]["id"]
        queso_id = queso.id
        queso.delete()

        response = self.client.patch(
            f"/api/mi-restaurante/pedidos/manuales/{pedido_id}/",
            {
                "items": [
                    self.linea(opciones=[queso_id], cantidad=500),
                    self.linea(opciones=[queso_id], cantidad=500),
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no puede superar 999", str(response.data["items"]))

    def test_snapshot_whatsapp_conserva_grupos_nombres_y_precios(self):
        grupo = self.crear_grupo()
        pollo = self.crear_opcion(grupo, "Pollo")
        queso = self.crear_opcion(grupo, "Queso extra", precio=1500)
        response = self.crear_pedido_whatsapp(
            [self.linea(opciones=[pollo.id, queso.id])]
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pedido = PedidoWhatsApp.objects.get(id=response.data["pedido_id"])
        item = pedido.productos_snapshot[0]
        self.assertEqual(item["precio_base"], 1500)
        self.assertEqual(item["opciones_total"], 1500)
        self.assertEqual(item["grupos_opciones"][0]["grupo_nombre"], "Proteinas")
        self.assertEqual(item["grupos_opciones"][0]["opciones"][1], {
            "opcion_id": queso.id,
            "nombre": "Queso extra",
            "precio_adicional": 1500,
        })

    def test_pedido_manual_guarda_opciones_snapshot(self):
        grupo = self.crear_grupo()
        queso = self.crear_opcion(grupo, "Queso extra", precio=1500)
        self.client.force_authenticate(user=self.dueno)
        response = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            {
                "tipo_entrega": PedidoManual.TIPO_RETIRO,
                "items": [self.linea(opciones=[queso.id])],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item = PedidoManualItem.objects.get(pedido__restaurante=self.restaurante)
        self.assertEqual(item.precio_unitario, 3000)
        self.assertEqual(item.opciones_snapshot[0]["grupo_nombre"], "Proteinas")
        self.assertEqual(
            item.opciones_snapshot[0]["opciones"][0]["precio_adicional"],
            1500,
        )

    def test_snapshot_historico_no_cambia_con_catalogo(self):
        grupo = self.crear_grupo()
        opcion = self.crear_opcion(grupo, "Queso extra", precio=1500)
        response = self.crear_pedido_whatsapp([self.linea(opciones=[opcion.id])])
        pedido = PedidoWhatsApp.objects.get(id=response.data["pedido_id"])

        opcion.nombre = "Queso premium"
        opcion.precio_adicional = 3000
        opcion.disponible = False
        opcion.save()

        pedido.refresh_from_db()
        opcion_snapshot = pedido.productos_snapshot[0]["grupos_opciones"][0]["opciones"][0]
        self.assertEqual(opcion_snapshot["nombre"], "Queso extra")
        self.assertEqual(opcion_snapshot["precio_adicional"], 1500)

    def test_pedido_antiguo_sin_grupos_sigue_generando_mensaje(self):
        pedido = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="Cliente antiguo",
            telefono_cliente="912345678",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[{
                "producto_id": self.producto.id,
                "nombre": self.producto.nombre,
                "precio_unitario": 1500,
                "cantidad": 1,
                "subtotal": 1500,
            }],
            total=1500,
            mensaje_whatsapp_generado="",
            whatsapp_destino=self.restaurante.whatsapp,
        )
        mensaje = generar_mensaje_whatsapp(pedido)
        self.assertIn(f"1 x {self.producto.nombre} - $1500", mensaje)

    def test_hash_idempotencia_canoniza_opciones_y_distingue_configuraciones(self):
        base = self.payload_whatsapp([self.linea(opciones=[12, 13, 25])])
        otro_orden = self.payload_whatsapp([self.linea(opciones=[25, 12, 13])])
        diferente = self.payload_whatsapp([self.linea(opciones=[12, 13])])
        self.assertEqual(
            calcular_hash_pedido_publico(self.restaurante, base),
            calcular_hash_pedido_publico(self.restaurante, otro_orden),
        )
        self.assertNotEqual(
            calcular_hash_pedido_publico(self.restaurante, base),
            calcular_hash_pedido_publico(self.restaurante, diferente),
        )

    def test_reutilizar_idempotency_key_con_configuracion_distinta_conflicta(self):
        grupo = self.crear_grupo(maximo=1)
        pollo = self.crear_opcion(grupo, "Pollo")
        carne = self.crear_opcion(grupo, "Carne")
        headers = {"HTTP_IDEMPOTENCY_KEY": "personalizacion-1"}
        primera = self.crear_pedido_whatsapp(
            [self.linea(opciones=[pollo.id])],
            headers=headers,
        )
        segunda = self.crear_pedido_whatsapp(
            [self.linea(opciones=[carne.id])],
            headers=headers,
        )
        self.assertEqual(primera.status_code, status.HTTP_201_CREATED)
        self.assertEqual(segunda.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(segunda.data["error"], "idempotency_key_reused")

    def test_mensaje_whatsapp_incluye_personalizacion_desde_snapshot(self):
        grupo = self.crear_grupo(nombre="Extras", maximo=1)
        queso = self.crear_opcion(grupo, "Queso extra", precio=1500)
        response = self.crear_pedido_whatsapp([self.linea(opciones=[queso.id])])
        pedido = PedidoWhatsApp.objects.get(id=response.data["pedido_id"])
        mensaje = pedido.mensaje_whatsapp_generado
        self.assertIn(f"1x {self.producto.nombre}", mensaje)
        self.assertIn("Extras: Queso extra (+$1.500)", mensaje)
        self.assertIn("$3.000", mensaje)

    def test_update_manual_reconstruye_personalizacion(self):
        grupo = self.crear_grupo(maximo=1)
        queso = self.crear_opcion(grupo, "Queso", precio=1000)
        camaron = self.crear_opcion(grupo, "Camaron", precio=2000)
        self.client.force_authenticate(user=self.dueno)
        crear = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            {
                "tipo_entrega": PedidoManual.TIPO_RETIRO,
                "items": [self.linea(opciones=[queso.id])],
            },
            format="json",
        )
        pedido_id = crear.data["pedido"]["id"]
        actualizar = self.client.patch(
            f"/api/mi-restaurante/pedidos/manuales/{pedido_id}/",
            {"items": [self.linea(opciones=[camaron.id])]},
            format="json",
        )
        self.assertEqual(actualizar.status_code, status.HTTP_200_OK)
        item = PedidoManualItem.objects.get(pedido_id=pedido_id)
        self.assertEqual(item.precio_unitario, 3500)
        self.assertEqual(
            item.opciones_snapshot[0]["opciones"][0]["nombre"],
            "Camaron",
        )

    def test_update_manual_conserva_snapshot_si_opcion_fue_eliminada(self):
        grupo = self.crear_grupo(maximo=1)
        queso = self.crear_opcion(grupo, "Queso extra", precio=1500)
        self.client.force_authenticate(user=self.dueno)
        crear = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            {
                "tipo_entrega": PedidoManual.TIPO_RETIRO,
                "items": [self.linea(opciones=[queso.id])],
            },
            format="json",
        )
        pedido_id = crear.data["pedido"]["id"]
        queso_id = queso.id
        queso.delete()

        actualizar = self.client.patch(
            f"/api/mi-restaurante/pedidos/manuales/{pedido_id}/",
            {"items": [self.linea(opciones=[queso_id], cantidad=2)]},
            format="json",
        )

        self.assertEqual(actualizar.status_code, status.HTTP_200_OK)
        item = PedidoManualItem.objects.get(pedido_id=pedido_id)
        self.assertEqual(item.cantidad, 2)
        self.assertEqual(item.precio_unitario, 3000)
        self.assertEqual(item.subtotal, 6000)
        self.assertEqual(item.opciones_snapshot[0]["opciones"][0]["nombre"], "Queso extra")

    def test_kds_normaliza_opciones_desde_ambos_tipos_de_snapshot(self):
        snapshot_grupos = [{
            "grupo_id": 10,
            "grupo_nombre": "Extras",
            "opciones": [{"opcion_id": 20, "nombre": "Queso extra", "precio_adicional": 1500}],
        }]
        whatsapp = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=91,
            nombre_cliente="WhatsApp",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[{"nombre": "Fajita", "cantidad": 1, "grupos_opciones": snapshot_grupos}],
            total=3000,
            estado=PedidoWhatsApp.ESTADO_EN_PREPARACION,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )
        manual = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=92,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=3000,
            total=3000,
            estado=PedidoManual.ESTADO_PREPARANDO,
        )
        manual.items.create(
            producto=self.producto,
            nombre_producto="Fajita",
            precio_unitario=3000,
            cantidad=1,
            subtotal=3000,
            opciones_snapshot=snapshot_grupos,
        )

        comandas = {item["id"]: item for item in obtener_comandas_activas(self.restaurante)}
        esperado = [{"grupo_nombre": "Extras", "opciones": [{"nombre": "Queso extra"}]}]
        self.assertEqual(comandas[f"whatsapp:{whatsapp.id}"]["items"][0]["opciones"], esperado)
        self.assertEqual(comandas[f"menly:{manual.id}"]["items"][0]["opciones"], esperado)

    def test_seguimiento_manual_expone_personalizacion_historica(self):
        grupo = self.crear_grupo(nombre="Extras", maximo=1)
        queso = self.crear_opcion(grupo, "Queso extra", precio=1500)
        self.client.force_authenticate(user=self.dueno)
        crear = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            {
                "tipo_entrega": PedidoManual.TIPO_RETIRO,
                "items": [self.linea(opciones=[queso.id])],
            },
            format="json",
        )
        token = crear.data["pedido"]["tracking_token"]
        self.client.force_authenticate(user=None)

        response = self.client.get(f"/api/public/pedidos/seguimiento/{token}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"][0]["precio_unitario"], 3000)
        self.assertEqual(
            response.data["items"][0]["opciones_snapshot"][0]["opciones"][0]["nombre"],
            "Queso extra",
        )

    def test_historial_incluye_pedido_manual_con_snapshot(self):
        grupo = self.crear_grupo(nombre="Extras", maximo=1)
        queso = self.crear_opcion(grupo, "Queso extra", precio=1500)
        self.client.force_authenticate(user=self.dueno)
        crear = self.client.post(
            "/api/mi-restaurante/pedidos/manuales/",
            {
                "tipo_entrega": PedidoManual.TIPO_RETIRO,
                "items": [self.linea(opciones=[queso.id])],
            },
            format="json",
        )
        pedido_id = crear.data["pedido"]["id"]
        PedidoManual.objects.filter(id=pedido_id).update(
            fecha_creacion=timezone.now() - timedelta(days=1)
        )

        response = self.client.get("/api/historial/pedidos/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        manual = next(
            pedido for pedido in response.data["results"]
            if pedido["tipo_origen"] == "manual" and pedido["id"] == pedido_id
        )
        self.assertEqual(
            manual["items"][0]["opciones_snapshot"][0]["opciones"][0]["nombre"],
            "Queso extra",
        )
