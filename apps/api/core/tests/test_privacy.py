"""Actual PostgreSQL retention/authorization tests; browser suite exercises real MLS."""

import hashlib
import secrets
import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from core import models as m
from core.privacy import rate_key
from core.retention import cleanup, retire_delivered
from core.cache_serializer import JSONCacheSerializer
from .conftest import login, post
from .test_view_once import bound_client

pytestmark = pytest.mark.django_db


def delivery():
    a, ad = bound_client()
    b, bd = bound_client()
    c = m.Conversation.objects.create(creator=ad, kind="direct", group_id=uuid.uuid4().hex, last_seq=2)
    for device in (ad, bd):
        m.Membership.objects.create(conversation=c, device=device, valid_from_epoch=0)
    messages = []
    for seq, kind in [(1, "commit"), (2, "application")]:
        e = m.MessageEnvelope.objects.create(
            conversation=c,
            sender_device=ad,
            server_seq=seq,
            client_message_id=uuid.uuid4(),
            group_epoch=0,
            kind=kind,
            ciphertext=secrets.token_bytes(64),
            request_digest="d" * 64,
            header={"seq": seq},
            signature=b"s" * 64,
            chain_hash="a" * 64,
        )
        m.MessageEnvelope.objects.filter(pk=e.pk).update(received_at=timezone.now() - timedelta(days=2))
        messages.append(e)
    return a, ad, b, bd, c, messages


def ack(device, conv, seq):
    m.DeliveryCursor.objects.update_or_create(
        device=device, conversation=conv, defaults={"last_acked_seq": seq}
    )


def test_retirement_requires_every_device_and_preserves_proofs(settings):
    settings.CRYPTO_READY = True
    a, ad, b, bd, c, (control, event) = delivery()
    before_header, before_bytes = event.header, bytes(event.ciphertext)
    ack(ad, c, 2)
    assert retire_delivered(timezone.now()) == 0  # Offline recipient is protected.
    ack(bd, c, 1)
    assert retire_delivered(timezone.now()) == 0  # A partial ACK is insufficient.
    ack(bd, c, 2)
    # A second approved device for the same account has its own durable cursor.
    _, second = bound_client(bd.user)
    m.Membership.objects.create(conversation=c, device=second, valid_from_epoch=0)
    assert retire_delivered(timezone.now()) == 0
    ack(second, c, 2)
    assert retire_delivered(timezone.now()) == 1
    event.refresh_from_db()
    control.refresh_from_db()
    assert event.ciphertext_retired and bytes(event.ciphertext) == b"" and event.received_at is None
    assert event.header == before_header and event.signature and event.request_digest == "d" * 64
    assert bytes(control.ciphertext) and control.received_at and not control.ciphertext_retired
    assert before_bytes not in bytes(event.ciphertext)
    assert retire_delivered(timezone.now()) == 0
    proofs = a.get(f"/api/v1/conversations/{c.pk}/proofs", secure=True)
    assert proofs.status_code == 200 and len(proofs.json()["proofs"]) == 2
    # Never silently skip missing application ciphertext in an old/restored vault.
    stale = b.get(f"/api/v1/conversations/{c.pk}/messages", secure=True)
    assert stale.status_code == 410 and stale.json()["error"].startswith("history_retired")
    assert b.get(f"/api/v1/conversations/{c.pk}/messages?after_seq=2", secure=True).json()["messages"] == []


def test_grace_epoch_revocation_and_batch_bounds():
    _, ad, _, bd, c, (_, event) = delivery()
    ack(ad, c, 2)
    # Newly joined devices cannot receive an older epoch and do not block its retirement.
    _, later = bound_client()
    m.Membership.objects.create(conversation=c, device=later, valid_from_epoch=1)
    # Revoked device can no longer fetch ciphertext; re-enrollment requires new identity.
    bd.revoked_at = timezone.now()
    bd.save()
    m.MessageEnvelope.objects.filter(pk=event.pk).update(received_at=timezone.now())
    assert retire_delivered(timezone.now()) == 0
    assert retire_delivered(timezone.now() + timedelta(hours=25), batch_size=0) == 0
    assert retire_delivered(timezone.now() + timedelta(hours=25), batch_size=1) == 1


def test_obsolete_metadata_removed_without_recycling_tokens(credentials):
    user, _ = credentials
    _, ad, _, _, _, _ = delivery()
    now = timezone.now()
    expired = m.Invitation.objects.create(
        creator=user,
        intended_username="sensitive_name",
        token_hash=secrets.token_hex(32),
        expires_at=now - timedelta(seconds=1),
    )
    valid = m.Invitation.objects.create(
        creator=user, token_hash=secrets.token_hex(32), expires_at=now + timedelta(hours=1)
    )
    m.Session.objects.create(
        user=user, token_hash=secrets.token_hex(32), expires_at=now - timedelta(seconds=1)
    )
    revoked = m.Session.objects.create(
        user=user, token_hash=secrets.token_hex(32), expires_at=now + timedelta(hours=1), revoked_at=now
    )
    challenge = m.RecoveryChallenge.objects.create(
        user=user, nonce_hash=secrets.token_hex(32), expires_at=now - timedelta(seconds=1)
    )
    old = m.AuditEvent.objects.create(actor=user, category="user.updated")
    m.AuditEvent.objects.filter(pk=old.pk).update(timestamp=now - timedelta(days=8))
    recent = m.AuditEvent.objects.create(actor=user, category="password.changed")
    m.AuditEvent.objects.create(actor=user, category="login")
    pkg = m.DeviceKeyPackage.objects.create(
        device=ad,
        package=b"old public package",
        digest=secrets.token_hex(32),
        claimed_by=ad,
        consumed_at=now,
        expires_at=now - timedelta(seconds=1),
    )
    counts = cleanup()
    assert counts["invitations"] == 1 and m.Invitation.objects.filter(pk=valid.pk).exists()
    assert not m.Invitation.objects.filter(pk=expired.pk).exists()
    assert not m.Session.objects.filter(pk=revoked.pk).exists()
    assert not m.RecoveryChallenge.objects.filter(pk=challenge.pk).exists()
    assert not m.AuditEvent.objects.filter(pk=old.pk).exists()
    assert m.AuditEvent.objects.filter(pk=recent.pk).exists()
    assert not m.AuditEvent.objects.filter(category="login").exists()
    pkg.refresh_from_db()
    assert bytes(pkg.package) == b"" and pkg.claimed_by_id is None and pkg.consumed_at is None
    assert pkg.digest  # Replay marker survives payload pruning.


def test_private_rate_labels_do_not_support_unkeyed_ip_enumeration(settings):
    label = rate_key("login", "192.0.2.4", 123)
    assert "192.0.2.4" not in label
    assert hashlib.sha256(b"192.0.2.4").hexdigest() not in label
    assert label != rate_key("login", "192.0.2.4", 124)
    assert label != rate_key("other", "192.0.2.4", 123)
    assert label != rate_key("log", "in192.0.2.4", 123)
    settings.SECRET_KEY = secrets.token_urlsafe(64)
    assert label != rate_key("login", "192.0.2.4", 123)


def test_policy_authenticated_and_login_does_not_track_activity(client, credentials):
    assert client.get("/api/v1/privacy-policy", secure=True).status_code == 403
    assert login(client, credentials).status_code == 200
    assert not m.AuditEvent.objects.filter(category="login").exists()
    value = client.get("/api/v1/privacy-policy", secure=True).json()
    assert value["attachment_days"] == 7 and value["delivered_ciphertext_grace_hours"] == 24
    assert value["accounts_and_membership_retained"] and value["ingress_observes_ip"]
    assert not value["independent_review"] and not value["unsynced_ciphertext_expires"]
    # Content negotiation cannot expose the browsable API or echo HTML diagnostics.
    assert client.get("/api/v1/privacy-policy", secure=True, HTTP_ACCEPT="text/html").status_code == 406
    assert post(client, "auth/logout", {}).status_code == 200


@pytest.mark.django_db(transaction=True)
def test_worker_reports_failure_without_traceback_or_secrets(capsys):
    with patch(
        "core.management.commands.maintain_privacy.cleanup", side_effect=RuntimeError("SECRET_MARKER")
    ):
        with pytest.raises(SystemExit):
            call_command("maintain_privacy", once=True)
    captured = capsys.readouterr()
    assert "SECRET_MARKER" not in captured.out + captured.err
    assert cache.get("privacy:maintenance") == {"status": "unavailable"}
    call_command("maintain_privacy", once=True, stdout=StringIO())
    assert cache.get("privacy:maintenance")["status"] == "ok"


def test_opening_timestamp_removed_from_schema():
    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, "core_attachmentview")
        }
    assert "consumed" in columns and "opened_at" not in columns


def test_redis_decoding_is_data_only_and_counter_compatible():
    codec = JSONCacheSerializer()
    for value in [True, False, None, "123", 123, {"status": "ok", "counts": {"sessions": 2}}]:
        encoded = codec.dumps(value)
        assert codec.loads(str(encoded).encode() if type(encoded) is int else encoded) == value
    # A valid pickle opcode stream is rejected as data, never dispatched to pickle.loads.
    with pytest.raises((ValueError, UnicodeError)):
        codec.loads(b"cos\nsystem\n(S'echo should-never-execute'\ntR.")
    with pytest.raises(ValueError):
        codec.loads(b"x" * 65537)
    cache.set("privacy-test-json", {"ok": True}, timeout=5)
    assert cache.get("privacy-test-json") == {"ok": True}
    cache.add("privacy-test-counter", 0, timeout=5)
    assert cache.incr("privacy-test-counter") == 1
