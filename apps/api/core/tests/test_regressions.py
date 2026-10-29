"""Security regressions for session binding and public-structure rejection. No mocked crypto validation."""

import base64
import secrets
import uuid
from datetime import timedelta
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.utils import timezone
from core import models as m
from core.protocol import public_validate
from .conftest import login, post

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def enable_qualified_test_profile(settings):
    settings.CRYPTO_READY = True


def enrollment(client, user, did, key):
    return post(
        client,
        "devices/enrollment/request",
        {
            "id": str(did),
            "label": "Regression browser",
            "identity": f"{user.pk}:{did}",
            "public_key": base64.b64encode(key.public_key().public_bytes_raw()).decode(),
        },
    )


def complete(client, did, key, payload):
    return post(
        client,
        "devices/enrollment/complete",
        {"device_id": str(did), "signature": base64.b64encode(key.sign(payload.encode())).decode()},
    )


def test_approved_device_rebind_requires_fresh_session_proof(client, credentials):
    user, _ = credentials
    login(client, credentials)
    key = Ed25519PrivateKey.generate()
    did = uuid.uuid4()
    req = enrollment(client, user, did, key).json()
    assert complete(client, did, key, req["signing_payload"]).status_code == 200
    assert complete(client, did, key, req["signing_payload"]).status_code == 403
    m.Device.objects.filter(pk=did).update(expires_at=timezone.now() - timedelta(days=2))
    login(client, credentials)
    assert client.get("/api/v1/auth/me", secure=True).json()["device_id"] is None
    req = enrollment(client, user, did, key).json()
    assert complete(client, did, key, req["signing_payload"]).status_code == 200
    assert client.get("/api/v1/auth/me", secure=True).json()["device_id"] == str(did)


def test_revoke_all_never_reopens_first_device_trust(client, credentials):
    user, _ = credentials
    login(client, credentials)
    key = Ed25519PrivateKey.generate()
    did = uuid.uuid4()
    req = enrollment(client, user, did, key).json()
    assert complete(client, did, key, req["signing_payload"]).status_code == 200
    assert post(client, f"devices/{did}/revoke", {}).status_code == 200
    login(client, credentials)
    other = Ed25519PrivateKey.generate()
    fresh = uuid.uuid4()
    req = enrollment(client, user, fresh, other).json()
    assert complete(client, fresh, other, req["signing_payload"]).status_code == 403
    assert not m.Device.objects.filter(trust_state="approved").exists()


def test_public_verifier_rejects_random_or_truncated_structures():
    from rest_framework.exceptions import ValidationError

    for value in [b"x", b"\x00\x01" * 100, secrets.token_bytes(1024)]:
        for op, field in [("wire", "ciphertext"), ("package", "package")]:
            with pytest.raises(ValidationError):
                public_validate(op=op, **{field: base64.b64encode(value).decode()})


def test_recovery_start_does_not_enumerate_account(client, credentials):
    known = post(client, "recovery/start", {"user_id": str(credentials[0].pk)})
    missing = post(client, "recovery/start", {"user_id": str(uuid.uuid4())})
    assert known.status_code == missing.status_code == 200
    assert set(known.json()) == set(missing.json()) == {"id", "nonce"}
    assert len(known.json()["nonce"]) == len(missing.json()["nonce"]) == 64


def test_invalid_header_shapes_are_bounded(client, credentials):
    login(client, credentials)
    key = Ed25519PrivateKey.generate()
    did = uuid.uuid4()
    req = enrollment(client, credentials[0], did, key).json()
    assert complete(client, did, key, req["signing_payload"]).status_code == 200
    body = {
        "id": str(uuid.uuid4()),
        "kind": "group",
        "group_id": str(uuid.uuid4()),
        "signature": base64.b64encode(b"x" * 64).decode(),
    }
    for header in [[], {"transition": "invalid"}, {"oversize": "x" * 65537}]:
        assert post(client, "conversations", {**body, "header": header}).status_code == 400


def test_historical_revoked_certificate_visibility_is_scoped(client, credentials):
    login(client, credentials)
    key, did = Ed25519PrivateKey.generate(), uuid.uuid4()
    req = enrollment(client, credentials[0], did, key).json()
    assert complete(client, did, key, req["signing_payload"]).status_code == 200
    requester = m.Device.objects.get(pk=did)
    other = m.User.objects.create_user(username="past-member", password=secrets.token_urlsafe(32))
    old_id = uuid.uuid4()
    old = m.Device.objects.create(
        id=old_id,
        user=other,
        label="Historical credential",
        identity=f"{other.pk}:{old_id}",
        public_key=Ed25519PrivateKey.generate().public_key().public_bytes_raw(),
        trust_state="revoked",
        revoked_at=timezone.now(),
        expires_at=timezone.now(),
    )
    assert client.get(f"/api/v1/crypto/key-packages/{old_id}", secure=True).status_code == 404
    conv = m.Conversation.objects.create(kind="group", creator=requester, group_id=uuid.uuid4().hex)
    m.Membership.objects.create(conversation=conv, device=requester, valid_from_epoch=2)
    m.Membership.objects.create(conversation=conv, device=old, valid_from_epoch=0, removed_at_epoch=1)
    assert client.get(f"/api/v1/crypto/key-packages/{old_id}", secure=True).status_code == 200
    assert post(client, f"crypto/key-packages/{old_id}", {}).status_code == 404
