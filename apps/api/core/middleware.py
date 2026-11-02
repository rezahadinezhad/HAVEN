import hashlib
import time
from .observability import request_observed
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import JsonResponse
from django.db import DatabaseError, connection
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from .models import Session, User, Device


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def projected_model(model, names, values):
    # from_db() expects concrete-field order, including inherited User fields.
    # Everything absent remains genuinely deferred, never a default placeholder.
    projected = dict(zip(names, values))
    ordered = [field.attname for field in model._meta.concrete_fields if field.attname in projected]
    return model.from_db(connection.alias, ordered, [projected[name] for name in ordered])


def resolve_session(token):
    if not token or len(token) > 128:
        return None
    # This fixed PostgreSQL lookup is on every request/frame. Avoid repeatedly
    # rebuilding the same related-model SQL; preserve the exact minimal fields,
    # live predicates, password binding and ordinary deferred Django models.
    # Values remain parameters, never interpolated into SQL or cached authority.
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT "core_session"."id", "core_session"."auth_hash",
                      "core_session"."user_id", "core_session"."device_id",
                      "core_user"."id", "core_user"."password", "core_user"."is_active", "core_user"."role",
                      "core_device"."id", "core_device"."user_id", "core_device"."identity",
                      "core_device"."public_key", "core_device"."trust_state", "core_device"."revoked_at"
               FROM "core_session" JOIN "core_user" ON "core_user"."id"="core_session"."user_id"
               LEFT JOIN "core_device" ON "core_device"."id"="core_session"."device_id"
               WHERE "core_session"."token_hash"=%s AND "core_session"."revoked_at" IS NULL
                     AND "core_session"."expires_at">%s AND "core_user"."is_active"
               LIMIT 1""",
            [digest(token), timezone.now()],
        )
        row = cursor.fetchone()
    if row is None:
        return None
    session = projected_model(Session, ["id", "auth_hash", "user_id", "device_id"], row[:4])
    session.user = projected_model(User, ["id", "password", "is_active", "role"], row[4:8])
    session.device = (
        projected_model(
            Device,
            ["id", "user_id", "identity", "public_key", "trust_state", "revoked_at"],
            row[8:],
        )
        if row[8] is not None
        else None
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
            try:
                session = resolve_session(token)
            except DatabaseError:
                response = JsonResponse({"error": "Service temporarily unavailable"}, status=503)
                response["Cache-Control"] = "no-store"
                return response
            if session:
                request.user, request.device, request.haven_session = session.user, session.device, session
        response = self.get_response(request)
        if request.path.startswith("/api/v1/") and not request.path.endswith("/health"):
            request_observed((time.monotonic() - started) * 1000, response.status_code)
        response["Cache-Control"] = "no-store"
        return response
