"""Real Ed25519 session proof binding with no global ordinal in new challenges."""

import uuid
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings
from rest_framework.test import APIClient

from core import models as m
from core.middleware import digest
from .conftest import login
from .test_regressions import enrollment, complete

pytestmark = pytest.mark.django_db


def current_session(client):
    return m.Session.objects.get(token_hash=digest(client.cookies[settings.SESSION_COOKIE_NAME].value))


def test_new_proof_hides_global_counter_rotates_and_rejects_stale_replay(client, credentials, settings):
    settings.CRYPTO_READY = True
    assert login(client, credentials).status_code == 200
    key, did = Ed25519PrivateKey.generate(), uuid.uuid4()
    first = enrollment(client, credentials[0], did, key).json()["signing_payload"]
    parts = first.split(":")
    assert len(parts) == 4 and parts[0] == "haven/session/v1" and parts[2] == str(did)
    assert parts[1].isdigit() and parts[1] != str(current_session(client).pk)
    assert len(parts[3]) == 64 and parts[3] == current_session(client).device_challenge.removeprefix("v2:")
    second = enrollment(client, credentials[0], did, key).json()["signing_payload"]
    assert second.split(":")[1] != parts[1] and second.split(":")[3] != parts[3]
    assert complete(client, did, key, first).status_code == 400
    assert complete(client, did, key, second).status_code == 200
    assert complete(client, did, key, second).status_code == 403  # Consumed challenge.


def test_proof_cannot_move_to_another_session_even_with_copied_nonce(client, credentials, settings):
    settings.CRYPTO_READY = True
    assert login(client, credentials).status_code == 200
    key, did = Ed25519PrivateKey.generate(), uuid.uuid4()
    payload = enrollment(client, credentials[0], did, key).json()["signing_payload"]
    original = current_session(client)
    other = APIClient(enforce_csrf_checks=True)
    other.defaults.update(client.defaults)
    assert login(other, credentials).status_code == 200
    assert enrollment(other, credentials[0], did, key).status_code == 201
    # Stronger than the natural random-nonce condition: context still prevents
    # transplantation if a restore/corruption copied the nonce to a different row.
    m.Session.objects.filter(pk=current_session(other).pk).update(device_challenge=original.device_challenge)
    assert complete(other, did, key, payload).status_code == 400
    assert complete(client, did, key, payload).status_code == 200


def test_inflight_legacy_proof_still_binds_current_session_and_is_one_use(client, credentials, settings):
    settings.CRYPTO_READY = True
    assert login(client, credentials).status_code == 200
    key, did = Ed25519PrivateKey.generate(), uuid.uuid4()
    response = enrollment(client, credentials[0], did, key)
    assert response.status_code == 201
    session = current_session(client)
    # Reproduce a real pre-upgrade row: a raw 64-hex challenge, no version prefix.
    nonce = session.device_challenge.removeprefix("v2:")
    m.Session.objects.filter(pk=session.pk).update(device_challenge=nonce)
    legacy = f"haven/session/v1:{session.pk}:{did}:{nonce}"
    assert response.json()["signing_payload"] != legacy
    assert complete(client, did, key, legacy).status_code == 200
    assert complete(client, did, key, legacy).status_code == 403


def test_fresh_challenge_cannot_probe_the_legacy_global_ordinal(client, credentials, settings):
    settings.CRYPTO_READY = True
    assert login(client, credentials).status_code == 200
    key, did = Ed25519PrivateKey.generate(), uuid.uuid4()
    current = enrollment(client, credentials[0], did, key).json()["signing_payload"]
    session = current_session(client)
    # Give this adversarial test the correct internal PK: even that old-style
    # proof must fail for a newly issued challenge, so guessing is not an oracle.
    legacy_guess = f"haven/session/v1:{session.pk}:{did}:{current.split(':')[3]}"
    assert complete(client, did, key, legacy_guess).status_code == 400
    assert complete(client, did, key, current).status_code == 200


def test_unknown_stored_challenge_version_fails_closed_and_refresh_preserves_identity(
    client, credentials, settings
):
    settings.CRYPTO_READY = True
    assert login(client, credentials).status_code == 200
    key, did = Ed25519PrivateKey.generate(), uuid.uuid4()
    current = enrollment(client, credentials[0], did, key).json()["signing_payload"]
    m.Session.objects.filter(pk=current_session(client).pk).update(device_challenge="v3:" + "a" * 64)
    assert complete(client, did, key, current).status_code == 403
    fresh = enrollment(client, credentials[0], did, key).json()["signing_payload"]
    assert complete(client, did, key, fresh).status_code == 200
    assert m.Device.objects.filter(pk=did).count() == 1
