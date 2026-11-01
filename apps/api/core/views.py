import base64
import hashlib
import json
import secrets
import threading
import os
from pathlib import Path
from cryptography import x509
from datetime import timedelta
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, IntegrityError
from django.db.models import Sum, Q, Min, F
from django.http import HttpResponse
from django.middleware.csrf import get_token, rotate_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError, Throttled
from .observability import snapshot as operational_snapshot
from . import models as m, serializers as s
from .attachment_lifecycle import finish_if_consumed
from .middleware import digest
from . import protocol as p
from .privacy import rate_key, policy as privacy_policy
from .storage import reserve, CONVERSATION_OVERHEAD


def b64(value):
    return base64.b64encode(bytes(value)).decode()


def data(request, serializer):
    obj = serializer(data=request.data)
    obj.is_valid(raise_exception=True)
    return obj.validated_data


def rate(request, category, limit=60, identity=None):
    # Fixed one-minute window with atomic Redis add/incr; unavailable Redis fails closed.
    identity = (
        identity
        if identity is not None
        else (
            str(request.user.pk)
            if request.user and request.user.is_authenticated
            else request.META.get("REMOTE_ADDR", "")
        )
    )
    key = rate_key(category, identity, int(timezone.now().timestamp()) // 60)
    cache.add(key, 0, timeout=120)
    try:
        count = cache.incr(key)
    except ValueError:
        raise Throttled(wait=60) from None
    if count > limit:
        raise Throttled(wait=60)


def audit(user, category, target=""):
    m.AuditEvent.objects.create(actor=user, category=category, target_opaque_id=str(target))


def admin(request, super_only=False):
    allowed = ["superadmin"] if super_only else ["superadmin", "community_admin"]
    if request.user.role not in allowed:
        raise PermissionDenied()


def crypto_gate():
    if not settings.CRYPTO_READY:
        raise PermissionDenied("CRYPTO_NOT_READY: integrated protocol gate is blocked")


def trusted_device(request):
    crypto_gate()
    d = request._request.device
    if not d or d.trust_state != "approved" or d.revoked_at:
        raise PermissionDenied("Approved device required")
    return d


def membership(request, cid, lock=False, control=False):
    device = trusted_device(request)
    conv = get_object_or_404(
        m.Conversation.objects.select_for_update() if lock else m.Conversation.objects, pk=cid
    )
    member = get_object_or_404(m.Membership, conversation=conv, device=device, removed_at_epoch=None)
    if conv.status != "active" and request.method not in ("GET", "HEAD") and not control:
        raise PermissionDenied("Conversation requires rekey")
    return conv, member


@transaction.atomic
def issue_session(request, user):
    verified_hash = user.get_session_auth_hash()
    verified_generation = user.security_generation
    current = m.User.objects.select_for_update().get(pk=user.pk)
    if (
        not current.is_active
        or current.security_generation != verified_generation
        or not constant_time_compare(verified_hash, current.get_session_auth_hash())
    ):
        raise PermissionDenied("Account changed; sign in again")
    user = current
    # Password possession alone cannot accumulate unlimited pending sessions or
    # evict a session already bound to an approved browser's signing key.
    pending = m.Session.objects.filter(user=user, device=None, revoked_at=None)
    stale = list(pending.order_by("-created_at", "-pk").values_list("pk", flat=True)[4:])
    if stale:
        m.Session.objects.filter(pk__in=stale).delete()
    token = secrets.token_urlsafe(48)
    m.Session.objects.create(
        token_hash=digest(token), user=user, expires_at=timezone.now() + timedelta(hours=12)
    )
    rotate_token(request)
    response = Response({"user": user_json(user), "crypto_ready": settings.CRYPTO_READY})
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        token,
        max_age=43200,
        secure=True,
        httponly=True,
        samesite="Strict",
        path="/",
    )
    return response


def user_json(user):
    return {
        "id": str(user.pk),
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "security_generation": user.security_generation,
        "is_active": user.is_active,
    }


@method_decorator(csrf_protect, name="dispatch")
class View(APIView):
    pass


class Public(View):
    permission_classes = [AllowAny]


class Health(Public):
    def get(self, request):
        return Response(
            {
                "status": "available",
                "crypto_ready": settings.CRYPTO_READY,
                "name": settings.APP_NAME,
                "maintenance": (
                    m.ServerPolicy.objects.filter(pk=1).values_list("maintenance", flat=True).first()
                    or settings.MAINTENANCE
                ),
                "release_status": "BLOCKED",
            }
        )


class CSRF(Public):
    def get(self, request):
        return Response({"csrf": get_token(request)})


_login_slots = threading.BoundedSemaphore(4)


class Login(Public):
    def post(self, request):
        d = data(request, s.Login)
        source = request.META.get("REMOTE_ADDR", "")
        rate(request, "login.source", 30, identity=source)
        rate(request, "login.account_source", 5, identity=[m.User.normalize_username(d["username"]), source])
        # Bound simultaneous Argon2 memory/CPU, rather than letting one caller
        # spend a service-wide minute's sign-in quota for everybody else.
        if not _login_slots.acquire(blocking=False):
            raise Throttled(wait=1)
        try:
            user = authenticate(username=d["username"], password=d["password"])
        finally:
            _login_slots.release()
        if user is None:
            return Response({"error": "invalid_credentials"}, status=400)
        return issue_session(request, user)


class Redeem(Public):
    @transaction.atomic
    def post(self, request):
        rate(request, "redeem.total", 300, identity="service")
        d = data(request, s.Redeem)
        rate(request, "redeem", 5, identity=d["token"])
        invite = (
            m.Invitation.objects.select_for_update()
            .filter(
                token_hash=digest(d["token"]),
                consumed_at=None,
                revoked_at=None,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if not invite or (invite.intended_username and invite.intended_username != d["username"]):
            raise ValidationError("Registration unavailable")
        if m.User.objects.filter(username=d["username"]).exists():
            raise ValidationError("Registration unavailable")
        user = m.User(username=d["username"], display_name=d["display_name"])
        try:
            validate_password(d["password"], user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from None
        user.set_password(d["password"])
        user.save()
        invite.consumed_at = timezone.now()
        invite.save(update_fields=["consumed_at"])
        audit(user, "invitation.redeemed", invite.pk)
        return issue_session(request, user)


class Me(View):
    def get(self, request):
        return Response(
            {
                "user": user_json(request.user),
                "device_id": str(request._request.device.pk) if request._request.device else None,
                "crypto_ready": settings.CRYPTO_READY,
                "recovery_configured": bool(request.user.recovery_public_key),
            }
        )


class PrivacyPolicy(View):
    def get(self, request):
        return Response(privacy_policy())


class Logout(View):
    def post(self, request, all_sessions=False):
        sessions = (
            m.Session.objects.filter(user=request.user)
            if all_sessions
            else m.Session.objects.filter(pk=request.auth.pk)
        )
        sessions.update(revoked_at=timezone.now())
        response = Response({"ok": True})
        response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/", samesite="Strict")
        return response


class ChangePassword(View):
    @transaction.atomic
    def post(self, request):
        rate(request, "password", 3)
        d = data(request, s.Password)
        user = m.User.objects.select_for_update().get(pk=request.user.pk, is_active=True)
        if not user.check_password(d["old_password"]):
            raise ValidationError("Password change unavailable")
        try:
            validate_password(d["new_password"], user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from None
        user.set_password(d["new_password"])
        user.save(update_fields=["password"])
        m.Session.objects.filter(user=user).update(revoked_at=timezone.now())
        audit(user, "password.changed")
        return Response({"ok": True, "reauthenticate": True})


class Invitations(View):
    def get(self, request):
        admin(request)
        return Response(
            list(
                m.Invitation.objects.order_by("-created_at").values(
                    "id", "intended_username", "expires_at", "consumed_at", "revoked_at"
                )[:100]
            )
        )

    def post(self, request):
        admin(request)
        return create_invitation(request)


def invitation_capability(request, user=None):
    user = user or request.user
    now = timezone.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    policy = m.ServerPolicy.objects.filter(pk=1).first()
    pending = m.Invitation.objects.filter(creator=user, consumed_at=None, revoked_at=None, expires_at__gt=now)
    operator = user.role in ("superadmin", "community_admin")
    used = m.AuditEvent.objects.filter(
        actor=user, category="invitation.created", timestamp__gte=midnight
    ).count()
    device = request._request.device
    reason = "ready"
    if policy and policy.invitations_paused:
        reason = "paused"
    elif not operator:
        if not settings.CRYPTO_READY:
            reason = "crypto_unavailable"
        elif policy and not policy.member_invitations:
            reason = "members_disabled"
        elif not device or device.trust_state != "approved" or device.revoked_at:
            reason = "browser_not_ready"
        elif used >= 3:
            reason = "daily_limit"
        elif pending.count() >= 3:
            reason = "pending_limit"
    return {
        "allowed": reason == "ready",
        "reason": reason,
        "remaining_today": None if operator else max(0, 3 - used),
        "max_hours": 72 if operator else 24,
        "resets_at": midnight + timedelta(days=1),
        "pending_invitations": list(pending.order_by("expires_at").values("id", "expires_at")[:100]),
    }


@transaction.atomic
def create_invitation(request):
    d = data(request, s.Invite)
    # Serialize quota checks with creation/audit even when prior invitations are
    # redeemed and removed by privacy maintenance. Members never become admins.
    user = m.User.objects.select_for_update().get(pk=request.user.pk, is_active=True)
    capability = invitation_capability(request, user)
    if not capability["allowed"]:
        if capability["reason"] in ("daily_limit", "pending_limit"):
            raise Throttled(detail="Invitation limit reached. Try after the daily reset.", wait=3600)
        raise PermissionDenied(
            {
                "paused": "Invitations are paused by the operator",
                "members_disabled": "Ask the administrator for an invitation",
                "browser_not_ready": "Finish setting up this browser before inviting a friend",
                "crypto_unavailable": "Messaging is unavailable until security qualification is complete",
            }[capability["reason"]]
        )
    if d["hours"] > capability["max_hours"]:
        raise ValidationError("Member invitations last at most 24 hours")
    rate(request, "invitation.create", 10)
    token = secrets.token_urlsafe(48)
    invite = m.Invitation.objects.create(
        token_hash=digest(token),
        creator=user,
        intended_username=d.get("intended_username", ""),
        expires_at=timezone.now() + timedelta(hours=d["hours"]),
    )
    audit(user, "invitation.created", invite.pk)
    return Response({"id": str(invite.pk), "token": token, "expires_at": invite.expires_at}, status=201)


class FriendInvitations(View):
    def get(self, request):
        return Response(invitation_capability(request))

    def post(self, request):
        return create_invitation(request)


class FriendRevokeInvitation(View):
    @transaction.atomic
    def post(self, request, iid):
        invite = get_object_or_404(m.Invitation, pk=iid, creator=request.user)
        if m.Invitation.objects.filter(pk=invite.pk, revoked_at=None).update(revoked_at=timezone.now()):
            audit(request.user, "invitation.revoked", iid)
        return Response({"ok": True})


class RevokeInvitation(View):
    def post(self, request, iid):
        admin(request)
        invite = get_object_or_404(m.Invitation, pk=iid)
        invite.revoked_at = timezone.now()
        invite.save(update_fields=["revoked_at"])
        audit(request.user, "invitation.revoked", iid)
        return Response({"ok": True})


class Users(View):
    def get(self, request):
        admin(request)
        return Response([user_json(u) for u in m.User.objects.order_by("date_joined")[:200]])

    @transaction.atomic
    def patch(self, request, uid):
        admin(request, super_only=True)
        d = data(request, s.UserPatch)
        user = get_object_or_404(m.User.objects.select_for_update(), pk=uid)
        if user.role == "superadmin" or user.pk == request.user.pk:
            raise PermissionDenied("Use documented superadmin recovery")
        for k, v in d.items():
            setattr(user, k, v)
        user.save()
        if "role" in d:
            m.Session.objects.filter(user=user).update(revoked_at=timezone.now())
        if not user.is_active:
            m.Session.objects.filter(user=user).update(revoked_at=timezone.now())
            m.Device.objects.filter(user=user).update(revoked_at=timezone.now(), trust_state="revoked")
            m.Conversation.objects.filter(membership__device__user=user).update(status="rekey_required")
        audit(request.user, "user.updated", uid)
        return Response(user_json(user))


def certificate_status():
    path = os.environ.get("HAVEN_TLS_CERT_PATH")
    if not path:
        return {"status": "external_probe_required"}
    try:
        cert = x509.load_pem_x509_certificate(Path(path).read_bytes())
        remaining = (cert.not_valid_after_utc - timezone.now()).total_seconds()
        return {
            "status": "expired"
            if remaining <= 0
            else "renewal_required"
            if remaining < 172800
            else "validity_window_ok",
            "not_after": cert.not_valid_after_utc,
            "remaining_seconds": int(remaining),
            "notice": "Validity dates alone do not verify trust chain or carrier reachability",
        }
    except (OSError, ValueError):
        return {"status": "certificate_unavailable"}


class SystemStatus(View):
    def patch(self, request):
        admin(request)
        d = data(request, s.ServerPolicy)
        policy, _ = m.ServerPolicy.objects.get_or_create(pk=1)
        for key, value in d.items():
            setattr(policy, key, value)
        policy.save()
        audit(request.user, "system.policy_updated")
        return Response(
            {
                "invitations_paused": policy.invitations_paused,
                "member_invitations": policy.member_invitations,
                "maintenance": policy.maintenance,
            }
        )

    def get(self, request):
        admin(request)
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_database_size(current_database())")
            database_bytes = cursor.fetchone()[0]
        oldest = m.NotificationOutbox.objects.filter(sent_at=None).aggregate(at=Min("envelope__received_at"))[
            "at"
        ]
        import resource
        import shutil

        usage = resource.getrusage(resource.RUSAGE_SELF)
        try:
            cache.set("health", True, 5)
            redis_ok = cache.get("health") is True
        except Exception:
            redis_ok = False
        return Response(
            {
                "database": "ok",
                "metrics": operational_snapshot(),
                "privacy": privacy_policy(),
                "privacy_maintenance": cache.get("privacy:maintenance") or {"status": "not_observed"},
                "database_bytes": database_bytes,
                "logical_message_storage": m.StorageUsage.objects.filter(pk="service")
                .values("used_bytes", "pending_bytes", "envelope_count", "conversation_count")
                .first(),
                "api_process_max_rss_kib": usage.ru_maxrss,
                "api_process_cpu_seconds": usage.ru_utime + usage.ru_stime,
                "api_filesystem_free_bytes": shutil.disk_usage("/").free,
                "oldest_notification_seconds": int((timezone.now() - oldest).total_seconds())
                if oldest
                else 0,
                "active_sessions": m.Session.objects.filter(
                    revoked_at=None, expires_at__gt=timezone.now()
                ).count(),
                "redis": "ok" if redis_ok else "unavailable",
                "invitations_paused": m.ServerPolicy.objects.filter(pk=1, invitations_paused=True).exists(),
                "member_invitations": not m.ServerPolicy.objects.filter(
                    pk=1, member_invitations=False
                ).exists(),
                "users": m.User.objects.count(),
                "approved_devices": m.Device.objects.filter(trust_state="approved").count(),
                "envelopes": m.MessageEnvelope.objects.count(),
                "envelopes_last_minute": m.MessageEnvelope.objects.filter(
                    received_at__gte=timezone.now() - timedelta(minutes=1)
                ).count(),
                "outbox": m.NotificationOutbox.objects.filter(sent_at=None).count(),
                "ciphertext_bytes": m.AttachmentChunk.objects.aggregate(size=Sum("byte_length"))["size"] or 0,
                "crypto_ready": settings.CRYPTO_READY,
                "certificate": certificate_status(),
                "backup": list(m.BackupManifest.objects.order_by("-created_at").values()[:1]),
                "release": list(m.SoftwareRelease.objects.order_by("-build_timestamp").values()[:1]),
                "failover": "manual_fencing_required",
                "configured_origins": settings.ORIGINS,
                "endpoints": list(m.BootstrapEndpoint.objects.order_by("priority").values()),
                "maintenance": (
                    m.ServerPolicy.objects.filter(pk=1).values_list("maintenance", flat=True).first()
                    or settings.MAINTENANCE
                ),
            }
        )


def device_json(d):
    return {
        "id": str(d.pk),
        "user_id": str(d.user_id),
        "label": d.label,
        "identity": d.identity,
        "public_key": b64(d.public_key),
        "trust_state": d.trust_state,
        "revoked_at": d.revoked_at,
        "approved_by": str(d.approved_by_id) if d.approved_by_id else None,
        "challenge": d.challenge,
        "approval_signature": b64(d.approval_signature),
    }


def verify(key, signature, payload):
    try:
        Ed25519PublicKey.from_public_bytes(bytes(key)).verify(signature, payload)
    except (ValueError, InvalidSignature):
        raise ValidationError("Signature rejected") from None


def enrollment_payload(d):
    return f"haven/enrollment/v1:{d.user_id}:{d.pk}:{b64(d.public_key)}:{d.challenge}".encode()


class Devices(View):
    def get(self, request):
        return Response(
            [device_json(d) for d in m.Device.objects.filter(user=request.user).order_by("created_at")[:100]]
        )


class EnrollmentRequest(View):
    def post(self, request):
        crypto_gate()
        rate(request, "enrollment", 5)
        d = data(request, s.Enrollment)
        if len(d["public_key"]) != 32 or d["identity"] != f"{request.user.pk}:{d['id']}":
            raise ValidationError("Invalid device binding")
        device = m.Device.objects.filter(pk=d["id"]).first()
        if device:
            if (
                device.user_id != request.user.pk
                or bytes(device.public_key) != d["public_key"]
                or device.identity != d["identity"]
                or device.revoked_at
            ):
                raise PermissionDenied("Device identity conflict")
            if device.trust_state == "pending" and device.expires_at <= timezone.now():
                raise PermissionDenied("Enrollment expired; create a fresh device")
        else:
            device = m.Device.objects.create(
                id=d["id"],
                user=request.user,
                label=d["label"],
                public_key=d["public_key"],
                identity=d["identity"],
                challenge=secrets.token_hex(32),
                expires_at=timezone.now() + timedelta(minutes=10),
            )
        request.auth.device_challenge = secrets.token_hex(32)
        request.auth.save(update_fields=["device_challenge"])
        payload = f"haven/session/v1:{request.auth.pk}:{device.pk}:{request.auth.device_challenge}"
        return Response({**device_json(device), "signing_payload": payload}, status=201)


class EnrollmentApprove(View):
    @transaction.atomic
    def post(self, request):
        signer = trusted_device(request)
        d = data(request, s.Approval)
        target = get_object_or_404(
            m.Device.objects.select_for_update(),
            pk=d["device_id"],
            user=request.user,
            trust_state="pending",
            expires_at__gt=timezone.now(),
        )
        verify(signer.public_key, d["signature"], enrollment_payload(target))
        target.approved_by = signer
        target.approval_signature = d["signature"]
        target.trust_state = "approved"
        target.save()
        audit(request.user, "device.approved", target.pk)
        return Response({"ok": True})


class EnrollmentComplete(View):
    @transaction.atomic
    def post(self, request):
        crypto_gate()
        d = data(request, s.Approval)
        # Lock account to serialize first-device enrollment across independent requests.
        user = m.User.objects.select_for_update().get(pk=request.user.pk, is_active=True)
        target = get_object_or_404(
            m.Device.objects.select_for_update(), pk=d["device_id"], user=user, revoked_at=None
        )
        first = (
            not user.device_bootstrapped
            and not m.Device.objects.filter(user=user).exclude(trust_state="pending").exists()
        )
        if target.trust_state != "approved":
            if not (first and user.security_generation == 1) or target.expires_at <= timezone.now():
                raise PermissionDenied("Existing-device approval or verified recovery required")
        session = (
            m.Session.objects.select_for_update()
            .filter(pk=request.auth.pk, user=user, revoked_at=None, expires_at__gt=timezone.now())
            .first()
        )
        if not session or not constant_time_compare(session.auth_hash, user.get_session_auth_hash()):
            raise PermissionDenied("Session changed; sign in again")
        if not session.device_challenge:
            raise PermissionDenied("Request a fresh device session challenge")
        payload = f"haven/session/v1:{session.pk}:{target.pk}:{session.device_challenge}".encode()
        verify(target.public_key, d["signature"], payload)
        target.trust_state = "approved"
        target.save(update_fields=["trust_state"])
        user.device_bootstrapped = True
        user.save(update_fields=["device_bootstrapped"])
        session.device = target
        session.device_challenge = ""
        session.save(update_fields=["device", "device_challenge"])
        audit(user, "device.enrolled", target.pk)
        return Response(device_json(target))


class RevokeDevice(View):
    @transaction.atomic
    def post(self, request, did):
        trusted_device(request)
        device = get_object_or_404(m.Device, pk=did, user=request.user)
        device.trust_state = "revoked"
        device.revoked_at = timezone.now()
        device.save()
        m.Session.objects.filter(device=device).update(revoked_at=timezone.now())
        # Stop all application traffic until authorized MLS removal completes. Do not claim server revoke rekeys MLS.
        m.Conversation.objects.filter(membership__device=device).update(status="rekey_required")
        audit(request.user, "device.revoked", did)
        return Response({"ok": True, "rekey_required": True})


class PeerDevices(View):
    def get(self, request, uid):
        trusted_device(request)
        # Only contacts sharing a conversation; no public directory.
        shared = m.Membership.objects.filter(device=request._request.device).values("conversation_id")
        devices = m.Device.objects.filter(
            user_id=uid, trust_state="approved", revoked_at=None, membership__conversation_id__in=shared
        ).distinct()
        return Response([device_json(d) for d in devices])


class KeyPackages(View):
    def post(self, request, did=None):
        if did is not None:
            return self.claim(request, did)
        device = trusted_device(request)
        rate(request, "keypackage", 10)
        d = data(request, s.Package)
        result = p.public_validate(op="package", package=b64(d["package"]))
        if result != {"identity": device.identity, "public_key": b64(device.public_key)}:
            raise ValidationError("Key package credential mismatch")
        h = p.fingerprint(d["package"])
        old = m.DeviceKeyPackage.objects.filter(digest=h).first()
        if old:
            if old.device_id != device.pk or old.consumed_at is not None or old.expires_at <= timezone.now():
                raise ValidationError("Used package")
            return Response({"id": str(old.pk)})
        if (
            m.DeviceKeyPackage.objects.filter(
                device=device, consumed_at=None, expires_at__gt=timezone.now()
            ).count()
            >= 20
        ):
            raise ValidationError("Package quota")
        package = m.DeviceKeyPackage.objects.create(
            device=device, package=d["package"], digest=h, expires_at=timezone.now() + timedelta(days=7)
        )
        return Response({"id": str(package.pk)}, status=201)

    def get(self, request, did):
        requester = trusted_device(request)
        rate(request, "device.lookup", 30)
        target = get_object_or_404(m.Device.objects.select_related("user"), pk=did)
        if target.trust_state != "approved" or target.revoked_at or not target.user.is_active:
            shared_history = m.Membership.objects.filter(
                device=requester,
                removed_at_epoch=None,
                conversation_id__in=m.Membership.objects.filter(device=target).values("conversation_id"),
            ).exists()
            if target.user_id != request.user.pk and not shared_history:
                from django.http import Http404

                raise Http404
        # Historical credentials remain verifiable; this read grants no package, membership or trust.
        return Response({"device": device_json(target)})

    @transaction.atomic
    def claim(self, request, did):
        device = trusted_device(request)
        rate(request, "claim", 30)
        # The requested credential must be explicitly known by opaque device ID; client verifies fingerprint OOB.
        target = get_object_or_404(
            m.Device, pk=did, trust_state="approved", revoked_at=None, user__is_active=True
        )
        # A claim is an idempotent reservation for this claimant, never another Add authorization.
        p = (
            m.DeviceKeyPackage.objects.select_for_update()
            .filter(
                device=target, claimed_by=device, consumed_at__isnull=False, expires_at__gt=timezone.now()
            )
            .first()
        )
        if p is None:
            p = (
                m.DeviceKeyPackage.objects.select_for_update(skip_locked=True)
                .filter(device=target, consumed_at=None, expires_at__gt=timezone.now())
                .order_by("expires_at")
                .first()
            )
        if p is None:
            return Response({"error": "package_unavailable"}, status=409)
        p.consumed_at = timezone.now()
        p.claimed_by = device
        p.save()
        return Response({"id": str(p.pk), "package": b64(p.package), "device": device_json(target)})


class Conversations(View):
    def get(self, request, cid=None):
        device = trusted_device(request)
        query = m.Conversation.objects.filter(membership__device=device, membership__removed_at_epoch=None)
        if cid:
            conv = get_object_or_404(query, pk=cid)
            return Response(
                {
                    **conversation_json(conv),
                    "members": [
                        {
                            "device": device_json(x.device),
                            "role": x.role,
                            "valid_from_epoch": x.valid_from_epoch,
                            "leaving": bool(x.leave_signature),
                        }
                        for x in m.Membership.objects.select_related("device").filter(
                            conversation=conv, removed_at_epoch=None
                        )
                    ],
                    "genesis": conv.genesis,
                    "genesis_signature": b64(conv.genesis_signature),
                }
            )
        items, cursor = conversation_page(query, request)
        response = Response([conversation_json(x) for x in items])
        if cursor:
            response["X-Haven-Next-Cursor"] = cursor
        return response

    @transaction.atomic
    def post(self, request):
        device = trusted_device(request)
        rate(request, "conversation", 10)
        d = data(request, s.CreateConversation)
        expected = {
            "domain": "haven/genesis/v1",
            "id": str(d["id"]),
            "kind": d["kind"],
            "group_id": d["group_id"],
            "members": [{**p.certificate(device), "role": "owner"}],
        }
        if d["header"] != expected:
            raise ValidationError("Genesis binding")
        verify(device.public_key, d["signature"], p.canonical(expected))
        old = m.Conversation.objects.filter(pk=d["id"]).first()
        if old:
            if (
                old.creator_id != device.pk
                or old.genesis != expected
                or bytes(old.genesis_signature) != d["signature"]
            ):
                raise ValidationError("Conversation conflict")
            return Response(conversation_json(old))
        reserve(request.user.pk, CONVERSATION_OVERHEAD, conversations=1)
        c = m.Conversation.objects.create(
            id=d["id"],
            kind=d["kind"],
            creator=device,
            group_id=d["group_id"],
            genesis=expected,
            genesis_signature=d["signature"],
            head_hash=p.chain_hash(expected, d["signature"]),
        )
        m.Membership.objects.create(conversation=c, device=device, role="owner", valid_from_epoch=0)
        return Response(conversation_json(c), status=201)


def conversation_page(query, request):
    cursor = request.query_params.get("cursor")
    # Signed, expiring keyset cursor; no growing OFFSET scan. All pages in a
    # traversal share an upper creation-time boundary.
    cutoff = timezone.now().isoformat()
    if cursor:
        try:
            value = signing.loads(cursor, salt="haven/conversations/v1", max_age=3600)
            if value["device"] != str(request._request.device.pk):
                raise ValueError()
            cutoff = value["cutoff"]
            query = query.filter(
                Q(created_at__lt=value["time"]) | Q(created_at=value["time"], pk__lt=value["id"])
            )
        except (signing.BadSignature, ValueError, TypeError, KeyError):
            raise ValidationError("Invalid conversation cursor") from None
    rows = list(query.filter(created_at__lte=cutoff).order_by("-created_at", "-pk")[:101])
    next_cursor = None
    if len(rows) > 100:
        last = rows[99]
        next_cursor = signing.dumps(
            {
                "device": str(request._request.device.pk),
                "cutoff": cutoff,
                "time": last.created_at.isoformat(),
                "id": str(last.pk),
            },
            salt="haven/conversations/v1",
            compress=True,
        )
    return rows[:100], next_cursor


def conversation_json(c):
    return {
        "id": str(c.pk),
        "kind": c.kind,
        "group_id": c.group_id,
        "epoch": c.epoch,
        "last_seq": c.last_seq,
        "status": c.status,
        "head_hash": c.head_hash,
        "receipt_version": c.receipt_version,
    }


def envelope_json(e, device=None, proof=False):
    result = {
        "id": str(e.pk),
        "client_message_id": str(e.client_message_id),
        "sender_device": str(e.sender_device_id),
        "v": e.protocol_version,
        "seq": e.server_seq,
        "epoch": e.group_epoch,
        "kind": e.kind,
        "header": e.header,
        "signature": b64(e.signature),
        "chain_hash": e.chain_hash,
    }
    if not proof:
        result.update(
            ciphertext=b64(e.ciphertext), received_at=e.received_at, ciphertext_retired=e.ciphertext_retired
        )
        if e.kind == "commit":
            control = e.cryptocontrolevent
            result["transition"] = control.transition
            if device and control.welcome_device_id == device.pk:
                result["welcome"] = b64(control.welcome)
    return result


def request_hash(d):
    # Parent and signature may be rebased after a same-epoch CAS conflict. Ciphertext and intent cannot change.
    return hashlib.sha256(
        json.dumps(
            {k: v for k, v in d.items() if k not in ("header", "signature")},
            default=lambda x: b64(x) if isinstance(x, bytes) else str(x),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def prior_envelope(c, member, d):
    old = m.MessageEnvelope.objects.filter(
        sender_device=member.device, client_message_id=d["client_message_id"]
    ).first()
    if old and (old.conversation_id != c.pk or old.request_digest != request_hash(d)):
        raise ValidationError("Idempotency conflict")
    return old


def save_envelope(request, c, member, d, kind, transition=None):
    expected = {
        "domain": "haven/envelope/v1",
        "v": 1,
        "conversation_id": str(c.pk),
        "group_id": c.group_id,
        "sender_device": str(member.device_id),
        "client_message_id": str(d["client_message_id"]),
        "epoch": c.epoch,
        "seq": c.last_seq + 1,
        "previous_hash": c.head_hash,
        "ciphertext_hash": p.fingerprint(d["ciphertext"]),
        "transition": transition,
    }
    if c.epoch != d["epoch"] or d["header"] != expected:
        raise ValidationError("HEAD_CONFLICT: synchronize before retry")
    verify(member.device.public_key, d["signature"], p.canonical(expected))
    wire = p.public_validate(op="wire", ciphertext=b64(d["ciphertext"]))
    if wire != {"group_id": c.group_id, "epoch": c.epoch}:
        raise ValidationError("MLS wire binding")
    charged = len(d["ciphertext"]) + len(p.canonical(expected)) + len(d["signature"]) + 4096
    if transition:
        charged += len(p.canonical(transition)) + len(d.get("welcome", b""))
    reserve(
        request.user.pk, charged, pending=len(d["ciphertext"]) if kind == "application" else 0, envelopes=1
    )
    c.last_seq += 1
    c.head_hash = p.chain_hash(expected, d["signature"])
    c.save(update_fields=["last_seq", "head_hash"])
    env = m.MessageEnvelope.objects.create(
        conversation=c,
        sender_device=member.device,
        server_seq=c.last_seq,
        client_message_id=d["client_message_id"],
        group_epoch=c.epoch,
        kind=kind,
        ciphertext=d["ciphertext"],
        request_digest=request_hash(d),
        header=expected,
        signature=d["signature"],
        chain_hash=c.head_hash,
    )
    m.NotificationOutbox.objects.create(envelope=env)
    return env


def accepted(e, device, created=True):
    return Response(
        {
            "id": str(e.pk),
            "seq": e.server_seq,
            "state": "server_accepted",
            "envelope": envelope_json(e, device),
        },
        status=201 if created else 200,
    )


class Messages(View):
    def get(self, request, cid):
        c, member = membership(request, cid)
        try:
            after = max(int(request.query_params.get("after_seq", "0")), member.start_seq)
            limit = min(max(int(request.query_params.get("limit", "100")), 1), 100)
        except ValueError:
            raise ValidationError("Invalid cursor") from None
        envs = list(
            m.MessageEnvelope.objects.filter(conversation=c, server_seq__gt=after).order_by("server_seq")[
                :limit
            ]
        )
        if any(e.ciphertext_retired for e in envs):
            return Response({"error": "history_retired_use_verified_fresh_device"}, status=410)
        return Response(
            {
                "messages": [envelope_json(e, member.device) for e in envs],
                "last_seq": c.last_seq,
                "head_hash": c.head_hash,
            }
        )

    @transaction.atomic
    def post(self, request, cid):
        rate(request, "send", 120)
        d = data(request, s.Envelope)
        c, member = membership(request, cid, lock=True)
        old = prior_envelope(c, member, d)
        if old:
            return accepted(old, member.device, False)
        return accepted(save_envelope(request, c, member, d, "application"), member.device)


class Proofs(View):
    def get(self, request, cid):
        c, _ = membership(request, cid)
        try:
            after = max(0, int(request.query_params.get("after_seq", "0")))
        except ValueError:
            raise ValidationError("Invalid cursor") from None
        items = (
            m.MessageEnvelope.objects.defer(
                "ciphertext", "request_digest", "received_at", "ciphertext_retired"
            )
            .filter(conversation=c, server_seq__gt=after)
            .order_by("server_seq")[:100]
        )
        return Response(
            {
                "proofs": [envelope_json(e, proof=True) for e in items],
                "last_seq": c.last_seq,
                "head_hash": c.head_hash,
                "genesis": c.genesis,
                "genesis_signature": b64(c.genesis_signature),
            }
        )


class MembersPropose(View):
    @transaction.atomic
    def post(self, request, cid):
        d = data(request, s.Leave)
        c, member = membership(request, cid, lock=True, control=True)
        if member.role == "owner":
            raise PermissionDenied("Transfer ownership before requesting departure")
        verify(
            member.device.public_key,
            d["signature"],
            f"haven/leave/v1:{c.pk}:{member.device_id}:{c.epoch}".encode(),
        )
        member.leave_signature = d["signature"]
        member.save(update_fields=["leave_signature"])
        c.status = "rekey_required"
        c.save(update_fields=["status"])
        audit(request.user, "membership.leave_requested", cid)
        return Response(
            {
                "state": "awaiting_authenticated_removal",
                "notice": "An owner or moderator must commit MLS removal before messaging resumes.",
            }
        )


class CryptoEvents(Messages):
    @transaction.atomic
    def post(self, request, cid):
        rate(request, "membership", 30)
        d = data(request, s.Control)
        c, member = membership(request, cid, lock=True, control=True)
        old = prior_envelope(c, member, d)
        if old:
            return accepted(old, member.device, False)
        if member.role not in ("owner", "moderator"):
            raise PermissionDenied("Owner or moderator required")
        action = d["action"]
        target = get_object_or_404(m.Device, pk=d.get("device_id")) if action != "update" else None
        before = p.roster(c)
        after = [dict(x) for x in before]
        if action == "add":
            if target.trust_state != "approved" or target.revoked_at or not target.user.is_active:
                raise PermissionDenied("Unapproved target")
            if m.Membership.objects.filter(conversation=c, device=target).exists():
                raise ValidationError("Re-add requires a fresh device credential")
            users_after = len({x["user_id"] for x in before} | {str(target.user_id)})
            if len(before) >= 100 or users_after > (2 if c.kind == "direct" else 50):
                raise ValidationError("Conversation member limit")
            kp = get_object_or_404(
                m.DeviceKeyPackage,
                pk=d.get("key_package_id"),
                device=target,
                claimed_by=member.device,
                consumed_at__isnull=False,
                expires_at__gt=timezone.now(),
            )
            if not d.get("welcome"):
                raise ValidationError("Welcome required")
            after.append({**p.certificate(target), "role": "member"})
        elif action == "remove":
            target_member = get_object_or_404(
                m.Membership, conversation=c, device=target, removed_at_epoch=None
            )
            if (
                target_member.role == "owner"
                or target.pk == member.device_id
                or (member.role == "moderator" and target_member.role != "member")
            ):
                raise PermissionDenied("Transfer ownership or obtain owner removal")
            after = [x for x in after if x["id"] != str(target.pk)]
        elif action in ("transfer", "role"):
            if member.role != "owner":
                raise PermissionDenied("Owner required")
            target_member = get_object_or_404(
                m.Membership, conversation=c, device=target, removed_at_epoch=None
            )
            if target.pk == member.device_id or target.revoked_at or target.trust_state != "approved":
                raise ValidationError("Invalid authority target")
            for item in after:
                if action == "transfer" and item["id"] == str(member.device_id):
                    item["role"] = "moderator"
                if item["id"] == str(target.pk):
                    item["role"] = "owner" if action == "transfer" else d.get("role", "member")
        claimed_transition = d["header"].get("transition")
        if not isinstance(claimed_transition, dict):
            raise ValidationError("Authenticated transition required")
        state_hash = claimed_transition.get("state_hash")
        if (
            not isinstance(state_hash, str)
            or len(state_hash) != 64
            or any(x not in "0123456789abcdef" for x in state_hash)
        ):
            raise ValidationError("MLS epoch confirmation required")
        transition = {
            "action": action,
            "device_id": str(target.pk) if target else None,
            "next_epoch": c.epoch + 1,
            "members": sorted(after, key=lambda x: x["id"]),
            "welcome_hash": p.fingerprint(d.get("welcome", b"")),
            "state_hash": state_hash,
        }
        env = save_envelope(request, c, member, d, "commit", transition)
        m.CryptoControlEvent.objects.create(
            envelope=env,
            transition=transition,
            signature=d["signature"],
            welcome_device=target if action == "add" else None,
            welcome=d.get("welcome", b""),
        )
        c.epoch += 1
        if action == "add":
            kp.expires_at = timezone.now()
            kp.save(update_fields=["expires_at"])
            m.Membership.objects.create(
                conversation=c, device=target, valid_from_epoch=c.epoch, start_seq=env.server_seq - 1
            )
        elif action == "remove":
            m.Membership.objects.filter(conversation=c, device=target).update(removed_at_epoch=c.epoch)
        elif action in ("transfer", "role"):
            if action == "transfer":
                m.Membership.objects.filter(conversation=c, device=member.device).update(role="moderator")
            m.Membership.objects.filter(conversation=c, device=target).update(
                role="owner" if action == "transfer" else d.get("role", "member")
            )
        unsafe = (
            m.Membership.objects.filter(conversation=c, removed_at_epoch=None)
            .filter(Q(device__revoked_at__isnull=False) | ~Q(leave_signature=b""))
            .exists()
        )
        c.status = "rekey_required" if unsafe else "active"
        c.save(update_fields=["epoch", "status"])
        return accepted(env, member.device)


class Acks(View):
    def get(self, request, cid):
        c, member = membership(request, cid)
        return Response(
            {
                "version": c.receipt_version,
                "cursors": list(
                    m.DeliveryCursor.objects.filter(conversation=c)
                    .exclude(device__user_id=member.device.user_id)
                    .values("device_id", "last_acked_seq")
                ),
            }
        )

    @transaction.atomic
    def post(self, request, cid):
        d = data(request, s.Ack)
        c, member = membership(request, cid, lock=True, control=True)
        if d["seq"] > c.last_seq:
            raise ValidationError("Future cursor")
        cursor, _ = m.DeliveryCursor.objects.get_or_create(device=member.device, conversation=c)
        if d["seq"] > cursor.last_acked_seq:
            cursor.last_acked_seq = d["seq"]
            cursor.save(update_fields=["last_acked_seq", "updated_at"])
            m.Conversation.objects.filter(pk=c.pk).update(receipt_version=F("receipt_version") + 1)
        # Bounded updates: receipts are derived from durable per-device cursor, not human reading.
        return Response({"seq": cursor.last_acked_seq, "state": "recipient_synced"})


class Sync(View):
    def get(self, request):
        device = trusted_device(request)
        convs = m.Conversation.objects.filter(membership__device=device, membership__removed_at_epoch=None)
        items, cursor = conversation_page(convs, request)
        return Response(
            {
                "conversations": [conversation_json(c) for c in items],
                "next_cursor": cursor,
                "strategy": "per_conversation_sequence",
                "max_page": 100,
            }
        )


class Attachments(View):
    @transaction.atomic
    def post(self, request):
        d = data(request, s.AttachmentInit)
        # Quota is per account across all conversations and devices. Serialize
        # reservations on the account before acquiring the conversation lock.
        m.User.objects.select_for_update().get(pk=request.user.pk, is_active=True)
        c, member = membership(request, d["conversation_id"], lock=True)
        rate(request, "upload", 30)
        old = m.EncryptedAttachment.objects.filter(pk=d["id"]).first()
        if old:
            if (
                old.uploader_device_id != member.device_id
                or old.conversation_id != c.pk
                or old.ciphertext_size != d["ciphertext_size"]
                or old.chunk_count != d["chunk_count"]
                or old.view_once != d["view_once"]
                or old.status in ("deleted", "consumed")
            ):
                raise ValidationError("Upload identity conflict")
            return Response({"id": str(old.pk), "status": old.status})
        if m.AttachmentTombstone.objects.filter(pk=d["id"]).exists():
            raise ValidationError("Attachment identifier retired")
        if d["view_once"]:
            # The marker is created with the original upload, not at cleanup time,
            # so an expired/deleted blob can never reset the original view budget.
            try:
                with transaction.atomic():
                    m.AttachmentTombstone.objects.create(id=d["id"])
            except IntegrityError as error:
                raise ValidationError("Attachment identifier retired") from error
        total = (
            m.EncryptedAttachment.objects.filter(uploader_device__user=request.user)
            .exclude(status__in=["deleted", "consumed"])
            .aggregate(size=Sum("ciphertext_size"))["size"]
            or 0
        )
        if total + d["ciphertext_size"] > 250 * 1024 * 1024:
            raise ValidationError("Storage quota exceeded")
        a = m.EncryptedAttachment.objects.create(
            id=d["id"],
            uploader_device=member.device,
            conversation=c,
            epoch=c.epoch,
            ciphertext_size=d["ciphertext_size"],
            chunk_count=d["chunk_count"],
            view_once=d["view_once"],
            expires_at=timezone.now() + timedelta(days=settings.ATTACHMENT_RETENTION_DAYS),
        )
        if a.view_once:
            # Snapshot eligible accounts. Later joins cannot acquire a historical view.
            recipients = (
                m.Membership.objects.filter(
                    conversation=c,
                    removed_at_epoch=None,
                    device__trust_state="approved",
                    device__revoked_at=None,
                    device__user__is_active=True,
                )
                .exclude(device__user=request.user)
                .values_list("device__user_id", flat=True)
                .distinct()
            )
            if not recipients:
                raise ValidationError("View-once media needs a recipient")
            m.AttachmentView.objects.bulk_create(
                [m.AttachmentView(attachment=a, user_id=uid) for uid in recipients]
            )
        return Response({"id": str(a.pk)}, status=201)


def attachment(request, aid, write=False):
    a = get_object_or_404(m.EncryptedAttachment, pk=aid, expires_at__gt=timezone.now())
    _, member = membership(request, a.conversation_id)
    if member.valid_from_epoch > a.epoch or a.status == "deleted":
        raise PermissionDenied()
    if write and a.uploader_device_id != member.device_id:
        raise PermissionDenied()
    return a


class Chunk(View):
    def put(self, request, aid, index):
        a = attachment(request, aid, True)
        if a.status != "uploading" or index >= a.chunk_count:
            raise ValidationError("Chunk unavailable")
        # Nginx caps request body before buffering; Django additionally bounds declared/actual bytes.
        if int(request.META.get("CONTENT_LENGTH", "0")) > 1048640:
            raise ValidationError("Chunk too large")
        value = request.body
        if not 16 <= len(value) <= 1048640:
            raise ValidationError("Invalid chunk size")
        h = hashlib.sha256(value).hexdigest()
        with transaction.atomic():
            locked = m.EncryptedAttachment.objects.select_for_update().get(pk=a.pk)
            if locked.status != "uploading":
                raise ValidationError("Upload closed")
            old = m.AttachmentChunk.objects.filter(attachment=a, chunk_index=index).first()
            if old:
                if old.content_hash != h:
                    raise ValidationError("Chunk conflict")
            else:
                size = (
                    m.AttachmentChunk.objects.filter(attachment=a).aggregate(size=Sum("byte_length"))["size"]
                    or 0
                )
                if size + len(value) > a.ciphertext_size:
                    raise ValidationError("Declared size exceeded")
                m.AttachmentChunk.objects.create(
                    attachment=a, chunk_index=index, content_hash=h, byte_length=len(value), ciphertext=value
                )
        return Response({"hash": h, "index": index})

    @transaction.atomic
    def get(self, request, aid, index):
        a = attachment(request, aid)
        if a.view_once:
            a = m.EncryptedAttachment.objects.select_for_update().get(pk=a.pk)
            view = get_object_or_404(m.AttachmentView, attachment=a, user=request.user)
            token = request.headers.get("X-Haven-View-Token", "")
            if (
                len(token) != 64
                or not view.token_hash
                or not view.consumed
                or view.opened_by_id != request._request.device.pk
                or not view.lease_expires_at
                or view.lease_expires_at <= timezone.now()
                or not secrets.compare_digest(view.token_hash, digest(token))
            ):
                raise PermissionDenied("View-once session unavailable")
        if a.status != "complete":
            raise ValidationError("Upload incomplete")
        chunk = get_object_or_404(m.AttachmentChunk, attachment=a, chunk_index=index)
        response = HttpResponse(bytes(chunk.ciphertext), content_type="application/octet-stream")
        response["X-Ciphertext-SHA256"] = chunk.content_hash
        response["Content-Disposition"] = "attachment"
        return response


class CompleteAttachment(View):
    @transaction.atomic
    def post(self, request, aid):
        a = attachment(request, aid, True)
        a = m.EncryptedAttachment.objects.select_for_update().get(pk=a.pk)
        chunks = m.AttachmentChunk.objects.filter(attachment=a)
        size = chunks.aggregate(size=Sum("byte_length"))["size"]
        if chunks.count() != a.chunk_count or size != a.ciphertext_size:
            raise ValidationError("Upload incomplete")
        a.status = "complete"
        a.save(update_fields=["status"])
        return Response({"ok": True})


class DeleteAttachment(View):
    @transaction.atomic
    def delete(self, request, aid):
        a = attachment(request, aid, True)
        a = m.EncryptedAttachment.objects.select_for_update().get(pk=a.pk)
        a.status = "deleted"
        a.save(update_fields=["status"])
        m.AttachmentChunk.objects.filter(attachment=a).delete()
        return Response({"ok": True})


class ViewOnceAttachment(View):
    def get(self, request, aid):
        a = attachment(request, aid)
        if not a.view_once:
            raise ValidationError("Not view-once media")
        if a.uploader_device.user_id == request.user.pk:
            return Response({"state": "sent"})
        if a.status == "consumed":
            return Response({"state": "opened"})
        view = get_object_or_404(m.AttachmentView, attachment=a, user=request.user)
        return Response({"state": "opened" if view.consumed else "available"})

    @transaction.atomic
    def post(self, request, aid):
        d = data(request, s.AttachmentViewToken)
        a = attachment(request, aid)
        # Serialize with membership changes, other claims and final ciphertext cleanup.
        membership(request, a.conversation_id, lock=True)
        a = m.EncryptedAttachment.objects.select_for_update().get(pk=a.pk)
        if not a.view_once or a.status != "complete":
            raise PermissionDenied("View-once media unavailable")
        rate(request, "view-once", 30)
        view = get_object_or_404(
            m.AttachmentView.objects.select_for_update(), attachment=a, user=request.user
        )
        now = timezone.now()
        if view.consumed:
            # Retry of the SAME in-memory session after a lost response, never a new view.
            if not (
                view.opened_by_id == request._request.device.pk
                and view.lease_expires_at
                and view.lease_expires_at > now
                and view.token_hash
                and secrets.compare_digest(view.token_hash, digest(d["token"]))
            ):
                raise PermissionDenied("View-once media already opened")
        else:
            view.consumed = True
            view.opened_by = request._request.device
            view.token_hash = digest(d["token"])
            view.lease_expires_at = now + timedelta(minutes=10)
            view.save(update_fields=["consumed", "opened_by", "token_hash", "lease_expires_at"])
        return Response({"expires_at": view.lease_expires_at.isoformat()})


class CloseViewOnceAttachment(View):
    @transaction.atomic
    def post(self, request, aid):
        d = data(request, s.AttachmentViewToken)
        a = attachment(request, aid)
        a = m.EncryptedAttachment.objects.select_for_update().get(pk=a.pk)
        view = get_object_or_404(m.AttachmentView, attachment=a, user=request.user)
        if (
            not a.view_once
            or view.opened_by_id != request._request.device.pk
            or not view.token_hash
            or not secrets.compare_digest(view.token_hash, digest(d["token"]))
        ):
            raise PermissionDenied("View-once session unavailable")
        view.token_hash = ""
        view.opened_by = None
        view.lease_expires_at = None
        view.save(update_fields=["token_hash", "lease_expires_at", "opened_by"])
        finish_if_consumed(a)
        return Response({"ok": True})


class RecoveryKey(View):
    @transaction.atomic
    def post(self, request):
        trusted_device(request)
        d = data(request, s.RecoveryKey)
        user = m.User.objects.select_for_update().get(pk=request.user.pk)
        if len(d["public_key"]) != 32 or (
            user.recovery_public_key and bytes(user.recovery_public_key) != d["public_key"]
        ):
            raise ValidationError("Recovery already provisioned or invalid key")
        user.recovery_public_key = d["public_key"]
        user.save(update_fields=["recovery_public_key"])
        audit(user, "recovery.provisioned")
        return Response({"ok": True})


class RecoveryStart(Public):
    def post(self, request):
        crypto_gate()
        rate(request, "recovery.total", 120, identity="service")
        d = data(request, s.RecoveryStart)
        rate(request, "recovery", 3, identity=d["user_id"])
        user = m.User.objects.filter(pk=d["user_id"], is_active=True).first()
        nonce = secrets.token_hex(32)
        challenge = m.RecoveryChallenge.objects.create(
            user=user, nonce_hash=digest(nonce), expires_at=timezone.now() + timedelta(minutes=5)
        )
        return Response({"id": str(challenge.pk), "nonce": nonce})


class RecoveryReset(Public):
    @transaction.atomic
    def post(self, request):
        crypto_gate()
        rate(request, "recovery.reset.total", 120, identity="service")
        d = data(request, s.RecoveryReset)
        rate(request, "recovery.reset", 3, identity=d["challenge_id"])
        challenge = get_object_or_404(
            m.RecoveryChallenge.objects.select_for_update(),
            pk=d["challenge_id"],
            nonce_hash=digest(d["nonce"]),
            consumed_at=None,
            expires_at__gt=timezone.now(),
        )
        user = m.User.objects.select_for_update().filter(pk=challenge.user_id, is_active=True).first()
        if not user or len(bytes(user.recovery_public_key)) != 32:
            raise ValidationError("Recovery rejected")
        device = d["device"]
        if (
            len(device["public_key"]) != 32
            or device["identity"] != f"{user.pk}:{device['id']}"
            or len(d["recovery_public_key"]) != 32
        ):
            raise ValidationError("Recovery binding")
        signed = {
            "domain": "haven/recovery/v1",
            "user_id": str(user.pk),
            "challenge_id": str(challenge.pk),
            "nonce": d["nonce"],
            "password_hash": p.fingerprint(d["new_password"].encode()),
            "device": {**device, "id": str(device["id"]), "public_key": b64(device["public_key"])},
            "recovery_public_key": b64(d["recovery_public_key"]),
        }
        verify(user.recovery_public_key, d["signature"], p.canonical(signed))
        verify(device["public_key"], d["device_signature"], p.canonical(signed))
        try:
            validate_password(d["new_password"], user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from None
        now = timezone.now()
        m.Session.objects.filter(user=user).update(revoked_at=now)
        m.Device.objects.filter(user=user).update(revoked_at=now, trust_state="revoked")
        m.Conversation.objects.filter(membership__device__user=user).update(status="rekey_required")
        user.security_generation += 1
        user.device_bootstrapped = True
        user.recovery_public_key = d["recovery_public_key"]
        user.set_password(d["new_password"])
        user.save()
        fresh = m.Device.objects.create(
            **device, user=user, trust_state="approved", challenge=secrets.token_hex(32), expires_at=now
        )
        challenge.consumed_at = now
        challenge.save(update_fields=["consumed_at"])
        audit(user, "recovery.security_reset", fresh.pk)
        response = issue_session(request, user)
        session = m.Session.objects.get(
            token_hash=digest(response.cookies[settings.SESSION_COOKIE_NAME].value)
        )
        session.device = fresh
        session.save(update_fields=["device"])
        return response


class AdminDevices(View):
    def get(self, request):
        admin(request)
        return Response(
            list(
                m.Device.objects.order_by("-created_at").values(
                    "id", "user_id", "trust_state", "created_at", "revoked_at"
                )[:500]
            )
        )

    @transaction.atomic
    def post(self, request, did):
        admin(request)
        rate(request, "admin.device_revoke", 20)
        device = get_object_or_404(m.Device, pk=did)
        device.revoked_at = timezone.now()
        device.trust_state = "revoked"
        device.save(update_fields=["revoked_at", "trust_state"])
        m.Session.objects.filter(device=device).update(revoked_at=timezone.now())
        m.Conversation.objects.filter(membership__device=device, membership__removed_at_epoch=None).update(
            status="rekey_required"
        )
        audit(request.user, "admin.device_revoked", did)
        return Response({"ok": True, "rekey_required": True})


class DisableAccount(View):
    @transaction.atomic
    def post(self, request):
        trusted_device(request)
        rate(request, "account.disable", 3)
        d = data(request, s.DisableAccount)
        user = m.User.objects.select_for_update().get(pk=request.user.pk)
        if not user.check_password(d["password"]) or user.role == "superadmin":
            raise PermissionDenied("Use the documented administrator recovery ceremony")
        user.is_active = False
        user.save(update_fields=["is_active"])
        m.Session.objects.filter(user=user).update(revoked_at=timezone.now())
        m.Device.objects.filter(user=user).update(revoked_at=timezone.now(), trust_state="revoked")
        m.Conversation.objects.filter(membership__device__user=user).update(status="rekey_required")
        audit(user, "account.disabled")
        response = Response(
            {
                "ok": True,
                "notice": "Ciphertext and opaque audit identifiers follow retention policy. Recipient copies cannot be remotely erased.",
            }
        )
        response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/", samesite="Strict")
        return response
