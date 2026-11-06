from datetime import date, datetime
from io import StringIO
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.core.management import call_command, CommandError
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
    EjecucionReportesMensuales,
    PedidoEspecial,
    PedidoManual,
    PedidoManualItem,
    PedidoWhatsApp,
    ReporteMetrica,
    Reserva,
    Restaurante,
    UsuarioRestaurante,
)
from menu.services.estados_pedidos import TransicionEstadoInvalida, cambiar_estado_pedido
from menu.services.reportes_mensuales import _limites_mes, guardar_reporte_mensual
from menu.services.reportes_mensuales import generar_reportes_pendientes
from menu.services.metricas.pedidos import metricas_pedidos_combinadas


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

    def test_limites_mensuales_cubren_28_29_30_31_dias_y_dst_chile(self):
        casos = [
            ((2026, 2), date(2026, 2, 1), date(2026, 3, 1)),
            ((2024, 2), date(2024, 2, 1), date(2024, 3, 1)),
            ((2026, 4), date(2026, 4, 1), date(2026, 5, 1)),
            ((2026, 10), date(2026, 10, 1), date(2026, 11, 1)),
        ]
        for (anio, mes), esperado_inicio, esperado_fin in casos:
            with self.subTest(anio=anio, mes=mes):
                inicio, siguiente = _limites_mes(anio, mes)
                self.assertEqual(inicio.date(), esperado_inicio)
                self.assertEqual(siguiente.date(), esperado_fin)
                self.assertEqual(str(inicio.tzinfo), "America/Santiago")

        inicio_abril, inicio_mayo = _limites_mes(2026, 4)
        self.assertNotEqual(inicio_abril.utcoffset(), inicio_mayo.utcoffset())

    def test_modo_programado_cierra_octubre_noviembre_y_diciembre(self):
        Restaurante.objects.filter(pk=self.restaurante.pk).update(
            fecha_creacion=self._fecha(2026, 10, 15)
        )
        fechas = [date(2026, 11, 1), date(2026, 12, 1), date(2027, 1, 1)]
        for fecha_ejecucion in fechas:
            with patch(
                "menu.management.commands.generar_reportes_mensuales.timezone.localdate",
                return_value=fecha_ejecucion,
            ), patch(
                "menu.services.reportes_mensuales.timezone.localdate",
                return_value=fecha_ejecucion,
            ):
                call_command(
                    "generar_reportes_mensuales",
                    scheduled=True,
                    include_inactive=True,
                    stdout=StringIO(),
                )

        self.assertEqual(
            set(
                ReporteMetrica.objects.filter(restaurante=self.restaurante)
                .values_list("periodo_mes", flat=True)
            ),
            {"2026-10", "2026-11", "2026-12"},
        )
        ejecuciones = EjecucionReportesMensuales.objects.filter(
            modo=EjecucionReportesMensuales.MODO_PROGRAMADO
        )
        self.assertEqual(ejecuciones.count(), 3)
        self.assertFalse(
            ejecuciones.exclude(
                estado=EjecucionReportesMensuales.ESTADO_EXITOSO
            ).exists()
        )

    def test_cierre_programado_registra_error_y_recupera_en_reintento(self):
        Restaurante.objects.filter(pk__in=[self.restaurante.pk, self.otro.pk]).update(
            fecha_creacion=self._fecha(2026, 10, 15)
        )
        original = guardar_reporte_mensual

        def fallar_un_restaurante(restaurante, anio, mes, regenerar=False):
            if restaurante.pk == self.restaurante.pk:
                raise RuntimeError("fallo controlado")
            return original(restaurante, anio, mes, regenerar=regenerar)

        with patch(
            "menu.management.commands.generar_reportes_mensuales.timezone.localdate",
            return_value=date(2026, 11, 2),
        ), patch(
            "menu.services.reportes_mensuales.timezone.localdate",
            return_value=date(2026, 11, 2),
        ), patch(
            "menu.services.reportes_mensuales.guardar_reporte_mensual",
            side_effect=fallar_un_restaurante,
        ):
            with self.assertRaises(CommandError):
                call_command(
                    "generar_reportes_mensuales",
                    scheduled=True,
                    include_inactive=True,
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

        primera = EjecucionReportesMensuales.objects.first()
        self.assertEqual(primera.estado, EjecucionReportesMensuales.ESTADO_PARCIAL)
        self.assertEqual(primera.cantidad_errores, 1)
        self.assertFalse(
            ReporteMetrica.objects.filter(
                restaurante=self.restaurante, periodo_mes="2026-10"
            ).exists()
        )

        with patch(
            "menu.management.commands.generar_reportes_mensuales.timezone.localdate",
            return_value=date(2026, 11, 3),
        ), patch(
            "menu.services.reportes_mensuales.timezone.localdate",
            return_value=date(2026, 11, 3),
        ):
            call_command(
                "generar_reportes_mensuales",
                scheduled=True,
                include_inactive=True,
                stdout=StringIO(),
            )

        self.assertTrue(
            ReporteMetrica.objects.filter(
                restaurante=self.restaurante, periodo_mes="2026-10"
            ).exists()
        )
        self.assertEqual(
            EjecucionReportesMensuales.objects.first().estado,
            EjecucionReportesMensuales.ESTADO_EXITOSO,
        )

    def test_cierre_programado_registra_fallo_general(self):
        with patch(
            "menu.management.commands.generar_reportes_mensuales.generar_reportes_pendientes",
            side_effect=RuntimeError("base temporalmente no disponible"),
        ):
            with self.assertRaisesRegex(RuntimeError, "temporalmente"):
                call_command(
                    "generar_reportes_mensuales",
                    scheduled=True,
                    stdout=StringIO(),
                )

        ejecucion = EjecucionReportesMensuales.objects.get()
        self.assertEqual(
            ejecucion.estado,
            EjecucionReportesMensuales.ESTADO_FALLIDO,
        )
        self.assertEqual(ejecucion.cantidad_errores, 1)
        self.assertIsNotNone(ejecucion.fecha_fin)

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

    def test_reporte_incluye_entregados_pendientes_y_reservas(self):
        fecha = self._fecha(2026, 10)
        self._whatsapp(
            self.restaurante, PedidoWhatsApp.ESTADO_ENTREGADO, 10000, 1, fecha
        )
        self._whatsapp(
            self.restaurante, PedidoWhatsApp.ESTADO_EN_PREPARACION, 5000, 2, fecha
        )
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Reserva octubre",
            telefono="+56933333333",
            fecha=date(2026, 10, 20),
            hora=datetime.strptime("20:00", "%H:%M").time(),
            cantidad_personas=2,
        )
        reporte, _ = guardar_reporte_mensual(self.restaurante, 2026, 10)
        self.assertEqual(reporte.resumen["pedidos_entregados"], 1)
        self.assertEqual(reporte.resumen["pedidos_pendientes"], 1)
        self.assertEqual(reporte.datos["reservas"]["total"], 1)

    def test_backfill_genera_octubre_y_meses_cero_desde_creacion(self):
        creado_septiembre = self._fecha(2026, 9, 15)
        Restaurante.objects.filter(pk=self.restaurante.pk).update(
            fecha_creacion=creado_septiembre
        )
        self.restaurante.refresh_from_db()
        resultado = generar_reportes_pendientes(
            restaurantes=Restaurante.objects.filter(pk=self.restaurante.pk),
            hasta=date(2026, 11, 5),
        )
        self.assertEqual(resultado["generados"], 2)
        self.assertEqual(resultado["errores"], [])
        self.assertEqual(
            set(
                ReporteMetrica.objects.filter(restaurante=self.restaurante)
                .values_list("periodo_mes", flat=True)
            ),
            {"2026-09", "2026-10"},
        )
        repetido = generar_reportes_pendientes(
            restaurantes=Restaurante.objects.filter(pk=self.restaurante.pk),
            hasta=date(2026, 11, 5),
        )
        self.assertEqual(repetido["generados"], 0)
        self.assertEqual(repetido["existentes"], 2)

    def test_comando_backfill_ejecuta_recuperacion_sin_intervencion_web(self):
        Restaurante.objects.filter(pk=self.restaurante.pk).update(
            fecha_creacion=self._fecha(2026, 10, 15)
        )
        salida = StringIO()
        with patch(
            "menu.services.reportes_mensuales.timezone.localdate",
            return_value=date(2026, 11, 5),
        ):
            call_command(
                "generar_reportes_mensuales",
                backfill=True,
                stdout=salida,
            )
        self.assertTrue(
            ReporteMetrica.objects.filter(
                restaurante=self.restaurante,
                periodo_mes="2026-10",
            ).exists()
        )
        self.assertIn("Recuperación histórica", salida.getvalue())

    def _admin_request(self, data=None, usuario=None):
        request = RequestFactory().post("/admin/menu/reportemetrica/", data or {})
        superuser = User.objects.filter(username="report-root").first()
        if not superuser:
            superuser = User.objects.create_superuser(
                "report-root", "report-root@example.com", "clave-segura"
            )
        request.user = usuario or superuser
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_admin_genera_octubre_y_exige_permiso(self):
        admin_model = ReporteMetricaAdmin(ReporteMetrica, AdminSite())
        request = self._admin_request({
            "restaurante": self.restaurante.pk,
            "anio": 2026,
            "mes": 10,
        })
        response = admin_model.generar_reporte_mensual(request)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ReporteMetrica.objects.filter(
                restaurante=self.restaurante,
                periodo_mes="2026-10",
            ).exists()
        )

        pendiente = crear_restaurante("reporte-pendiente-admin")
        Restaurante.objects.filter(pk=pendiente.pk).update(
            fecha_creacion=self._fecha(2026, 10, 15)
        )
        response = admin_model.generar_reportes_pendientes_view(
            self._admin_request({"confirmar": "1"})
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ReporteMetrica.objects.filter(
                restaurante=pendiente,
                periodo_mes="2026-10",
            ).exists()
        )

        staff = User.objects.create_user(
            "sin-permiso-reportes", password="clave-segura", is_staff=True
        )
        UsuarioRestaurante.objects.create(
            user=staff, restaurante=self.restaurante, rol="admin", activo=True
        )
        with self.assertRaises(PermissionDenied):
            admin_model.generar_reportes_pendientes_view(
                self._admin_request({"confirmar": "1"}, usuario=staff)
            )

    def test_admin_regenera_solo_con_confirmacion_explicita(self):
        fecha = self._fecha(2026, 10)
        pedido = self._whatsapp(
            self.restaurante, PedidoWhatsApp.ESTADO_ENTREGADO, 10000, 1, fecha
        )
        reporte, _ = guardar_reporte_mensual(self.restaurante, 2026, 10)
        PedidoWhatsApp.objects.filter(pk=pedido.pk).update(total=30000)
        admin_model = ReporteMetricaAdmin(ReporteMetrica, AdminSite())

        confirmacion = admin_model.regenerar_reportes_mensuales(
            self._admin_request(),
            ReporteMetrica.objects.filter(pk=reporte.pk),
        )
        self.assertEqual(
            confirmacion.template_name,
            "admin/reportes_regenerar_confirmacion.html",
        )
        reporte.refresh_from_db()
        self.assertEqual(reporte.resumen["monto_pedidos_no_cancelados"], 10000)

        admin_model.regenerar_reportes_mensuales(
            self._admin_request({"confirmar_regeneracion": "1"}),
            ReporteMetrica.objects.filter(pk=reporte.pk),
        )
        reporte.refresh_from_db()
        self.assertEqual(reporte.resumen["monto_pedidos_no_cancelados"], 30000)


class MetricasCalendarioTests(TestCase):
    def setUp(self):
        self.restaurante = crear_restaurante("metricas-calendario")
        self.otro = crear_restaurante("metricas-ajeno")

    def _poner_fecha(self, pedido, anio, mes, dia):
        fecha = timezone.make_aware(
            datetime(anio, mes, dia, 12, 0),
            timezone.get_current_timezone(),
        )
        pedido.__class__.objects.filter(pk=pedido.pk).update(fecha_creacion=fecha)

    def _whatsapp(self, restaurante, estado, total, numero, anio, mes, dia):
        pedido = PedidoWhatsApp.objects.create(
            restaurante=restaurante,
            numero_pedido=numero,
            nombre_cliente="Cliente",
            telefono_cliente="+56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[],
            total=total,
            estado=estado,
            mensaje_whatsapp_generado="mensaje",
            whatsapp_destino="+56922222222",
        )
        self._poner_fecha(pedido, anio, mes, dia)
        return pedido

    def test_dia_semana_y_mes_usan_calendario_tenant_y_excluyen_cancelados(self):
        self._whatsapp(
            self.restaurante, PedidoWhatsApp.ESTADO_ENTREGADO,
            120029, 1, 2026, 10, 30,
        )
        manual = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=2,
            estado=PedidoManual.ESTADO_ENTREGADO,
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            total=50000,
        )
        self._poner_fecha(manual, 2026, 11, 1)
        self._whatsapp(
            self.restaurante, PedidoWhatsApp.ESTADO_ENTREGADO,
            28331, 3, 2026, 11, 5,
        )
        self._whatsapp(
            self.restaurante, PedidoWhatsApp.ESTADO_CANCELADO,
            999999, 4, 2026, 11, 5,
        )
        self._whatsapp(
            self.otro, PedidoWhatsApp.ESTADO_ENTREGADO,
            888888, 1, 2026, 11, 5,
        )

        metricas = metricas_pedidos_combinadas(
            self.restaurante,
            hoy=date(2026, 11, 5),
        )
        self.assertEqual(
            metricas["ventas"]["monto_entregado_dia_calendario"],
            28331,
        )
        self.assertEqual(metricas["ventas"]["venta_real_semana"], 28331)
        self.assertEqual(metricas["ventas"]["venta_real_mes"], 78331)
