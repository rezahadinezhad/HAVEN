"""Authenticated, scoped synchronization hints; MLS content remains on the HTTP path."""

import hashlib
import secrets
import uuid
from datetime import timedelta
import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.utils import timezone
from core import models as m
from haven.asgi import application

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


@sync_to_async
def identities():
    items = []
    for _ in range(3):
        user = m.User.objects.create_user(
            username="ws_" + uuid.uuid4().hex[:12], password=secrets.token_urlsafe(32)
        )
        did = uuid.uuid4()
        device = m.Device.objects.create(
            id=did,
            user=user,
            label="WS fixture",
            identity=f"{user.pk}:{did}",
            public_key=secrets.token_bytes(32),
            trust_state="approved",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        token = secrets.token_urlsafe(48)
        session = m.Session.objects.create(
            user=user,
            device=device,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        items.append((device, token, session))
    conv = m.Conversation.objects.create(kind="group", creator=items[0][0], group_id=uuid.uuid4().hex)
    for device, _, _ in items[:2]:
        m.Membership.objects.create(conversation=conv, device=device, valid_from_epoch=0)
    return items, str(conv.pk)


def socket(token):
    ws = WebsocketCommunicator(
        application,
        "/ws/v1",
        headers=[
            (b"host", b"127.0.0.1:8443"),
            (b"origin", b"https://127.0.0.1:8443"),
            (b"cookie", ("__Host-haven=" + token).encode()),
        ],
    )

    ws.scope["scheme"] = "wss"
    return ws


async def test_scoped_typing_and_revocation(settings):
    settings.CRYPTO_READY = True
    items, cid = await identities()
    sockets = [socket(token) for _, token, _ in items]
    try:
        for ws in sockets:
            assert (await ws.connect())[0]
            assert (await ws.receive_json_from())["kind"] == "hello"
        await sockets[0].send_json_to({"v": 1, "kind": "ephemeral.typing", "conversation_id": cid})
        hint = await sockets[1].receive_json_from()
        assert hint == {
            "v": 1,
            "kind": "ephemeral.typing",
            "conversation_id": cid,
            "sender_device": str(items[0][0].pk),
            "expires_in": 5,
        }
        await sockets[0].send_json_to({"v": 1, "kind": "ephemeral.presence", "conversation_id": cid})
        presence = await sockets[1].receive_json_from()
        assert presence["kind"] == "ephemeral.presence" and presence["expires_in"] == 50
        assert presence["sender_device"] == str(items[0][0].pk)
        assert await sockets[2].receive_nothing(timeout=0.1)
        await sockets[2].send_json_to({"v": 1, "kind": "ephemeral.typing", "conversation_id": cid})
        assert (await sockets[2].receive_output())["code"] == 4403
        await sync_to_async(m.Session.objects.filter(pk=items[1][2].pk).update)(revoked_at=timezone.now())
        await sockets[1].send_json_to({"v": 1, "kind": "heartbeat"})
        assert (await sockets[1].receive_output())["code"] == 4401
    finally:
        for ws in sockets:
            await ws.disconnect()


async def test_unauthed_and_bounded_frames(settings):
    settings.CRYPTO_READY = True
    missing = WebsocketCommunicator(
        application, "/ws/v1", headers=[(b"host", b"127.0.0.1:8443"), (b"origin", b"https://127.0.0.1:8443")]
    )
    missing.scope["scheme"] = "wss"
    assert await missing.connect() == (False, 4401)
    await missing.disconnect()
    items, _ = await identities()
    for payload, code in [
        ("{", 1007),
        ('{"v":true,"kind":"heartbeat"}', 1008),
        ('{"v":1,"kind":"heartbeat","unexpected":1}', 1008),
        ("x" * 2049, 1009),
    ]:
        ws = socket(items[0][1])
        try:
            assert (await ws.connect())[0]
            await ws.receive_json_from()
            await ws.send_to(text_data=payload)
            assert (await ws.receive_output())["code"] == code
        finally:
            await ws.disconnect()


@pytest.mark.parametrize(
    "scheme,host,origin",
    [
        ("ws", b"127.0.0.1:8443", b"https://127.0.0.1:8443"),
        ("wss", b"evil.test", b"https://127.0.0.1:8443"),
        ("wss", b"127.0.0.1:8443", b"https://127.0.0.1:8443\xff"),
    ],
)
async def test_socket_transport_and_authority_fail_closed(scheme, host, origin):
    items, _ = await identities()
    ws = socket(items[0][1])
    ws.scope["scheme"] = scheme
    ws.scope["headers"] = [
        (key, value) for key, value in ws.scope["headers"] if key not in (b"host", b"origin")
    ]
    ws.scope["headers"] += [(b"host", host), (b"origin", origin)]
    try:
        assert await ws.connect() == (False, 4403)
    finally:
        await ws.disconnect()


async def test_password_change_invalidates_live_websocket(settings):
    settings.CRYPTO_READY = True
    items, _ = await identities()
    device, token, session = items[0]
    ws = socket(token)
    try:
        assert (await ws.connect())[0]
        await ws.receive_json_from()

        @sync_to_async
        def change_password():
            user = m.User.objects.get(pk=device.user_id)
            user.set_password(secrets.token_urlsafe(32))
            user.save(update_fields=["password"])
            assert m.Session.objects.get(pk=session.pk).revoked_at is None

        await change_password()
        await ws.send_json_to({"v": 1, "kind": "heartbeat"})
        assert (await ws.receive_output())["code"] == 4401
    finally:
        await ws.disconnect()
