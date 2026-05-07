from django.core.cache import cache


MENU_CACHE_TIMEOUT = 60 * 5


def menu_cache_key(slug):
    return f"menu_{slug}"


def get_cached_menu(slug):
    return cache.get(menu_cache_key(slug))


def set_cached_menu(slug, data):
    cache.set(menu_cache_key(slug), data, timeout=MENU_CACHE_TIMEOUT)


def invalidate_menu_cache(restaurante):
    slug = getattr(restaurante, "slug", None)

    if slug:
        cache.delete(menu_cache_key(slug))
