"""Small real PostgreSQL/Redis fixtures; no synthetic cipher is a crypto verdict."""

import base64
import secrets
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from core import models as m
from core.middleware import digest
from core.privacy import routing_groups
from .conftest import post, csrf

pytestmark = pytest.mark.django_db


def approved(name):
    user = m.User.objects.create_user(
        username=name, password=secrets.token_urlsafe(24), display_name="Secret name"
    )
    device = m.Device.objects.create(
        user=user,
        identity="",
        public_key=secrets.token_bytes(32),
        label="Private browser label",
        challenge=secrets.token_hex(32),
        trust_state="approved",
        expires_at=timezone.now() + timedelta(hours=1),
    )
    device.identity = f"{user.pk}:{device.pk}"
    device.save()
    token = secrets.token_urlsafe(48)
    m.Session.objects.create(
        user=user, device=device, token_hash=digest(token), expires_at=timezone.now() + timedelta(hours=1)
    )
    client = APIClient(enforce_csrf_checks=True)
    client.defaults.update(HTTP_HOST="127.0.0.1:8443", HTTP_ORIGIN="https://127.0.0.1:8443")
    client.cookies["__Host-haven"] = token
    return user, device, client


def test_registration_needs_no_human_name_or_chosen_handle(client, credentials):
    owner, _ = credentials
    token = secrets.token_urlsafe(48)
    invite = m.Invitation.objects.create(
        creator=owner, token_hash=digest(token), expires_at=timezone.now() + timedelta(hours=1)
    )
    response = post(client, "invitations/redeem", {"token": token, "password": secrets.token_urlsafe(24)})
    assert response.status_code == 200
    account = response.json()["user"]
    assert account["display_name"] == "" and len(account["username"]) == 34
    assert account["username"].startswith("h_")
    assert (
        post(
            client, "invitations/redeem", {"token": token, "password": secrets.token_urlsafe(24)}
        ).status_code
        == 400
    )
    invite.refresh_from_db()
    assert invite.consumed_at


def test_unrelated_uuid_is_not_discovery_and_shared_introduction_keeps_certificate(settings):
    settings.CRYPTO_READY = True
    _, sender, source = approved("intro_source")
    _, target, recipient = approved("intro_target")
    url = f"/api/v1/crypto/key-packages/{sender.pk}"
    absent = f"/api/v1/crypto/key-packages/{uuid.uuid4()}"
    assert (
        recipient.get(url, secure=True).status_code == recipient.get(absent, secure=True).status_code == 404
    )
    assert post(recipient, url.removeprefix("/api/v1/"), {}).status_code == 404
    grant = post(source, "devices/contact-introduction", {}).json()["token"]
    response = recipient.get(url, secure=True, HTTP_X_HAVEN_CONTACT=grant)
    assert response.status_code == 200
    result = response.json()["device"]
    assert set(result) == {"id", "user_id", "identity", "public_key", "trust_state", "revoked_at"}
    assert result["identity"] == sender.identity
    assert result["public_key"] == base64.b64encode(bytes(sender.public_key)).decode()
    assert "Private browser label" not in str(result)
    # A first contact with no package is authorized but cannot bypass package availability.
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as queries:
        claim = recipient.post(
            url, {}, format="json", secure=True, HTTP_X_CSRFTOKEN=csrf(recipient), HTTP_X_HAVEN_CONTACT=grant
        )
    assert claim.status_code == 409
    target_reads = [
        q["sql"].split(" FROM ")[0] for q in queries if '"core_device"."introduction_generation"' in q["sql"]
    ]
    assert target_reads
    assert all('"core_user"."password"' not in q and '"display_name"' not in q for q in target_reads)
    other = f"/api/v1/crypto/key-packages/{target.pk}"
    assert source.get(other, secure=True, HTTP_X_HAVEN_CONTACT=grant).status_code == 404
    assert recipient.get(url, secure=True, HTTP_X_HAVEN_CONTACT=grant + "x").status_code == 404
    with patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 86402):
        assert recipient.get(url, secure=True, HTTP_X_HAVEN_CONTACT=grant).status_code == 404
    assert (
        source.delete(
            "/api/v1/devices/contact-introduction", secure=True, HTTP_X_CSRFTOKEN=csrf(source)
        ).status_code
        == 200
    )
    assert recipient.get(url, secure=True, HTTP_X_HAVEN_CONTACT=grant).status_code == 404
    fresh = post(source, "devices/contact-introduction", {}).json()["token"]
    assert fresh != grant
    sender.revoked_at = timezone.now()
    sender.save()
    assert recipient.get(url, secure=True, HTTP_X_HAVEN_CONTACT=fresh).status_code == 404


def test_shared_history_survives_link_expiration_and_revocation(settings):
    settings.CRYPTO_READY = True
    _, a, caller = approved("history_a")
    _, b, _ = approved("history_b")
    signed = {
        "members": [
            {"id": str(a.pk), "user_id": str(a.user_id)},
            {"id": str(b.pk), "user_id": str(b.user_id)},
        ]
    }
    conv = m.Conversation.objects.create(
        creator=a, kind="direct", group_id=uuid.uuid4().hex, genesis=signed, genesis_signature=b"preserved"
    )
    m.Membership.objects.create(conversation=conv, device=a, valid_from_epoch=0)
    m.Membership.objects.create(conversation=conv, device=b, valid_from_epoch=0, removed_at_epoch=1)
    b.user.is_active = False
    b.user.save(update_fields=["is_active"])
    b.revoked_at = timezone.now()
    b.trust_state = "revoked"
    b.save()
    result = caller.get(f"/api/v1/crypto/key-packages/{b.pk}", secure=True)
    assert result.status_code == 200 and result.json()["device"]["identity"] == b.identity
    assert post(caller, f"crypto/key-packages/{b.pk}", {}).status_code == 404
    conv.refresh_from_db()
    assert conv.genesis == signed and bytes(conv.genesis_signature) == b"preserved"


def test_routing_domain_key_rotation_and_fail_closed(settings):
    from django.core.exceptions import ImproperlyConfigured

    uid = uuid.uuid4()
    settings.ROUTING_SECRET = "a" * 64
    settings.ROUTING_PREVIOUS_SECRET = "b" * 64
    first, previous = routing_groups(uid)
    assert str(uid) not in first and uid.hex not in first and len(first) < 100
    assert routing_groups(str(uid).upper()) == (first, previous)
    settings.ROUTING_SECRET, settings.ROUTING_PREVIOUS_SECRET = "b" * 64, "a" * 64
    assert routing_groups(uid) == (previous, first)
    assert routing_groups(uuid.uuid4())[0] != previous
    settings.ROUTING_SECRET = settings.SECRET_KEY
    with pytest.raises(ImproperlyConfigured):
        routing_groups(uid)
    settings.ROUTING_SECRET = ""
    with pytest.raises(ImproperlyConfigured):
        routing_groups(uid)


def test_synthetic_database_still_reconstructs_graph_and_redundant_signed_copies():
    from django.db import connection

    _, a, _ = approved("graph_a")
    _, b, _ = approved("graph_b")
    members = [{"id": str(d.pk), "user_id": str(d.user_id)} for d in (a, b)]
    conv = m.Conversation.objects.create(
        creator=a, kind="direct", group_id=uuid.uuid4().hex, genesis={"members": members}
    )
    for d in (a, b):
        m.Membership.objects.create(conversation=conv, device=d, valid_from_epoch=0)
    env = m.MessageEnvelope.objects.create(
        conversation=conv,
        sender_device=a,
        server_seq=1,
        client_message_id=uuid.uuid4(),
        group_epoch=0,
        ciphertext=b"opaque",
        request_digest="a" * 64,
        header={"sender_device": str(a.pk), "transition": {"members": members}},
    )
    m.DeliveryCursor.objects.create(device=b, conversation=conv, last_acked_seq=1)
    m.NotificationOutbox.objects.create(envelope=env)
    with connection.cursor() as cursor:
        cursor.execute("""SELECT u.id, d.id, m.conversation_id, e.sender_device_id
            FROM core_user u JOIN core_device d ON d.user_id=u.id
            JOIN core_membership m ON m.device_id=d.id
            JOIN core_messageenvelope e ON e.conversation_id=m.conversation_id""")
        rows = cursor.fetchall()
    assert len(rows) == 2 and all(r[2] == conv.pk and r[3] == a.pk for r in rows)
    # Removing an ordinary FK would leave these copies intact.
    assert conv.genesis["members"] == env.header["transition"]["members"]
    assert set(str(r[0]) for r in rows) == {x["user_id"] for x in conv.genesis["members"]}


def test_restore_epoch_invalidates_pre_restore_contact_grants_without_session_rotation(settings):
    settings.CRYPTO_READY = True
    _, device, issuer = approved("restore_issuer")
    _, _, recipient = approved("restore_recipient")
    token = post(issuer, "devices/contact-introduction", {}).json()["token"]
    url = f"/api/v1/crypto/key-packages/{device.pk}"
    assert recipient.get(url, secure=True, HTTP_X_HAVEN_CONTACT=token).status_code == 200
    settings.CONTACT_LINK_EPOCH = secrets.token_urlsafe(32)
    assert recipient.get(url, secure=True, HTTP_X_HAVEN_CONTACT=token).status_code == 404
    fresh = post(issuer, "devices/contact-introduction", {}).json()["token"]
    assert recipient.get(url, secure=True, HTTP_X_HAVEN_CONTACT=fresh).status_code == 200
    assert issuer.get("/api/v1/auth/me", secure=True).status_code == 200


def test_admin_account_contract_omits_profile_and_security_state():
    from .test_contracts import validate

    user, _, operator = approved("minimal_admin")
    user.role = "superadmin"
    user.save(update_fields=["role"])
    response = operator.get("/api/v1/admin/users", secure=True)
    assert response.status_code == 200
    for account in response.json():
        validate("AdminUser", account)
        assert set(account) == {"id", "username", "role", "is_active"}
    assert "Secret name" not in str(response.json())
