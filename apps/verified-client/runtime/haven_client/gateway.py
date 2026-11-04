"""Serve verified executable assets; remote responses can only become bounded API data."""

import asyncio
import http.client
import ipaddress
import json
import logging
import mimetypes
import re
import socket
import ssl
from http.cookies import CookieError, SimpleCookie
from types import MappingProxyType
from urllib.parse import urlsplit

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from .release import verify

MAX_BODY = 1500000
MAX_RESPONSE = 32 * 1024 * 1024
CSP = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; connect-src 'self'; worker-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
DATA_CSP = "default-src 'none'; sandbox; frame-ancestors 'none'"
ALLOWED_REQUEST_HEADERS = {
    "cookie",
    "content-type",
    "x-csrftoken",
    "x-haven-contact",
    "x-haven-view-token",
    "if-none-match",
}
BINARY = re.compile(r"^/api/v1/attachments/[0-9a-f-]{36}/chunks/[0-9]+$")


def https_origin(value):
    u = urlsplit(value)
    try:
        ipaddress.IPv4Address(u.hostname)
        port = u.port
    except (ValueError, TypeError):
        raise ValueError("Use an exact HTTPS IPv4 origin") from None
    if (
        u.scheme != "https"
        or u.username
        or u.password
        or u.path not in ("", "/")
        or u.query
        or u.fragment
        or port == 0
        or str(ipaddress.IPv4Address(u.hostname)) != u.hostname
    ):
        raise ValueError("Use an exact HTTPS IPv4 origin")
    return u.scheme + "://" + u.netloc


def normalized_cookies(headers):
    result = []
    for name, value in headers:
        if name.lower() != "set-cookie":
            continue
        cookie = SimpleCookie()
        try:
            cookie.load(value)
        except CookieError:
            # Invalid remote cookies are discarded without logging secret values.
            continue
        for key, m in cookie.items():
            if key not in {"__Host-haven", "__Host-haven-csrf"} or not re.fullmatch(
                r"[A-Za-z0-9_-]{0,256}", m.value
            ):
                continue
            # Upstream domain/path/security policies never control this origin.
            output = SimpleCookie()
            output[key] = m.value
            output[key]["path"] = "/"
            output[key]["secure"] = True
            output[key]["httponly"] = True
            output[key]["samesite"] = "Strict"
            if m["max-age"]:
                try:
                    age = int(m["max-age"])
                except ValueError:
                    continue
                output[key]["max-age"] = str(max(0, min(age, 2592000)))
            result.append((b"set-cookie", output[key].OutputString().encode("ascii")))
    return result


class Upstream:
    def __init__(self, origin, ca_file=None, address=None, port=None):
        self.origin = https_origin(origin)
        self.url = urlsplit(self.origin)
        self.context = ssl.create_default_context(cafile=ca_file)
        self.address = address or self.url.hostname
        self.port = port or self.url.port or 443
        self.logger = logging.getLogger("haven.client.websocket")
        self.logger.addHandler(logging.NullHandler())
        self.logger.propagate = False

    def request(self, method, target, headers, body):
        connection = http.client.HTTPSConnection(
            self.url.hostname, self.url.port or 443, context=self.context, timeout=20
        )

        # A separately configured transport address may be container DNS. TLS
        # identity remains the pinned logical API hostname, with normal validation.
        def dial():
            raw = socket.create_connection((self.address, self.port), timeout=20)
            try:
                connection.sock = self.context.wrap_socket(
                    raw, server_hostname=self.url.hostname
                )
            except BaseException:
                raw.close()
                raise

        connection.connect = dial
        clean = {k: v for k, v in headers.items() if k in ALLOWED_REQUEST_HEADERS}
        clean.update(
            {
                "Host": self.url.netloc,
                "Origin": self.origin,
                "Accept-Encoding": "identity",
                "Connection": "close",
            }
        )
        try:
            connection.request(method, target, body=body, headers=clean)
            response = connection.getresponse()
            media = response.getheader("Content-Type", "").split(";")[0].strip().lower()
            if (
                response.status in (301, 302, 303, 307, 308)
                or response.getheader("Content-Encoding", "identity").lower()
                != "identity"
            ):
                raise ValueError("Upstream redirects and encoded responses are refused")
            if not (
                media == "application/json"
                or (
                    media == "application/octet-stream"
                    and BINARY.fullmatch(urlsplit(target).path)
                )
                or response.status in (204, 304)
            ):
                raise ValueError("Upstream executable/document response refused")
            data = response.read(MAX_RESPONSE + 1)
            if len(data) > MAX_RESPONSE:
                raise ValueError("Upstream response exceeded client budget")
            extra = normalized_cookies(response.getheaders())
            for key in ("Retry-After", "X-Haven-Next-Cursor"):
                value = response.getheader(key)
                if (
                    value
                    and len(value) < 512
                    and re.fullmatch(r"[A-Za-z0-9_:.+/=-]+", value)
                ):
                    extra.append((key.lower().encode(), value.encode("ascii")))
            return response.status, media or "application/json", data, extra
        finally:
            connection.close()


class Gateway:
    def __init__(
        self, bundle, trusted_key, origin, upstream, mode="installed", minimum=1
    ):
        self.manifest, self.digest, payload = verify(bundle, trusted_key, minimum)
        self.assets = MappingProxyType(
            {"/" + k[4:]: v for k, v in payload.items() if k.startswith("web/")}
        )
        self.origin = https_origin(origin)
        self.upstream = upstream
        self.mode = mode
        self.public_config = {
            "v": 1,
            "mode": mode,
            "service_origin": upstream.origin,
            "sequence": self.manifest["sequence"],
            "digest": self.digest,
        }
        self.http_slots = asyncio.Semaphore(4)
        self.ws_slots = asyncio.Semaphore(16)

    def headers(self, scope):
        headers = {}
        for key, value in scope.get("headers", []):
            k = key.decode("ascii").lower()
            v = value.decode("latin1")
            if k in headers and k not in {"cookie"}:
                raise ValueError("Duplicate request header")
            headers[k] = (headers[k] + "; " + v) if k in headers else v
        if headers.get("host") != urlsplit(self.origin).netloc:
            raise ValueError("Client Host rejected")
        return headers

    async def response(
        self, send, status, body, media="application/json", extra=(), document=False
    ):
        headers = [
            (b"content-type", media.encode()),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"),
            (b"x-content-type-options", b"nosniff"),
            (b"content-security-policy", (CSP if document else DATA_CSP).encode()),
            (b"referrer-policy", b"no-referrer"),
            (b"x-frame-options", b"DENY"),
            (b"cross-origin-opener-policy", b"same-origin"),
            (b"cross-origin-resource-policy", b"same-origin"),
            (b"permissions-policy", b"camera=(), microphone=(self), geolocation=()"),
            *extra,
        ]
        await send(
            {"type": "http.response.start", "status": status, "headers": headers}
        )
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                event = await receive()
                await send({"type": event["type"] + ".complete"})
                if event["type"] == "lifespan.shutdown":
                    return
        try:
            headers = self.headers(scope)
        except (ValueError, UnicodeError):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            else:
                await self.response(send, 403, b'{"error":"client_origin_rejected"}')
            return
        if scope["type"] == "websocket":
            return await self.websocket(scope, headers, receive, send)
        if scope["type"] != "http":
            return
        path = scope["path"]
        method = scope["method"]
        if path.startswith("/api/v1/"):
            if (
                method not in {"GET", "POST", "PUT", "DELETE", "HEAD"}
                or headers.get("origin", self.origin) != self.origin
                or headers.get("sec-fetch-site", "same-origin") != "same-origin"
            ):
                return await self.response(
                    send, 403, b'{"error":"client_origin_rejected"}'
                )
            raw = scope.get("raw_path", path.encode()).decode("ascii", "strict")
            query = scope.get("query_string", b"").decode("ascii", "strict")
            if (
                len(raw) + len(query) > 4096
                or any(x in raw.lower() for x in ("%2f", "%5c", "%2e", "..", "\\"))
                or re.search(r"[\x00-\x20\x7f]", raw + query)
            ):
                return await self.response(
                    send, 400, b'{"error":"client_path_rejected"}'
                )
            body = bytearray()
            try:
                while True:
                    event = await asyncio.wait_for(receive(), 20)
                    if event["type"] == "http.disconnect":
                        return
                    body.extend(event.get("body", b""))
                    if len(body) > MAX_BODY:
                        return await self.response(
                            send, 413, b'{"error":"client_request_too_large"}'
                        )
                    if not event.get("more_body"):
                        break
                async with self.http_slots:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.upstream.request,
                            method,
                            raw + ("?" + query if query else ""),
                            headers,
                            bytes(body),
                        ),
                        45,
                    )
                status, media, data, extra = result
                return await self.response(send, status, data, media, extra)
            except (OSError, ValueError, http.client.HTTPException, TimeoutError):
                return await self.response(
                    send, 502, b'{"error":"messaging_server_unavailable_or_invalid"}'
                )
        if method not in {"GET", "HEAD"}:
            return await self.response(send, 405, b'{"error":"method_rejected"}')
        if path == "/client-config.json":
            return await self.response(
                send, 200, json.dumps(self.public_config).encode()
            )
        prefix = "/releases/" + self.digest
        asset = path[len(prefix) :] if path.startswith(prefix + "/") else path
        asset = "/index.html" if asset == "/" else asset
        if asset not in self.assets:
            return await self.response(send, 404, b'{"error":"not_found"}')
        media = mimetypes.guess_type(asset)[0] or "application/octet-stream"
        if asset.endswith(".js"):
            media = "text/javascript"
        if asset.endswith(".wasm"):
            media = "application/wasm"
        data = self.assets[asset] if method != "HEAD" else b""
        if asset == "/index.html":
            data = data.replace(b'"/assets/', ('"' + prefix + "/assets/").encode())
        # Worker scripts need their own executable CSP; API data never gets it.
        return await self.response(
            send,
            200,
            data,
            media,
            extra=[(b"service-worker-allowed", b"/")] if asset == "/sw.js" else (),
            document=True,
        )

    async def websocket(self, scope, headers, receive, send):
        if (
            scope["path"] != "/ws/v1"
            or headers.get("origin") != self.origin
            or scope.get("query_string")
        ):
            await send({"type": "websocket.close", "code": 1008})
            return
        if (await receive())["type"] != "websocket.connect":
            return
        try:
            async with (
                self.ws_slots,
                connect(
                    self.upstream.origin.replace("https:", "wss:") + "/ws/v1",
                    ssl=self.upstream.context,
                    host=self.upstream.address,
                    port=self.upstream.port,
                    server_hostname=self.upstream.url.hostname,
                    origin=self.upstream.origin,
                    additional_headers={"Cookie": headers.get("cookie", "")},
                    compression=None,
                    max_size=2048,
                    max_queue=4,
                    open_timeout=15,
                    logger=self.upstream.logger,
                ) as remote,
            ):
                await send({"type": "websocket.accept"})

                async def outgoing():
                    while True:
                        event = await receive()
                        if event["type"] == "websocket.disconnect":
                            return
                        text = event.get("text")
                        if not isinstance(text, str) or len(text.encode()) > 2048:
                            raise ValueError("Invalid client hint")
                        await remote.send(text)

                async def incoming():
                    async for text in remote:
                        if not isinstance(text, str) or len(text.encode()) > 2048:
                            raise ValueError("Invalid server hint")
                        await send({"type": "websocket.send", "text": text})

                tasks = [
                    asyncio.create_task(outgoing()),
                    asyncio.create_task(incoming()),
                ]
                try:
                    _, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                finally:
                    for task in tasks:
                        task.cancel()
                await send({"type": "websocket.close", "code": 1000})
        except (WebSocketException, OSError, ValueError, RuntimeError):
            try:
                await send({"type": "websocket.close", "code": 1011})
            except RuntimeError:
                pass
