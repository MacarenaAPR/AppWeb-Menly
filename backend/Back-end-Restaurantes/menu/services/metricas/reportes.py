from calendar import monthrange
from datetime import date

from django.utils.timezone import localtime, now

from .pedidos import (
    pedidos_especiales_cancelados,
    pedidos_especiales_creados,
    pedidos_especiales_finalizados,
    pedidos_manuales_cancelados,
    pedidos_manuales_creados,
    pedidos_manuales_finalizados,
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


def _resumen_canal(restaurante, desde, hasta, canal, incluir_productos=True):
    if canal == "whatsapp":
        creados = pedidos_whatsapp_creados(restaurante, desde, hasta)
        finalizados = pedidos_whatsapp_finalizados(restaurante, desde, hasta)
        cancelados = pedidos_whatsapp_cancelados(restaurante, desde, hasta)
    elif canal == "especiales":
        creados = pedidos_especiales_creados(restaurante, desde, hasta)
        finalizados = pedidos_especiales_finalizados(restaurante, desde, hasta)
        cancelados = pedidos_especiales_cancelados(restaurante, desde, hasta)
    else:
        creados = pedidos_manuales_creados(restaurante, desde, hasta)
        finalizados = pedidos_manuales_finalizados(restaurante, desde, hasta)
        cancelados = pedidos_manuales_cancelados(restaurante, desde, hasta)

    resumen = {
        "venta_real": sumar_total(finalizados),
        "pedidos_creados": creados.count(),
        "pedidos_finalizados": finalizados.count(),
        "pedidos_cancelados": cancelados.count(),
    }
    resumen["top_productos_por_cantidad"] = (
        top_productos_por_cantidad(
            restaurante,
            desde,
            hasta,
            canal=canal,
            incluir_especiales_inactivos=True,
        )
        if incluir_productos
        else []
    )
    resumen["top_productos_por_ingresos"] = (
        top_productos_por_ingresos(
            restaurante,
            desde,
            hasta,
            canal=canal,
            incluir_especiales_inactivos=True,
        )
        if incluir_productos
        else []
    )
    return resumen


def _consolidado(restaurante, desde, hasta, incluir_productos=True):
    whatsapp = _resumen_canal(
        restaurante, desde, hasta, "whatsapp", incluir_productos
    )
    especiales = _resumen_canal(
        restaurante, desde, hasta, "especiales", incluir_productos
    )
    menly = _resumen_canal(
        restaurante, desde, hasta, "menly", incluir_productos
    )
    venta_total = (
        whatsapp["venta_real"] + especiales["venta_real"] + menly["venta_real"]
    )
    pedidos_finalizados = (
        whatsapp["pedidos_finalizados"]
        + especiales["pedidos_finalizados"]
        + menly["pedidos_finalizados"]
    )
    pedidos_creados = (
        whatsapp["pedidos_creados"]
        + especiales["pedidos_creados"]
        + menly["pedidos_creados"]
    )
    pedidos_cancelados = (
        whatsapp["pedidos_cancelados"]
        + especiales["pedidos_cancelados"]
        + menly["pedidos_cancelados"]
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
            "menly": menly,
        },
    }


def construir_reporte_mensual(restaurante, anio=None, mes=None):
    hoy = localtime(now()).date()
    anio = int(anio or hoy.year)
    mes_numero = int(mes or hoy.month)
    inicio = date(anio, mes_numero, 1)
    dias_mes = monthrange(anio, mes_numero)[1]
    fin = date(anio, mes_numero, dias_mes)
    periodo = inicio.strftime("%Y-%m")
    consolidado = _consolidado(restaurante, inicio, fin)

    venta_diaria = []
    for dia in range(1, dias_mes + 1):
        fecha = date(anio, mes_numero, dia)
        total = _consolidado(
            restaurante, fecha, fecha, incluir_productos=False
        )["global"]["venta_real"]
        venta_diaria.append({"dia": dia, "total": total})

    productos_globales = productos_vendidos(
        restaurante, inicio, fin, incluir_especiales_inactivos=True
    )
    productos_por_canal = {
        "whatsapp": productos_vendidos(restaurante, inicio, fin, canal="whatsapp"),
        "especiales": productos_vendidos(
            restaurante,
            inicio,
            fin,
            canal="especiales",
            incluir_especiales_inactivos=True,
        ),
        "menly": productos_vendidos(restaurante, inicio, fin, canal="menly"),
    }
    dia_mayor = max(venta_diaria, key=lambda item: item["total"])
    dia_menor = min(venta_diaria, key=lambda item: item["total"])
    whatsapp = consolidado["canales"]["whatsapp"]
    especiales = consolidado["canales"]["especiales"]
    menly = consolidado["canales"]["menly"]

    return {
        "mes": periodo,
        "resumen_global": consolidado["global"],
        "desglose_por_canal": consolidado["canales"],
        "resumen_canales": consolidado["canales"],
        "consolidado_total": consolidado["global"],
        "venta_total": consolidado["global"]["venta_real"],
        "venta_whatsapp": whatsapp["venta_real"],
        "venta_especiales": especiales["venta_real"],
        "venta_menly": menly["venta_real"],
        "pedidos_total": consolidado["global"]["pedidos_creados"],
        "pedidos_creados": consolidado["global"]["pedidos_creados"],
        "pedidos_finalizados": consolidado["global"]["pedidos_finalizados"],
        "pedidos_cancelados": consolidado["global"]["pedidos_cancelados"],
        "pedidos_creados_whatsapp": whatsapp["pedidos_creados"],
        "pedidos_creados_especiales": especiales["pedidos_creados"],
        "pedidos_creados_menly": menly["pedidos_creados"],
        "pedidos_finalizados_whatsapp": whatsapp["pedidos_finalizados"],
        "pedidos_finalizados_especiales": especiales["pedidos_finalizados"],
        "pedidos_finalizados_menly": menly["pedidos_finalizados"],
        "pedidos_cancelados_whatsapp": whatsapp["pedidos_cancelados"],
        "pedidos_cancelados_especiales": especiales["pedidos_cancelados"],
        "pedidos_cancelados_menly": menly["pedidos_cancelados"],
        "venta_diaria": venta_diaria,
        "dia_mayor_venta": dia_mayor,
        "dia_menor_venta": dia_menor,
        "producto_mas_vendido": producto_mas_vendido(
            restaurante, inicio, fin, incluir_especiales_inactivos=True
        ),
        "producto_menos_vendido": producto_menos_vendido(
            restaurante, inicio, fin, incluir_especiales_inactivos=True
        ),
        "productos_vendidos": productos_globales,
        "productos_por_canal": productos_por_canal,
        "top_productos_globales": productos_globales,
        "top_productos_por_ingresos": top_productos_por_ingresos(
            restaurante, inicio, fin, incluir_especiales_inactivos=True
        ),
    }


def construir_reporte_anual(restaurante, anio=None):
    hoy = localtime(now()).date()
    anio = int(anio or hoy.year)
    inicio = date(anio, 1, 1)
    fin = date(anio, 12, 31)
    consolidado = _consolidado(restaurante, inicio, fin)

    ventas_por_mes = []
    for mes in range(1, 13):
        inicio_mes = date(anio, mes, 1)
        fin_mes = date(anio, mes, monthrange(anio, mes)[1])
        resumen_mes = _consolidado(
            restaurante, inicio_mes, fin_mes, incluir_productos=False
        )
        ventas_por_mes.append({
            "mes": mes,
            "nombre_mes": MESES[mes - 1],
            "total": resumen_mes["global"]["venta_real"],
            "pedidos": resumen_mes["global"]["pedidos_creados"],
            "finalizados": resumen_mes["global"]["pedidos_finalizados"],
            "cancelados": resumen_mes["global"]["pedidos_cancelados"],
        })

    productos_globales = productos_vendidos(
        restaurante, inicio, fin, incluir_especiales_inactivos=True
    )
    productos_por_canal = {
        "whatsapp": productos_vendidos(restaurante, inicio, fin, canal="whatsapp"),
        "especiales": productos_vendidos(
            restaurante,
            inicio,
            fin,
            canal="especiales",
            incluir_especiales_inactivos=True,
        ),
        "menly": productos_vendidos(restaurante, inicio, fin, canal="menly"),
    }
    mes_mayor = max(ventas_por_mes, key=lambda item: item["total"])
    mes_menor = min(ventas_por_mes, key=lambda item: item["total"])
    whatsapp = consolidado["canales"]["whatsapp"]
    especiales = consolidado["canales"]["especiales"]
    menly = consolidado["canales"]["menly"]

    return {
        "anio": str(anio),
        "resumen_global": consolidado["global"],
        "desglose_por_canal": consolidado["canales"],
        "resumen_canales": consolidado["canales"],
        "consolidado_total": consolidado["global"],
        "venta_total_anual": consolidado["global"]["venta_real"],
        "venta_whatsapp": whatsapp["venta_real"],
        "venta_especiales": especiales["venta_real"],
        "venta_menly": menly["venta_real"],
        "pedidos_total_anual": consolidado["global"]["pedidos_creados"],
        "pedidos_creados": consolidado["global"]["pedidos_creados"],
        "pedidos_finalizados_anual": consolidado["global"]["pedidos_finalizados"],
        "pedidos_finalizados": consolidado["global"]["pedidos_finalizados"],
        "pedidos_cancelados_anual": consolidado["global"]["pedidos_cancelados"],
        "pedidos_cancelados": consolidado["global"]["pedidos_cancelados"],
        "pedidos_creados_whatsapp": whatsapp["pedidos_creados"],
        "pedidos_creados_especiales": especiales["pedidos_creados"],
        "pedidos_creados_menly": menly["pedidos_creados"],
        "pedidos_finalizados_whatsapp": whatsapp["pedidos_finalizados"],
        "pedidos_finalizados_especiales": especiales["pedidos_finalizados"],
        "pedidos_finalizados_menly": menly["pedidos_finalizados"],
        "pedidos_cancelados_whatsapp": whatsapp["pedidos_cancelados"],
        "pedidos_cancelados_especiales": especiales["pedidos_cancelados"],
        "pedidos_cancelados_menly": menly["pedidos_cancelados"],
        "mes_mayor_venta": mes_mayor,
        "mes_menor_venta": mes_menor,
        "producto_mas_vendido_anual": producto_mas_vendido(
            restaurante, inicio, fin, incluir_especiales_inactivos=True
        ),
        "producto_menos_vendido_anual": producto_menos_vendido(
            restaurante, inicio, fin, incluir_especiales_inactivos=True
        ),
        "productos_vendidos": productos_globales,
        "productos_por_canal": productos_por_canal,
        "top_productos_globales": productos_globales,
        "top_productos_por_ingresos": top_productos_por_ingresos(
            restaurante, inicio, fin, incluir_especiales_inactivos=True
        ),
        "ventas_por_mes": ventas_por_mes,
    }
