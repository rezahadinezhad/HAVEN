import json
import asyncio
from .observability import websocket_lease
import time
import uuid
from urllib.parse import urlsplit
from http.cookies import SimpleCookie
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from .middleware import resolve_session
from .models import Membership


@database_sync_to_async
def session_user(token):
    s = resolve_session(token)
    return str(s.user_id) if s else None


@database_sync_to_async
def typing_recipients(token, cid):
    session = resolve_session(token)
    if (
        not session
        or not session.device
        or session.device.trust_state != "approved"
        or not settings.CRYPTO_READY
    ):
        return None
    if not Membership.objects.filter(
        conversation_id=cid, device=session.device, removed_at_epoch=None, conversation__status="active"
    ).exists():
        return None
    peers = Membership.objects.filter(
        conversation_id=cid, removed_at_epoch=None, device__revoked_at=None
    ).exclude(device__user_id=session.user_id)
    return str(session.device_id), list(peers.values_list("device__user_id", flat=True).distinct()[:100])


class SyncConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        headers = dict(self.scope["headers"])
        try:
            origin = headers.get(b"origin", b"").decode("ascii")
            host = headers.get(b"host", b"").decode("ascii")
        except UnicodeDecodeError:
            await self.close(code=4403)
            return
        if (
            self.scope.get("scheme") != "wss"
            or origin not in settings.ORIGINS
            or host != urlsplit(origin).netloc
        ):
            await self.close(code=4403)
            return
        cookie = SimpleCookie()
        try:
            cookie.load(headers.get(b"cookie", b"").decode("ascii"))
            token = cookie[settings.SESSION_COOKIE_NAME].value
        except (KeyError, ValueError):
            await self.close(code=4401)
            return
        self.frame_window = time.monotonic()
        self.frame_count = 0
        self.token = token
        self.uid = await session_user(token)
        if self.uid is None:
            await self.close(code=4401)
            return
        self.group = "user." + self.uid
        try:
            await self.channel_layer.group_add(self.group, self.channel_name)
        except Exception:
            await self.close(code=1013)
            return
        await self.accept()
        await asyncio.to_thread(websocket_lease, self.channel_name)
        await self.send_json({"v": 1, "kind": "hello", "sync": "http", "crypto_ready": settings.CRYPTO_READY})

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data is not None or text_data is None or len(text_data) > 2048:
            await self.close(code=1009)
            return
        if time.monotonic() - self.frame_window > 60:
            self.frame_window, self.frame_count = time.monotonic(), 0
        self.frame_count += 1
        if self.frame_count > 60:
            await self.close(code=1008)
            return
        try:
            d = json.loads(text_data)
        except ValueError:
            await self.close(code=1007)
            return
        if (
            not isinstance(d, dict)
            or type(d.get("v")) is not int
            or d.get("v") != 1
            or d.get("kind") not in ("heartbeat", "resume", "ephemeral.typing", "ephemeral.presence")
        ):
            await self.close(code=1008)
            return
        # Check revocation on every incoming frame; notifications also recheck before sending.
        if not await session_user(self.token):
            await self.close(code=4401)
            return
        await asyncio.to_thread(websocket_lease, self.channel_name)
        if d["kind"] in ("ephemeral.typing", "ephemeral.presence"):
            if set(d) != {"v", "kind", "conversation_id"}:
                await self.close(code=1008)
                return
            try:
                cid = str(uuid.UUID(d["conversation_id"]))
            except (ValueError, TypeError, KeyError):
                await self.close(code=1008)
                return
            recipients = await typing_recipients(self.token, cid)
            if recipients is None:
                await self.close(code=4403)
                return
            sender, users = recipients
            for user in users:
                await self.channel_layer.group_send(
                    "user." + str(user),
                    {
                        "type": "typing.hint",
                        "kind": d["kind"],
                        "conversation_id": cid,
                        "sender_device": sender,
                    },
                )
        else:
            if set(d) != {"v", "kind"}:
                await self.close(code=1008)
                return
            await self.send_json(
                {"v": 1, "kind": "heartbeat" if d["kind"] == "heartbeat" else "sync.required"}
            )

    async def typing_hint(self, event):
        recipients = await typing_recipients(self.token, event["conversation_id"])
        if recipients is not None:
            await self.send_json(
                {
                    "v": 1,
                    "kind": event.get("kind", "ephemeral.typing"),
                    "conversation_id": event["conversation_id"],
                    "sender_device": event["sender_device"],
                    "expires_in": 50 if event.get("kind") == "ephemeral.presence" else 5,
                }
            )

    async def sync_hint(self, event):
        if not await session_user(self.token):
            await self.close(code=4401)
            return
        await self.send_json({"v": 1, "kind": "sync.required"})

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await asyncio.to_thread(websocket_lease, self.channel_name, True)
        if hasattr(self, "group"):
            try:
                await self.channel_layer.group_discard(self.group, self.channel_name)
            except Exception:
                pass
