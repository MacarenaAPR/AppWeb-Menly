from decimal import Decimal
from datetime import timedelta

from django.db.models import Count, Sum
from django.utils.timezone import localtime, now

from menu.models import PedidoEspecial, PedidoManual, PedidoWhatsApp
from .estados import (
    ESPECIALES_ACTIVOS,
    ESPECIALES_CANCELADOS,
    ESPECIALES_FINALIZADOS,
    MANUALES_ACTIVOS,
    MANUALES_CANCELADOS,
    MANUALES_FINALIZADOS,
    WHATSAPP_ACTIVOS,
    WHATSAPP_CANCELADOS,
    WHATSAPP_FINALIZADOS,
)


def fecha_hoy():
    return localtime(now()).date()


def inicio_mes(fecha=None):
    fecha = fecha or fecha_hoy()
    return fecha.replace(day=1)


def inicio_semana(fecha=None):
    fecha = fecha or fecha_hoy()
    return fecha - timedelta(days=6)


def _filtrar_rango_creacion(queryset, desde=None, hasta=None):
    if desde:
        queryset = queryset.filter(fecha_creacion__date__gte=desde)
    if hasta:
        queryset = queryset.filter(fecha_creacion__date__lte=hasta)
    return queryset


def pedidos_whatsapp_creados(restaurante, desde=None, hasta=None):
    return _filtrar_rango_creacion(
        PedidoWhatsApp.objects.filter(restaurante=restaurante),
        desde,
        hasta,
    )


def pedidos_especiales_creados(restaurante, desde=None, hasta=None):
    return _filtrar_rango_creacion(
        PedidoEspecial.objects.filter(restaurante=restaurante),
        desde,
        hasta,
    )


def pedidos_manuales_creados(restaurante, desde=None, hasta=None):
    return _filtrar_rango_creacion(
        PedidoManual.objects.filter(restaurante=restaurante),
        desde,
        hasta,
    )


def pedidos_whatsapp_finalizados(restaurante, desde=None, hasta=None):
    return pedidos_whatsapp_creados(restaurante, desde, hasta).filter(
        estado__in=WHATSAPP_FINALIZADOS
    )


def pedidos_especiales_finalizados(restaurante, desde=None, hasta=None):
    return pedidos_especiales_creados(restaurante, desde, hasta).filter(
        estado__in=ESPECIALES_FINALIZADOS
    )


def pedidos_manuales_finalizados(restaurante, desde=None, hasta=None):
    return pedidos_manuales_creados(restaurante, desde, hasta).filter(
        estado__in=MANUALES_FINALIZADOS
    )


def pedidos_whatsapp_cancelados(restaurante, desde=None, hasta=None):
    return pedidos_whatsapp_creados(restaurante, desde, hasta).filter(
        estado__in=WHATSAPP_CANCELADOS
    )


def pedidos_especiales_cancelados(restaurante, desde=None, hasta=None):
    return pedidos_especiales_creados(restaurante, desde, hasta).filter(
        estado__in=ESPECIALES_CANCELADOS
    )


def pedidos_manuales_cancelados(restaurante, desde=None, hasta=None):
    return pedidos_manuales_creados(restaurante, desde, hasta).filter(
        estado__in=MANUALES_CANCELADOS
    )


def pedidos_whatsapp_activos(restaurante):
    return PedidoWhatsApp.objects.filter(
        restaurante=restaurante,
        estado__in=WHATSAPP_ACTIVOS,
    )


def pedidos_especiales_activos(restaurante):
    return PedidoEspecial.objects.filter(
        restaurante=restaurante,
        estado__in=ESPECIALES_ACTIVOS,
    )


def pedidos_manuales_activos(restaurante):
    return PedidoManual.objects.filter(
        restaurante=restaurante,
        estado__in=MANUALES_ACTIVOS,
    )


def sumar_total(queryset):
    total = queryset.aggregate(total=Sum("total"))["total"] or 0
    return int(total)


def contar(queryset):
    return queryset.aggregate(total=Count("id"))["total"] or 0


def venta_real_whatsapp(restaurante, desde=None, hasta=None):
    """Venta real WhatsApp: solo pedidos entregados."""
    return sumar_total(pedidos_whatsapp_finalizados(restaurante, desde, hasta))


def venta_real_especiales(restaurante, desde=None, hasta=None):
    """Venta real especiales: pedidos entregados o completados."""
    return sumar_total(pedidos_especiales_finalizados(restaurante, desde, hasta))


def venta_real_manuales(restaurante, desde=None, hasta=None):
    """Venta real Menly: solo pedidos entregados."""
    return sumar_total(pedidos_manuales_finalizados(restaurante, desde, hasta))


def venta_real_total(restaurante, desde=None, hasta=None):
    return (
        venta_real_whatsapp(restaurante, desde, hasta)
        + venta_real_especiales(restaurante, desde, hasta)
        + venta_real_manuales(restaurante, desde, hasta)
    )


def metricas_canal_whatsapp(restaurante, desde_mes=None, hoy=None):
    hoy = hoy or fecha_hoy()
    desde_mes = desde_mes or inicio_mes(hoy)
    desde_semana = hoy - timedelta(days=6)

    creados_hoy = pedidos_whatsapp_creados(restaurante, hoy, hoy)
    creados_mes = pedidos_whatsapp_creados(restaurante, desde_mes, hoy)
    finalizados_hoy = pedidos_whatsapp_finalizados(restaurante, hoy, hoy)
    finalizados_mes = pedidos_whatsapp_finalizados(restaurante, desde_mes, hoy)
    finalizados_semana = pedidos_whatsapp_finalizados(restaurante, desde_semana, hoy)
    cancelados_mes = pedidos_whatsapp_cancelados(restaurante, desde_mes, hoy)
    activos = pedidos_whatsapp_activos(restaurante)

    return {
        "venta_real_hoy": sumar_total(finalizados_hoy),
        "venta_real_semana": sumar_total(finalizados_semana),
        "venta_real_mes": sumar_total(finalizados_mes),
        "pedidos_creados_hoy": creados_hoy.count(),
        "pedidos_creados_mes": creados_mes.count(),
        "pedidos_finalizados_hoy": finalizados_hoy.count(),
        "pedidos_finalizados_mes": finalizados_mes.count(),
        "pedidos_cancelados_mes": cancelados_mes.count(),
        "pedidos_activos": activos.count(),
    }


def metricas_canal_especiales(restaurante, desde_mes=None, hoy=None):
    hoy = hoy or fecha_hoy()
    desde_mes = desde_mes or inicio_mes(hoy)
    desde_semana = hoy - timedelta(days=6)

    creados_hoy = pedidos_especiales_creados(restaurante, hoy, hoy)
    creados_mes = pedidos_especiales_creados(restaurante, desde_mes, hoy)
    finalizados_hoy = pedidos_especiales_finalizados(restaurante, hoy, hoy)
    finalizados_mes = pedidos_especiales_finalizados(restaurante, desde_mes, hoy)
    finalizados_semana = pedidos_especiales_finalizados(restaurante, desde_semana, hoy)
    cancelados_mes = pedidos_especiales_cancelados(restaurante, desde_mes, hoy)
    activos = pedidos_especiales_activos(restaurante)

    return {
        "venta_real_hoy": sumar_total(finalizados_hoy),
        "venta_real_semana": sumar_total(finalizados_semana),
        "venta_real_mes": sumar_total(finalizados_mes),
        "pedidos_creados_hoy": creados_hoy.count(),
        "pedidos_creados_mes": creados_mes.count(),
        "pedidos_finalizados_hoy": finalizados_hoy.count(),
        "pedidos_finalizados_mes": finalizados_mes.count(),
        "pedidos_cancelados_mes": cancelados_mes.count(),
        "pedidos_activos": activos.count(),
    }


def metricas_canal_manuales(restaurante, desde_mes=None, hoy=None):
    hoy = hoy or fecha_hoy()
    desde_mes = desde_mes or inicio_mes(hoy)
    desde_semana = hoy - timedelta(days=6)

    creados_hoy = pedidos_manuales_creados(restaurante, hoy, hoy)
    vendidos_hoy = creados_hoy.filter(
        origen=PedidoManual.ORIGEN_MENLY
    ).exclude(
        estado=PedidoManual.ESTADO_CANCELADO
    )
    creados_mes = pedidos_manuales_creados(restaurante, desde_mes, hoy)
    finalizados_hoy = pedidos_manuales_finalizados(restaurante, hoy, hoy)
    finalizados_mes = pedidos_manuales_finalizados(restaurante, desde_mes, hoy)
    finalizados_semana = pedidos_manuales_finalizados(restaurante, desde_semana, hoy)
    cancelados_mes = pedidos_manuales_cancelados(restaurante, desde_mes, hoy)
    activos = pedidos_manuales_activos(restaurante)

    return {
        "venta_real_hoy": sumar_total(finalizados_hoy),
        "venta_diaria_menly": sumar_total(vendidos_hoy),
        "venta_real_semana": sumar_total(finalizados_semana),
        "venta_real_mes": sumar_total(finalizados_mes),
        "cantidad_pedidos_menly_hoy": vendidos_hoy.count(),
        "pedidos_creados_hoy": creados_hoy.count(),
        "pedidos_creados_mes": creados_mes.count(),
        "pedidos_finalizados_hoy": finalizados_hoy.count(),
        "pedidos_finalizados_mes": finalizados_mes.count(),
        "pedidos_cancelados_mes": cancelados_mes.count(),
        "pedidos_activos": activos.count(),
    }


def metricas_pedidos_combinadas(restaurante, hoy=None):
    hoy = hoy or fecha_hoy()
    desde_mes = inicio_mes(hoy)
    whatsapp = metricas_canal_whatsapp(restaurante, desde_mes, hoy)
    especiales = metricas_canal_especiales(restaurante, desde_mes, hoy)
    manuales = metricas_canal_manuales(restaurante, desde_mes, hoy)

    pedidos_creados_mes = (
        whatsapp["pedidos_creados_mes"] + especiales["pedidos_creados_mes"]
        + manuales["pedidos_creados_mes"]
    )
    pedidos_finalizados_mes = (
        whatsapp["pedidos_finalizados_mes"] + especiales["pedidos_finalizados_mes"]
        + manuales["pedidos_finalizados_mes"]
    )
    pedidos_cancelados_mes = (
        whatsapp["pedidos_cancelados_mes"] + especiales["pedidos_cancelados_mes"]
        + manuales["pedidos_cancelados_mes"]
    )
    pedidos_activos = whatsapp["pedidos_activos"] + especiales["pedidos_activos"] + manuales["pedidos_activos"]
    venta_real_mes = whatsapp["venta_real_mes"] + especiales["venta_real_mes"] + manuales["venta_real_mes"]
    ticket_promedio_mes = (
        int(Decimal(venta_real_mes) / pedidos_finalizados_mes)
        if pedidos_finalizados_mes
        else 0
    )
    tasa_cancelacion_mes = (
        round((pedidos_cancelados_mes / pedidos_creados_mes) * 100, 2)
        if pedidos_creados_mes
        else 0
    )

    return {
        "ventas": {
            "venta_real_hoy": whatsapp["venta_real_hoy"] + especiales["venta_real_hoy"] + manuales["venta_real_hoy"],
            "venta_real_semana": (
                whatsapp.get("venta_real_semana", 0)
                + especiales.get("venta_real_semana", 0)
                + manuales.get("venta_real_semana", 0)
            ),
            "venta_real_mes": venta_real_mes,
            "venta_whatsapp_mes": whatsapp["venta_real_mes"],
            "venta_especiales_mes": especiales["venta_real_mes"],
            "venta_menly_mes": manuales["venta_real_mes"],
            "ticket_promedio_mes": ticket_promedio_mes,
        },
        "pedidos": {
            "pedidos_creados_hoy": (
                whatsapp["pedidos_creados_hoy"] + especiales["pedidos_creados_hoy"]
                + manuales["pedidos_creados_hoy"]
            ),
            "pedidos_creados_mes": pedidos_creados_mes,
            "pedidos_finalizados_mes": pedidos_finalizados_mes,
            "pedidos_cancelados_mes": pedidos_cancelados_mes,
            "pedidos_activos": pedidos_activos,
            "tasa_cancelacion_mes": tasa_cancelacion_mes,
        },
        "canales": {
            "whatsapp": whatsapp,
            "especiales": especiales,
            "menly": manuales,
        },
        "venta_diaria_menly": manuales["venta_diaria_menly"],
        "cantidad_pedidos_menly_hoy": manuales["cantidad_pedidos_menly_hoy"],
    }
