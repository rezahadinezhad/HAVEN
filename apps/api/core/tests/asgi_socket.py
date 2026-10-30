"""WebSocket ASGI events over asgiref's standard in-process test transport.

HAVEN runs Uvicorn. These tests need no Daphne/Twisted server or live-server
fixture. Keep Django test connections alive across async event dispatch, as
Channels' test helpers do; production connection handling is unchanged.
"""

import json
from unittest.mock import patch
from asgiref.testing import ApplicationCommunicator


class WebsocketProbe(ApplicationCommunicator):
    def __init__(self, application, path, headers=None):
        super().__init__(
            application,
            {
                "type": "websocket",
                "path": path,
                "query_string": b"",
                "headers": headers or [],
                "subprotocols": [],
            },
        )

    async def send_input(self, message):
        with patch("channels.db.close_old_connections"):
            await super().send_input(message)

    async def receive_output(self, timeout=1):
        with patch("channels.db.close_old_connections"):
            return await super().receive_output(timeout)

    async def connect(self):
        await self.send_input({"type": "websocket.connect"})
        event = await self.receive_output()
        if event["type"] == "websocket.close":
            return False, event.get("code", 1000)
        assert event["type"] == "websocket.accept", event
        return True, event.get("subprotocol")

    async def send_to(self, *, text_data):
        assert isinstance(text_data, str)
        await self.send_input({"type": "websocket.receive", "text": text_data})

    async def send_json_to(self, payload):
        await self.send_to(text_data=json.dumps(payload))

    async def receive_json_from(self):
        event = await self.receive_output()
        assert event["type"] == "websocket.send" and isinstance(event.get("text"), str), event
        assert "bytes" not in event
        return json.loads(event["text"])

    async def disconnect(self):
        await self.send_input({"type": "websocket.disconnect", "code": 1000})
        await self.wait()
