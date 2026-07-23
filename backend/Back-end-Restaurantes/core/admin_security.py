import hashlib
import ipaddress
import logging
import math
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseNotFound


logger = logging.getLogger("core.admin_security")


def _admin_prefix():
    return f"/{settings.ADMIN_URL_PATH.strip('/')}/"


def _client_ip(request):
    header = getattr(settings, "ADMIN_CLIENT_IP_HEADER", "REMOTE_ADDR")
    raw_value = request.META.get(header, "")
    if header == "HTTP_X_FORWARDED_FOR":
        raw_value = raw_value.split(",", 1)[0]

    value = raw_value.strip()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return "unknown"


def _allowed_networks():
    networks = []
    for value in getattr(settings, "ADMIN_ALLOWED_NETWORKS", []):
        value = value.strip()
        if value:
            networks.append(ipaddress.ip_network(value, strict=False))
    return networks


def _ip_is_allowed(ip_value):
    networks = _allowed_networks()
    if not networks:
        return not settings.IS_PRODUCTION

    try:
        address = ipaddress.ip_address(ip_value)
    except ValueError:
        return False
    return any(address in network for network in networks)


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _identifiers(request):
    ip_value = _client_ip(request)
    username = request.POST.get("username", "").strip().casefold()
    identifiers = [("ip", _digest(f"ip:{ip_value}"))]
    if username:
        identifiers.append(("account", _digest(f"account:{username}")))
    return ip_value, identifiers


def _cache_key(kind, identifier, suffix):
    return f"admin-security:{kind}:{identifier}:{suffix}"


def _active_lock(identifiers):
    now = time.time()
    locked_until = 0
    for kind, identifier in identifiers:
        value = cache.get(_cache_key(kind, identifier, "locked-until"), 0)
        try:
            locked_until = max(locked_until, float(value))
        except (TypeError, ValueError):
            continue
    return locked_until if locked_until > now else 0


def _register_failure(identifiers):
    max_failures = settings.ADMIN_LOGIN_MAX_FAILURES
    window_seconds = settings.ADMIN_LOGIN_WINDOW_SECONDS
    base_lockout = settings.ADMIN_LOGIN_LOCKOUT_BASE_SECONDS
    max_lockout = settings.ADMIN_LOGIN_LOCKOUT_MAX_SECONDS
    now = time.time()
    locked_until = 0

    for kind, identifier in identifiers:
        failures_key = _cache_key(kind, identifier, "failures")
        if cache.add(failures_key, 1, timeout=window_seconds):
            failures = 1
        else:
            try:
                failures = cache.incr(failures_key)
            except ValueError:
                cache.set(failures_key, 1, timeout=window_seconds)
                failures = 1

        if failures < max_failures:
            continue

        level_key = _cache_key(kind, identifier, "level")
        try:
            level = cache.incr(level_key)
        except ValueError:
            cache.set(level_key, 1, timeout=max_lockout * 2)
            level = 1

        lockout_seconds = min(base_lockout * (2 ** (level - 1)), max_lockout)
        bucket_locked_until = now + lockout_seconds
        cache.set(
            _cache_key(kind, identifier, "locked-until"),
            bucket_locked_until,
            timeout=lockout_seconds,
        )
        cache.delete(failures_key)
        locked_until = max(locked_until, bucket_locked_until)

    return locked_until


def _clear_failures(identifiers):
    for kind, identifier in identifiers:
        cache.delete_many(
            [
                _cache_key(kind, identifier, "failures"),
                _cache_key(kind, identifier, "locked-until"),
                _cache_key(kind, identifier, "level"),
            ]
        )


def _lockout_response(locked_until):
    retry_after = max(1, math.ceil(locked_until - time.time()))
    response = HttpResponse(
        "Demasiados intentos de acceso. Intente nuevamente mas tarde.",
        status=429,
        content_type="text/plain; charset=utf-8",
    )
    response["Retry-After"] = str(retry_after)
    response["Cache-Control"] = "no-store"
    return response


class AdminSecurityMiddleware:
    """Restrict Django Admin and throttle its password login."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        prefix = _admin_prefix()
        if not request.path.startswith(prefix):
            return self.get_response(request)

        ip_value = _client_ip(request)
        if not _ip_is_allowed(ip_value):
            logger.warning("admin_access_denied ip=%s path=%s", ip_value, request.path)
            return HttpResponseNotFound()

        login_path = f"{prefix}login/"
        if request.method != "POST" or request.path != login_path:
            return self.get_response(request)

        _, identifiers = _identifiers(request)
        locked_until = _active_lock(identifiers)
        if locked_until:
            logger.warning("admin_login_blocked ip=%s", ip_value)
            return _lockout_response(locked_until)

        response = self.get_response(request)
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            _clear_failures(identifiers)
            logger.info("admin_login_success user_id=%s ip=%s", request.user.pk, ip_value)
            return response

        locked_until = _register_failure(identifiers)
        logger.warning("admin_login_failed ip=%s", ip_value)
        if locked_until:
            logger.error("admin_login_lockout ip=%s", ip_value)
            return _lockout_response(locked_until)
        return response
