"""Independent HTTPS client runtime and private browser-profile provisioning."""

import argparse
import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import uvicorn

from .gateway import Gateway, Upstream, https_origin


def profile_upstream(profile):
    """Operator transport overrides do not replace the logical TLS identity."""
    address = profile.get("upstream_address")
    port = profile.get("upstream_port")
    if address is not None and (
        not isinstance(address, str)
        or not address
        or len(address) > 253
        or any(character.isspace() or ord(character) < 32 for character in address)
    ):
        raise ValueError("Invalid upstream transport address")
    if port is not None and (type(port) is not int or not 1 <= port <= 65535):
        raise ValueError("Invalid upstream transport port")
    return Upstream(profile["api_origin"], profile.get("api_ca"), address, port)


def provision(state, origin, ca, port, upstream_address=None, upstream_port=None):
    config = state / "profile.json"
    if config.exists():
        raise ValueError(
            "Existing client profile preserved; use a distinct profile for another server"
        )
    origin = https_origin(origin)
    if not shutil.which("openssl") or not shutil.which("certutil"):
        raise ValueError(
            "OpenSSL and NSS certutil are required; no system trust changes are made"
        )
    profile_upstream(
        {
            "api_origin": origin,
            "api_ca": str(ca) if ca else None,
            "upstream_address": upstream_address,
            "upstream_port": upstream_port,
        }
    )
    if not 1024 <= port <= 65535:
        raise ValueError("Invalid local client port")
    tls = state / "tls"
    tls.mkdir(mode=0o700)

    def openssl(*args):
        subprocess.run(
            ["openssl", *args],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )

    openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:3072",
        "-nodes",
        "-days",
        "3650",
        "-keyout",
        str(tls / "root.key"),
        "-out",
        str(tls / "root.crt"),
        "-subj",
        "/CN=HAVEN LOCAL CLIENT ONLY",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
    )
    openssl(
        "req",
        "-new",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        str(tls / "leaf.key"),
        "-out",
        str(tls / "leaf.csr"),
        "-subj",
        "/CN=HAVEN LOCAL CLIENT ONLY",
    )
    (tls / "leaf.ext").write_text(
        "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:127.0.0.1\n"
    )
    openssl(
        "x509",
        "-req",
        "-in",
        str(tls / "leaf.csr"),
        "-CA",
        str(tls / "root.crt"),
        "-CAkey",
        str(tls / "root.key"),
        "-set_serial",
        str(int.from_bytes(os.urandom(16), "big")),
        "-days",
        "365",
        "-sha256",
        "-extfile",
        str(tls / "leaf.ext"),
        "-out",
        str(tls / "leaf.crt"),
    )
    if ca:
        if not Path(ca).is_file() or Path(ca).stat().st_size > 128 * 1024:
            raise ValueError("Invalid independently supplied API CA file")
        shutil.copyfile(ca, state / "api-ca.crt")
    browser = state / "browser"
    browser.mkdir(mode=0o700)
    subprocess.run(
        ["certutil", "-N", "-d", "sql:" + str(browser), "--empty-password"],
        check=True,
        capture_output=True,
        timeout=20,
    )
    subprocess.run(
        [
            "certutil",
            "-A",
            "-d",
            "sql:" + str(browser),
            "-n",
            "HAVEN LOCAL CLIENT ONLY",
            "-t",
            "C,,",
            "-i",
            str(tls / "root.crt"),
        ],
        check=True,
        capture_output=True,
        timeout=20,
    )
    config.write_text(
        json.dumps(
            {
                "api_origin": origin,
                "api_ca": str(state / "api-ca.crt") if ca else None,
                "port": port,
                "upstream_address": upstream_address,
                "upstream_port": upstream_port,
            }
        )
        + "\n"
    )
    config.chmod(0o600)
    print(
        "Private HTTPS client profile prepared. Only its dedicated Firefox profile trusts the local CA."
    )
    print("Client URL: https://127.0.0.1:" + str(port))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--trusted-key", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("configure")
    setup.add_argument("--api-origin", required=True)
    setup.add_argument("--api-ca", type=Path)
    setup.add_argument("--port", type=int, default=9443)
    setup.add_argument("--upstream-address")
    setup.add_argument("--upstream-port", type=int)
    serve = commands.add_parser("serve")
    serve.add_argument(
        "--open", action="store_true", help="Open the dedicated private Firefox profile"
    )
    serve.add_argument("--browser-binary")
    serve.add_argument("--api-origin")
    serve.add_argument("--api-ca")
    serve.add_argument("--upstream-address")
    serve.add_argument("--upstream-port", type=int)
    serve.add_argument("--listen", default="127.0.0.1")
    serve.add_argument("--port", type=int)
    serve.add_argument("--public-origin")
    serve.add_argument("--cert")
    serve.add_argument("--key")
    serve.add_argument("--minimum-sequence", type=int, default=1)
    options = parser.parse_args()
    os.umask(0o077)
    if options.command == "configure":
        if not options.state:
            parser.error("Installed state is required")
        provision(
            options.state,
            options.api_origin,
            options.api_ca,
            options.port,
            options.upstream_address,
            options.upstream_port,
        )
        return
    if options.state:
        profile = json.loads((options.state / "profile.json").read_text())
        if (
            any(
                [
                    options.api_origin,
                    options.api_ca,
                    options.public_origin,
                    options.cert,
                    options.key,
                    options.upstream_address,
                    options.upstream_port,
                    options.port,
                ]
            )
            or options.listen != "127.0.0.1"
        ):
            parser.error(
                "Installed endpoint and TLS identity are fixed by the independent profile"
            )
        upstream = profile_upstream(profile)
        port = profile["port"]
        origin = "https://127.0.0.1:" + str(port)
        cert = str(options.state / "tls/leaf.crt")
        key = str(options.state / "tls/leaf.key")
        mode = "installed"
    else:
        if not all(
            [
                options.api_origin,
                options.public_origin,
                options.cert,
                options.key,
                options.port,
            ]
        ):
            parser.error(
                "Independent delivery requires explicit API, public origin and TLS configuration"
            )
        port = options.port
        origin = https_origin(options.public_origin)
        cert = options.cert
        key = options.key
        mode = "independent-web"
        upstream = Upstream(
            options.api_origin,
            options.api_ca,
            options.upstream_address,
            options.upstream_port,
        )
    if options.open:
        if not options.state:
            parser.error("Private browser launch requires an installed profile")
        binary = options.browser_binary or shutil.which("firefox")
        if not binary:
            parser.error(
                "Install Firefox or supply --browser-binary; never bypass a TLS warning"
            )

        def open_browser():
            for _ in range(100):
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                return
            subprocess.Popen(
                [
                    binary,
                    "--no-remote",
                    "--profile",
                    str(options.state / "browser"),
                    origin,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    app = Gateway(
        options.bundle,
        options.trusted_key,
        origin,
        upstream,
        mode,
        options.minimum_sequence,
    )
    if options.open:
        threading.Thread(target=open_browser, daemon=True).start()
    logging.getLogger("uvicorn.error").addHandler(logging.NullHandler())
    print("Verified client release", app.manifest["sequence"], "on", origin, flush=True)
    uvicorn.run(
        app,
        host=options.listen,
        port=port,
        ssl_certfile=cert,
        ssl_keyfile=key,
        access_log=False,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {"null": {"class": "logging.NullHandler"}},
            "root": {"handlers": ["null"], "level": "WARNING"},
        },
        limit_concurrency=64,
        timeout_keep_alive=5,
        ws_max_size=2048,
        ws_max_queue=4,
        ws_per_message_deflate=False,
        proxy_headers=False,
        h11_max_incomplete_event_size=16384,
        server_header=False,
    )
