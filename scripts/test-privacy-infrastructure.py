#!/usr/bin/env python3
"""Exercise real pinned Nginx with trusted test TLS and an isolated loopback echo backend."""

import http.server
import json
import secrets
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "nginx:1.28.3-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236"
PRIVATE_HEADERS = ["X-Real-IP", "X-Forwarded-For", "Forwarded", "X-Client-IP", "True-Client-IP", "CF-Connecting-IP", "X-Forwarded-Host"]


class Echo(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        body = json.dumps({k.lower(): v for k, v in self.headers.items()}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_POST = do_GET

    def log_message(self, *args):
        pass


def run(*args):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(result.stdout)
    return result.stdout


def main():
    echo = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Echo)
    threading.Thread(target=echo.serve_forever, daemon=True).start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    name = "haven-privacy-proxy-" + secrets.token_hex(6)
    marker = "sensitive-" + secrets.token_hex(12)
    try:
        with tempfile.TemporaryDirectory(prefix="privacy-proxy-", dir=ROOT / ".local") as directory:
            config = (ROOT / "infrastructure/nginx/nginx.conf").read_text()
            config = config.replace("listen 443 ssl;", f"listen 127.0.0.1:{port} ssl;")
            for upstream in ["api:8100", "web:3100"]:
                config = config.replace(upstream, f"127.0.0.1:{echo.server_port}")
            target = Path(directory) / "nginx.conf"
            target.write_text(config)
            run("docker", "run", "-d", "--name", name, "--network", "host", "--read-only",
                "--tmpfs", "/var/cache/nginx", "--tmpfs", "/var/run", "--tmpfs", "/tmp",
                "-v", f"{target}:/etc/nginx/nginx.conf:ro", "-v", f"{ROOT / '.local/tls'}:/etc/haven/tls:ro", IMAGE)
            context = ssl.create_default_context(cafile=str(ROOT / ".local/tls/root.crt"))
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
            base = f"https://127.0.0.1:{port}"
            for _ in range(100):
                try:
                    opener.open(base + "/api/health", timeout=1).close()
                    break
                except (OSError, urllib.error.URLError):
                    time.sleep(.1)
            else:
                raise RuntimeError("Test proxy did not become ready")
            for route in ["/api/v1/test", "/ws/v1", "/"]:
                headers = dict.fromkeys(PRIVATE_HEADERS, marker)
                headers.update({"Cookie": "__Host-haven=" + marker, "Origin": base,
                                "Content-Type": "application/json", "X-CSRFToken": marker,
                                "X-Haven-View-Token": marker})
                req = urllib.request.Request(base + route, data=json.dumps({"test": marker}).encode(), headers=headers)
                with opener.open(req, timeout=5) as response:
                    received = json.load(response)
                    assert response.headers["Referrer-Policy"] == "no-referrer"
                assert not any(key.lower() in received for key in PRIVATE_HEADERS), received.keys()
                assert received["cookie"] == headers["Cookie"]
                assert received["x-csrftoken"] == marker and received["x-haven-view-token"] == marker
                assert received["origin"] == base and received["x-forwarded-proto"] == "https"
            # Login is the sole exception: replace spoofed forwarding data with
            # the observed transport peer, without storing it in logs/metrics.
            req = urllib.request.Request(base + "/api/v1/auth/login", data=b"{}", headers=dict.fromkeys(PRIVATE_HEADERS, marker))
            with opener.open(req, timeout=5) as response:
                received = json.load(response)
            assert received.get("x-forwarded-for") == "127.0.0.1"
            assert all(key.lower() not in received for key in PRIVATE_HEADERS if key != "X-Forwarded-For")
            assert marker not in run("docker", "logs", name)
            print("PASS: real pinned Nginx, verified IP TLS, API/WS/web strip client address headers; login alone overwrites source for throttling, preserve auth/CSRF/media capability, no request markers in logs")
    finally:
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        echo.shutdown()


if __name__ == "__main__":
    main()
