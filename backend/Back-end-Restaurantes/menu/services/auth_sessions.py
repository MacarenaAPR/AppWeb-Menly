from django.conf import settings


def set_admin_refresh_cookie(response, refresh_token):
    response.set_cookie(
        settings.ADMIN_REFRESH_COOKIE_NAME,
        str(refresh_token),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.IS_PRODUCTION,
        samesite="Lax",
        path="/api/",
        domain=settings.ADMIN_COOKIE_DOMAIN,
    )


def clear_admin_refresh_cookie(response):
    response.delete_cookie(
        settings.ADMIN_REFRESH_COOKIE_NAME,
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
