from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from menu.models import HorarioAtencion, Restaurante, TurnoOperativo
from menu.services.estado_restaurante import horario_operativo


@dataclass(frozen=True)
class RangoTurnoOperativo:
    inicio: datetime | None
    fin: datetime | None
    activo: bool
    origen_inicio: str | None
    turno: TurnoOperativo | None = None


def _ahora_local(ahora=None):
    valor = ahora or timezone.now()
    if timezone.is_naive(valor):
        valor = timezone.make_aware(valor, timezone.get_current_timezone())
    return timezone.localtime(valor)


def _combinar(fecha, hora):
    return timezone.make_aware(
        datetime.combine(fecha, hora),
        timezone.get_current_timezone(),
    )


def _intervalo_horario(horario, fecha_operativa):
    inicio = _combinar(fecha_operativa, horario.hora_apertura)
    fecha_fin = (
        fecha_operativa + timedelta(days=1)
        if horario.hora_cierre <= horario.hora_apertura
        else fecha_operativa
    )
    fin = _combinar(fecha_fin, horario.hora_cierre)
    return inicio, fin


def _intervalos_programados(restaurante, ahora, dias_hacia_adelante=8):
    horarios_configurados = list(restaurante.horarios.filter(activo=True))
    horarios = {
        horario.dia: horario
        for horario in horarios_configurados
        if horario_operativo(horario)
    }
    fecha_base = ahora.date()
    if not horarios_configurados:
        return [
            (
                _combinar(fecha_base, datetime.min.time()),
                _combinar(fecha_base + timedelta(days=1), datetime.min.time()),
                fecha_base,
            )
        ]
    intervalos = []
    for desplazamiento in range(-1, dias_hacia_adelante + 1):
        fecha = fecha_base + timedelta(days=desplazamiento)
        horario = horarios.get(fecha.isoweekday())
        if horario:
            inicio, fin = _intervalo_horario(horario, fecha)
            intervalos.append((inicio, fin, fecha))
    return sorted(intervalos, key=lambda item: item[0])


def _intervalo_actual_y_siguiente(restaurante, ahora):
    intervalos = _intervalos_programados(restaurante, ahora)
    actual = next(
        (intervalo for intervalo in intervalos if intervalo[0] <= ahora < intervalo[1]),
        None,
    )
    siguiente = next(
        (intervalo for intervalo in intervalos if intervalo[0] > ahora),
        None,
    )
    return actual, siguiente


def _cerrar_turno_vencido(turno, ahora):
    if turno and ahora >= timezone.localtime(turno.fin_programado):
        turno.cerrado = True
        turno.fecha_cierre_real = turno.fin_programado
        turno.save(
            update_fields=["cerrado", "fecha_cierre_real", "actualizado_en"]
        )
        return None
    return turno


def _crear_turno(restaurante, inicio, fin, fecha_operativa, origen):
    return TurnoOperativo.objects.create(
        restaurante=restaurante,
        inicio=inicio,
        fin_programado=fin,
        fecha_operativa=fecha_operativa,
        origen_inicio=origen,
    )


def obtener_turno_operativo_actual(restaurante, ahora=None):
    ahora = _ahora_local(ahora)

    with transaction.atomic():
        Restaurante.objects.select_for_update().only("id").get(id=restaurante.id)
        turno = (
            TurnoOperativo.objects
            .select_for_update()
            .filter(restaurante=restaurante, cerrado=False)
            .first()
        )
        turno = _cerrar_turno_vencido(turno, ahora)
        if turno:
            return RangoTurnoOperativo(
                inicio=turno.inicio,
                fin=turno.fin_programado,
                activo=True,
                origen_inicio=turno.origen_inicio,
                turno=turno,
            )

        intervalo_actual, siguiente = _intervalo_actual_y_siguiente(restaurante, ahora)
        if intervalo_actual:
            inicio, fin, fecha_operativa = intervalo_actual
            turno = _crear_turno(
                restaurante,
                inicio,
                fin,
                fecha_operativa,
                TurnoOperativo.ORIGEN_HORARIO,
            )
            return RangoTurnoOperativo(
                inicio=turno.inicio,
                fin=turno.fin_programado,
                activo=True,
                origen_inicio=turno.origen_inicio,
                turno=turno,
            )

        if siguiente:
            inicio, fin, _ = siguiente
            return RangoTurnoOperativo(
                inicio=inicio,
                fin=fin,
                activo=False,
                origen_inicio=TurnoOperativo.ORIGEN_HORARIO,
            )

        return RangoTurnoOperativo(
            inicio=None,
            fin=None,
            activo=False,
            origen_inicio=None,
        )


def registrar_apertura_excepcional(restaurante, hasta, ahora=None):
    ahora = _ahora_local(ahora)
    hasta = _ahora_local(hasta)
    if hasta <= ahora:
        raise ValueError("La apertura excepcional debe tener un fin posterior al inicio.")

    with transaction.atomic():
        Restaurante.objects.select_for_update().only("id").get(id=restaurante.id)
        turno = (
            TurnoOperativo.objects
            .select_for_update()
            .filter(restaurante=restaurante, cerrado=False)
            .first()
        )
        turno = _cerrar_turno_vencido(turno, ahora)
        if turno:
            return turno

        intervalo_actual, siguiente = _intervalo_actual_y_siguiente(restaurante, ahora)
        if intervalo_actual:
            inicio, fin, fecha_operativa = intervalo_actual
            return _crear_turno(
                restaurante,
                inicio,
                fin,
                fecha_operativa,
                TurnoOperativo.ORIGEN_HORARIO,
            )

        if siguiente and siguiente[2] == ahora.date():
            _, fin, fecha_operativa = siguiente
        else:
            fin = hasta
            fecha_operativa = ahora.date()

        return _crear_turno(
            restaurante,
            ahora,
            fin,
            fecha_operativa,
            TurnoOperativo.ORIGEN_APERTURA_EXCEPCIONAL,
        )


def filtrar_queryset_turno_actual(queryset, restaurante, ahora=None):
    rango = obtener_turno_operativo_actual(restaurante, ahora=ahora)
    if not rango.inicio or not rango.fin:
        return queryset.none()
    return queryset.filter(
        fecha_creacion__gte=rango.inicio,
        fecha_creacion__lt=rango.fin,
    )
