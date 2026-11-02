"""WebSocket ASGI events over asgiref's standard in-process test transport.

HAVEN runs Uvicorn. These tests need no Daphne/Twisted server or live-server
fixture. Authenticated socket tests use committed transactional fixtures;
real Channels connection cleanup stays enabled, including bounded DB workers.
"""

import json
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
