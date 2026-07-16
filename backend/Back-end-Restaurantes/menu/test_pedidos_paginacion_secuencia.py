from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status

from .models import (
    PedidoEspecial,
    PedidoManual,
    PedidoWhatsApp,
    Restaurante,
    RestaurantePedidoSecuencia,
)
from .serializers import PedidoEspecialSerializer, PedidoManualSerializer
from .services.cocina import obtener_comandas_activas
from .services.pedidos_whatsapp import crear_pedido_whatsapp
from .services.secuencia_pedidos import obtener_siguiente_numero_pedido
from .tests import BaseTestCase


class PedidosDashboardPaginacionTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.restaurante.pedidos_pos = True
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.save(update_fields=["pedidos_pos", "solicitudes_especiales_activas"])
        self.client.force_authenticate(user=self.dueno)

        for numero in range(1, 26):
            PedidoWhatsApp.objects.create(
                restaurante=self.restaurante,
                numero_pedido=numero,
                nombre_cliente=f"WhatsApp {numero}",
                telefono_cliente="56911111111",
                tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
                productos_snapshot=[],
                total=numero * 100,
                mensaje_whatsapp_generado="Pedido",
                whatsapp_destino="56911111111",
            )
            PedidoManual.objects.create(
                restaurante=self.restaurante,
                numero_pedido=numero,
                nombre_cliente=f"Menly {numero}",
                tipo_entrega=PedidoManual.TIPO_RETIRO,
                subtotal=numero * 100,
                total=numero * 100,
            )
            PedidoEspecial.objects.create(
                restaurante=self.restaurante,
                numero_pedido=numero,
                nombre_cliente=f"Especial {numero}",
                telefono_cliente="56911111111",
                items=[],
                total=numero * 100,
                fecha_entrega=timezone.localdate(),
                estado=(
                    PedidoEspecial.ESTADO_ENTREGADO
                    if numero == 1
                    else PedidoEspecial.ESTADO_PENDIENTE
                ),
            )

        pedido_antiguo = PedidoWhatsApp.objects.get(restaurante=self.restaurante, numero_pedido=1)
        PedidoWhatsApp.objects.filter(id=pedido_antiguo.id).update(
            fecha_creacion=timezone.now() - timedelta(days=2)
        )

    def assert_paginacion_25(self, endpoint):
        pagina_1 = self.client.get(endpoint, {"scope": "historico"})
        pagina_2 = self.client.get(endpoint, {"page": 2, "scope": "historico"})
        pagina_3 = self.client.get(endpoint, {"page": 3, "scope": "historico"})

        self.assertEqual(pagina_1.status_code, status.HTTP_200_OK)
        self.assertEqual(pagina_1.data["count"], 25)
        self.assertEqual(len(pagina_1.data["results"]), 10)
        self.assertIsNone(pagina_1.data["previous"])
        self.assertIsNotNone(pagina_1.data["next"])

        self.assertEqual(len(pagina_2.data["results"]), 10)
        self.assertIsNotNone(pagina_2.data["previous"])
        self.assertIsNotNone(pagina_2.data["next"])

        self.assertEqual(len(pagina_3.data["results"]), 5)
        self.assertIsNotNone(pagina_3.data["previous"])
        self.assertIsNone(pagina_3.data["next"])
        return pagina_1, pagina_2, pagina_3

    def test_whatsapp_pagina_todos_los_pedidos_en_orden_descendente(self):
        pagina_1, pagina_2, pagina_3 = self.assert_paginacion_25(
            "/api/mi-restaurante/pedidos/whatsapp/"
        )
        self.assertEqual([item["numero_pedido"] for item in pagina_1.data["results"]], list(range(25, 15, -1)))
        self.assertEqual([item["numero_pedido"] for item in pagina_2.data["results"]], list(range(15, 5, -1)))
        self.assertEqual([item["numero_pedido"] for item in pagina_3.data["results"]], list(range(5, 0, -1)))

    def test_menly_pagina_25_pedidos(self):
        self.assert_paginacion_25("/api/mi-restaurante/pedidos/manuales/")

    def test_especiales_pagina_25_e_incluye_entregados(self):
        _, _, pagina_3 = self.assert_paginacion_25("/api/mi-restaurante/pedidos/especiales/")
        self.assertIn(PedidoEspecial.ESTADO_ENTREGADO, [item["estado"] for item in pagina_3.data["results"]])


class SecuenciaPedidosTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.restaurante.pedidos_pos = True
        self.restaurante.save(update_fields=["pedidos_pos"])

    def crear_whatsapp(self, restaurante=None):
        restaurante = restaurante or self.restaurante
        return crear_pedido_whatsapp(
            restaurante,
            {
                "nombre_cliente": "Cliente WhatsApp",
                "telefono_cliente": "56911111111",
                "tipo_entrega": PedidoWhatsApp.TIPO_RETIRO_LOCAL,
                "direccion_entrega": None,
                "metodo_pago": None,
                "metodo_pago_nombre": "",
                "productos": [],
                "productos_snapshot": [],
                "total": 0,
                "whatsapp_destino": "56911111111",
            },
        )

    def crear_menly(self):
        serializer = PedidoManualSerializer(
            data={
                "nombre_cliente": "Cliente Menly",
                "tipo_entrega": PedidoManual.TIPO_RETIRO,
                "items": [{"producto_id": self.producto.id, "cantidad": 1}],
            },
            context={"restaurante": self.restaurante, "usuario": self.dueno},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def crear_especial(self):
        serializer = PedidoEspecialSerializer(
            data={
                "nombre_cliente": "Cliente especial",
                "telefono_cliente": "56911111111",
                "fecha_entrega": timezone.localdate(),
                "items": [{"nombre": "Torta", "cantidad": 1, "precio_unitario": 1000}],
            },
            context={"restaurante": self.restaurante},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def test_whatsapp_menly_y_especial_comparten_correlativo(self):
        whatsapp = self.crear_whatsapp()
        menly = self.crear_menly()
        especial = self.crear_especial()

        self.assertEqual(whatsapp.numero_pedido, 1)
        self.assertEqual(menly.numero_pedido, 2)
        self.assertEqual(especial.numero_pedido, 3)
        self.assertEqual(
            RestaurantePedidoSecuencia.objects.get(restaurante=self.restaurante).ultimo_numero,
            3,
        )

    def test_cada_restaurante_mantiene_su_secuencia(self):
        primero = self.crear_whatsapp(self.restaurante)
        otro = self.crear_whatsapp(self.otro_restaurante)
        segundo = self.crear_menly()

        self.assertEqual((primero.numero_pedido, segundo.numero_pedido), (1, 2))
        self.assertEqual(otro.numero_pedido, 1)

    def test_rollover_de_9999_a_1(self):
        RestaurantePedidoSecuencia.objects.create(restaurante=self.restaurante, ultimo_numero=9999)
        self.assertEqual(obtener_siguiente_numero_pedido(self.restaurante), 1)

    def test_no_reinicia_por_fecha_y_recupera_el_maximo_historico(self):
        pedido_antiguo = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=7,
            nombre_cliente="Historico",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=0,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )
        PedidoWhatsApp.objects.filter(id=pedido_antiguo.id).update(
            fecha_creacion=timezone.now() - timedelta(days=1)
        )

        self.assertEqual(self.crear_menly().numero_pedido, 8)

    def test_kds_muestra_el_mismo_correlativo_de_los_modelos(self):
        whatsapp = self.crear_whatsapp()
        menly = self.crear_menly()
        especial = self.crear_especial()
        whatsapp.estado = PedidoWhatsApp.ESTADO_EN_PREPARACION
        whatsapp.save(update_fields=["estado"])
        menly.estado = PedidoManual.ESTADO_PREPARANDO
        menly.save(update_fields=["estado"])
        especial.estado = PedidoEspecial.ESTADO_EN_PREPARACION
        especial.save(update_fields=["estado"])

        numeros = {
            (comanda["tipo_origen"], comanda["numero"])
            for comanda in obtener_comandas_activas(self.restaurante)
        }
        self.assertEqual(numeros, {("whatsapp", 1), ("menly", 2), ("especial", 3)})


@skipUnless(connection.vendor == "postgresql", "Requiere PostgreSQL para validar select_for_update real.")
class SecuenciaPedidosPostgreSQLConcurrenciaTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.restaurante = Restaurante.objects.create(
            nombre_empresa="Concurrencia",
            slug="concurrencia",
            telefono="999999999",
            email_contacto="concurrencia@example.com",
            direccion="Calle 1",
            ciudad="Santiago",
            activo=True,
        )

    def test_dos_reservas_simultaneas_reciben_numeros_distintos(self):
        barrera = Barrier(2)

        def reservar_numero():
            close_old_connections()
            restaurante = Restaurante.objects.get(id=self.restaurante.id)
            barrera.wait()
            pedido = crear_pedido_whatsapp(
                restaurante,
                {
                    "nombre_cliente": "Pedido concurrente",
                    "telefono_cliente": "56911111111",
                    "tipo_entrega": PedidoWhatsApp.TIPO_RETIRO_LOCAL,
                    "direccion_entrega": None,
                    "metodo_pago": None,
                    "metodo_pago_nombre": "",
                    "productos": [],
                    "productos_snapshot": [],
                    "total": 0,
                    "whatsapp_destino": "56911111111",
                },
            )
            close_old_connections()
            return pedido.numero_pedido

        with ThreadPoolExecutor(max_workers=2) as executor:
            numeros = sorted(executor.map(lambda _: reservar_numero(), range(2)))

        self.assertEqual(numeros, [1, 2])
        self.assertEqual(PedidoWhatsApp.objects.filter(restaurante=self.restaurante).count(), 2)
