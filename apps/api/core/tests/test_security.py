import base64
import hashlib
import secrets
import uuid
from datetime import timedelta
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings
from django.utils import timezone
from django.test import override_settings
from .asgi_socket import WebsocketProbe
from haven.asgi import application
from core import models as m
from .conftest import post as raw_post, login, csrf
from core import protocol as p

pytestmark = pytest.mark.django_db


def post(client, path, body):
    """Construct authenticated headers for transport tests; actual MLS is exercised in browser integration."""
    body = dict(body)
    if path == "conversations" and hasattr(client, "signing_key"):
        device = client.signing_device
        header = {
            "domain": "haven/genesis/v1",
            "id": body["id"],
            "kind": body["kind"],
            "group_id": body["group_id"],
            "members": [{**p.certificate(device), "role": "owner"}],
        }
        body.update(
            header=header, signature=base64.b64encode(client.signing_key.sign(p.canonical(header))).decode()
        )
    elif path.endswith("/messages") and hasattr(client, "signing_key"):
        c = m.Conversation.objects.get(pk=path.split("/")[1])
        header = {
            "domain": "haven/envelope/v1",
            "v": 1,
            "conversation_id": str(c.pk),
            "group_id": c.group_id,
            "sender_device": str(client.signing_device.pk),
            "client_message_id": body["client_message_id"],
            "epoch": body["epoch"],
            "seq": 1,
            "previous_hash": p.chain_hash(c.genesis, bytes(c.genesis_signature)),
            "ciphertext_hash": p.fingerprint(base64.b64decode(body["ciphertext"])),
            "transition": None,
        }
        body.update(
            header=header, signature=base64.b64encode(client.signing_key.sign(p.canonical(header))).decode()
        )
    elif path == "attachments/init" and "filename" not in body:
        body.setdefault("id", str(uuid.uuid4()))
    return raw_post(client, path, body)


@pytest.fixture
def transport_public_validator(monkeypatch):
    # This fixture isolates HTTP durability/authorization from MLS parsing. It is NOT crypto test evidence.
    def validate(**command):
        c = m.Conversation.objects.latest("created_at")
        return {"group_id": c.group_id, "epoch": c.epoch}

    monkeypatch.setattr(p, "public_validate", validate)


def test_invite_consumption_expiry_and_hash(client, credentials):
    assert login(client, credentials).status_code == 200
    inv = post(client, "admin/invitations", {"hours": 1})
    assert inv.status_code == 201
    token = inv.json()["token"]
    stored = m.Invitation.objects.get(pk=inv.json()["id"])
    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in str(stored.__dict__)
    pw = secrets.token_urlsafe(30)
    reg = {"token": token, "username": "invitee", "password": pw, "display_name": "Person"}
    assert post(client, "invitations/redeem", reg).status_code == 200
    assert post(client, "invitations/redeem", {**reg, "username": "second"}).status_code == 400
    assert post(client, "admin/invitations", {}).status_code == 403


def test_auth_transport_origin_csrf_revocation(client, credentials):
    assert client.post("/api/v1/auth/login", {}, format="json").status_code == 421
    assert client.post("/api/v1/auth/login", {}, format="json", secure=True).status_code == 403
    bad = client.post(
        "/api/v1/auth/login",
        {},
        format="json",
        secure=True,
        HTTP_X_CSRFTOKEN=csrf(client),
        HTTP_ORIGIN="https://evil.test",
    )
    assert bad.status_code == 403
    assert login(client, credentials).status_code == 200
    cookie = client.cookies[settings.SESSION_COOKIE_NAME]
    assert cookie["secure"] and cookie["httponly"] and cookie["samesite"] == "Strict"
    raw = cookie.value
    assert not m.Session.objects.filter(token_hash=raw).exists()
    assert m.Session.objects.filter(token_hash=hashlib.sha256(raw.encode()).hexdigest()).exists()
    assert client.get("/api/v1/auth/me", secure=True).status_code == 200
    assert post(client, "auth/logout", {}).status_code == 200
    assert client.get("/api/v1/auth/me", secure=True).status_code == 403


def test_rate_and_schema(client, credentials):
    for _ in range(5):
        assert post(client, "auth/login", {"username": "unknown", "password": "incorrect"}).status_code == 400
    assert post(client, "auth/login", {"username": "unknown", "password": "incorrect"}).status_code == 429
    # Other people behind the same ingress/NAT are not all locked out.
    assert post(client, "auth/login", {"username": "owner", "password": credentials[1]}).status_code == 200


def test_crypto_release_gate(client, credentials):
    login(client, credentials)
    assert client.get("/api/v1/conversations", secure=True).status_code == 403
    assert post(client, "devices/enrollment/request", {}).status_code == 403
    assert post(client, "attachments/init", {}).status_code == 400
    assert client.get("/api/v1/health", secure=True).json()["crypto_ready"] is False


def test_password_reset_revokes_does_not_grant_keys(client, credentials):
    login(client, credentials)
    result = post(
        client,
        "auth/change-password",
        {"old_password": credentials[1], "new_password": secrets.token_urlsafe(28)},
    )
    assert result.status_code == 200
    assert client.get("/api/v1/auth/me", secure=True).status_code == 403
    assert m.Device.objects.count() == 0


def setup_device(c, credentials):
    login(c, credentials)
    key = Ed25519PrivateKey.generate()
    d = m.Device.objects.create(
        user=credentials[0],
        label="test",
        identity="test-only",
        public_key=key.public_key().public_bytes_raw(),
        trust_state="approved",
        challenge=secrets.token_hex(32),
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    m.Session.objects.filter(user=credentials[0], revoked_at=None).update(device=d)
    d.identity = f"{d.user_id}:{d.pk}"
    d.save(update_fields=["identity"])
    c.signing_key, c.signing_device = key, d
    return d, key


@override_settings(CRYPTO_READY=True)
@pytest.mark.usefixtures("transport_public_validator")
def test_transport_idempotence_epoch_idor_and_acks(client, credentials):
    device, key = setup_device(client, credentials)
    cid = str(uuid.uuid4())
    assert post(client, "conversations", {"id": cid, "kind": "direct", "group_id": cid}).status_code == 201
    body = {
        "v": 1,
        "client_message_id": str(uuid.uuid4()),
        "epoch": 0,
        "ciphertext": base64.b64encode(secrets.token_bytes(120)).decode(),
    }
    first = post(client, f"conversations/{cid}/messages", body)
    again = post(client, f"conversations/{cid}/messages", body)
    assert first.status_code == 201 and again.status_code == 200
    assert first.json() == again.json()
    assert m.MessageEnvelope.objects.count() == 1 and m.NotificationOutbox.objects.count() == 1
    assert (
        post(client, f"conversations/{cid}/messages", {**body, "ciphertext": "dGFtcGVy"}).status_code == 400
    )
    assert (
        post(
            client,
            f"conversations/{cid}/messages",
            {**body, "client_message_id": str(uuid.uuid4()), "epoch": 1},
        ).status_code
        == 400
    )
    assert post(client, f"conversations/{cid}/acks", {"seq": 2}).status_code == 400
    assert post(client, f"conversations/{cid}/acks", {"seq": 1}).status_code == 200
    assert post(client, f"conversations/{cid}/acks", {"seq": 0}).json()["seq"] == 1
    assert len(client.get(f"/api/v1/conversations/{cid}/messages", secure=True).json()["messages"]) == 1
    stranger = m.User.objects.create_user(
        username="stranger", password=credentials[1], display_name="stranger"
    )
    setup_device(client, (stranger, credentials[1]))
    assert client.get(f"/api/v1/conversations/{cid}/messages", secure=True).status_code == 404
    assert post(client, f"conversations/{cid}/messages", body).status_code == 404


@override_settings(CRYPTO_READY=True)
def test_attachment_bounds_idempotence_and_no_names(client, credentials):
    setup_device(client, credentials)
    cid = str(uuid.uuid4())
    post(client, "conversations", {"id": cid, "kind": "group", "group_id": cid})
    a = post(
        client, "attachments/init", {"conversation_id": cid, "ciphertext_size": 60, "chunk_count": 2}
    ).json()["id"]
    for i in (0, 1):
        r = client.put(
            f"/api/v1/attachments/{a}/chunks/{i}",
            b"x" * 30,
            content_type="application/octet-stream",
            secure=True,
            HTTP_X_CSRFTOKEN=csrf(client),
        )
        assert r.status_code == 200
    assert post(client, f"attachments/{a}/complete", {}).status_code == 200
    assert client.get(f"/api/v1/attachments/{a}/chunks/0", secure=True).content == b"x" * 30
    assert m.AttachmentChunk.objects.count() == 2
    assert (
        post(
            client,
            "attachments/init",
            {"conversation_id": cid, "ciphertext_size": 30, "chunk_count": 1, "filename": "private"},
        ).status_code
        == 400
    )


@override_settings(CRYPTO_READY=True)
def test_enrollment_requires_existing_signature(client, credentials):
    signer, key = setup_device(client, credentials)
    did = uuid.uuid4()
    target = Ed25519PrivateKey.generate()
    req = post(
        client,
        "devices/enrollment/request",
        {
            "id": str(did),
            "label": "new",
            "identity": f"{credentials[0].pk}:{did}",
            "public_key": base64.b64encode(target.public_key().public_bytes_raw()).decode(),
        },
    )
    assert req.status_code == 201
    payload = req.json()["signing_payload"].encode()
    bad = base64.b64encode(target.sign(payload)).decode()
    assert (
        post(client, "devices/enrollment/approve", {"device_id": str(did), "signature": bad}).status_code
        == 400
    )
    assert (
        post(client, "devices/enrollment/complete", {"device_id": str(did), "signature": bad}).status_code
        == 403
    )
    device = m.Device.objects.get(pk=did)
    from core.views import enrollment_payload

    good = base64.b64encode(key.sign(enrollment_payload(device))).decode()
    assert (
        post(client, "devices/enrollment/approve", {"device_id": str(did), "signature": good}).status_code
        == 200
    )
    assert (
        post(client, "devices/enrollment/complete", {"device_id": str(did), "signature": bad}).status_code
        == 200
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_hostile_websocket_origin():
    ws = WebsocketProbe(application, "/ws/v1", headers=[(b"origin", b"https://evil.test")])
    connected, code = await ws.connect()
    assert not connected and code == 4403
    await ws.disconnect()


def test_invite_expiry_revoke_and_role(client, credentials):
    login(client, credentials)
    inv = post(client, "admin/invitations", {"hours": 1}).json()
    m.Invitation.objects.filter(pk=inv["id"]).update(expires_at=timezone.now() - timedelta(seconds=1))
    reg = {
        "token": inv["token"],
        "username": "expired",
        "display_name": "Expired",
        "password": secrets.token_urlsafe(30),
    }
    assert post(client, "invitations/redeem", reg).status_code == 400
    inv = post(client, "admin/invitations", {"hours": 1}).json()
    assert post(client, f"admin/invitations/{inv['id']}/revoke", {}).status_code == 200
    assert post(client, "invitations/redeem", {**reg, "token": inv["token"]}).status_code == 400
    other = m.User.objects.create_user(username="member", password=credentials[1], display_name="Member")
    login(client, (other, credentials[1]))
    assert client.get("/api/v1/admin/users", secure=True).status_code == 403
    assert client.get("/api/v1/admin/system-status", secure=True).status_code == 403


@override_settings(CRYPTO_READY=True)
def test_attachment_cross_user_and_device_revocation(client, credentials):
    device, key = setup_device(client, credentials)
    cid = str(uuid.uuid4())
    post(client, "conversations", {"id": cid, "kind": "group", "group_id": cid})
    aid = post(
        client, "attachments/init", {"conversation_id": cid, "ciphertext_size": 30, "chunk_count": 1}
    ).json()["id"]
    stranger = m.User.objects.create_user(
        username="stranger", password=credentials[1], display_name="Stranger"
    )
    setup_device(client, (stranger, credentials[1]))
    assert client.get(f"/api/v1/attachments/{aid}/chunks/0", secure=True).status_code == 404
    login(client, credentials)
    m.Session.objects.filter(user=credentials[0], revoked_at=None).update(device=device)
    assert post(client, f"devices/{device.pk}/revoke", {}).status_code == 200
    assert m.Conversation.objects.get(pk=cid).status == "rekey_required"
    assert client.get("/api/v1/auth/me", secure=True).status_code == 403


@pytest.mark.django_db(transaction=True)
@override_settings(CRYPTO_READY=True)
@pytest.mark.usefixtures("transport_public_validator")
def test_concurrent_duplicate_send_is_one_committed_row(client, credentials):
    from concurrent.futures import ThreadPoolExecutor
    from rest_framework.test import APIClient
    from django.db import close_old_connections

    device, key = setup_device(client, credentials)
    cid = str(uuid.uuid4())
    post(client, "conversations", {"id": cid, "kind": "group", "group_id": cid})
    token = client.cookies[settings.SESSION_COOKIE_NAME].value
    body = {
        "v": 1,
        "client_message_id": str(uuid.uuid4()),
        "epoch": 0,
        "ciphertext": base64.b64encode(secrets.token_bytes(120)).decode(),
    }

    def submit(_):
        close_old_connections()
        try:
            c = APIClient(enforce_csrf_checks=True)
            c.defaults.update(HTTP_HOST="127.0.0.1:8443", HTTP_ORIGIN="https://127.0.0.1:8443")
            c.cookies[settings.SESSION_COOKIE_NAME] = token
            c.signing_key, c.signing_device = key, device
            r = post(c, f"conversations/{cid}/messages", body)
            return r.status_code, r.json()
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sorted(x[0] for x in results) == [200, 201]
    assert results[0][1] == results[1][1]
    assert m.MessageEnvelope.objects.filter(conversation_id=cid).count() == 1
    assert m.Conversation.objects.get(pk=cid).last_seq == 1
