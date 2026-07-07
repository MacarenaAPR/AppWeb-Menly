from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone

from menu.models import Restaurante
from menu.services.estado_restaurante import calcular_estado_abierto


def debug_time(request):
    current_utc = timezone.now()
    current_local = timezone.localtime(current_utc)
    restaurante = Restaurante.objects.first()

    return JsonResponse(
        {
            "django_timezone": settings.TIME_ZONE,
            "current_utc": current_utc.isoformat(),
            "current_local": current_local.isoformat(),
            "timezone_name": timezone.get_current_timezone_name(),
            "current_day": current_local.strftime("%A"),
            "current_time": current_local.strftime("%H:%M:%S"),
            "restaurant_open": (
                calcular_estado_abierto(restaurante)
                if restaurante is not None
                else None
            ),
        }
    )
