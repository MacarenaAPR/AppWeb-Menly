from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache_utils import invalidate_menu_cache
from .models import Categoria, Producto


@receiver([post_save, post_delete], sender=Producto)
def invalidate_menu_cache_on_producto_change(sender, instance, **kwargs):
    invalidate_menu_cache(instance.restaurante)


@receiver([post_save, post_delete], sender=Categoria)
def invalidate_menu_cache_on_categoria_change(sender, instance, **kwargs):
    invalidate_menu_cache(instance.restaurante)
