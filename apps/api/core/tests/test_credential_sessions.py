"""Credential binding and races across real authentication boundaries."""

import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient
from core import models as m, views
from core.middleware import resolve_session
from .conftest import login, post
from .test_security import setup_device

pytestmark = pytest.mark.django_db


def test_out_of_band_password_change_invalidates_http_without_session_update(client, credentials):
    user, _ = credentials
    assert login(client, credentials).status_code == 200
    token = client.cookies["__Host-haven"].value
    session = resolve_session(token)
    assert session and session.auth_hash and session.auth_hash != user.password
    user.set_password(secrets.token_urlsafe(32))
    user.save(update_fields=["password"])
    session.refresh_from_db()
    assert session.revoked_at is None  # No explicit session revocation was needed.
    assert resolve_session(token) is None
    assert client.get("/api/v1/auth/me", secure=True).status_code == 403
    session.device_challenge = "unrelated update"
    session.save(update_fields=["device_challenge"])
    assert resolve_session(token) is None


def test_verified_login_cannot_issue_after_concurrent_credential_change(client, credentials, monkeypatch):
    original = views.authenticate

    def reset_after_verification(**kwargs):
        verified = original(**kwargs)
        fresh = m.User.objects.get(pk=verified.pk)
        fresh.set_password(secrets.token_urlsafe(32))
        fresh.save(update_fields=["password"])
        return verified

    monkeypatch.setattr(views, "authenticate", reset_after_verification)
    assert login(client, credentials).status_code == 403
    assert not m.Session.objects.exists()


def test_verified_login_cannot_issue_after_account_disable(client, credentials, monkeypatch):
    original = views.authenticate

    def disable_after_verification(**kwargs):
        verified = original(**kwargs)
        m.User.objects.filter(pk=verified.pk).update(is_active=False)
        return verified

    monkeypatch.setattr(views, "authenticate", disable_after_verification)
    assert login(client, credentials).status_code == 403
    assert not m.Session.objects.exists()


def test_pending_signins_are_bounded_and_never_evict_bound_sessions(client, credentials, settings):
    settings.CRYPTO_READY = True
    device, _ = setup_device(client, credentials)
    token = client.cookies["__Host-haven"].value
    bound = resolve_session(token)
    request = RequestFactory().post("/api/v1/auth/login")
    issued = []
    for _ in range(9):
        response = views.issue_session(request, credentials[0])
        issued.append(response.cookies["__Host-haven"].value)
    assert m.Session.objects.filter(user=device.user, device=None).count() == 5
    assert resolve_session(issued[0]) is None
    assert resolve_session(issued[-1]) is not None
    assert resolve_session(token).pk == bound.pk
    assert m.Session.objects.filter(pk=bound.pk, device=device).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_password_changes_cannot_both_use_old_password(credentials, monkeypatch):
    first, second = APIClient(enforce_csrf_checks=True), APIClient(enforce_csrf_checks=True)
    for client in (first, second):
        client.defaults.update(HTTP_HOST="127.0.0.1:8443", HTTP_ORIGIN="https://127.0.0.1:8443")
        assert login(client, credentials).status_code == 200
    barrier = Barrier(2)
    original = views.data

    def wait_before_lock(request, serializer):
        value = original(request, serializer)
        if serializer is views.s.Password:
            barrier.wait(timeout=10)
        return value

    monkeypatch.setattr(views, "data", wait_before_lock)
    candidates = [secrets.token_urlsafe(32), secrets.token_urlsafe(32)]

    def change(args):
        client, new = args
        close_old_connections()
        try:
            return post(
                client, "auth/change-password", {"old_password": credentials[1], "new_password": new}
            ).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(change, zip((first, second), candidates))) == [200, 400]
    assert m.Session.objects.filter(revoked_at=None).count() == 0
    user = m.User.objects.get(pk=credentials[0].pk)
    assert sum(user.check_password(value) for value in candidates) == 1


def test_blank_or_tampered_binding_fails_closed(client, credentials):
    login(client, credentials)
    token = client.cookies["__Host-haven"].value
    session = resolve_session(token)
    for value in ("", "f" * 64):
        m.Session.objects.filter(pk=session.pk).update(auth_hash=value)
        assert resolve_session(token) is None


@pytest.mark.django_db(transaction=True)
def test_migration_revokes_existing_unbound_sessions():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    old, new = ("core", "0009_member_invitations"), ("core", "0010_credential_bound_sessions")
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate([old])
        apps = executor.loader.project_state([old]).apps
        user = apps.get_model("core", "User").objects.create(username="pre_binding_migration")
        session = apps.get_model("core", "Session").objects.create(
            user=user,
            token_hash=secrets.token_hex(32),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        executor = MigrationExecutor(connection)
        executor.migrate([new])
        migrated = m.Session.objects.get(pk=session.pk)
        assert not migrated.auth_hash and migrated.revoked_at is not None
    finally:
        MigrationExecutor(connection).migrate(latest)


def test_enrollment_rechecks_revocation_after_request_authentication(
    client, credentials, settings, monkeypatch
):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    import uuid
    from .test_regressions import enrollment, complete

    settings.CRYPTO_READY = True
    user, _ = credentials
    assert login(client, credentials).status_code == 200
    key, did = Ed25519PrivateKey.generate(), uuid.uuid4()
    pending = enrollment(client, user, did, key).json()
    original = views.data

    def revoke_after_parse(request, serializer):
        value = original(request, serializer)
        if serializer is views.s.Approval:
            m.Session.objects.filter(pk=request.auth.pk).update(revoked_at=timezone.now())
        return value

    monkeypatch.setattr(views, "data", revoke_after_parse)
    assert complete(client, did, key, pending["signing_payload"]).status_code == 403
    assert m.Device.objects.get(pk=did).trust_state == "pending"
    user.refresh_from_db()
    assert not user.device_bootstrapped
