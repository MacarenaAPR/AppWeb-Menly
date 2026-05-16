from django.conf import settings


class ProductionSecurityHeadersMiddleware:
    """Defense-in-depth security headers for the API and Django admin."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        #csp = getattr(settings, "CONTENT_SECURITY_POLICY", "")
        #if csp:
        #    response.setdefault("Content-Security-Policy", csp)

        response.setdefault("Permissions-Policy", getattr(settings, "PERMISSIONS_POLICY", ""))
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("X-Frame-Options", "DENY")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault("X-Permitted-Cross-Domain-Policies", "none")

        return response
