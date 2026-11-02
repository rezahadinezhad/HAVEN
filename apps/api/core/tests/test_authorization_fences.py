"""Concurrent HTTP authority changes; no mocked authorization or crypto verdicts."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from django.db import close_old_connections
from core import models as m
from core.auth import CookieAuthentication
from .conftest import post
from .test_view_once import group as group, uploaded

pytestmark = pytest.mark.django_db(transaction=True)


def test_message_read_keeps_live_authority_without_a_write_transaction(group):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    _, _, client, _, _, _, _, _, conv = group
    with CaptureQueriesContext(connection) as captured:
        response = client.get(f"/api/v1/conversations/{conv.pk}/messages", secure=True)
    assert response.status_code == 200
    assert "messages" in response.json()
    statements = [query["sql"].strip().upper() for query in captured]
    assert not any(
        query.startswith(("BEGIN", "COMMIT", "INSERT", "UPDATE", "DELETE")) for query in statements
    )
    assert any("CORE_SESSION" in query for query in statements)


def test_existing_cursor_ack_keeps_outer_commit_without_redundant_savepoints(group):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    _, _, client, device, _, _, _, _, conv = group
    m.Conversation.objects.filter(pk=conv.pk).update(last_seq=1)
    m.DeliveryCursor.objects.create(device=device, conversation=conv, last_acked_seq=0)
    with CaptureQueriesContext(connection) as captured:
        response = post(client, f"conversations/{conv.pk}/acks", {"seq": 1})
    assert response.status_code == 200
    statements = [query["sql"].strip().upper() for query in captured]
    assert "BEGIN" in statements and "COMMIT" in statements
    assert not any(query.startswith(("SAVEPOINT", "RELEASE SAVEPOINT")) for query in statements)
    assert m.DeliveryCursor.objects.get(device=device, conversation=conv).last_acked_seq == 1


def test_slow_ack_cursor_read_does_not_lock_out_another_recipient(group, monkeypatch):
    from django.db.models.query import QuerySet

    _, _, first_client, first_device, _, _, second_client, second_device, conv = group
    m.Conversation.objects.filter(pk=conv.pk).update(last_seq=2)
    for device in (first_device, second_device):
        m.DeliveryCursor.objects.create(device=device, conversation=conv)
    reached, release = Event(), Event()
    actual = QuerySet.first

    def delayed(query):
        if query.model is m.DeliveryCursor and first_device.pk in query.query.sql_with_params()[1]:
            reached.set()
            assert release.wait(10)
        return actual(query)

    monkeypatch.setattr(QuerySet, "first", delayed)

    def ack(client):
        close_old_connections()
        try:
            return post(client, f"conversations/{conv.pk}/acks", {"seq": 2}).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as threads:
        first = threads.submit(ack, first_client)
        try:
            assert reached.wait(5)
            assert threads.submit(ack, second_client).result(timeout=2) == 200
        finally:
            release.set()
        assert first.result(timeout=5) == 200
    assert m.Conversation.objects.get(pk=conv.pk).receipt_version == 2
    assert m.DeliveryCursor.objects.filter(conversation=conv, last_acked_seq=2).count() == 2


def test_uncommitted_ack_never_authorizes_ciphertext_retirement(group, monkeypatch):
    from datetime import timedelta
    import uuid
    from django.db.models.query import QuerySet
    from django.utils import timezone
    from core.retention import retire_delivered

    _, owner, client, device, _, _, _, _, conv = group
    m.Conversation.objects.filter(pk=conv.pk).update(last_seq=1)
    # Opaque durable ciphertext fixture: this checks transaction visibility,
    # not MLS. Real signature/MLS checks are exercised by the native suite.
    envelope = m.MessageEnvelope.objects.create(
        conversation=conv,
        sender_device=owner,
        server_seq=1,
        client_message_id=uuid.uuid4(),
        group_epoch=0,
        ciphertext=b"synthetic opaque ciphertext",
        request_digest="d" * 64,
    )
    m.MessageEnvelope.objects.filter(pk=envelope.pk).update(received_at=timezone.now() - timedelta(days=2))
    for member in m.Membership.objects.filter(conversation=conv):
        m.DeliveryCursor.objects.create(
            device_id=member.device_id,
            conversation=conv,
            last_acked_seq=0 if member.device_id == device.pk else 1,
        )
    updated, release = Event(), Event()
    actual = QuerySet.update

    def paused(query, **values):
        result = actual(query, **values)
        if query.model is m.DeliveryCursor:
            updated.set()
            assert release.wait(10)
        return result

    monkeypatch.setattr(QuerySet, "update", paused)

    def work(ack):
        close_old_connections()
        try:
            return (
                post(client, f"conversations/{conv.pk}/acks", {"seq": 1}).status_code
                if ack
                else retire_delivered(timezone.now())
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as threads:
        pending = threads.submit(work, True)
        try:
            assert updated.wait(5)
            assert threads.submit(work, False).result(timeout=2) == 0
            assert bytes(m.MessageEnvelope.objects.get(pk=envelope.pk).ciphertext)
        finally:
            release.set()
        assert pending.result(timeout=5) == 200
    assert retire_delivered(timezone.now()) == 1
    assert not bytes(m.MessageEnvelope.objects.get(pk=envelope.pk).ciphertext)


def test_ack_waits_for_membership_removal_account_fence_then_rechecks(group):
    from django.db import connection, transaction

    _, owner, client, device, _, _, _, _, conv = group
    changed, release, waiting = Event(), Event(), Event()

    def remove():
        close_old_connections()
        try:
            with transaction.atomic():
                # Same account-before-conversation protocol as CryptoEvents.
                list(
                    m.User.objects.select_for_update()
                    .filter(pk__in=[owner.user_id, device.user_id])
                    .order_by("pk")
                )
                m.Conversation.objects.select_for_update().get(pk=conv.pk)
                m.Membership.objects.filter(conversation=conv, device=device).update(removed_at_epoch=1)
                changed.set()
                assert release.wait(10)
        finally:
            close_old_connections()

    def ack():
        close_old_connections()

        def observe(execute, sql, params, many, context):
            if '"core_user"' in sql and "FOR UPDATE" in sql:
                waiting.set()
            return execute(sql, params, many, context)

        try:
            with connection.execute_wrapper(observe):
                return post(client, f"conversations/{conv.pk}/acks", {"seq": 0}).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as threads:
        removal = threads.submit(remove)
        try:
            assert changed.wait(5)
            pending = threads.submit(ack)
            assert waiting.wait(5) and not pending.done()
        finally:
            release.set()
        removal.result(timeout=5)
        assert pending.result(timeout=5) == 404
    assert not m.DeliveryCursor.objects.filter(conversation=conv, device=device).exists()
    assert m.Conversation.objects.get(pk=conv.pk).receipt_version == 0


def test_concurrent_same_device_acks_remain_monotonic(group, monkeypatch):
    from copy import deepcopy
    from threading import Barrier

    _, _, client, device, _, _, _, _, conv = group
    m.Conversation.objects.filter(pk=conv.pk).update(last_seq=10)
    m.DeliveryCursor.objects.create(device=device, conversation=conv)
    other = type(client)(enforce_csrf_checks=True)
    other.defaults = dict(client.defaults)
    other.cookies = deepcopy(client.cookies)
    barrier = Barrier(2)
    actual = CookieAuthentication.authenticate

    def simultaneous(self, request):
        result = actual(self, request)
        if request.method == "POST" and request.path.endswith("/acks"):
            barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(CookieAuthentication, "authenticate", simultaneous)

    def ack(item):
        actor, seq = item
        close_old_connections()
        try:
            return post(actor, f"conversations/{conv.pk}/acks", {"seq": seq}).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as threads:
        assert list(threads.map(ack, [(client, 10), (other, 5)])) == [200, 200]
    assert m.DeliveryCursor.objects.get(conversation=conv, device=device).last_acked_seq == 10


def test_database_unavailable_during_cookie_auth_is_generic_and_fail_closed(group, monkeypatch):
    from django.db import OperationalError
    from core import middleware

    _, _, client, _, _, _, _, _, conv = group

    def unavailable(*args):
        raise OperationalError("synthetic database diagnostic canary")

    monkeypatch.setattr(middleware, "resolve_session", unavailable)
    response = client.get(f"/api/v1/conversations/{conv.pk}/messages", secure=True)
    assert response.status_code == 503
    assert response.json() == {"error": "Service temporarily unavailable"}
    assert response["Cache-Control"] == "no-store"


def paused_request(monkeypatch, client, path, body, revoke, method="POST"):
    """Pause after real middleware authentication, before the view can authorize."""
    reached, proceed = Event(), Event()
    original = CookieAuthentication.authenticate

    def authenticate(self, request):
        result = original(self, request)
        if request.method == method and request.path == "/api/v1/" + path:
            reached.set()
            if not proceed.wait(10):
                raise RuntimeError("Controlled authorization race did not resume")
        return result

    monkeypatch.setattr(CookieAuthentication, "authenticate", authenticate)

    def operation():
        close_old_connections()
        try:
            return client.get("/api/v1/" + path, secure=True) if method == "GET" else post(client, path, body)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(operation)
        try:
            assert reached.wait(10)
            revoke()
        finally:
            proceed.set()
        return future.result(timeout=15)


def test_device_revoked_after_authentication_cannot_ack(group, monkeypatch):
    _, _, b, bd, b2, _, _, _, conv = group
    m.Conversation.objects.filter(pk=conv.pk).update(last_seq=2)
    response = paused_request(
        monkeypatch,
        b,
        f"conversations/{conv.pk}/acks",
        {"seq": 2},
        lambda: assert_revoked(b2, bd),
    )
    assert response.status_code == 403
    assert not m.DeliveryCursor.objects.filter(device=bd, conversation=conv).exists()
    assert m.Conversation.objects.get(pk=conv.pk).receipt_version == 0


def assert_revoked(client, device):
    assert post(client, f"devices/{device.pk}/revoke", {}).status_code == 200


def test_revocation_after_authentication_cannot_consume_view_once(group, monkeypatch):
    _, _, b, bd, b2, _, _, _, _ = group
    aid, _ = uploaded(group)
    response = paused_request(
        monkeypatch,
        b,
        f"attachments/{aid}/view-once",
        {"token": "d" * 64},
        lambda: assert_logout(b2),
    )
    assert response.status_code == 403
    view = m.AttachmentView.objects.get(attachment_id=aid, user=bd.user)
    assert not view.consumed and view.opened_by_id is None and not view.token_hash


def assert_logout(client):
    assert post(client, "auth/logout-all", {}).status_code == 200


def test_read_revalidates_logout_after_middleware_authentication(group, monkeypatch):
    _, _, client, _, other, _, _, _, conv = group
    response = paused_request(
        monkeypatch,
        client,
        f"conversations/{conv.pk}/messages",
        None,
        lambda: assert_logout(other),
        method="GET",
    )
    assert response.status_code == 403
    assert "messages" not in response.json()


def test_admin_read_revalidates_current_role(group, monkeypatch):
    _, _, client, device, _, _, _, _, _ = group
    m.User.objects.filter(pk=device.user_id).update(role="community_admin")
    response = paused_request(
        monkeypatch,
        client,
        "admin/devices",
        None,
        lambda: m.User.objects.filter(pk=device.user_id).update(role="member"),
        method="GET",
    )
    assert response.status_code == 403


def test_cross_account_revocations_lock_accounts_in_one_order(settings, monkeypatch):
    from threading import Barrier
    from .test_view_once import bound_client

    settings.CRYPTO_READY = True
    a, ad = bound_client()
    b, bd = bound_client()
    m.User.objects.filter(pk__in=[ad.user_id, bd.user_id]).update(role="community_admin")
    barrier = Barrier(2)
    original = CookieAuthentication.authenticate

    def authenticate(self, request):
        result = original(self, request)
        if request.method == "POST" and "/admin/devices/" in request.path:
            barrier.wait(timeout=10)
        return result

    monkeypatch.setattr(CookieAuthentication, "authenticate", authenticate)

    def revoke(item):
        client, device = item
        close_old_connections()
        try:
            return post(client, f"admin/devices/{device.pk}/revoke", {}).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(revoke, [(a, bd), (b, ad)])) == [200, 403]
    assert m.Device.objects.filter(pk__in=[ad.pk, bd.pk], revoked_at__isnull=False).count() == 1


def test_handled_api_error_rolls_back_all_request_writes(settings):
    from django.urls import path
    from rest_framework.exceptions import ValidationError
    from core.views import View
    from .test_view_once import bound_client

    client, device = bound_client()

    class PartialWrite(View):
        def post(self, request):
            m.AuditEvent.objects.create(actor=request.user, category="test.partial")
            raise ValidationError("Synthetic rejected operation")

    global urlpatterns
    urlpatterns = [
        path("api/v1/test/partial", PartialWrite.as_view()),
        path("api/v1/auth/csrf", __import__("core.views", fromlist=["CSRF"]).CSRF.as_view()),
    ]
    settings.ROOT_URLCONF = __name__
    assert post(client, "test/partial", {}).status_code == 400
    assert not m.AuditEvent.objects.filter(actor=device.user, category="test.partial").exists()


@pytest.mark.parametrize("fault", ["database", "redis", "unexpected"])
def test_failure_responses_hide_diagnostics_and_rollback_partial_writes(settings, caplog, fault):
    from django.db import connection
    from django.urls import path
    import redis
    from core.views import View, CSRF
    from .test_view_once import bound_client

    client, device = bound_client()
    canary = "SYNTHETIC_PRIVATE_REQUEST_MUST_NOT_APPEAR"

    class FailingWrite(View):
        def post(self, request):
            m.AuditEvent.objects.create(actor=request.user, category="test.failure")
            if fault == "database":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1 / 0")  # Actual PostgreSQL transaction failure.
            if fault == "redis":
                raise redis.ConnectionError(canary)
            raise RuntimeError(canary)

    global urlpatterns
    urlpatterns = [
        path("api/v1/test/failure", FailingWrite.as_view()),
        path("api/v1/auth/csrf", CSRF.as_view()),
    ]
    settings.ROOT_URLCONF = __name__
    response = post(client, "test/failure", {"private": canary})
    assert response.status_code == 503
    assert response.json() == {"error": "service_unavailable"}
    assert canary not in response.content.decode() and canary not in caplog.text
    assert not m.AuditEvent.objects.filter(actor=device.user, category="test.failure").exists()
    assert m.Session.objects.filter(user=device.user, revoked_at=None).exists()


def test_inflight_mutation_finishes_before_waiting_logout(group, monkeypatch):
    from django.db import connection
    from core.views import Acks

    _, _, client, device, other, _, _, _, conv = group
    m.Conversation.objects.filter(pk=conv.pk).update(last_seq=2)
    entered, finish, logout_waiting = Event(), Event(), Event()
    original = Acks.post

    def paused(self, request, cid):
        entered.set()  # Authentication and the account fence have already succeeded.
        assert finish.wait(10)
        return original(self, request, cid)

    monkeypatch.setattr(Acks, "post", paused)

    def ack():
        close_old_connections()
        try:
            return post(client, f"conversations/{conv.pk}/acks", {"seq": 2})
        finally:
            close_old_connections()

    def logout():
        close_old_connections()

        def observed(execute, sql, params, many, context):
            if '"core_user"' in sql and "FOR UPDATE" in sql:
                logout_waiting.set()
            return execute(sql, params, many, context)

        try:
            with connection.execute_wrapper(observed):
                return post(other, "auth/logout-all", {})
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending_ack = pool.submit(ack)
        try:
            assert entered.wait(10)
            pending_logout = pool.submit(logout)
            assert logout_waiting.wait(10)
            assert not pending_logout.done()
        finally:
            finish.set()
        assert pending_ack.result(timeout=10).status_code == 200
        assert pending_logout.result(timeout=10).status_code == 200
    assert m.DeliveryCursor.objects.get(device=device, conversation=conv).last_acked_seq == 2
    assert not m.Session.objects.filter(user=device.user, revoked_at=None).exists()


def test_concurrent_account_revocations_rekey_shared_groups_without_deadlock(group, monkeypatch):
    from threading import Barrier
    import uuid
    from core import views

    _, _, b, bd, _, _, c, cd, conv = group
    conversations = [conv]
    for _ in range(3):
        shared = m.Conversation.objects.create(creator=bd, kind="group", group_id=uuid.uuid4().hex)
        for device in [bd, cd]:
            m.Membership.objects.create(conversation=shared, device=device, valid_from_epoch=0)
        conversations.append(shared)
    barrier = Barrier(2)
    original = views.require_rekey

    def simultaneous(query):
        barrier.wait(timeout=10)
        return original(query)

    monkeypatch.setattr(views, "require_rekey", simultaneous)

    def revoke(item):
        client, device = item
        close_old_connections()
        try:
            return post(client, f"devices/{device.pk}/revoke", {}).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(revoke, [(b, bd), (c, cd)])) == [200, 200]
    assert set(
        m.Conversation.objects.filter(pk__in=[v.pk for v in conversations]).values_list("status", flat=True)
    ) == {"rekey_required"}
    assert m.Device.objects.filter(pk__in=[bd.pk, cd.pk], revoked_at__isnull=False).count() == 2


def test_oversized_body_rejected_before_account_row_lock():
    import uuid
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    from .conftest import csrf
    from .test_view_once import bound_client

    client, _ = bound_client()
    token = csrf(client)
    with CaptureQueriesContext(connection) as queries:
        response = client.put(
            f"/api/v1/attachments/{uuid.uuid4()}/chunks/0",
            b"x" * (1400 * 1024 + 1),
            content_type="application/octet-stream",
            secure=True,
            HTTP_X_CSRFTOKEN=token,
        )
    assert response.status_code == 400
    assert not any('"core_user"' in q["sql"] and "FOR UPDATE" in q["sql"] for q in queries)
    assert not m.AttachmentChunk.objects.exists()
