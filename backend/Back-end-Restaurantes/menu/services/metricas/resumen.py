from .pedidos import metricas_pedidos_combinadas
from .productos import metricas_productos
from .reservas import metricas_reservas


def construir_resumen_metricas(restaurante):
    """Payload canónico para Dashboard, Pedidos y Métricas."""
    pedidos = metricas_pedidos_combinadas(restaurante)
    productos = metricas_productos(restaurante)
    reservas = (
        metricas_reservas(restaurante)
        if restaurante.reservas_activas
        else {
            "reservas_hoy": 0,
            "reservas_creadas_mes": 0,
            "reservas_programadas_mes": 0,
            "reservas_pendientes_futuras": 0,
            "reservas_canceladas_mes": 0,
        }
    )

    return {
        **pedidos,
        "reservas": reservas,
        "productos": productos,
    }


def construir_payload_pedidos_compat(restaurante):
    """Compatibilidad temporal para /pedidos/metricas usando la capa canónica."""
    payload = construir_resumen_metricas(restaurante)
    whatsapp = payload["canales"]["whatsapp"]
    especiales = payload["canales"]["especiales"]
    ventas = payload["ventas"]
    pedidos = payload["pedidos"]
    productos = payload["productos"]

    payload["whatsapp"] = {
        "venta_diaria_total": whatsapp["venta_real_hoy"],
        "venta_semanal_total": whatsapp.get("venta_real_semana", 0),
        "venta_mensual_total": whatsapp["venta_real_mes"],
        "pedidos_diarios": whatsapp["pedidos_creados_hoy"],
        "pedidos_mes": whatsapp["pedidos_creados_mes"],
        "pedidos_creados_mes": whatsapp["pedidos_creados_mes"],
        "pedidos_finalizados_mes": whatsapp["pedidos_finalizados_mes"],
        "pedidos_pendientes": whatsapp["pedidos_activos"],
        "pedidos_activos": whatsapp["pedidos_activos"],
        "pedidos_cancelados": whatsapp["pedidos_cancelados_mes"],
        "producto_mas_vendido_dia": productos["mas_vendido_hoy"],
        "producto_mas_vendido_mes": productos["mas_vendido_mes"],
    }
    payload["especiales"] = {
        "pedidos_diarios": especiales["pedidos_creados_hoy"],
        "total_diario": especiales["venta_real_hoy"],
        "pedidos_mes": especiales["pedidos_creados_mes"],
        "pedidos_creados_mes": especiales["pedidos_creados_mes"],
        "pedidos_finalizados_mes": especiales["pedidos_finalizados_mes"],
        "total_mensual": especiales["venta_real_mes"],
        "pedidos_pendientes": especiales["pedidos_activos"],
        "pedidos_activos": especiales["pedidos_activos"],
        "pedidos_cancelados": especiales["pedidos_cancelados_mes"],
    }
    payload["resumen"] = {
        "venta_diaria_wsp": whatsapp["venta_real_hoy"],
        "pedidos_wsp_hoy": whatsapp["pedidos_creados_hoy"],
        "venta_especiales_mes": especiales["venta_real_mes"],
        "pedidos_especiales_mes": especiales["pedidos_creados_mes"],
        "venta_total_mes": ventas["venta_real_mes"],
        "pedidos_total_mes": pedidos["pedidos_finalizados_mes"],
        "pedidos_creados_mes": pedidos["pedidos_creados_mes"],
        "pedidos_finalizados_mes": pedidos["pedidos_finalizados_mes"],
        "pedidos_cancelados_mes": pedidos["pedidos_cancelados_mes"],
        "ticket_promedio_mes": ventas["ticket_promedio_mes"],
        "tasa_cancelacion_mes": pedidos["tasa_cancelacion_mes"],
    }
    payload["visitas"] = {
        "clicks_productos_total": productos["clicks_total"],
    }
    return payload
