from __future__ import annotations

import hmac

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse, JsonResponse


class ProxySharedSecretMiddleware:
    """
    When PROXY_SHARED_SECRET is configured (e.g. Render free public web service),
    require Next.js proxy requests to present X-Drip-Proxy-Secret and reject
    unauthorized direct backend access while keeping GET/HEAD /api/health/ open
    for Render platform health checks.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        expected = getattr(settings, "PROXY_SHARED_SECRET", "")
        if expected:
            provided = request.META.get("HTTP_X_DRIP_PROXY_SECRET", "")
            if provided and hmac.compare_digest(provided, expected):
                request.proxy_verified = True
            else:
                request.proxy_verified = False
                # Never trust forwarded host/client IP headers from untrusted public callers.
                request.META.pop("HTTP_X_FORWARDED_HOST", None)
                request.META.pop("HTTP_X_DRIP_CLIENT_IP", None)

                is_health = request.path == "/api/health/" and request.method in {"GET", "HEAD"}
                if not is_health:
                    resp = JsonResponse(
                        {
                            "error": {
                                "code": "FORBIDDEN",
                                "message": "Direct backend access is not permitted.",
                                "details": {},
                            }
                        },
                        status=403,
                    )
                    resp["Cache-Control"] = "no-store, max-age=0, private"
                    return resp
        else:
            request.proxy_verified = False

        return self.get_response(request)


class ActiveAdminAndCacheControlMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not user.is_active:
            logout(request)
            if request.path.startswith("/api/"):
                resp = JsonResponse(
                    {
                        "error": {
                            "code": "ACCOUNT_PAUSED",
                            "message": "Your administrator account has been temporarily paused. Please contact the Super Admin to restore your access.",
                            "details": {},
                        }
                    },
                    status=403,
                )
                resp["Cache-Control"] = "no-store, max-age=0, private"
                return resp

        response = self.get_response(request)

        if request.path.startswith("/api/"):
            if "Cache-Control" not in response:
                response["Cache-Control"] = "no-store, max-age=0, private"
                response["Pragma"] = "no-cache"

        return response
