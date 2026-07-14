from django.conf import settings


def set_admin_refresh_cookie(response, refresh_token, remember_me=False):
    cookie_options = {
        "httponly": True,
        "secure": settings.IS_PRODUCTION,
        "samesite": "Lax",
        "path": "/api/",
        "domain": settings.ADMIN_COOKIE_DOMAIN,
    }
    if remember_me:
        cookie_options["max_age"] = int(
            settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()
        )

    response.set_cookie(
        settings.ADMIN_REFRESH_COOKIE_NAME,
        str(refresh_token),
        **cookie_options,
    )
    response.set_cookie(
        settings.ADMIN_REMEMBER_COOKIE_NAME,
        "1" if remember_me else "0",
        **cookie_options,
    )


def get_admin_remember_me(request):
    return request.COOKIES.get(settings.ADMIN_REMEMBER_COOKIE_NAME) == "1"


def parse_remember_me(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def clear_admin_refresh_cookie(response):
    response.delete_cookie(
        settings.ADMIN_REFRESH_COOKIE_NAME,
        path="/api/",
        samesite="Lax",
        domain=settings.ADMIN_COOKIE_DOMAIN,
    )
    response.delete_cookie(
        settings.ADMIN_REMEMBER_COOKIE_NAME,
        path="/api/",
        samesite="Lax",
        domain=settings.ADMIN_COOKIE_DOMAIN,
    )


def get_admin_refresh_token(request):
    # El body se conserva temporalmente para clientes desplegados con la version
    # anterior; el frontend actual utiliza exclusivamente la cookie HttpOnly.
    return (
        request.COOKIES.get(settings.ADMIN_REFRESH_COOKIE_NAME)
        or request.data.get("refresh")
    )
