from calendar import monthrange

from django.utils.timezone import localtime, now

from .pedidos import (
    pedidos_especiales_cancelados,
    pedidos_especiales_creados,
    pedidos_especiales_finalizados,
    pedidos_whatsapp_cancelados,
    pedidos_whatsapp_creados,
    pedidos_whatsapp_finalizados,
    sumar_total,
)
from .productos import (
    producto_mas_vendido,
    producto_menos_vendido,
    productos_vendidos,
    top_productos_por_cantidad,
    top_productos_por_ingresos,
)


MESES = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]


def _resumen_canal(restaurante, desde, hasta, canal):
    if canal == "whatsapp":
        creados = pedidos_whatsapp_creados(restaurante, desde, hasta)
        finalizados = pedidos_whatsapp_finalizados(restaurante, desde, hasta)
        cancelados = pedidos_whatsapp_cancelados(restaurante, desde, hasta)
    else:
        creados = pedidos_especiales_creados(restaurante, desde, hasta)
        finalizados = pedidos_especiales_finalizados(restaurante, desde, hasta)
        cancelados = pedidos_especiales_cancelados(restaurante, desde, hasta)

    return {
        "venta_real": sumar_total(finalizados),
        "pedidos_creados": creados.count(),
        "pedidos_finalizados": finalizados.count(),
        "pedidos_cancelados": cancelados.count(),
        "top_productos_por_cantidad": top_productos_por_cantidad(
            restaurante, desde, hasta, canal=canal
        ),
        "top_productos_por_ingresos": top_productos_por_ingresos(
            restaurante, desde, hasta, canal=canal
        ),
    }


def _consolidado(restaurante, desde, hasta):
    whatsapp = _resumen_canal(restaurante, desde, hasta, "whatsapp")
    especiales = _resumen_canal(restaurante, desde, hasta, "especiales")
    venta_total = whatsapp["venta_real"] + especiales["venta_real"]
    pedidos_finalizados = (
        whatsapp["pedidos_finalizados"] + especiales["pedidos_finalizados"]
    )
    pedidos_creados = whatsapp["pedidos_creados"] + especiales["pedidos_creados"]
    pedidos_cancelados = (
        whatsapp["pedidos_cancelados"] + especiales["pedidos_cancelados"]
    )

    return {
        "global": {
            "venta_real": venta_total,
            "pedidos_creados": pedidos_creados,
            "pedidos_finalizados": pedidos_finalizados,
            "pedidos_cancelados": pedidos_cancelados,
            "ticket_promedio": int(venta_total / pedidos_finalizados) if pedidos_finalizados else 0,
        },
        "canales": {
            "whatsapp": whatsapp,
            "especiales": especiales,
        },
    }


def construir_reporte_mensual(restaurante):
    hoy = localtime(now()).date()
    inicio = hoy.replace(day=1)
    dias_mes = monthrange(hoy.year, hoy.month)[1]
    fin = hoy.replace(day=dias_mes)
    mes = hoy.strftime("%Y-%m")
    consolidado = _consolidado(restaurante, inicio, fin)

    venta_diaria = []
    for dia in range(1, dias_mes + 1):
        fecha = hoy.replace(day=dia)
        total = (
            sumar_total(pedidos_whatsapp_finalizados(restaurante, fecha, fecha))
            + sumar_total(pedidos_especiales_finalizados(restaurante, fecha, fecha))
        )
        venta_diaria.append({"dia": dia, "total": total})

    productos_globales = productos_vendidos(restaurante, inicio, fin)
    dia_mayor = max(venta_diaria, key=lambda item: item["total"])
    dia_menor = min(venta_diaria, key=lambda item: item["total"])

    return {
        "mes": mes,
        "resumen_global": consolidado["global"],
        "desglose_por_canal": consolidado["canales"],
        "consolidado_total": consolidado["global"],
        "venta_total": consolidado["global"]["venta_real"],
        "pedidos_total": consolidado["global"]["pedidos_creados"],
        "pedidos_finalizados": consolidado["global"]["pedidos_finalizados"],
        "pedidos_cancelados": consolidado["global"]["pedidos_cancelados"],
        "venta_diaria": venta_diaria,
        "dia_mayor_venta": dia_mayor,
        "dia_menor_venta": dia_menor,
        "producto_mas_vendido": producto_mas_vendido(restaurante, inicio, fin),
        "producto_menos_vendido": producto_menos_vendido(restaurante, inicio, fin),
        "productos_vendidos": productos_globales,
        "top_productos_globales": productos_globales,
        "top_productos_por_ingresos": top_productos_por_ingresos(restaurante, inicio, fin),
    }


def construir_reporte_anual(restaurante):
    hoy = localtime(now()).date()
    anio = hoy.year
    inicio = hoy.replace(month=1, day=1)
    fin = hoy.replace(month=12, day=31)
    consolidado = _consolidado(restaurante, inicio, fin)

    ventas_por_mes = []
    for mes in range(1, 13):
        inicio_mes = hoy.replace(month=mes, day=1)
        fin_mes = hoy.replace(month=mes, day=monthrange(anio, mes)[1])
        resumen_mes = _consolidado(restaurante, inicio_mes, fin_mes)
        ventas_por_mes.append({
            "mes": mes,
            "nombre_mes": MESES[mes - 1],
            "total": resumen_mes["global"]["venta_real"],
            "pedidos": resumen_mes["global"]["pedidos_creados"],
            "finalizados": resumen_mes["global"]["pedidos_finalizados"],
            "cancelados": resumen_mes["global"]["pedidos_cancelados"],
        })

    productos_globales = productos_vendidos(restaurante, inicio, fin)
    mes_mayor = max(ventas_por_mes, key=lambda item: item["total"])
    mes_menor = min(ventas_por_mes, key=lambda item: item["total"])

    return {
        "anio": str(anio),
        "resumen_global": consolidado["global"],
        "desglose_por_canal": consolidado["canales"],
        "consolidado_total": consolidado["global"],
        "venta_total_anual": consolidado["global"]["venta_real"],
        "pedidos_total_anual": consolidado["global"]["pedidos_creados"],
        "pedidos_finalizados_anual": consolidado["global"]["pedidos_finalizados"],
        "pedidos_cancelados_anual": consolidado["global"]["pedidos_cancelados"],
        "mes_mayor_venta": mes_mayor,
        "mes_menor_venta": mes_menor,
        "producto_mas_vendido_anual": producto_mas_vendido(restaurante, inicio, fin),
        "producto_menos_vendido_anual": producto_menos_vendido(restaurante, inicio, fin),
        "productos_vendidos": productos_globales,
        "top_productos_globales": productos_globales,
        "top_productos_por_ingresos": top_productos_por_ingresos(restaurante, inicio, fin),
        "ventas_por_mes": ventas_por_mes,
    }
