from datetime import datetime, time
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status

from .models import (
    HorarioAtencion,
    PedidoEspecial,
    PedidoManual,
    PedidoWhatsApp,
    RestaurantePedidoSecuencia,
    TurnoOperativo,
)
from .services.metricas.resumen import construir_resumen_metricas
from .services.secuencia_pedidos import obtener_siguiente_numero_pedido
from .services.turnos_operativos import (
    obtener_turno_operativo_actual,
    registrar_apertura_excepcional,
)
from .tests import BaseTestCase


def fecha_local(anio, mes, dia, hora, minuto=0):
    return timezone.make_aware(
        datetime(anio, mes, dia, hora, minuto),
        timezone.get_current_timezone(),
    )


class TurnoOperativoServiceTests(BaseTestCase):
    def configurar_horario(self, dia, apertura=time(18, 0), cierre=time(2, 0)):
        return HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=dia,
            hora_apertura=apertura,
            hora_cierre=cierre,
            cerrado=False,
            activo=True,
        )

    def test_horario_que_cruza_medianoche_mantiene_el_mismo_turno(self):
        self.configurar_horario(6)
        inicio = fecha_local(2026, 7, 11, 18)
        madrugada = fecha_local(2026, 7, 12, 1, 30)

        turno_inicio = obtener_turno_operativo_actual(self.restaurante, ahora=inicio)
        turno_madrugada = obtener_turno_operativo_actual(self.restaurante, ahora=madrugada)

        self.assertEqual(turno_inicio.turno.id, turno_madrugada.turno.id)
        self.assertEqual(timezone.localtime(turno_inicio.inicio), inicio)
        self.assertEqual(
            timezone.localtime(turno_inicio.fin),
            fecha_local(2026, 7, 12, 2),
        )

    def test_horario_diurno_usa_inicio_y_fin_del_mismo_dia(self):
        self.configurar_horario(6, apertura=time(10), cierre=time(20))
        ahora = fecha_local(2026, 7, 11, 12)

        turno = obtener_turno_operativo_actual(self.restaurante, ahora=ahora)

        self.assertEqual(timezone.localtime(turno.inicio), fecha_local(2026, 7, 11, 10))
        self.assertEqual(timezone.localtime(turno.fin), fecha_local(2026, 7, 11, 20))

    def test_apertura_excepcional_anticipada_extiende_hasta_cierre_programado(self):
        self.configurar_horario(6)
        apertura = fecha_local(2026, 7, 11, 17)
        turno = registrar_apertura_excepcional(
            self.restaurante,
            ahora=apertura,
            hasta=fecha_local(2026, 7, 11, 19),
        )

        self.assertEqual(timezone.localtime(turno.inicio), apertura)
        self.assertEqual(
            timezone.localtime(turno.fin_programado),
            fecha_local(2026, 7, 12, 2),
        )
        self.assertEqual(
            turno.origen_inicio,
            TurnoOperativo.ORIGEN_APERTURA_EXCEPCIONAL,
        )

    def test_cierre_temporal_y_reapertura_no_crean_otro_turno(self):
        self.configurar_horario(6)
        turno = registrar_apertura_excepcional(
            self.restaurante,
            ahora=fecha_local(2026, 7, 11, 17),
            hasta=fecha_local(2026, 7, 11, 19),
        )
        self.restaurante.abierto = False
        self.restaurante.save(update_fields=["abierto"])

        durante_cierre = obtener_turno_operativo_actual(
            self.restaurante,
            ahora=fecha_local(2026, 7, 11, 20),
        )
        self.restaurante.abierto = True
        self.restaurante.save(update_fields=["abierto"])
        reapertura = obtener_turno_operativo_actual(
            self.restaurante,
            ahora=fecha_local(2026, 7, 11, 20, 30),
        )

        self.assertEqual(turno.id, durante_cierre.turno.id)
        self.assertEqual(turno.id, reapertura.turno.id)
        self.assertEqual(
            TurnoOperativo.objects.filter(
                restaurante=self.restaurante,
                cerrado=False,
            ).count(),
            1,
        )

    def test_caso_completo_apertura_cierre_y_reapertura_desde_dashboard(self):
        self.configurar_horario(6)
        self.client.force_authenticate(user=self.dueno)
        apertura = fecha_local(2026, 7, 11, 17)

        with (
            patch("menu.views.now", return_value=apertura),
            patch("menu.services.turnos_operativos.timezone.now", return_value=apertura),
        ):
            respuesta_apertura = self.client.patch(
                "/api/mi-restaurante/estado-apertura/",
                {"abierto": True, "forzar_fuera_de_horario": True},
                format="json",
            )

        cierre_temporal = fecha_local(2026, 7, 11, 20)
        with (
            patch("menu.views.now", return_value=cierre_temporal),
            patch(
                "menu.services.turnos_operativos.timezone.now",
                return_value=cierre_temporal,
            ),
        ):
            respuesta_cierre = self.client.patch(
                "/api/mi-restaurante/estado-apertura/",
                {"abierto": False},
                format="json",
            )

        reapertura = fecha_local(2026, 7, 11, 20, 30)
        with (
            patch("menu.views.now", return_value=reapertura),
            patch(
                "menu.services.turnos_operativos.timezone.now",
                return_value=reapertura,
            ),
        ):
            respuesta_reapertura = self.client.patch(
                "/api/mi-restaurante/estado-apertura/",
                {"abierto": True},
                format="json",
            )

        turno = TurnoOperativo.objects.get(restaurante=self.restaurante)
        self.assertEqual(respuesta_apertura.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta_cierre.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta_reapertura.status_code, status.HTTP_200_OK)
        self.assertEqual(timezone.localtime(turno.inicio), apertura)
        self.assertEqual(
            timezone.localtime(turno.fin_programado),
            fecha_local(2026, 7, 12, 2),
        )
        self.assertFalse(turno.cerrado)

    def test_al_llegar_al_cierre_programado_finaliza_el_turno(self):
        self.configurar_horario(6)
        turno = obtener_turno_operativo_actual(
            self.restaurante,
            ahora=fecha_local(2026, 7, 11, 18),
        ).turno

        resultado = obtener_turno_operativo_actual(
            self.restaurante,
            ahora=fecha_local(2026, 7, 12, 2),
        )

        turno.refresh_from_db()
        self.assertTrue(turno.cerrado)
        self.assertFalse(resultado.activo)
        self.assertIsNone(
            TurnoOperativo.objects.filter(
                restaurante=self.restaurante,
                cerrado=False,
            ).first()
        )

    def test_dia_sin_horario_usa_fin_de_apertura_excepcional(self):
        self.configurar_horario(1)
        apertura = fecha_local(2026, 7, 11, 12)
        fin_excepcion = fecha_local(2026, 7, 11, 14)

        turno = registrar_apertura_excepcional(
            self.restaurante,
            ahora=apertura,
            hasta=fin_excepcion,
        )

        self.assertEqual(timezone.localtime(turno.inicio), apertura)
        self.assertEqual(timezone.localtime(turno.fin_programado), fin_excepcion)

    def test_cada_restaurante_resuelve_su_propio_turno(self):
        self.configurar_horario(6)
        HorarioAtencion.objects.create(
            restaurante=self.otro_restaurante,
            dia=6,
            hora_apertura=time(10),
            hora_cierre=time(20),
            cerrado=False,
            activo=True,
        )

        nocturno = obtener_turno_operativo_actual(
            self.restaurante,
            ahora=fecha_local(2026, 7, 11, 19),
        )
        diurno = obtener_turno_operativo_actual(
            self.otro_restaurante,
            ahora=fecha_local(2026, 7, 11, 19),
        )

        self.assertNotEqual(nocturno.turno.restaurante_id, diurno.turno.restaurante_id)
        self.assertNotEqual(nocturno.inicio, diurno.inicio)


class TurnoOperativoPanelMetricasTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.restaurante.pedidos_pos = True
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.save(
            update_fields=[
                "pedidos_pos",
                "solicitudes_especiales_activas",
                "carrito_whatsapp_activo",
            ]
        )
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=6,
            hora_apertura=time(18),
            hora_cierre=time(2),
            cerrado=False,
            activo=True,
        )
        self.turno = registrar_apertura_excepcional(
            self.restaurante,
            ahora=fecha_local(2026, 7, 11, 17),
            hasta=fecha_local(2026, 7, 11, 19),
        )
        self.client.force_authenticate(user=self.dueno)

    def crear_whatsapp(self, numero, fecha, total=1000):
        pedido = PedidoWhatsApp.objects.create(
            restaurante=self.restaurante,
            numero_pedido=numero,
            nombre_cliente=f"WhatsApp {numero}",
            telefono_cliente="56911111111",
            tipo_entrega=PedidoWhatsApp.TIPO_RETIRO_LOCAL,
            productos_snapshot=[
                {
                    "nombre": "Producto",
                    "cantidad": 1,
                    "precio_unitario": total,
                    "subtotal": total,
                }
            ],
            total=total,
            estado=PedidoWhatsApp.ESTADO_ENTREGADO,
            mensaje_whatsapp_generado="Pedido",
            whatsapp_destino="56911111111",
        )
        PedidoWhatsApp.objects.filter(id=pedido.id).update(fecha_creacion=fecha)
        pedido.refresh_from_db()
        return pedido

    def crear_manual(self, numero, fecha, total=2000):
        pedido = PedidoManual.objects.create(
            restaurante=self.restaurante,
            numero_pedido=numero,
            nombre_cliente=f"Menly {numero}",
            tipo_entrega=PedidoManual.TIPO_RETIRO,
            subtotal=total,
            total=total,
            estado=PedidoManual.ESTADO_ENTREGADO,
        )
        PedidoManual.objects.filter(id=pedido.id).update(fecha_creacion=fecha)
        pedido.refresh_from_db()
        return pedido

    def crear_especial(self, numero, fecha, total=3000):
        pedido = PedidoEspecial.objects.create(
            restaurante=self.restaurante,
            numero_pedido=numero,
            nombre_cliente=f"Especial {numero}",
            telefono_cliente="56911111111",
            items=[],
            total=total,
            fecha_entrega=timezone.localdate(),
            estado=PedidoEspecial.ESTADO_ENTREGADO,
        )
        PedidoEspecial.objects.filter(id=pedido.id).update(fecha_creacion=fecha)
        pedido.refresh_from_db()
        return pedido

    def test_panel_muestra_solo_turno_actual_y_historico_sigue_accesible(self):
        anterior = self.crear_whatsapp(55, fecha_local(2026, 7, 11, 16, 59))
        actual = self.crear_whatsapp(56, fecha_local(2026, 7, 12, 0, 30))

        with patch(
            "menu.services.turnos_operativos.timezone.now",
            return_value=fecha_local(2026, 7, 12, 1),
        ):
            operativo = self.client.get(
                "/api/mi-restaurante/pedidos/whatsapp/",
                {"scope": "turno_actual"},
            )
            historico = self.client.get(
                "/api/mi-restaurante/pedidos/whatsapp/",
                {"scope": "historico"},
            )

        self.assertEqual(operativo.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [pedido["id"] for pedido in operativo.data["results"]],
            [actual.id],
        )
        self.assertEqual(historico.data["count"], 2)
        self.assertIn(anterior.id, [pedido["id"] for pedido in historico.data["results"]])

    def test_paginacion_se_aplica_dentro_del_turno(self):
        for numero in range(1, 26):
            self.crear_manual(
                numero,
                fecha_local(2026, 7, 11, 17, numero),
                total=100,
            )

        with patch(
            "menu.services.turnos_operativos.timezone.now",
            return_value=fecha_local(2026, 7, 11, 23),
        ):
            pagina_1 = self.client.get(
                "/api/mi-restaurante/pedidos/manuales/",
                {"page": 1, "scope": "turno_actual"},
            )
            pagina_3 = self.client.get(
                "/api/mi-restaurante/pedidos/manuales/",
                {"page": 3, "scope": "turno_actual"},
            )

        self.assertEqual(pagina_1.data["count"], 25)
        self.assertEqual(len(pagina_1.data["results"]), 10)
        self.assertEqual(len(pagina_3.data["results"]), 5)

    def test_metricas_incluyen_antes_y_despues_de_medianoche_hasta_el_cierre(self):
        self.crear_whatsapp(1, fecha_local(2026, 7, 11, 16, 59), total=9000)
        self.crear_whatsapp(2, fecha_local(2026, 7, 11, 17), total=1000)
        self.crear_manual(3, fecha_local(2026, 7, 12, 0, 30), total=2000)
        self.crear_especial(4, fecha_local(2026, 7, 12, 1, 59), total=3000)
        self.crear_whatsapp(5, fecha_local(2026, 7, 12, 2), total=8000)

        ahora = fecha_local(2026, 7, 12, 1, 59)
        with (
            patch("menu.services.turnos_operativos.timezone.now", return_value=ahora),
            patch("menu.services.metricas.pedidos.now", return_value=ahora),
        ):
            metricas = construir_resumen_metricas(self.restaurante)

        self.assertEqual(metricas["ventas"]["venta_real_hoy"], 6000)
        self.assertEqual(metricas["pedidos"]["pedidos_creados_hoy"], 3)
        self.assertEqual(metricas["canales"]["whatsapp"]["pedidos_creados_hoy"], 1)
        self.assertEqual(metricas["canales"]["menly"]["pedidos_creados_hoy"], 1)
        self.assertEqual(metricas["canales"]["especiales"]["pedidos_creados_hoy"], 1)

    def test_cierre_temporal_y_reapertura_conservan_metricas_y_correlativo(self):
        RestaurantePedidoSecuencia.objects.create(
            restaurante=self.restaurante,
            ultimo_numero=56,
        )
        self.crear_whatsapp(56, fecha_local(2026, 7, 11, 19), total=1000)
        self.restaurante.abierto = False
        self.restaurante.save(update_fields=["abierto"])

        durante_cierre = fecha_local(2026, 7, 11, 20)
        with (
            patch("menu.services.turnos_operativos.timezone.now", return_value=durante_cierre),
            patch("menu.services.metricas.pedidos.now", return_value=durante_cierre),
        ):
            metricas_cerrado = construir_resumen_metricas(self.restaurante)

        self.restaurante.abierto = True
        self.restaurante.save(update_fields=["abierto"])
        reapertura = fecha_local(2026, 7, 11, 20, 30)
        with (
            patch("menu.services.turnos_operativos.timezone.now", return_value=reapertura),
            patch("menu.services.metricas.pedidos.now", return_value=reapertura),
        ):
            metricas_reabierto = construir_resumen_metricas(self.restaurante)

        self.assertEqual(metricas_cerrado["ventas"]["venta_real_hoy"], 1000)
        self.assertEqual(metricas_reabierto["ventas"]["venta_real_hoy"], 1000)
        self.assertEqual(
            RestaurantePedidoSecuencia.objects.get(
                restaurante=self.restaurante
            ).ultimo_numero,
            56,
        )
    def test_turno_siguiente_empieza_vacio_y_correlativo_continua(self):
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=7,
            hora_apertura=time(18),
            hora_cierre=time(2),
            cerrado=False,
            activo=True,
        )
        RestaurantePedidoSecuencia.objects.create(
            restaurante=self.restaurante,
            ultimo_numero=56,
        )
        self.crear_whatsapp(56, fecha_local(2026, 7, 12, 1, 59))

        siguiente_inicio = fecha_local(2026, 7, 12, 18)
        with patch(
            "menu.services.turnos_operativos.timezone.now",
            return_value=siguiente_inicio,
        ):
            respuesta = self.client.get(
                "/api/mi-restaurante/pedidos/whatsapp/",
                {"scope": "turno_actual"},
            )

        self.assertEqual(respuesta.data["count"], 0)
        self.assertEqual(
            RestaurantePedidoSecuencia.objects.get(
                restaurante=self.restaurante
            ).ultimo_numero,
            56,
        )
        self.assertEqual(obtener_siguiente_numero_pedido(self.restaurante), 57)
