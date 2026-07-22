import ipaddress
import re
import socket
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError


WEBPUSH_ENDPOINT_ERROR = "Endpoint Web Push no permitido."

# Push services returned by the browsers supported by the frontend's
# standards-based PushManager integration:
# - FCM: Chrome, Chromium and current Edge.
# - Mozilla Autopush: Firefox.
# - Apple Web Push: Safari.
# - WNS: Windows/legacy Edge uses regional hosts below notify.windows.com.
WEBPUSH_EXACT_HOSTS = frozenset({
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "web.push.apple.com",
})
WEBPUSH_HOST_SUFFIXES = frozenset({"notify.windows.com"})
WEBPUSH_ALLOWED_PORTS = frozenset({443})
HOST_LABEL_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def _invalid_endpoint():
    raise ValidationError(WEBPUSH_ENDPOINT_ERROR, code="invalid_webpush_endpoint")


def _normalize_hostname(hostname):
    if not hostname:
        _invalid_endpoint()

    hostname = hostname.rstrip(".").lower()
    if not hostname or len(hostname) > 253:
        _invalid_endpoint()

    try:
        normalized = hostname.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        _invalid_endpoint()

    labels = normalized.split(".")
    if any(
        not label
        or len(label) > 63
        or not HOST_LABEL_PATTERN.fullmatch(label)
        for label in labels
    ):
        _invalid_endpoint()

    return normalized


def _is_allowed_provider(hostname):
    if hostname in WEBPUSH_EXACT_HOSTS:
        return True
    return any(
        hostname == suffix or hostname.endswith(f".{suffix}")
        for suffix in WEBPUSH_HOST_SUFFIXES
    )


def _validate_global_ip(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        _invalid_endpoint()

    # is_global excludes private, loopback, link-local, multicast, reserved,
    # unspecified and documentation ranges for both IPv4 and IPv6.
    if not address.is_global:
        _invalid_endpoint()


def _resolve_all_addresses(hostname, port):
    try:
        answers = socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except (socket.gaierror, OSError, UnicodeError):
        _invalid_endpoint()

    addresses = {answer[4][0] for answer in answers if answer[4]}
    if not addresses:
        _invalid_endpoint()

    for address in addresses:
        _validate_global_ip(address)


def validate_webpush_endpoint(endpoint):
    """Reject Web Push endpoints that could escape to an unsafe destination.

    The function deliberately returns the original URL instead of attempting
    to repair dangerous input. It is used both at API ingestion and directly
    before the network call.
    """
    if not isinstance(endpoint, str) or not endpoint or endpoint.strip() != endpoint:
        _invalid_endpoint()
    if any(ord(character) < 32 or ord(character) == 127 for character in endpoint):
        _invalid_endpoint()

    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
        hostname = parsed.hostname
    except (TypeError, ValueError):
        _invalid_endpoint()

    if parsed.scheme.lower() != "https":
        _invalid_endpoint()
    if parsed.username is not None or parsed.password is not None:
        _invalid_endpoint()
    if parsed.fragment:
        _invalid_endpoint()
    if port is not None and port not in WEBPUSH_ALLOWED_PORTS:
        _invalid_endpoint()

    normalized_hostname = _normalize_hostname(hostname)

    # Reject every IP literal, including alternative textual representations.
    # Legitimate browser PushManager endpoints are provider hostnames.
    try:
        ipaddress.ip_address(normalized_hostname)
    except ValueError:
        pass
    else:
        _invalid_endpoint()

    if not _is_allowed_provider(normalized_hostname):
        _invalid_endpoint()

    _resolve_all_addresses(normalized_hostname, port or 443)
    return endpoint
