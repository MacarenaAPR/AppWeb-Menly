from django.utils import timezone


def calcular_estado_abierto(restaurante):
    if not bool(getattr(restaurante, "abierto", True)):
        return False

    horarios_manager = getattr(restaurante, "horarios", None)
    if horarios_manager is None:
        return True

    horarios = list(horarios_manager.filter(activo=True))
    if not horarios:
        return True

    ahora = timezone.localtime()
    horario_hoy = next((horario for horario in horarios if horario.dia == ahora.isoweekday()), None)

    if not horario_hoy or horario_hoy.cerrado:
        return False

    if not horario_hoy.hora_apertura or not horario_hoy.hora_cierre:
        return True

    hora_actual = ahora.time()
    return horario_hoy.hora_apertura <= hora_actual <= horario_hoy.hora_cierre
