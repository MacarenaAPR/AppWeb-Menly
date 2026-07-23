from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone
import logging
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)


security_logger = logging.getLogger("menu.security")


def record_user_security_event(*, operation, affected_user, actor):
    security_logger.info(
        "user_security_event operation=%s affected_user_id=%s "
        "affected_username=%s actor_user_id=%s actor_username=%s occurred_at=%s",
        operation,
        affected_user.pk,
        affected_user.get_username(),
        actor.pk,
        actor.get_username(),
        timezone.now().isoformat(),
    )


def revoke_user_authentication(user):
    """Revoca refresh tokens y sesiones Django del usuario indicado."""
    refresh_tokens_revoked = 0
    for token in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        refresh_tokens_revoked += int(created)

    django_sessions_revoked = 0
    active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
    for session in active_sessions.iterator():
        try:
            session_user_id = session.get_decoded().get("_auth_user_id")
        except Exception:
            continue
        if str(session_user_id) == str(user.pk):
            session.delete()
            django_sessions_revoked += 1

    return {
        "refresh_tokens_revoked": refresh_tokens_revoked,
        "django_sessions_revoked": django_sessions_revoked,
    }


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
