from django.conf import settings
from django.utils import timezone


class ChileTimezoneMiddleware:
    """Keep every request in the project timezone."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        timezone.activate(settings.TIME_ZONE)
        return self.get_response(request)
