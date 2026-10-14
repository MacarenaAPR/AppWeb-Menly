from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from .cache_utils import invalidate_menu_cache
from .models import Categoria, GrupoOpcionesProducto, OpcionProducto, Producto


@receiver([post_save, post_delete], sender=Producto)
def invalidate_menu_cache_on_producto_change(sender, instance, **kwargs):
    invalidate_menu_cache(instance.restaurante)


@receiver([post_save, post_delete], sender=Categoria)
def invalidate_menu_cache_on_categoria_change(sender, instance, **kwargs):
    invalidate_menu_cache(instance.restaurante)


@receiver(post_save, sender=GrupoOpcionesProducto)
def invalidate_menu_cache_on_grupo_opciones_change(sender, instance, **kwargs):
    invalidate_menu_cache(instance.producto.restaurante)


@receiver(pre_delete, sender=GrupoOpcionesProducto)
def invalidate_menu_cache_before_grupo_opciones_delete(sender, instance, **kwargs):
    invalidate_menu_cache(instance.producto.restaurante)


@receiver(post_save, sender=OpcionProducto)
def invalidate_menu_cache_on_opcion_producto_change(sender, instance, **kwargs):
    invalidate_menu_cache(instance.grupo.producto.restaurante)


@receiver(pre_delete, sender=OpcionProducto)
def invalidate_menu_cache_before_opcion_producto_delete(sender, instance, **kwargs):
    invalidate_menu_cache(instance.grupo.producto.restaurante)
