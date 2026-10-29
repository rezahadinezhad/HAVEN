"""Bounded member invitations; approved session is a transport precondition.

Actual enrollment, MLS and explicit human verification are covered by browser tests.
"""

import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.utils import timezone

from core import models as m
from core.middleware import digest
from .conftest import csrf, post
from .test_contracts import validate
from .test_view_once import bound_client

pytestmark = pytest.mark.django_db


def capability(client):
    response = client.get("/api/v1/invitations", secure=True)
    assert response.status_code == 200
    validate("InvitationAccess", response.json())
    return response.json()


def test_member_limits_hash_only_and_revocation(settings):
    settings.CRYPTO_READY = True
    client, device = bound_client()
    assert capability(client)["remaining_today"] == 3
    assert post(client, "invitations", {"hours": 25}).status_code == 400
    issued = [post(client, "invitations", {"hours": 24}) for _ in range(3)]
    assert [r.status_code for r in issued] == [201, 201, 201]
    first = issued[0].json()
    stored = m.Invitation.objects.get(pk=first["id"])
    assert stored.token_hash == digest(first["token"])
    assert first["token"] not in str(stored.__dict__)
    assert stored.creator == device.user
    assert capability(client)["reason"] == "daily_limit"
    assert post(client, "invitations", {}).status_code == 429
    assert post(client, f"invitations/{stored.pk}/revoke", {}).status_code == 200
    assert post(client, f"invitations/{stored.pk}/revoke", {}).status_code == 200
    assert m.AuditEvent.objects.filter(actor=device.user, category="invitation.revoked").count() == 1
    # Revocation and cleanup cannot replenish today's quota.
    m.Invitation.objects.filter(creator=device.user).delete()
    assert capability(client)["remaining_today"] == 0
    assert post(client, "invitations", {}).status_code == 429
    assert device.user.role == "member"
    assert client.get("/api/v1/admin/users", secure=True).status_code == 403
    assert post(client, "admin/invitations", {}).status_code == 403


def test_policy_crypto_approval_and_operator_controls(settings):
    settings.CRYPTO_READY = True
    client, device = bound_client()
    device.trust_state = "pending"
    device.save(update_fields=["trust_state"])
    assert capability(client)["reason"] == "browser_not_ready"
    assert post(client, "invitations", {}).status_code == 403
    device.trust_state = "approved"
    device.save(update_fields=["trust_state"])
    m.Session.objects.filter(device=device).update(device=None)
    assert post(client, "invitations", {}).status_code == 403
    m.Session.objects.filter(user=device.user).update(device=device)
    settings.CRYPTO_READY = False
    assert capability(client)["reason"] == "crypto_unavailable"
    assert post(client, "invitations", {}).status_code == 403
    settings.CRYPTO_READY = True
    policy = m.ServerPolicy.objects.create(pk=1, member_invitations=False)
    assert capability(client)["reason"] == "members_disabled"
    assert post(client, "invitations", {}).status_code == 403
    device.user.role = "community_admin"
    device.user.save(update_fields=["role"])
    assert capability(client)["allowed"] is True
    assert capability(client)["remaining_today"] is None
    assert post(client, "admin/invitations", {"hours": 72}).status_code == 201
    policy.invitations_paused = True
    policy.save()
    assert capability(client)["reason"] == "paused"
    assert post(client, "invitations", {}).status_code == 403
    assert post(client, "admin/invitations", {}).status_code == 403


def test_ownership_csrf_and_single_use(settings):
    settings.CRYPTO_READY = True
    client, device = bound_client()
    other, _ = bound_client()
    assert client.post("/api/v1/invitations", {}, format="json", secure=True).status_code == 403
    assert (
        client.post(
            "/api/v1/invitations",
            {},
            format="json",
            secure=True,
            HTTP_X_CSRFTOKEN=csrf(client),
            HTTP_ORIGIN="https://evil.invalid",
        ).status_code
        == 403
    )
    invite = post(client, "invitations", {}).json()
    assert not capability(other)["pending_invitations"]
    assert post(other, f"invitations/{invite['id']}/revoke", {}).status_code == 404
    body = {
        "token": invite["token"],
        "username": "friend_a",
        "password": secrets.token_urlsafe(32),
        "display_name": "Friend",
    }
    assert post(other, "invitations/redeem", body).status_code == 200
    assert m.User.objects.get(username="friend_a").role == "member"
    body["username"] = "friend_b"
    assert post(other, "invitations/redeem", body).status_code == 400
    assert capability(client)["remaining_today"] == 2
    assert not capability(client)["pending_invitations"]
    revoked = post(client, "invitations", {}).json()
    assert post(client, f"invitations/{revoked['id']}/revoke", {}).status_code == 200
    body["token"] = revoked["token"]
    assert post(other, "invitations/redeem", body).status_code == 400


def test_utc_reset_and_pending_limit(settings):
    settings.CRYPTO_READY = True
    client, device = bound_client()
    for _ in range(3):
        assert post(client, "invitations", {}).status_code == 201
    # Yesterday's invites may still be pending after the UTC reset.
    m.AuditEvent.objects.filter(actor=device.user).update(timestamp=timezone.now() - timedelta(days=1))
    assert capability(client)["remaining_today"] == 3
    assert capability(client)["reason"] == "pending_limit"
    assert post(client, "invitations", {}).status_code == 429
    m.Invitation.objects.filter(creator=device.user).update(expires_at=timezone.now() - timedelta(seconds=1))
    assert capability(client)["allowed"] is True
    assert post(client, "invitations", {}).status_code == 201


@pytest.mark.django_db(transaction=True)
def test_concurrent_member_quota(settings):
    settings.CRYPTO_READY = True
    client, device = bound_client()
    other, _ = bound_client(device.user)
    for _ in range(2):
        assert post(client, "invitations", {}).status_code == 201
    barrier = Barrier(2)

    def issue(c):
        close_old_connections()
        try:
            csrf(c)
            barrier.wait(timeout=10)
            return post(c, "invitations", {}).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(issue, [client, other]))
    assert sorted(statuses) == [201, 429]
    assert m.Invitation.objects.filter(creator=device.user).count() == 3
    assert m.AuditEvent.objects.filter(actor=device.user, category="invitation.created").count() == 3
