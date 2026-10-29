"""View-once authorization/lifecycle tests; ciphertext fixtures are not MLS tests."""

import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient
from core import models as m
from core.middleware import digest
from .conftest import post, csrf

pytestmark = pytest.mark.django_db


def bound_client(user=None):
    user = user or m.User.objects.create_user(username=uuid.uuid4().hex, password=secrets.token_hex(24))
    did = uuid.uuid4()
    # An already-approved, proof-bound session is the precondition under test.
    device = m.Device.objects.create(
        id=did,
        user=user,
        identity=f"{user.pk}:{did}",
        label="View test",
        public_key=secrets.token_bytes(32),
        trust_state="approved",
        expires_at=timezone.now() + timedelta(days=1),
    )
    token = secrets.token_hex(32)
    m.Session.objects.create(
        user=user, device=device, token_hash=digest(token), expires_at=timezone.now() + timedelta(hours=1)
    )
    client = APIClient(enforce_csrf_checks=True)
    client.defaults.update(HTTP_HOST="127.0.0.1:8443", HTTP_ORIGIN="https://127.0.0.1:8443")
    client.cookies[settings.SESSION_COOKIE_NAME] = token
    return client, device


@pytest.fixture
def group(settings):
    settings.CRYPTO_READY = True
    a, ad = bound_client()
    b, bd = bound_client()
    b2, bd2 = bound_client(bd.user)
    c, cd = bound_client()
    conv = m.Conversation.objects.create(creator=ad, kind="group", group_id=uuid.uuid4().hex)
    for device in (ad, bd, bd2, cd):
        m.Membership.objects.create(conversation=conv, device=device, valid_from_epoch=0)
    return a, ad, b, bd, b2, bd2, c, cd, conv


def uploaded(group, view_once=True):
    a, _, *_, conv = group
    aid = uuid.uuid4()
    body = {
        "id": str(aid),
        "conversation_id": str(conv.pk),
        "ciphertext_size": 32,
        "chunk_count": 1,
        "view_once": view_once,
    }
    assert post(a, "attachments/init", body).status_code == 201
    assert (
        a.put(
            f"/api/v1/attachments/{aid}/chunks/0",
            b"x" * 32,
            content_type="application/octet-stream",
            secure=True,
            HTTP_X_CSRFTOKEN=csrf(a),
        ).status_code
        == 200
    )
    assert post(a, f"attachments/{aid}/complete", {}).status_code == 200
    return aid, body


def chunk(client, aid, token=None):
    return client.get(
        f"/api/v1/attachments/{aid}/chunks/0",
        secure=True,
        **({"HTTP_X_HAVEN_VIEW_TOKEN": token} if token else {}),
    )


def test_per_account_claim_replay_close_and_other_recipient(group):
    a, _, b, bd, b2, _, c, _, _ = group
    aid, body = uploaded(group)
    token = secrets.token_hex(32)
    assert m.AttachmentView.objects.filter(attachment_id=aid).count() == 2
    for client in (a, b, b2, c):
        assert chunk(client, aid).status_code in (403, 404)
    assert post(a, f"attachments/{aid}/view-once", {"token": token}).status_code == 404
    assert post(b, f"attachments/{aid}/view-once", {"token": token}).status_code == 200
    # Lost-response retry is idempotent for precisely the same device and token.
    assert post(b, f"attachments/{aid}/view-once", {"token": token}).status_code == 200
    assert post(b, f"attachments/{aid}/view-once", {"token": secrets.token_hex(32)}).status_code == 403
    assert post(b2, f"attachments/{aid}/view-once", {"token": token}).status_code == 403
    assert chunk(b2, aid, token).status_code == 403
    assert chunk(c, aid, token).status_code == 403
    assert chunk(b, aid, token).content == b"x" * 32
    assert chunk(b, aid, secrets.token_hex(32)).status_code == 403
    assert b2.get(f"/api/v1/attachments/{aid}/view-once", secure=True).json() == {"state": "opened"}
    assert a.get(f"/api/v1/attachments/{aid}/view-once", secure=True).json() == {"state": "sent"}
    assert post(b, f"attachments/{aid}/view-once/close", {"token": token}).status_code == 200
    assert chunk(b, aid, token).status_code in (403, 404)
    assert m.AttachmentChunk.objects.filter(attachment_id=aid).exists()  # C still has a view.
    token_c = secrets.token_hex(32)
    assert post(c, f"attachments/{aid}/view-once", {"token": token_c}).status_code == 200
    assert post(c, f"attachments/{aid}/view-once/close", {"token": token_c}).status_code == 200
    assert not m.AttachmentChunk.objects.filter(attachment_id=aid).exists()
    assert m.EncryptedAttachment.objects.get(pk=aid).status == "consumed"
    assert post(a, "attachments/init", body).status_code == 400
    assert not m.AttachmentView.objects.filter(attachment_id=aid).exists()
    assert b.get(f"/api/v1/attachments/{aid}/view-once", secure=True).json() == {"state": "opened"}


def test_leases_expire_without_restoring_views_and_cleanup(group):
    _, _, b, _, _, _, c, _, _ = group
    aid, _ = uploaded(group)
    for client in (b, c):
        assert (
            post(client, f"attachments/{aid}/view-once", {"token": secrets.token_hex(32)}).status_code == 200
        )
    m.AttachmentView.objects.filter(attachment_id=aid).update(
        lease_expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert post(b, f"attachments/{aid}/view-once", {"token": secrets.token_hex(32)}).status_code == 403
    call_command("cleanup_expired", verbosity=0)
    assert not m.AttachmentChunk.objects.filter(attachment_id=aid).exists()
    assert m.EncryptedAttachment.objects.get(pk=aid).status == "consumed"


def test_scope_mode_rekey_revocation_and_normal_attachments(group, settings):
    a, _, b, bd, _, _, _, _, conv = group
    aid, body = uploaded(group)
    assert post(a, "attachments/init", {**body, "view_once": False}).status_code == 400
    outsider, device = bound_client()
    assert post(outsider, f"attachments/{aid}/view-once", {"token": secrets.token_hex(32)}).status_code == 404
    m.Membership.objects.create(conversation=conv, device=device, valid_from_epoch=1)
    assert post(outsider, f"attachments/{aid}/view-once", {"token": secrets.token_hex(32)}).status_code == 403
    # Even a same-epoch late account with copied metadata is absent from the snapshot.
    m.Membership.objects.filter(device=device).update(valid_from_epoch=0)
    assert post(outsider, f"attachments/{aid}/view-once", {"token": secrets.token_hex(32)}).status_code == 404
    assert (
        b.post(
            f"/api/v1/attachments/{aid}/view-once",
            {"token": secrets.token_hex(32)},
            format="json",
            secure=True,
        ).status_code
        == 403
    )
    assert post(b, f"attachments/{aid}/view-once", {"token": "short"}).status_code == 400
    normal, _ = uploaded(group, False)
    assert chunk(b, normal).status_code == 200
    assert chunk(b, normal).status_code == 200
    assert post(b, f"attachments/{normal}/view-once", {"token": secrets.token_hex(32)}).status_code == 403
    settings.CRYPTO_READY = False
    assert post(b, f"attachments/{aid}/view-once", {"token": secrets.token_hex(32)}).status_code == 403
    settings.CRYPTO_READY = True
    m.Device.objects.filter(pk=bd.pk).update(revoked_at=timezone.now())
    assert post(b, f"attachments/{aid}/view-once", {"token": secrets.token_hex(32)}).status_code == 403


@pytest.mark.django_db(transaction=True)
def test_simultaneous_devices_only_one_can_claim(group):
    _, _, b, _, b2, _, _, _, _ = group
    aid, _ = uploaded(group)
    barrier = Barrier(2)

    def claim(client):
        try:
            token = csrf(client)
            barrier.wait(timeout=10)
            return client.post(
                f"/api/v1/attachments/{aid}/view-once",
                {"token": secrets.token_hex(32)},
                format="json",
                secure=True,
                HTTP_X_CSRFTOKEN=token,
            ).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(claim, (b, b2)))
    assert sorted(statuses) == [200, 403]
    assert m.AttachmentView.objects.filter(attachment_id=aid, consumed=True).count() == 1


def test_expiry_cleanup_cannot_reset_a_view_once_identifier(group):
    a, _, b, _, _, _, _, _, _ = group
    aid, body = uploaded(group)
    assert post(b, f"attachments/{aid}/view-once", {"token": secrets.token_hex(32)}).status_code == 200
    m.EncryptedAttachment.objects.filter(pk=aid).update(expires_at=timezone.now() - timedelta(seconds=1))
    call_command("cleanup_expired", verbosity=0)
    assert not m.EncryptedAttachment.objects.filter(pk=aid).exists()
    assert not m.AttachmentView.objects.filter(attachment_id=aid).exists()
    assert m.AttachmentTombstone.objects.filter(pk=aid).exists()
    assert post(a, "attachments/init", body).status_code == 400
    assert post(a, "attachments/init", {**body, "view_once": False}).status_code == 400
    assert chunk(b, aid).status_code == 404
