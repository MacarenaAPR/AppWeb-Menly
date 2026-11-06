from datetime import datetime
from io import StringIO

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.utils import timezone

from menu.admin import (
    PedidoEspecialAdmin,
    PedidoManualAdmin,
    PedidoWhatsAppAdmin,
    ReporteMetricaAdmin,
)
from menu.management.commands.generar_reportes_mensuales import mes_anterior
from menu.models import (
    HistorialEstadoPedidoManual,
    HistorialEstadoPedidoWhatsApp,
    PedidoEspecial,
    PedidoManual,
    PedidoManualItem,
    PedidoWhatsApp,
    ReporteMetrica,
    Restaurante,
    UsuarioRestaurante,
)
from menu.services.estados_pedidos import TransicionEstadoInvalida, cambiar_estado_pedido
from menu.services.reportes_mensuales import guardar_reporte_mensual


def crear_restaurante(slug, activo=True):
    return Restaurante.objects.create(
        nombre_empresa=slug.title(),
        slug=slug,
        telefono="+56900000000",
        email_contacto=f"{slug}@example.com",
        direccion="Dirección 1",
        ciudad="Santiago",
        activo=activo,
    )


class AccionProductosListosAdminTests(TestCase):
    def setUp(self):
        self.restaurante = crear_restaurante("tenant-a")
        self.otro = crear_restaurante("tenant-b")
        self.superuser = User.objects.create_superuser("root", "root@example.com", "clave-segura")
        self.factory = RequestFactory()

    def _request(self, confirmar=True, usuario=None, accion="listos"):
        campo = (
            "confirmar_marcar_entregados"
            if accion == "entregados"
            else "confirmar_marcar_listos"
        )
        data = {campo: "1"} if confirmar else {}
        request = self.factory.post("/admin/", data)
        request.user = usuario or self.superuser
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def _whatsapp(self, restaurante, estado, items=None, numero=1):
        return PedidoWhatsApp.objects.create(
            restaurante=restaurante,
            numero_pedido=numero,
            nombre_cliente="Cliente",
            telefono_cliente="+56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=items if items is not None else [{"nombre": "Pizza", "cantidad": 2}],
            total=10000,
            estado=estado,
            mensaje_whatsapp_generado="mensaje",
            whatsapp_destino="+56922222222",
        )

    def test_accion_confirma_y_solo_transiciona_preparacion_con_items(self):
        valido = self._whatsapp(self.restaurante, PedidoWhatsApp.ESTADO_EN_PREPARACION, numero=1)
        cancelado = self._whatsapp(self.restaurante, PedidoWhatsApp.ESTADO_CANCELADO, numero=2)
        vacio = self._whatsapp(self.restaurante, PedidoWhatsApp.ESTADO_EN_PREPARACION, [], numero=3)
        listo = self._whatsapp(self.restaurante, PedidoWhatsApp.ESTADO_LISTO, numero=4)
        admin_model = PedidoWhatsAppAdmin(PedidoWhatsApp, AdminSite())
        queryset = PedidoWhatsApp.objects.filter(
            pk__in=[valido.pk, cancelado.pk, vacio.pk, listo.pk]
        )

        respuesta = admin_model.marcar_productos_listos(self._request(confirmar=False), queryset)
        self.assertEqual(respuesta.template_name, "admin/pedidos_marcar_listos_confirmacion.html")

        admin_model.marcar_productos_listos(self._request(), queryset)
        valido.refresh_from_db()
        cancelado.refresh_from_db()
        vacio.refresh_from_db()
        listo.refresh_from_db()
        self.assertEqual(valido.estado, PedidoWhatsApp.ESTADO_LISTO)
        self.assertEqual(cancelado.estado, PedidoWhatsApp.ESTADO_CANCELADO)
        self.assertEqual(vacio.estado, PedidoWhatsApp.ESTADO_EN_PREPARACION)
        self.assertEqual(listo.estado, PedidoWhatsApp.ESTADO_LISTO)
        self.assertEqual(HistorialEstadoPedidoWhatsApp.objects.filter(pedido=valido).count(), 1)

    def test_accion_manual_reutiliza_transicion_oficial(self):
        pedido = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=1,
            estado=PedidoManual.ESTADO_PREPARANDO,
            tipo_entrega=PedidoManual.TIPO_MESA,
            total=2000,
        )
        PedidoManualItem.objects.create(
            pedido=pedido,
            nombre_producto="Café",
            precio_unitario=1000,
            cantidad=2,
            subtotal=2000,
        )
        admin_model = PedidoManualAdmin(PedidoManual, AdminSite())
        admin_model.marcar_productos_listos(self._request(), PedidoManual.objects.filter(pk=pedido.pk))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoManual.ESTADO_LISTO)
        self.assertEqual(HistorialEstadoPedidoManual.objects.filter(pedido=pedido).count(), 1)

    def test_queryset_admin_aisla_restaurante_para_staff(self):
        propio = self._whatsapp(self.restaurante, PedidoWhatsApp.ESTADO_EN_PREPARACION, numero=1)
        self._whatsapp(self.otro, PedidoWhatsApp.ESTADO_EN_PREPARACION, numero=1)
        staff = User.objects.create_user("staff", password="clave-segura", is_staff=True)
        UsuarioRestaurante.objects.create(
            user=staff, restaurante=self.restaurante, rol="admin", activo=True
        )
        request = self._request(usuario=staff)
        queryset = PedidoWhatsAppAdmin(PedidoWhatsApp, AdminSite()).get_queryset(request)
        self.assertEqual(list(queryset.values_list("pk", flat=True)), [propio.pk])

    def test_accion_entregados_finaliza_directamente_y_omite_terminales(self):
        estados_actualizables = [
            PedidoWhatsApp.ESTADO_RECIBIDO,
            PedidoWhatsApp.ESTADO_PENDIENTE_CONFIRMACION,
            PedidoWhatsApp.ESTADO_CONFIRMADO,
            PedidoWhatsApp.ESTADO_EN_PREPARACION,
            PedidoWhatsApp.ESTADO_LISTO,
            PedidoWhatsApp.ESTADO_EN_REPARTO,
        ]
        actualizables = [
            self._whatsapp(self.restaurante, estado, numero=numero)
            for numero, estado in enumerate(estados_actualizables, start=10)
        ]
        cancelado = self._whatsapp(
            self.restaurante, PedidoWhatsApp.ESTADO_CANCELADO, numero=20
        )
        ya_entregado = self._whatsapp(
            self.restaurante, PedidoWhatsApp.ESTADO_ENTREGADO, numero=21
        )
        queryset = PedidoWhatsApp.objects.filter(
            pk__in=[*(pedido.pk for pedido in actualizables), cancelado.pk, ya_entregado.pk]
        )
        admin_model = PedidoWhatsAppAdmin(PedidoWhatsApp, AdminSite())

        confirmacion = admin_model.marcar_pedidos_entregados(
            self._request(confirmar=False, accion="entregados"), queryset
        )
        self.assertEqual(confirmacion.context_data["actualizables"], 6)
        self.assertEqual(confirmacion.context_data["cancelados"], 1)
        self.assertEqual(confirmacion.context_data["ya_entregados"], 1)

        admin_model.marcar_pedidos_entregados(
            self._request(accion="entregados"), queryset
        )
        for pedido in actualizables:
            pedido.refresh_from_db()
            self.assertEqual(pedido.estado, PedidoWhatsApp.ESTADO_ENTREGADO)
            self.assertEqual(
                HistorialEstadoPedidoWhatsApp.objects.filter(pedido=pedido).count(), 1
            )
        cancelado.refresh_from_db()
        ya_entregado.refresh_from_db()
        self.assertEqual(cancelado.estado, PedidoWhatsApp.ESTADO_CANCELADO)
        self.assertEqual(ya_entregado.estado, PedidoWhatsApp.ESTADO_ENTREGADO)
        self.assertFalse(HistorialEstadoPedidoWhatsApp.objects.filter(pedido=cancelado).exists())
        self.assertFalse(HistorialEstadoPedidoWhatsApp.objects.filter(pedido=ya_entregado).exists())

    def test_accion_entregados_manual_y_transiciones_normales_siguen_intactas(self):
        pendiente = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=30,
            estado=PedidoManual.ESTADO_PENDIENTE,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            total=2000,
        )
        with self.assertRaises(TransicionEstadoInvalida):
            cambiar_estado_pedido(pendiente, PedidoManual.ESTADO_ENTREGADO)

        admin_model = PedidoManualAdmin(PedidoManual, AdminSite())
        admin_model.marcar_pedidos_entregados(
            self._request(accion="entregados"),
            PedidoManual.objects.filter(pk=pendiente.pk),
        )
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, PedidoManual.ESTADO_ENTREGADO)
        self.assertEqual(
            HistorialEstadoPedidoManual.objects.filter(pedido=pendiente).count(), 1
        )

    def test_accion_entregados_solo_aparece_en_whatsapp_y_manuales(self):
        request = self._request(confirmar=False, accion="entregados")
        self.assertIn(
            "marcar_pedidos_entregados",
            PedidoWhatsAppAdmin(PedidoWhatsApp, AdminSite()).get_actions(request),
        )
        self.assertIn(
            "marcar_pedidos_entregados",
            PedidoManualAdmin(PedidoManual, AdminSite()).get_actions(request),
        )
        self.assertNotIn(
            "marcar_pedidos_entregados",
            PedidoEspecialAdmin(PedidoEspecial, AdminSite()).get_actions(request),
        )


class ReportesMensualesTests(TestCase):
    def setUp(self):
        self.restaurante = crear_restaurante("reporte-a")
        self.otro = crear_restaurante("reporte-b")

    def _fecha(self, anio, mes, dia=10):
        return timezone.make_aware(datetime(anio, mes, dia, 12, 0))

    def _whatsapp(self, restaurante, estado, total, numero, fecha, tipo="delivery"):
        pedido = PedidoWhatsApp.objects.create(
            restaurante=restaurante,
            numero_pedido=numero,
            nombre_cliente="Cliente",
            telefono_cliente="+56911111111",
            tipo_entrega=tipo,
            productos_snapshot=[{"nombre": "Hamburguesa", "cantidad": 2}],
            total=total,
            estado=estado,
            mensaje_whatsapp_generado="mensaje",
            whatsapp_destino="+56922222222",
        )
        PedidoWhatsApp.objects.filter(pk=pedido.pk).update(fecha_creacion=fecha)
        return pedido

    def test_snapshot_excluye_cancelados_y_otros_tenants_sin_duplicar(self):
        fecha = self._fecha(2026, 10)
        self._whatsapp(self.restaurante, PedidoWhatsApp.ESTADO_ENTREGADO, 10000, 1, fecha)
        self._whatsapp(self.restaurante, PedidoWhatsApp.ESTADO_CANCELADO, 9000, 2, fecha)
        self._whatsapp(self.otro, PedidoWhatsApp.ESTADO_ENTREGADO, 99000, 1, fecha)

        reporte, creado = guardar_reporte_mensual(self.restaurante, 2026, 10)
        self.assertTrue(creado)
        self.assertEqual(reporte.resumen["total_pedidos"], 2)
        self.assertEqual(reporte.resumen["pedidos_cancelados"], 1)
        self.assertEqual(reporte.resumen["monto_pedidos_no_cancelados"], 10000)
        self.assertEqual(reporte.datos["productos_mas_solicitados"][0]["cantidad"], 2)
        self.assertIn("no registra un estado de pago", reporte.datos["criterio_monetario"])

    def test_guardado_es_idempotente_y_snapshot_no_cambia(self):
        fecha = self._fecha(2026, 10)
        pedido = self._whatsapp(
            self.restaurante, PedidoWhatsApp.ESTADO_ENTREGADO, 10000, 1, fecha
        )
        primero, creado = guardar_reporte_mensual(self.restaurante, 2026, 10)
        self.assertTrue(creado)
        PedidoWhatsApp.objects.filter(pk=pedido.pk).update(total=50000)
        segundo, creado = guardar_reporte_mensual(self.restaurante, 2026, 10)
        self.assertFalse(creado)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(segundo.resumen["monto_pedidos_no_cancelados"], 10000)
        regenerado, escrito = guardar_reporte_mensual(
            self.restaurante, 2026, 10, regenerar=True
        )
        self.assertTrue(escrito)
        self.assertEqual(regenerado.resumen["monto_pedidos_no_cancelados"], 50000)

    def test_comando_genera_ceros_omite_inactivos_y_no_duplica(self):
        inactivo = crear_restaurante("inactivo", activo=False)
        salida = StringIO()
        call_command("generar_reportes_mensuales", periodo="2026-10", stdout=salida)
        self.assertTrue(
            ReporteMetrica.objects.filter(
                restaurante=self.restaurante, periodo_mes="2026-10", resumen__total_pedidos=0
            ).exists()
        )
        self.assertFalse(ReporteMetrica.objects.filter(restaurante=inactivo).exists())
        call_command("generar_reportes_mensuales", periodo="2026-10", stdout=salida)
        self.assertEqual(
            ReporteMetrica.objects.filter(restaurante=self.restaurante, periodo_mes="2026-10").count(),
            1,
        )
        call_command(
            "generar_reportes_mensuales",
            periodo="2026-10",
            include_inactive=True,
            stdout=salida,
        )
        self.assertTrue(ReporteMetrica.objects.filter(restaurante=inactivo).exists())

    def test_mes_anterior_cambia_de_anio(self):
        from datetime import date

        self.assertEqual(mes_anterior(date(2026, 1, 15)), (2025, 12))

    def test_admin_reportes_aisla_tenant_y_descarga_snapshot_csv(self):
        reporte, _ = guardar_reporte_mensual(self.restaurante, 2026, 10)
        guardar_reporte_mensual(self.otro, 2026, 10)
        staff = User.objects.create_user("reportes", password="clave-segura", is_staff=True)
        staff.user_permissions.add(
            Permission.objects.get(codename="view_reportemetrica")
        )
        UsuarioRestaurante.objects.create(
            user=staff, restaurante=self.restaurante, rol="admin", activo=True
        )
        request = RequestFactory().get("/admin/menu/reportemetrica/")
        request.user = staff
        admin_model = ReporteMetricaAdmin(ReporteMetrica, AdminSite())
        self.assertEqual(admin_model.get_queryset(request).count(), 1)
        respuesta = admin_model.descargar_reporte_csv(request, reporte.pk)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("monto_pedidos_no_cancelados", respuesta.content.decode("utf-8-sig"))
