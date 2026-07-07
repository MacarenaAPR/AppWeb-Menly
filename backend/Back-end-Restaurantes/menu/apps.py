from django.apps import AppConfig
from django.conf import settings
from django.utils import timezone


class MenuConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'menu'

    def ready(self):
        timezone.activate(settings.TIME_ZONE)
        import menu.signals  # noqa: F401
