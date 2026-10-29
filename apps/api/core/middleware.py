import hashlib
import time
from .observability import request_observed
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import JsonResponse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from .models import Session


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def resolve_session(token):
    if not token or len(token) > 128:
        return None
    session = (
        Session.objects.select_related("user", "device")
        .filter(
            token_hash=digest(token), revoked_at=None, expires_at__gt=timezone.now(), user__is_active=True
        )
        .first()
    )
    if session and session.device and session.device.revoked_at:
        return None
    if session and (
        not session.auth_hash
        or not constant_time_compare(session.auth_hash, session.user.get_session_auth_hash())
    ):
        return None
    return session


class SessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        request.user = AnonymousUser()
        request.haven_session = None
        request.device = None
        if request.path.startswith("/api/") and not request.is_secure():
            return JsonResponse({"error": "https_required"}, status=421)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("Origin") not in settings.ORIGINS:
                return JsonResponse({"error": "origin_rejected"}, status=403)
        token = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
        if token:
            session = resolve_session(token)
            if session:
                request.user, request.device, request.haven_session = session.user, session.device, session
        response = self.get_response(request)
        if request.path.startswith("/api/v1/") and not request.path.endswith("/health"):
            request_observed((time.monotonic() - started) * 1000, response.status_code)
        response["Cache-Control"] = "no-store"
        return response
