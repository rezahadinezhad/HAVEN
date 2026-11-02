"""Expired enrollment disassociation without deleting trusted or referenced devices."""

import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import pytest
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from core import models as m
from core.retention import delete_pending_devices
from .conftest import post
from .test_view_once import bound_client

pytestmark = pytest.mark.django_db(transaction=True)


def pending(user, *, expired=True):
    did = uuid.uuid4()
    return m.Device.objects.create(
        id=did,
        user=user,
        identity=f"{user.pk}:{did}",
        public_key=secrets.token_bytes(32),
        label="Synthetic unfinished enrollment",
        challenge=secrets.token_hex(32),
        expires_at=timezone.now() + timedelta(minutes=-1 if expired else 1),
    )


def test_cleanup_disassociates_only_expired_pending_and_retains_replay_marker(settings):
    from core.views import b64

    settings.CRYPTO_READY = True
    client, approved = bound_client()
    expired = [pending(approved.user) for _ in range(2)]
    live = pending(approved.user, expired=False)
    revoked = pending(approved.user)
    revoked.trust_state = "revoked"
    revoked.revoked_at = timezone.now()
    revoked.save()
    now = timezone.now()
    assert delete_pending_devices(now, 1) == (1, 0)
    assert delete_pending_devices(now, 500) == (1, 0)
    assert delete_pending_devices(now, 500) == (0, 0)
    assert set(m.Device.objects.values_list("pk", flat=True)) == {approved.pk, live.pk, revoked.pk}
    assert set(m.DeviceEnrollmentTombstone.objects.values_list("pk", flat=True)) == {d.pk for d in expired}
    assert [f.name for f in m.DeviceEnrollmentTombstone._meta.fields] == ["id"]
    d = expired[0]
    response = post(
        client,
        "devices/enrollment/request",
        {
            "id": str(d.pk),
            "identity": d.identity,
            "public_key": b64(d.public_key),
            "label": d.label,
        },
    )
    assert response.status_code == 403
    assert not m.Device.objects.filter(pk=d.pk).exists()
    assert m.DeviceEnrollmentTombstone.objects.filter(pk=d.pk).exists()


def test_unexpected_reference_preserves_pending_device_and_does_not_commit_marker():
    _, approved = bound_client()
    d = pending(approved.user)
    m.Session.objects.create(
        user=approved.user,
        device=d,
        token_hash=secrets.token_hex(32),
        expires_at=timezone.now() + timedelta(hours=1),
    )
    assert delete_pending_devices(timezone.now(), 500) == (0, 1)
    assert m.Device.objects.filter(pk=d.pk).exists()
    assert not m.DeviceEnrollmentTombstone.objects.filter(pk=d.pk).exists()


def test_cleanup_waits_for_account_and_rechecks_concurrent_approval():
    _, approved = bound_client()
    d = pending(approved.user)
    waiting = Event()

    def collect():
        close_old_connections()

        def observed(execute, sql, params, many, context):
            if '"core_user"' in sql and "FOR UPDATE" in sql:
                waiting.set()
            return execute(sql, params, many, context)

        try:
            with connection.execute_wrapper(observed):
                return delete_pending_devices(timezone.now(), 500)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            m.User.objects.select_for_update().get(pk=approved.user_id)
            future = pool.submit(collect)
            assert waiting.wait(5)
            # Approval is the state change being raced; its signature validation
            # is independently exercised by actual enrollment/browser tests.
            m.Device.objects.filter(pk=d.pk).update(trust_state="approved", approved_by=approved)
        assert future.result(timeout=10) == (0, 0)
    assert m.Device.objects.get(pk=d.pk).trust_state == "approved"
    assert not m.DeviceEnrollmentTombstone.objects.filter(pk=d.pk).exists()


def test_verified_recovery_cannot_recycle_deleted_enrollment_but_fresh_id_succeeds(settings):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from core import protocol as p
    from core.views import b64

    settings.CRYPTO_READY = True
    client, approved = bound_client()
    old = pending(approved.user)
    assert delete_pending_devices(timezone.now(), 500) == (1, 0)
    recovery, fresh, next_recovery = [Ed25519PrivateKey.generate() for _ in range(3)]
    m.User.objects.filter(pk=approved.user_id).update(
        recovery_public_key=recovery.public_key().public_bytes_raw()
    )
    challenge = post(client, "recovery/start", {"user_id": str(approved.user_id)}).json()
    password = secrets.token_urlsafe(40)

    def body(did):
        device = {
            "id": str(did),
            "label": "Synthetic recovered device",
            "identity": f"{approved.user_id}:{did}",
            "public_key": b64(fresh.public_key().public_bytes_raw()),
        }
        replacement_key = b64(next_recovery.public_key().public_bytes_raw())
        signed = {
            "domain": "haven/recovery/v1",
            "user_id": str(approved.user_id),
            "challenge_id": challenge["id"],
            "nonce": challenge["nonce"],
            "password_hash": p.fingerprint(password.encode()),
            "device": device,
            "recovery_public_key": replacement_key,
        }
        return {
            "challenge_id": challenge["id"],
            "nonce": challenge["nonce"],
            "new_password": password,
            "device": device,
            "recovery_public_key": replacement_key,
            "signature": b64(recovery.sign(p.canonical(signed))),
            "device_signature": b64(fresh.sign(p.canonical(signed))),
        }

    assert post(client, "recovery/reset", body(old.pk)).status_code == 400
    approved.refresh_from_db()
    assert approved.revoked_at is None
    assert not m.Device.objects.filter(pk=old.pk).exists()
    assert m.RecoveryChallenge.objects.get(pk=challenge["id"]).consumed_at is None
    did = uuid.uuid4()
    assert post(client, "recovery/reset", body(did)).status_code == 200
    approved.refresh_from_db()
    assert approved.revoked_at is not None
    assert m.Device.objects.get(pk=did).trust_state == "approved"
    assert m.DeviceEnrollmentTombstone.objects.filter(pk=old.pk).exists()
