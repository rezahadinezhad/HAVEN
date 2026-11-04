"""Real TLS and malicious-origin regressions for the independent client boundary."""

import asyncio
import hashlib
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path

import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/verified-client/runtime"))
from haven_client.gateway import Gateway, Upstream
from haven_client.release import InvalidRelease, canonical, fingerprint, verify


def release(folder, sequence=1, files=None, key=None, name="release.haven"):
    files = files or {
        "bootstrap.py": b"# trusted launcher",
        "runtime.pyz": b"trusted runtime",
        "requirements.lock": b"locked",
        "web/index.html": b'<script src="/assets/client.js"></script>',
        "web/assets/client.js": b"window.trustedClient=true",
        "web/crypto-worker.js": b"// trusted crypto worker",
        "web/crypto/haven_crypto_bg.wasm": b"\0asm",
    }
    manifest = {
        "domain": "haven/verified-client-release/v1",
        "sequence": sequence,
        "source": "a" * 40,
        "files": {
            p: {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
            for p, b in files.items()
        },
    }
    (folder / "manifest").write_bytes(canonical(manifest))
    subprocess.run(
        [
            "openssl",
            "pkeyutl",
            "-sign",
            "-rawin",
            "-inkey",
            str(key or folder / "private.key"),
            "-in",
            str(folder / "manifest"),
            "-out",
            str(folder / "sig"),
        ],
        check=True,
        capture_output=True,
    )
    target = folder / name
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("manifest.json", canonical(manifest))
        archive.writestr("signature.ed25519", (folder / "sig").read_bytes())
        for p, b in files.items():
            archive.writestr(p, b)
    return target


class Releases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "ed25519",
                "-out",
                str(self.root / "private.key"),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "openssl",
                "pkey",
                "-in",
                str(self.root / "private.key"),
                "-pubout",
                "-out",
                str(self.root / "release.pub"),
            ],
            check=True,
            capture_output=True,
        )
        self.bundle = release(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_release_and_independent_key(self):
        manifest, digest, payload = verify(self.bundle, self.root / "release.pub")
        self.assertEqual(manifest["sequence"], 1)
        self.assertEqual(len(digest), 64)
        self.assertEqual(payload["web/crypto/haven_crypto_bg.wasm"], b"\0asm")
        self.assertEqual(len(fingerprint(self.root / "release.pub")), 64)
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "ed25519",
                "-out",
                str(self.root / "other.key"),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "openssl",
                "pkey",
                "-in",
                str(self.root / "other.key"),
                "-pubout",
                "-out",
                str(self.root / "other.pub"),
            ],
            check=True,
            capture_output=True,
        )
        with self.assertRaises(InvalidRelease):
            verify(self.bundle, self.root / "other.pub")

    def test_manifest_signature_and_unsupported_compression_are_rejected(self):
        altered = self.root / "manifest-altered.haven"
        with (
            zipfile.ZipFile(self.bundle) as original,
            zipfile.ZipFile(altered, "w") as output,
        ):
            for item in original.infolist():
                body = original.read(item)
                if item.filename == "manifest.json":
                    value = json.loads(body)
                    value["sequence"] = 999
                    body = canonical(value)
                output.writestr(item, body)
        with self.assertRaises(InvalidRelease):
            verify(altered, self.root / "release.pub")
        unsupported = self.root / "compressed.haven"
        with (
            zipfile.ZipFile(self.bundle) as original,
            zipfile.ZipFile(unsupported, "w", compression=zipfile.ZIP_LZMA) as output,
        ):
            for item in original.infolist():
                output.writestr(item.filename, original.read(item))
        with self.assertRaises(InvalidRelease):
            verify(unsupported, self.root / "release.pub")

    def test_changed_code_worker_and_wasm_are_rejected(self):
        for name in [
            "web/index.html",
            "web/assets/client.js",
            "web/crypto-worker.js",
            "web/crypto/haven_crypto_bg.wasm",
            "runtime.pyz",
            "bootstrap.py",
        ]:
            changed = self.root / "changed.haven"
            with (
                zipfile.ZipFile(self.bundle) as original,
                zipfile.ZipFile(changed, "w") as output,
            ):
                for entry in original.infolist():
                    output.writestr(
                        entry,
                        b"evil" if entry.filename == name else original.read(entry),
                    )
            with self.assertRaises(InvalidRelease):
                verify(changed, self.root / "release.pub")

    def test_rollback_conflict_and_unlisted_payload_are_rejected(self):
        _, digest, _ = verify(self.bundle, self.root / "release.pub")
        with self.assertRaises(InvalidRelease):
            verify(self.bundle, self.root / "release.pub", 2)
        with self.assertRaises(InvalidRelease):
            verify(self.bundle, self.root / "release.pub", 1, "b" * 64)
        self.assertEqual(
            verify(self.bundle, self.root / "release.pub", 1, digest)[1], digest
        )
        with zipfile.ZipFile(self.bundle, "a") as archive:
            archive.writestr("web/unlisted.js", b"evil")
        with self.assertRaises(InvalidRelease):
            verify(self.bundle, self.root / "release.pub")

    def test_signed_traversal_and_duplicate_archive_entries_are_rejected(self):
        bad = release(self.root, files={"../escape": b"evil"}, name="bad.haven")
        with self.assertRaises(InvalidRelease):
            verify(bad, self.root / "release.pub")
        with zipfile.ZipFile(self.bundle, "a") as archive:
            archive.writestr("runtime.pyz", b"evil")
        with self.assertRaises(InvalidRelease):
            verify(self.bundle, self.root / "release.pub")


class Fixture:
    def __init__(self):
        self.response = (200, "application/json", b'{"ok":true}', [])
        self.calls = []
        self.ws_origin = None

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                event = await receive()
                await send({"type": event["type"] + ".complete"})
                if event["type"] == "lifespan.shutdown":
                    return
        if scope["type"] == "websocket":
            self.ws_origin = dict(scope["headers"]).get(b"origin")
            await receive()
            await send({"type": "websocket.accept"})
            while True:
                event = await receive()
                if event["type"] == "websocket.disconnect":
                    return
                await send({"type": "websocket.send", "text": event.get("text", "")})
        self.calls.append((scope["path"], dict(scope["headers"])))
        while (await receive()).get("more_body"):
            pass
        status, media, body, headers = self.response
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", media.encode()), *headers],
            }
        )
        await send({"type": "http.response.body", "body": body})


class Server:
    def __init__(self, app, root):
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.port = self.socket.getsockname()[1]
        self.server = uvicorn.Server(
            uvicorn.Config(
                app,
                ssl_certfile=str(root / "tls.crt"),
                ssl_keyfile=str(root / "tls.key"),
                log_level="critical",
                access_log=False,
                ws_max_size=2048,
                ws_per_message_deflate=False,
            )
        )
        self.thread = threading.Thread(
            target=self.server.run, kwargs={"sockets": [self.socket]}, daemon=True
        )
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                break
            time.sleep(0.02)
        else:
            raise RuntimeError("TLS fixture did not start")

    def close(self):
        self.server.should_exit = True
        self.thread.join(5)


class MaliciousOrigin(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-keyout",
                str(cls.root / "tls.key"),
                "-out",
                str(cls.root / "tls.crt"),
                "-subj",
                "/CN=127.0.0.1",
                "-addext",
                "subjectAltName=IP:127.0.0.1",
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "ed25519",
                "-out",
                str(cls.root / "private.key"),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "openssl",
                "pkey",
                "-in",
                str(cls.root / "private.key"),
                "-pubout",
                "-out",
                str(cls.root / "release.pub"),
            ],
            check=True,
            capture_output=True,
        )
        cls.bundle = release(cls.root)
        cls.fixture = Fixture()
        cls.remote = Server(cls.fixture, cls.root)
        cls.api = "https://127.0.0.1:" + str(cls.remote.port)

    @classmethod
    def tearDownClass(cls):
        cls.remote.close()
        cls.temp.cleanup()

    def setUp(self):
        self.fixture.response = (200, "application/json", b'{"ok":true}', [])
        self.fixture.calls.clear()
        self.gateway = Gateway(
            self.bundle,
            self.root / "release.pub",
            "https://127.0.0.1:9443",
            Upstream(self.api, str(self.root / "tls.crt")),
        )

    async def call(self, path, method="GET", extra=(), app=None):
        events = []

        async def receive():
            return {"type": "http.request", "body": b"{}", "more_body": False}

        async def send(event):
            events.append(event)

        await (app or self.gateway)(
            {
                "type": "http",
                "method": method,
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [(b"host", b"127.0.0.1:9443"), *extra],
            },
            receive,
            send,
        )
        return events[0]["status"], dict(events[0]["headers"]), events[1]["body"]

    async def test_server_cannot_replace_html_worker_or_wasm(self):
        self.fixture.response = (200, "text/javascript", b"window.stolen=true", [])
        for path in [
            "/",
            "/crypto-worker.js",
            "/crypto/haven_crypto_bg.wasm",
            "/assets/client.js",
        ]:
            status, headers, body = await self.call(path)
            self.assertEqual(status, 200)
            self.assertNotIn(b"stolen", body)
            self.assertIn(b"nosniff", headers[b"x-content-type-options"])
        self.assertEqual(self.fixture.calls, [])

    async def test_html_javascript_redirects_and_compression_cannot_become_code(self):
        for response in [
            (200, "text/html", b"<script>evil()</script>", []),
            (200, "text/javascript", b"evil()", []),
            (302, "application/json", b"{}", [(b"location", b"https://evil.invalid/")]),
            (200, "application/json", b"{}", [(b"content-encoding", b"gzip")]),
        ]:
            self.fixture.response = response
            status, headers, body = await self.call("/api/v1/health")
            self.assertEqual(status, 502)
            self.assertEqual(headers[b"content-type"], b"application/json")
            self.assertNotIn(b"location", headers)
            self.assertNotIn(b"<script>", body)

    async def test_strict_api_origin_cookie_and_header_boundary(self):
        self.fixture.response = (
            200,
            "application/json",
            b'{"name":"<script>evil()</script>"}',
            [
                (b"content-security-policy", b"script-src * 'unsafe-eval'"),
                (b"set-cookie", b"evil=1"),
                (b"set-cookie", b"__Host-haven=abc; Domain=evil.invalid; Path=/bad"),
            ],
        )
        status, headers, _body = await self.call(
            "/api/v1/auth/me",
            extra=[(b"cookie", b"__Host-haven=local"), (b"x-forwarded-for", b"evil")],
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"application/json")
        self.assertIn(b"default-src 'none'", headers[b"content-security-policy"])
        self.assertIn(b"HttpOnly", headers[b"set-cookie"])
        self.assertIn(b"Path=/", headers[b"set-cookie"])
        self.assertNotIn(b"evil", headers[b"set-cookie"])
        self.assertEqual(self.fixture.calls[-1][1][b"origin"], self.api.encode())
        self.assertNotIn(b"x-forwarded-for", self.fixture.calls[-1][1])
        self.assertEqual(
            (
                await self.call(
                    "/api/v1/auth/me", extra=[(b"sec-fetch-site", b"same-site")]
                )
            )[0],
            403,
        )
        self.assertEqual(
            (
                await self.call(
                    "/api/v1/auth/me", "POST", [(b"origin", b"https://evil.invalid")]
                )
            )[0],
            403,
        )
        self.assertEqual((await self.call("/api/v1/../crypto-worker.js"))[0], 400)

    async def test_transport_address_does_not_disable_hostname_verification(self):
        bad = Gateway(
            self.bundle,
            self.root / "release.pub",
            "https://127.0.0.1:9443",
            Upstream(
                "https://127.0.0.2:" + str(self.remote.port),
                str(self.root / "tls.crt"),
                "127.0.0.1",
                self.remote.port,
            ),
        )
        self.assertEqual((await self.call("/api/v1/health", app=bad))[0], 502)

    async def test_websocket_bridge_preserves_data_and_exact_origin(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        app = Gateway(
            self.bundle,
            self.root / "release.pub",
            "https://127.0.0.1:" + str(port),
            Upstream(self.api, str(self.root / "tls.crt")),
        )
        server = ServerAtPort(app, self.root, port)
        try:
            import ssl

            context = ssl.create_default_context(cafile=str(self.root / "tls.crt"))
            async with connect(
                "wss://127.0.0.1:" + str(port) + "/ws/v1",
                ssl=context,
                origin="https://127.0.0.1:" + str(port),
            ) as ws:
                await ws.send('{"v":1,"kind":"resume"}')
                self.assertEqual(await ws.recv(), '{"v":1,"kind":"resume"}')
            self.assertEqual(self.fixture.ws_origin, self.api.encode())
            with self.assertRaises(InvalidStatus):
                async with connect(
                    "wss://127.0.0.1:" + str(port) + "/ws/v1",
                    ssl=context,
                    origin=self.api,
                ):
                    pass
        finally:
            await asyncio.to_thread(server.close)


class ServerAtPort(Server):
    def __init__(self, app, root, port):
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", port))
        self.port = port
        self.server = uvicorn.Server(
            uvicorn.Config(
                app,
                ssl_certfile=str(root / "tls.crt"),
                ssl_keyfile=str(root / "tls.key"),
                log_level="critical",
                access_log=False,
                ws_max_size=2048,
                ws_per_message_deflate=False,
            )
        )
        self.thread = threading.Thread(
            target=self.server.run, kwargs={"sockets": [self.socket]}, daemon=True
        )
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                break
            time.sleep(0.02)
        else:
            raise RuntimeError("Gateway fixture did not start")


if __name__ == "__main__":
    unittest.main()
