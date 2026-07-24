from django.utils import timezone
from rest_framework import status

from .models import (
    PedidoEspecial,
    PedidoManual,
    PedidoManualItem,
    PedidoWhatsApp,
    Plan,
    ReporteMetrica,
)
from .tests import BaseTestCase


class H05MetricasFinancierasTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        plan, _ = Plan.objects.get_or_create(
            slug="pro",
            defaults={"nombre": "Pro"},
        )
        self.restaurante.plan = plan
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.save(
            update_fields=["plan", "solicitudes_especiales_activas"]
        )
        self.otro_restaurante.plan = plan
        self.otro_restaurante.save(update_fields=["plan"])

    def crear_pedidos_del_periodo(self):
        whatsapp = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            nombre_cliente="WhatsApp",
            telefono_cliente="111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[{
                "producto_id": self.producto.id,
                "nombre": self.producto.nombre,
                "cantidad": 1,
                "precio_unitario": 1000,
                "subtotal": 1000,
            }],
            total=1000,
            estado=PedidoWhatsApp.ESTADO_ENTREGADO,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="111",
        )
        manual = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            nombre_cliente="Manual",
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=2000,
            total=2000,
            estado=PedidoManual.ESTADO_ENTREGADO,
        )
        PedidoManualItem.objects.create(
            pedido=manual,
            producto=self.producto,
            nombre_producto=self.producto.nombre,
            precio_unitario=2000,
            cantidad=1,
            subtotal=2000,
        )
        especial = PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            numero_pedido=3,
            nombre_cliente="Especial",
            telefono_cliente="333",
            items=[{
                "nombre": "Torta",
                "cantidad": 1,
                "precio_unitario": 3000,
                "subtotal": 3000,
            }],
            total=3000,
            fecha_entrega=timezone.localdate(),
            estado=PedidoEspecial.ESTADO_ENTREGADO,
        )
        cancelado = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=4,
            nombre_cliente="Cancelado",
            telefono_cliente="444",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=8000,
            estado=PedidoWhatsApp.ESTADO_CANCELADO,
            mensaje_whatsapp_generado="Cancelado",
            whatsapp_destino="444",
        )
        return whatsapp, manual, especial, cancelado

    def test_guardado_ignora_cifras_falsas_y_recalcula_todos_los_canales(self):
        self.crear_pedidos_del_periodo()
        PedidoManual.objects.create(
            restaurante=self.otro_restaurante,
            numero_pedido=1,
            nombre_cliente="Ajeno",
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=9000,
            total=9000,
            estado=PedidoManual.ESTADO_ENTREGADO,
        )
        periodo = timezone.localdate().strftime("%Y-%m")
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/metricas/reportes/guardar/",
            {
                "tipo": ReporteMetrica.TIPO_MENSUAL,
                "periodo_mes": periodo,
                "titulo": "Reporte compatible",
                "restaurante_id": self.otro_restaurante.id,
                "resumen": {"venta_real": 999999999},
                "datos": {
                    "venta_total": 999999999,
                    "pedidos_creados": 999999999,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reporte = ReporteMetrica.objects.get(id=response.data["reporte"]["id"])
        self.assertEqual(reporte.restaurante, self.restaurante)
        self.assertEqual(reporte.resumen["venta_real"], 6000)
        self.assertEqual(reporte.datos["venta_total"], 6000)
        self.assertEqual(reporte.datos["venta_menly"], 2000)
        self.assertEqual(reporte.datos["venta_whatsapp"], 1000)
        self.assertEqual(reporte.datos["venta_especiales"], 3000)
        self.assertEqual(reporte.datos["pedidos_creados"], 4)
        self.assertEqual(reporte.datos["pedidos_finalizados"], 3)
        self.assertEqual(reporte.datos["pedidos_cancelados"], 1)
        self.assertEqual(
            set(reporte.datos["desglose_por_canal"]),
            {"whatsapp", "especiales", "menly"},
        )

    def test_reporte_conserva_contrato_historico_y_agrega_manual_sin_duplicar(self):
        self.crear_pedidos_del_periodo()
        self.client.force_authenticate(user=self.admin)

        response = self.client.get("/api/metricas/reporte-mensual/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["venta_total"], 6000)
        for campo in (
            "resumen_global",
            "desglose_por_canal",
            "resumen_canales",
            "consolidado_total",
            "venta_total",
            "venta_whatsapp",
            "venta_especiales",
            "pedidos_total",
            "productos_vendidos",
            "productos_por_canal",
        ):
            self.assertIn(campo, response.data)
        self.assertEqual(response.data["venta_menly"], 2000)
        self.assertEqual(
            response.data["desglose_por_canal"]["menly"]["pedidos_finalizados"],
            1,
        )

    def test_empleado_recibe_403_en_metricas_y_reportes(self):
        reporte = ReporteMetrica.objects.create(
            restaurante=self.restaurante,
            tipo=ReporteMetrica.TIPO_MENSUAL,
            periodo_mes=timezone.localdate().strftime("%Y-%m"),
            periodo_anio=str(timezone.localdate().year),
            titulo="Protegido",
            resumen={},
            datos={},
        )
        self.client.force_authenticate(user=self.empleado)
        periodo = timezone.localdate().strftime("%Y-%m")
        endpoints = [
            ("get", "/api/mi-restaurante/pedidos/metricas/", None),
            ("get", "/api/mi-restaurante/metricas/resumen/", None),
            ("get", "/api/metricas/reporte-mensual/", None),
            ("get", "/api/metricas/reporte-anual/", None),
            ("get", "/api/metricas/reportes/", None),
            ("get", f"/api/metricas/reportes/{reporte.id}/", None),
            (
                "post",
                "/api/metricas/reportes/guardar/",
                {"tipo": "mensual", "periodo_mes": periodo},
            ),
        ]

        for metodo, url, payload in endpoints:
            with self.subTest(url=url):
                response = getattr(self.client, metodo)(
                    url,
                    payload or {},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dueno_y_admin_pueden_acceder_a_metricas(self):
        for usuario in (self.dueno, self.admin):
            with self.subTest(usuario=usuario.username):
                self.client.force_authenticate(user=usuario)
                response = self.client.get(
                    "/api/mi-restaurante/metricas/resumen/"
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_otro_restaurante_no_puede_ver_reporte_ajeno(self):
        reporte = ReporteMetrica.objects.create(
            restaurante=self.otro_restaurante,
            tipo=ReporteMetrica.TIPO_MENSUAL,
            periodo_mes=timezone.localdate().strftime("%Y-%m"),
            periodo_anio=str(timezone.localdate().year),
            titulo="Ajeno",
            resumen={"venta_real": 9000},
            datos={"venta_total": 9000},
        )
        self.client.force_authenticate(user=self.dueno)

        response = self.client.get(
            f"/api/metricas/reportes/{reporte.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
