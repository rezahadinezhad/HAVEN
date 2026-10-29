"""Validate representative public responses against the checked-in generated contracts."""

import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
from .conftest import login, post

pytestmark = pytest.mark.django_db
SPEC = json.loads((Path(__file__).resolve().parents[4] / "packages/contracts/openapi.json").read_text())


def validate(name, value):
    Draft202012Validator({**SPEC, "$ref": "#/components/schemas/" + name}).validate(value)


def test_user_and_me_contract(client, credentials):
    login(client, credentials)
    response = client.get("/api/v1/auth/me", secure=True)
    assert response.status_code == 200
    validate("User", response.json()["user"])
    assert response.json()["recovery_configured"] is False


def test_operator_pause_and_account_disable(client, credentials):
    user, _ = credentials
    user.role = "superadmin"
    user.save()
    login(client, credentials)
    from .conftest import csrf

    headers = {"HTTP_X_CSRFTOKEN": csrf(client)}
    response = client.patch(
        "/api/v1/admin/system-status",
        {"invitations_paused": True, "maintenance": "Test maintenance"},
        format="json",
        secure=True,
        **headers,
    )
    assert response.status_code == 200
    assert post(client, "admin/invitations", {"hours": 1}).status_code == 403
    assert client.get("/api/v1/health", secure=True).json()["maintenance"] == "Test maintenance"
    # The last superadmin cannot disable itself through the member deletion flow.
    response = post(client, "auth/disable", {"password": credentials[1]})
    assert response.status_code == 403


def test_member_disable_revokes_session(client, credentials, settings):
    import uuid
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from .test_regressions import enrollment, complete

    settings.CRYPTO_READY = True
    user, password = credentials
    user.role = "member"
    user.save()
    login(client, credentials)
    key, did = Ed25519PrivateKey.generate(), uuid.uuid4()
    req = enrollment(client, user, did, key).json()
    response = complete(client, did, key, req["signing_payload"])
    assert response.status_code == 200
    response = post(client, "auth/disable", {"password": password, "confirmation": "DISABLE"})
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me", secure=True).status_code in (401, 403)


def test_operational_metadata_command(client):
    from django.core.management import call_command
    from core.models import BackupManifest, SoftwareRelease

    call_command("record_operational_evidence", "backup", "a" * 64, reference="test-backup")
    call_command("record_operational_evidence", "restored", "a" * 64, reference="test-restore")
    call_command(
        "record_operational_evidence",
        "release",
        "b" * 64,
        reference="test-public-key",
        release_version="test-only",
    )
    assert BackupManifest.objects.get(encrypted_checksum="a" * 64).tested_restore_at
    assert SoftwareRelease.objects.get(version="test-only").status == "operator_verified_unreviewed"


def test_bounded_operational_counters():
    from core.observability import request_observed, websocket_lease, snapshot
    import uuid

    channel = "test-only-" + uuid.uuid4().hex
    try:
        websocket_lease(channel)
        request_observed(30, 200)
        value = snapshot()
        assert value["api_requests"] >= 1 and value["websocket_leases"] >= 1
        assert value["status"] == "local_counters"
    finally:
        websocket_lease(channel, True)


def test_endpoint_probe_rejects_nonliteral_or_credential_urls():
    from django.core.management import call_command
    from django.core.management.base import CommandError
    from core.models import BootstrapEndpoint

    before = BootstrapEndpoint.objects.count()
    for url in [
        "http://127.0.0.1",
        "https://example.test",
        "https://user:secret@127.0.0.1",
        "https://@127.0.0.1",
        "https://127.0.0.1:0",
        "https://127.0.0.1/path",
    ]:
        with pytest.raises(CommandError):
            call_command(
                "check_endpoint", url, ca_file="/nonexistent-public-root", tls_profile="EMERGENCY_PRIVATE_PKI"
            )
    assert BootstrapEndpoint.objects.count() == before
