"""Actual PostgreSQL/Redis routing; opaque ciphertext fixtures, not MLS verdicts."""

import asyncio
import uuid
from asgiref.sync import sync_to_async
from channels.layers import channel_layers
from django.db import close_old_connections, connection
import pytest

from core import models as m
from core.management.commands.publish_outbox import Command
from .test_websocket import identities, socket

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]


@sync_to_async
def events(cid, device, count=3):
    try:
        for seq in range(1, count + 1):
            env = m.MessageEnvelope.objects.create(
                conversation_id=cid,
                sender_device=device,
                server_seq=seq,
                client_message_id=uuid.uuid4(),
                group_epoch=0,
                ciphertext=b"opaque fixture",
                request_digest="d" * 64,
            )
            m.NotificationOutbox.objects.create(envelope=env)
    finally:
        connection.close()


@sync_to_async
def published(expected):
    try:
        assert m.NotificationOutbox.objects.count() == expected
        assert m.NotificationOutbox.objects.filter(sent_at__isnull=False, attempts=1).count() == expected
    finally:
        connection.close()


def batch(fail=False):
    close_old_connections()
    layer = channel_layers.make_backend("default")
    actual = layer.group_send
    count = 0

    async def interrupted(group, event):
        nonlocal count
        count += 1
        if count == 2:
            raise ConnectionError("synthetic private failure must stay out of diagnostics")
        return await actual(group, event)

    if fail:
        layer.group_send = interrupted
    try:
        with asyncio.Runner() as runner:
            try:
                return Command().publish_batch(layer, runner)
            finally:
                runner.run(layer.close_pools())
    finally:
        close_old_connections()


async def test_batch_coalesces_multiple_messages_into_one_scoped_hint_per_account():
    items, cid = await identities()
    await events(cid, items[0][0])
    sockets = [socket(token) for _, token, _ in items]
    try:
        for ws in sockets:
            assert (await ws.connect())[0]
            assert (await ws.receive_json_from())["kind"] == "hello"
        assert await asyncio.to_thread(batch) == 3
        for ws in sockets[:2]:
            assert await ws.receive_json_from() == {"v": 1, "kind": "sync.required"}
            assert await ws.receive_nothing(0.1)
        assert await sockets[2].receive_nothing(0.1)
        await published(3)
    finally:
        for ws in sockets:
            await ws.disconnect()


async def test_partial_notification_failure_keeps_every_outbox_row_retryable():
    items, cid = await identities()
    await events(cid, items[0][0])
    with pytest.raises(ConnectionError):
        await asyncio.to_thread(batch, True)

    @sync_to_async
    def unsent():
        try:
            assert m.NotificationOutbox.objects.filter(sent_at=None, attempts=0).count() == 3
        finally:
            connection.close()

    await unsent()
    assert await asyncio.to_thread(batch) == 3
    await published(3)


async def test_independent_publisher_process_delivers_over_real_redis():
    import os
    import sys
    from pathlib import Path
    from django.conf import settings

    items, cid = await identities()
    await events(cid, items[0][0], 1)
    ws = socket(items[1][1])
    try:
        assert (await ws.connect())[0]
        await ws.receive_json_from()
        config = connection.settings_dict
        env = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "haven.settings",
            "POSTGRES_DB": config["NAME"],
            "POSTGRES_USER": config["USER"],
            "POSTGRES_PASSWORD": config["PASSWORD"],
            "POSTGRES_HOST": config["HOST"],
            "POSTGRES_PORT": str(config["PORT"]),
            "HAVEN_ROUTING_SECRET": settings.ROUTING_SECRET,
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "manage.py",
            "publish_outbox",
            "--once",
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(process.communicate(), 15)
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise
        assert process.returncode == 0 and b"unavailable" not in stderr
        assert await ws.receive_json_from() == {"v": 1, "kind": "sync.required"}
        await published(1)
    finally:
        await ws.disconnect()
