"""Real DB delay/revocation checks for bounded WebSocket authentication work."""

import asyncio
from datetime import timedelta
import secrets
import threading
import uuid

from asgiref.sync import sync_to_async
from django.db import connection
from django.utils import timezone
import pytest

from core import consumers, models as m
from core.middleware import digest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]


@sync_to_async
def sessions():
    user = m.User.objects.create_user(username="db_" + uuid.uuid4().hex, password=secrets.token_urlsafe(32))
    tokens = [secrets.token_urlsafe(48) for _ in range(2)]
    for token in tokens:
        m.Session.objects.create(
            user=user, token_hash=digest(token), expires_at=timezone.now() + timedelta(hours=1)
        )
    connection.close()
    return str(user.pk), tokens


async def test_slow_socket_auth_query_does_not_block_unrelated_session(monkeypatch):
    uid, tokens = await sessions()
    actual = consumers.resolve_session
    entered = threading.Event()

    def delayed(token):
        if token == tokens[0]:
            with connection.cursor() as cursor:
                entered.set()
                cursor.execute("SELECT pg_sleep(1.2)")
        return actual(token)

    monkeypatch.setattr(consumers, "resolve_session", delayed)
    first = asyncio.create_task(consumers.session_user(tokens[0]))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        assert await asyncio.wait_for(consumers.session_user(tokens[1]), timeout=0.6) == uid
    finally:
        assert await first == uid


async def test_socket_auth_still_reads_live_revocation_after_prior_success():
    uid, tokens = await sessions()
    assert await consumers.session_user(tokens[0]) == uid

    @sync_to_async
    def revoke():
        m.Session.objects.filter(token_hash=digest(tokens[0])).update(revoked_at=timezone.now())
        connection.close()

    await revoke()
    assert await consumers.session_user(tokens[0]) is None
    assert await consumers.session_user(tokens[1]) == uid


async def test_session_projection_preserves_inherited_field_order_and_deferred_values():
    uid, tokens = await sessions()

    @sync_to_async
    def inspect():
        session = consumers.resolve_session(tokens[0])
        assert session is not None
        assert str(session.user_id) == uid and str(session.user.pk) == uid
        assert isinstance(session.pk, int)
        assert session.user.password.startswith("argon2$")
        assert "username" in session.user.get_deferred_fields()
        assert "device_challenge" in session.get_deferred_fields()
        assert session.user.username.startswith("db_")
        assert session.device_challenge == ""
        connection.close()

    await inspect()


async def test_database_failure_closes_socket_for_retry_without_auth_bypass(monkeypatch):
    from django.db import OperationalError
    from .test_websocket import identities, socket

    items, _ = await identities()
    ws = socket(items[0][1])
    try:
        assert (await ws.connect())[0]
        assert (await ws.receive_json_from())["kind"] == "hello"

        def unavailable(*args):
            raise OperationalError("synthetic database failure")

        monkeypatch.setattr(consumers, "resolve_session", unavailable)
        await ws.send_json_to({"v": 1, "kind": "heartbeat"})
        assert (await ws.receive_output())["code"] == 1013
    finally:
        await ws.disconnect()
