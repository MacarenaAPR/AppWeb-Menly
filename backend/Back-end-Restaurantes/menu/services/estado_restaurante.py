from django.utils import timezone


def horario_operativo(horario):
    return bool(
        horario
        and horario.activo
        and not horario.cerrado
        and horario.hora_apertura
        and horario.hora_cierre
        and horario.hora_apertura != horario.hora_cierre
    )


def horario_cubre_hora_del_dia(horario, hora):
    """Evalua el tramo que comienza el dia configurado."""
    if not horario_operativo(horario):
        return False

    apertura = horario.hora_apertura
    cierre = horario.hora_cierre
    if cierre > apertura:
        return apertura <= hora <= cierre
    return hora >= apertura


def horario_cubre_madrugada_siguiente(horario, hora):
    """Evalua el tramo posterior a medianoche de un horario nocturno."""
    if not horario_operativo(horario):
        return False

    return horario.hora_cierre < horario.hora_apertura and hora <= horario.hora_cierre


def calcular_estado_horario(restaurante, ahora=None):
    horarios_manager = getattr(restaurante, "horarios", None)
    if horarios_manager is None:
        return True

    horarios = list(horarios_manager.filter(activo=True))
    if not horarios:
        return True

    ahora = ahora or timezone.localtime()
    dia_hoy = ahora.isoweekday()
    dia_anterior = 7 if dia_hoy == 1 else dia_hoy - 1
    horario_hoy = next((horario for horario in horarios if horario.dia == dia_hoy), None)
    horario_anterior = next((horario for horario in horarios if horario.dia == dia_anterior), None)
    hora_actual = ahora.time()
    return (
        horario_cubre_hora_del_dia(horario_hoy, hora_actual)
        or horario_cubre_madrugada_siguiente(horario_anterior, hora_actual)
    )


def calcular_estado_restaurante(restaurante, ahora=None):
    ahora = ahora or timezone.localtime()
    dentro_de_horario = calcular_estado_horario(restaurante, ahora=ahora)
    apertura_excepcional_hasta = getattr(restaurante, "apertura_excepcional_hasta", None)
    excepcion_vigente = bool(
        apertura_excepcional_hasta
        and apertura_excepcional_hasta > ahora
    )

    if not bool(getattr(restaurante, "abierto", True)):
        abierto_ahora = False
        motivo = "cierre_manual"
    elif excepcion_vigente:
        abierto_ahora = True
        motivo = "apertura_excepcional"
    elif dentro_de_horario:
        abierto_ahora = True
        motivo = "dentro_de_horario"
    else:
        abierto_ahora = False
        motivo = "fuera_de_horario"

    return {
        "abierto_ahora": abierto_ahora,
        "motivo": motivo,
        "dentro_de_horario": dentro_de_horario,
        "apertura_excepcional_activa": excepcion_vigente,
        "apertura_excepcional_hasta": apertura_excepcional_hasta if excepcion_vigente else None,
        "puede_abrirse_excepcionalmente": not dentro_de_horario and not excepcion_vigente,
    }


def calcular_estado_abierto(restaurante, ahora=None):
    return calcular_estado_restaurante(restaurante, ahora=ahora)["abierto_ahora"]
