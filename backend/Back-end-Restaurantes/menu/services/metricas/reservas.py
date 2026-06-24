from django.utils.timezone import localtime, now
from calendar import monthrange

from menu.models import Reserva
from .estados import RESERVA_CANCELADA, RESERVA_PENDIENTE


def fecha_hoy():
    return localtime(now()).date()


def inicio_mes(fecha=None):
    fecha = fecha or fecha_hoy()
    return fecha.replace(day=1)


def fin_mes(fecha=None):
    fecha = fecha or fecha_hoy()
    return fecha.replace(day=monthrange(fecha.year, fecha.month)[1])


def reservas_creadas(restaurante, desde=None, hasta=None):
    qs = Reserva.objects.filter(restaurante=restaurante)
    if desde:
        qs = qs.filter(fecha_creacion__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha_creacion__date__lte=hasta)
    return qs


def reservas_programadas(restaurante, desde=None, hasta=None):
    qs = Reserva.objects.filter(restaurante=restaurante)
    if desde:
        qs = qs.filter(fecha__gte=desde)
    if hasta:
        qs = qs.filter(fecha__lte=hasta)
    return qs


def metricas_reservas(restaurante, hoy=None):
    hoy = hoy or fecha_hoy()
    desde_mes = inicio_mes(hoy)
    hasta_mes = fin_mes(hoy)
    creadas_mes = reservas_creadas(restaurante, desde_mes, hoy)
    programadas_mes = reservas_programadas(restaurante, desde_mes, hasta_mes)
    pendientes_futuras = Reserva.objects.filter(
        restaurante=restaurante,
        estado=RESERVA_PENDIENTE,
        fecha__gte=hoy,
    )

    return {
        "reservas_hoy": reservas_programadas(restaurante, hoy, hoy).count(),
        "reservas_creadas_mes": creadas_mes.count(),
        "reservas_programadas_mes": programadas_mes.count(),
        "reservas_pendientes_futuras": pendientes_futuras.count(),
        "reservas_canceladas_mes": programadas_mes.filter(estado=RESERVA_CANCELADA).count(),
    }
