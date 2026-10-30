#!/usr/bin/env python3
"""Guided, isolated Docker setup. No production qualification or TLS bypass."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import signal
import shlex
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import time
from http.cookies import SimpleCookie

ROOT = Path(__file__).resolve().parent.parent
SLUG = re.compile(r"[a-z][a-z0-9-]{2,30}\Z")
USER = re.compile(r"[a-zA-Z0-9_.-]{3,64}\Z")
HOST = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\Z"
)


class SetupError(Exception):
    pass


def need(ok, message):
    if not ok:
        raise SetupError(message)


def safe_value(value):
    need(
        isinstance(value, str) and not any(c in value for c in '\r\n\x00$"\\#'),
        "Configuration contains an unsupported character",
    )
    return value


def secure_dir(path):
    need(not path.is_symlink(), "Refusing a symlink in installation storage")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    need(
        path.is_dir() and path.stat().st_uid == os.getuid(),
        "Installation directory must belong to you",
    )
    path.chmod(0o700)


def write_new(path, value, mode=0o600):
    fd = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode
    )
    with os.fdopen(fd, "w") as stream:
        stream.write(value)


def read_private(path):
    need(
        not path.is_symlink() and path.is_file(),
        "Protected file is missing or is a symlink",
    )
    info = path.stat()
    need(
        info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) & 0o077 == 0,
        "Protected installation files must belong to you and have mode 0600",
    )
    return path.read_text()


def save_state(directory, state):
    temp = directory / ("state-" + secrets.token_hex(8))
    write_new(temp, json.dumps(state, indent=2) + "\n")
    os.replace(temp, directory / "state.json")


def verify_manifest(root):
    manifest = root / "SOURCE_MANIFEST.sha256"
    need(
        manifest.is_file(), "Source manifest missing; use a complete reviewed checkout"
    )
    names = set()
    for line in manifest.read_text().splitlines():
        digest, separator, name = line.partition("  ")
        need(
            separator and re.fullmatch(r"[0-9a-f]{64}", digest),
            "Invalid source manifest",
        )
        relative = Path(name)
        need(
            not relative.is_absolute() and ".." not in relative.parts,
            "Unsafe manifest path",
        )
        need(name not in names, "Duplicate source manifest entry")
        names.add(name)
        path = root / relative
        need(
            path.is_file() and not path.is_symlink(),
            "A source artifact is missing or is a symlink",
        )
        need(
            hashlib.sha256(path.read_bytes()).hexdigest() == digest,
            f"Source integrity mismatch: {name}. Review changes before regenerating the source manifest.",
        )
    need(
        {
            "setup.sh",
            "scripts/setup.py",
            "infrastructure/compose/compose.yml",
            "apps/api/Dockerfile",
            "apps/web/Dockerfile",
        }
        <= names,
        "Source manifest does not cover the installer and deployment sources",
    )
    return hashlib.sha256(manifest.read_bytes()).hexdigest()


def validate_plan(value):
    need(isinstance(value, dict), "Setup answers must be an object")
    p = dict(value)
    need(p.get("mode") in ("local", "server"), "Choose local or server mode")
    need(
        isinstance(p.get("slug"), str) and SLUG.fullmatch(p["slug"]),
        "Installation name: 3–31 lowercase letters/digits/hyphens, starting with a letter",
    )
    need(
        isinstance(p.get("admin"), str) and USER.fullmatch(p["admin"]),
        "Administrator username: 3–64 letters, digits, dot, underscore or hyphen",
    )
    p["name"] = safe_value(p.get("name", "HAVEN"))
    need(1 <= len(p["name"]) <= 80, "Community name must have 1–80 characters")
    try:
        ip = str(ipaddress.IPv4Address(p.get("ip", "")))
    except (ValueError, TypeError):
        raise SetupError("A canonical literal IPv4 address is required") from None
    need(ip == p["ip"], "Use a canonical IPv4 address")
    minimum_port = 1024 if p["mode"] == "local" else 1
    need(
        type(p.get("port")) is int and minimum_port <= p["port"] <= 65535,
        "Invalid HTTPS port",
    )
    hostname = p.get("hostname", "")
    need(
        isinstance(hostname, str)
        and (not hostname or (len(hostname) <= 253 and HOST.fullmatch(hostname))),
        "Invalid optional exact hostname",
    )
    need(
        not hostname or not re.fullmatch(r"[0-9.]+", hostname),
        "Optional hostname must not be an IP address",
    )
    need(
        type(p.get("local_compatibility", False)) is bool,
        "Compatibility choice must be a boolean",
    )
    if p["mode"] == "local":
        need(
            ip == "127.0.0.1" and hostname in ("", "localhost"),
            "Local evaluation is restricted to 127.0.0.1 and optional localhost",
        )
        need(
            os.geteuid() != 0,
            "Run local evaluation as a regular user with Docker access, so the browser sandbox remains enabled",
        )
    else:
        need(
            not ipaddress.IPv4Address(ip).is_unspecified
            and not ipaddress.IPv4Address(ip).is_multicast,
            "A usable server IPv4 address is required",
        )
        need(
            not p.get("local_compatibility", False),
            "Server setup cannot disable container hardening",
        )
        for key in ("certificate", "private_key"):
            need(
                isinstance(p.get(key), str) and p[key],
                "Server mode requires an existing full-chain certificate and matching private key",
            )
    return p


def origin(host, port):
    return f"https://{host}" + (f":{port}" if port != 443 else "")


def render_env(plan, directory, generated):
    hosts = [plan["ip"]] + ([plan["hostname"]] if plan.get("hostname") else [])
    values = {
        "HAVEN_NAME": plan["name"],
        "HAVEN_HOSTS": ",".join(hosts),
        "HAVEN_ORIGINS": ",".join(origin(h, plan["port"]) for h in hosts),
        "HAVEN_OPTIONAL_HOSTNAME": plan.get("hostname", ""),
        "HAVEN_SECRET_KEY": generated["application"],
        "POSTGRES_PASSWORD": generated["database"],
        "HAVEN_DB_MIGRATION_PASSWORD": generated["migration"],
        "HAVEN_DB_RUNTIME_PASSWORD": generated["runtime"],
        "POSTGRES_DB": "haven",
        "POSTGRES_USER": "haven",
        "HAVEN_DB_MIGRATION_USER": "haven_migrate",
        "HAVEN_DB_RUNTIME_USER": "haven_app",
        "HAVEN_TLS_DIR": str(directory / "tls-bundle" / "tls"),
        "HAVEN_API_IMAGE": plan["api_image"],
        "HAVEN_WEB_IMAGE": plan["web_image"],
        "HAVEN_MAINTENANCE": "Experimental software. Independent review pending.",
    }
    return "".join(
        key + "=" + safe_value(value) + "\n" for key, value in values.items()
    )


def render_overlay(plan):
    bind = "127.0.0.1" if plan["mode"] == "local" else "0.0.0.0"
    output = (
        "services:\n  ingress:\n    ports: !override ["
        + json.dumps(f"{bind}:{plan['port']}:443")
        + "]\n"
    )
    if plan["mode"] == "local":
        for service in ("api", "outbox", "privacy"):
            output += f"  {service}:\n    environment:\n      DJANGO_SETTINGS_MODULE: haven.integration_settings\n"
        if plan.get("local_compatibility"):
            for service in ("redis", "prepare-db-roles", "migrate", "web"):
                output += f"  {service}:\n    security_opt: !override []\n"
            # Each service key occurs only once in this generated YAML.
            output = output.replace(
                "      DJANGO_SETTINGS_MODULE: haven.integration_settings\n",
                "      DJANGO_SETTINGS_MODULE: haven.integration_settings\n    security_opt: !override []\n",
            )
    return output


class Runner:
    def __init__(self, directory, secrets_to_hide=()):
        self.log = directory / "setup.log"
        self.secrets = list(secrets_to_hide)
        if not self.log.exists():
            write_new(self.log, "HAVEN guided setup\n")
        read_private(self.log)

    def run(self, command, *, input_text=None, timeout=1800, check=True):
        process = None
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                start_new_session=True,
            )
            deadline = time.monotonic() + timeout
            while True:
                try:
                    output, _ = process.communicate(
                        input_text,
                        timeout=min(45, max(0.01, deadline - time.monotonic())),
                    )
                    break
                except subprocess.TimeoutExpired:
                    input_text = None  # communicate already sent the protected input.
                    if time.monotonic() >= deadline:
                        raise
                    print(
                        f"    Still running {command[0]} {command[1] if len(command) > 1 else ''}…",
                        flush=True,
                    )
            result = subprocess.CompletedProcess(command, process.returncode, output)
        except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            if process and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
            if isinstance(exc, KeyboardInterrupt):
                raise
            raise SetupError(
                f"Could not finish {command[0]}; review the private setup log and resume"
            ) from exc
        output = result.stdout
        for secret in self.secrets:
            if secret:
                output = output.replace(secret, "[redacted]")
        with self.log.open("a") as stream:
            stream.write("\n$ " + shlex.join(command) + "\n" + output + "\n")
        if check and result.returncode:
            raise SetupError(
                f"Step failed: {command[0]}. Private details: {self.log}. State/data preserved; resume to retry."
            )
        return result


def compose(directory, plan):
    return [
        "docker",
        "compose",
        "--project-name",
        "haven-" + plan["slug"],
        "--env-file",
        str(directory / "config.env"),
        "-f",
        str(ROOT / "infrastructure/compose/compose.yml"),
        "-f",
        str(directory / "compose.yml"),
    ]


def validate_tls(plan, directory, runner, roots=None, *, minimum_seconds=172800):
    tls = directory / "tls"
    certificate, key = tls / "leaf.crt", tls / "leaf.key"
    read_private(key)
    text = runner.run(
        ["openssl", "x509", "-in", str(certificate), "-noout", "-text"]
    ).stdout
    need("CA:FALSE" in text, "The HTTPS leaf must not be a CA certificate")
    runner.run(
        [
            "openssl",
            "x509",
            "-in",
            str(certificate),
            "-noout",
            "-checkend",
            str(minimum_seconds),
        ]
    )
    cert_pub = runner.run(
        ["openssl", "x509", "-in", str(certificate), "-pubkey", "-noout"]
    ).stdout.strip()
    key_pub = runner.run(
        ["openssl", "pkey", "-in", str(key), "-passin", "pass:", "-pubout"]
    ).stdout.strip()
    need(cert_pub == key_pub, "TLS certificate and private key do not match")
    command = [
        "openssl",
        "verify",
        "-purpose",
        "sslserver",
        "-untrusted",
        str(certificate),
    ]
    if roots:
        command += ["-CAfile", str(roots)]
    runner.run(command + ["-verify_ip", plan["ip"], str(certificate)])
    if plan.get("hostname"):
        need("DNS:" in text, "Optional hostname requires a DNS SAN")
        runner.run(command + ["-verify_hostname", plan["hostname"], str(certificate)])
    need(
        not any((tls / n).exists() for n in ("root.key", "intermediate.key")),
        "CA signing keys must not enter the server TLS mount",
    )


def prepare_tls(plan, directory, runner):
    bundle = directory / "tls-bundle"
    if bundle.exists():
        need(not bundle.is_symlink(), "Refusing a symlink in TLS storage")
        roots = bundle / (
            "issuer/root.crt" if plan["mode"] == "local" else "trust-roots.pem"
        )
        roots = roots if roots.exists() else None
        validate_tls(plan, bundle, runner, roots)
        return str(roots) if roots else ""
    staging = Path(tempfile.mkdtemp(prefix=".tls-preparing-", dir=directory))
    try:
        roots = create_tls(plan, staging, runner)
        relative_roots = Path(roots).relative_to(staging) if roots else None
        staging.rename(bundle)  # Publish the certificate, chain and roots together.
        return str(bundle / relative_roots) if relative_roots else ""
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def create_tls(plan, directory, runner):
    tls = directory / "tls"
    secure_dir(tls)
    roots = None
    if plan["mode"] == "local":
        issuer = directory / "issuer"
        secure_dir(issuer)
        roots = issuer / "root.crt"
        runner.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:3072",
                "-nodes",
                "-keyout",
                str(issuer / "root.key"),
                "-out",
                str(roots),
                "-days",
                "7",
                "-sha256",
                "-subj",
                "/CN=HAVEN ISOLATED TEST ROOT",
                "-addext",
                "basicConstraints=critical,CA:TRUE,pathlen:0",
                "-addext",
                "keyUsage=critical,keyCertSign,cRLSign",
            ]
        )
        runner.run(
            [
                "openssl",
                "req",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(tls / "leaf.key"),
                "-out",
                str(issuer / "leaf.csr"),
                "-subj",
                "/CN=HAVEN LOCAL EVALUATION",
            ]
        )
        extension = "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:127.0.0.1"
        if plan.get("hostname"):
            extension += ",DNS:localhost"
        write_new(issuer / "extensions", extension + "\n")
        runner.run(
            [
                "openssl",
                "x509",
                "-req",
                "-in",
                str(issuer / "leaf.csr"),
                "-CA",
                str(roots),
                "-CAkey",
                str(issuer / "root.key"),
                "-CAcreateserial",
                "-out",
                str(tls / "leaf.crt"),
                "-days",
                "3",
                "-sha256",
                "-extfile",
                str(issuer / "extensions"),
            ]
        )
    else:
        cert_source, key_source = (
            Path(plan["certificate"]).expanduser().resolve(),
            Path(plan["private_key"]).expanduser().resolve(),
        )
        read_private(key_source)
        certificate = cert_source.read_text()
        need(
            "PRIVATE KEY" not in certificate,
            "Certificate chain must not contain private keys",
        )
        write_new(tls / "leaf.crt", certificate)
        write_new(tls / "leaf.key", key_source.read_text())
        if plan.get("roots"):
            roots_source = Path(plan["roots"]).expanduser().resolve()
            content = roots_source.read_text()
            need(
                "PRIVATE KEY" not in content,
                "Trust bundle must contain public certificates only",
            )
            roots = directory / "trust-roots.pem"
            write_new(roots, content)
    (tls / "leaf.key").chmod(0o600)
    (tls / "leaf.crt").chmod(0o644)  # Public leaf is also read by the unprivileged API.
    validate_tls(plan, directory, runner, roots)
    return str(roots) if roots else ""


def preflight(runner):
    for command in ("docker", "openssl"):
        need(shutil.which(command), f"Install {command} before running HAVEN setup")
    version = (
        runner.run(["docker", "compose", "version", "--short"])
        .stdout.strip()
        .lstrip("v")
    )
    parts = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    need(
        parts and tuple(map(int, parts.groups())) >= (2, 24, 4),
        "Docker Compose 2.24.4 or newer is required",
    )
    platform = runner.run(
        ["docker", "info", "--format", "{{.OSType}}/{{.Architecture}}"], timeout=30
    ).stdout.strip()
    need(
        platform in ("linux/x86_64", "linux/amd64"),
        "Prepared native artifacts require a Linux x86_64 Docker engine",
    )


def check_namespace(plan, runner):
    project = "haven-" + plan["slug"]
    found = runner.run(
        [
            "docker",
            "ps",
            "-aq",
            "--filter",
            "label=com.docker.compose.project=" + project,
        ]
    ).stdout.strip()
    volumes = runner.run(
        ["docker", "volume", "ls", "-q", "--filter", "name=^" + project + "_db$"]
    ).stdout.strip()
    networks = runner.run(
        [
            "docker",
            "network",
            "ls",
            "-q",
            "--filter",
            "label=com.docker.compose.project=" + project,
        ]
    ).stdout.strip()
    need(
        not found and not volumes and not networks,
        "An unowned Docker project/volume/network already uses this name. Choose a different installation name",
    )


def check_port(plan, directory, runner, *, resume):
    try:
        with socket.socket() as probe:
            probe.bind(
                ("127.0.0.1" if plan["mode"] == "local" else "0.0.0.0", plan["port"])
            )
    except OSError:
        if resume and (directory / "compose.yml").is_file():
            ingress = runner.run(
                compose(directory, plan) + ["ps", "-q", "ingress"]
            ).stdout.strip()
            if ingress:
                ports = json.loads(
                    runner.run(
                        [
                            "docker",
                            "inspect",
                            "--format",
                            "{{json .NetworkSettings.Ports}}",
                            ingress,
                        ]
                    ).stdout
                )
                expected = "127.0.0.1" if plan["mode"] == "local" else "0.0.0.0"
                if any(
                    p["HostPort"] == str(plan["port"]) and p["HostIp"] == expected
                    for p in (ports or {}).get("443/tcp", []) or []
                ):
                    return
        raise SetupError(
            "HTTPS port is unavailable. Choose an unused port; existing services were not stopped"
        ) from None


class LoopbackTLS(http.client.HTTPSConnection):
    def connect(self):
        # Reach the local ingress while validating its actual configured identity.
        # This does not establish external/public reachability on a NATed host.
        raw = socket.create_connection(("127.0.0.1", self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def verify_service(plan, roots, credentials):
    context = ssl.create_default_context(cafile=roots or None)
    cookies = SimpleCookie()
    base = origin(plan["ip"], plan["port"])

    def request(path, body=None, csrf=None):
        connection = LoopbackTLS(plan["ip"], plan["port"], context=context, timeout=10)
        headers = {"Host": base.removeprefix("https://"), "Origin": base}
        if cookies:
            headers["Cookie"] = "; ".join(
                f"{name}={item.value}" for name, item in cookies.items()
            )
        if body is not None:
            headers["Content-Type"] = "application/json"
        if csrf:
            headers["X-CSRFToken"] = csrf
        try:
            connection.request(
                "POST" if body is not None else "GET",
                path,
                body=json.dumps(body) if body is not None else None,
                headers=headers,
            )
            response = connection.getresponse()
            for key, value in response.getheaders():
                if key.lower() == "set-cookie":
                    cookies.load(value)
            value = response.read(2_000_000)
            need(
                response.status == 200,
                f"Verified HTTPS probe rejected ({response.status}); check the protected log and saved administrator credentials",
            )
            return value, dict((k.lower(), v) for k, v in response.getheaders())
        finally:
            connection.close()

    last = None
    for _ in range(30):
        try:
            raw, _ = request("/api/v1/health")
            health = json.loads(raw)
            need(
                health.get("crypto_ready") is (plan["mode"] == "local")
                and health.get("release_status") == "BLOCKED",
                "Unexpected security gate state; setup cannot qualify a release",
            )
            break
        except (OSError, http.client.HTTPException) as exc:
            last = exc
            time.sleep(1)
    else:
        raise SetupError(
            "HTTPS did not become ready; state preserved for resume"
        ) from last
    _, headers = request("/")
    policy = headers.get("content-security-policy", "")
    need(
        "default-src 'self'" in policy
        and "'unsafe-inline'" not in policy
        and "'unsafe-eval'" not in policy,
        "Expected strict browser CSP is missing",
    )
    raw, _ = request("/api/v1/auth/csrf")
    csrf = json.loads(raw)["csrf"]
    raw, _ = request("/api/v1/auth/login", credentials, csrf)
    need(
        json.loads(raw)["user"]["role"] == "superadmin",
        "Saved account is not the installation administrator",
    )
    request(
        "/api/v1/auth/logout", {}, json.loads(request("/api/v1/auth/csrf")[0])["csrf"]
    )


def browser_profile(plan, directory, runner):
    if plan["mode"] != "local" or not shutil.which("certutil"):
        return None
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        return None
    home = directory / "browser-home"
    secure_dir(home)
    for relative in (".pki/nssdb", ".local/share/pki/nssdb"):
        profile = home / relative
        secure_dir(profile)
        if not (profile / "cert9.db").exists():
            runner.run(
                ["certutil", "-N", "-d", "sql:" + str(profile), "--empty-password"]
            )
        runner.run(
            [
                "certutil",
                "-D",
                "-d",
                "sql:" + str(profile),
                "-n",
                "HAVEN SETUP TEST ONLY",
            ],
            check=False,
        )
        runner.run(
            [
                "certutil",
                "-A",
                "-d",
                "sql:" + str(profile),
                "-n",
                "HAVEN SETUP TEST ONLY",
                "-t",
                "C,,",
                "-i",
                plan["roots"],
            ]
        )
    launcher = directory / "open-browser.sh"
    url = origin(plan.get("hostname") or plan["ip"], plan["port"])
    content = (
        "#!/bin/sh\nexport HOME="
        + shlex.quote(str(home))
        + "\nexec "
        + shlex.join(
            [
                chrome,
                "--user-data-dir=" + str(directory / "browser-profile"),
                "--no-first-run",
                "--no-default-browser-check",
                url,
            ]
        )
        + "\n"
    )
    if not launcher.exists():
        write_new(launcher, content, 0o700)
    return launcher


def ask(label, default=None):
    value = input(
        label + (f" [{default}]" if default is not None else "") + ": "
    ).strip()
    return value or default


def questionnaire():
    print(
        "\nHAVEN · Guided setup\nLocal evaluation uses a private test CA. Server mode keeps production messaging gated.\n"
    )
    mode = ask("Mode: 1 local evaluation, 2 gated server", "1")
    need(mode in ("1", "2"), "Choose 1 or 2")
    local = mode == "1"
    p = {
        "mode": "local" if local else "server",
        "slug": ask("Installation name", "my-haven"),
        "name": ask("Community name", "HAVEN"),
        "admin": ask("Administrator username", "owner"),
        "ip": "127.0.0.1"
        if local
        else ask("Server IPv4 address (must match the certificate SAN)"),
    }
    try:
        p["port"] = int(ask("HTTPS port", "8447" if local else "443"))
    except (ValueError, TypeError):
        raise SetupError("Enter a numeric port") from None
    p["hostname"] = (
        "localhost" if local else ask("Optional exact hostname (blank for IP only)", "")
    )
    if not local:
        p["certificate"] = ask("Path to existing TLS full-chain PEM certificate")
        p["private_key"] = ask("Path to matching unencrypted private key (mode 0600)")
        p["roots"] = ask(
            "Independently verified public CA bundle path (blank for system trust)", ""
        )
    return validate_plan(p)


def install(plan, *, resume=False, interactive=True):
    parent = ROOT / ".local" / "setup"
    secure_dir(parent)
    directory = parent / plan["slug"]
    safe_value(str(directory))
    secure_dir(directory)
    state_file = directory / "state.json"
    lock = directory / "setup.lock"
    import fcntl

    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SetupError("Another setup process owns this installation") from None
        source_hash = verify_manifest(ROOT)
        print("[1/6] Checking Docker, architecture and source integrity…", flush=True)
        if resume:
            state = json.loads(read_private(state_file))
            plan = validate_plan(state["plan"])
            need(
                plan["slug"] == directory.name and state["source_hash"] == source_hash,
                "Resume requires the same reviewed source and original installation name; use the documented upgrade procedure for changed releases",
            )
            need(
                state.get("namespace_checked") is True,
                "Installation namespace ownership was not established; choose a new installation name",
            )
            read_private(directory / "config.env")
            credentials = json.loads(read_private(directory / "admin-credentials.json"))
        else:
            need(
                not state_file.exists() and not (directory / "config.env").exists(),
                "Installation already exists. Use --resume NAME; secrets/data will not be overwritten",
            )
            runner = Runner(directory)
            preflight(runner)
            check_namespace(plan, runner)
            check_port(plan, directory, runner, resume=False)
            suffix = source_hash[:12]
            plan.update(
                api_image=f"haven-{plan['slug']}-api:{suffix}",
                web_image=f"haven-{plan['slug']}-web:{suffix}",
            )
            generated = {
                key: secrets.token_urlsafe(48)
                for key in ("application", "database", "migration", "runtime")
            }
            credentials = {
                "username": plan["admin"],
                "password": secrets.token_urlsafe(32),
            }
            write_new(directory / "config.env", render_env(plan, directory, generated))
            write_new(
                directory / "admin-credentials.json",
                json.dumps(credentials, indent=2) + "\n",
            )
            state = {
                "version": 1,
                "source_hash": source_hash,
                "plan": plan,
                "namespace_checked": True,
                "tls_ready": False,
                "complete": False,
            }
            save_state(directory, state)
        runner = Runner(
            directory,
            [credentials["password"]]
            + [
                line.partition("=")[2]
                for line in read_private(directory / "config.env").splitlines()
                if "PASSWORD=" in line or line.startswith("HAVEN_SECRET_KEY=")
            ],
        )
        if resume:
            preflight(runner)
            check_port(plan, directory, runner, resume=True)
        base = compose(directory, plan)
        print("[2/6] Preparing verified TLS and protected configuration…", flush=True)
        if not state["tls_ready"]:
            plan["roots"] = prepare_tls(plan, directory, runner)
            state["plan"] = plan
            state["tls_ready"] = True
            save_state(directory, state)
        else:
            validate_tls(
                plan, directory / "tls-bundle", runner, plan.get("roots") or None
            )
        overlay = directory / "compose.yml"
        overlay.write_text(render_overlay(plan))
        overlay.chmod(0o600)
        runner.run(base + ["config", "--quiet"])
        print(
            f"[3/6] Building API/web images from this checkout. Private progress log: {runner.log}",
            flush=True,
        )
        for service in ("api", "web"):
            runner.run(
                [
                    "docker",
                    "build",
                    "-f",
                    f"apps/{service}/Dockerfile",
                    "-t",
                    plan[service + "_image"],
                    ".",
                ]
            )
        probe = runner.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--entrypoint",
                "python",
                plan["api_image"],
                "-c",
                "print('hardening available')",
            ],
            check=False,
        )
        if probe.returncode and not plan.get("local_compatibility"):
            if plan["mode"] == "local" and interactive:
                print(
                    "Hardened containers could not start on this Docker host. The test-only compatibility mode removes no-new-privileges and remains loopback-only."
                )
                plan["local_compatibility"] = (
                    ask(
                        "Use that reduced-hardening local evaluation profile? y/N", "n"
                    ).lower()
                    == "y"
                )
            need(
                plan["mode"] == "local" and plan.get("local_compatibility"),
                "Container hardening check failed. Server hardening will not be weakened; use a qualified host",
            )
        if plan.get("local_compatibility"):
            overlay.write_text(render_overlay(plan))
            overlay.chmod(0o600)
            state["plan"] = plan
            save_state(directory, state)
        images = runner.run(base + ["config", "--images"]).stdout.splitlines()
        for image in sorted(set(images) - {plan["api_image"], plan["web_image"]}):
            need(
                re.search(r"@sha256:[a-f0-9]{64}$", image),
                "Infrastructure image is not digest-pinned",
            )
            if runner.run(
                ["docker", "image", "inspect", image], check=False
            ).returncode:
                runner.run(["docker", "pull", image])
        print(
            "[4/6] Starting private database/cache and preparing least-privilege roles…",
            flush=True,
        )
        runner.run(base + ["up", "-d", "--wait", "--pull", "never", "db", "redis"])
        runner.run(base + ["run", "--rm", "--no-deps", "prepare-db-roles"])
        print(
            "[5/6] Applying durability-checked migrations and bootstrapping the administrator…",
            flush=True,
        )
        runner.run(base + ["run", "--rm", "--no-deps", "migrate"])
        runner.run(
            base
            + [
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "api",
                "python",
                "manage.py",
                "bootstrap_admin",
                "--username",
                plan["admin"],
            ],
            input_text=credentials["password"] + "\n",
        )
        runner.run(
            base
            + [
                "up",
                "-d",
                "--wait",
                "--pull",
                "never",
                "api",
                "web",
                "outbox",
                "privacy",
                "ingress",
            ]
        )
        print(
            "[6/6] Verifying HTTPS identity, browser policy, security gate and administrator login…",
            flush=True,
        )
        verify_service(plan, plan.get("roots"), credentials)
        launcher = browser_profile(plan, directory, runner)
        management = directory / "manage.sh"
        if not management.exists():
            write_new(
                management, "#!/bin/sh\nexec " + shlex.join(base) + ' "$@"\n', 0o700
            )
        state["complete"] = True
        save_state(directory, state)
        print("\nHAVEN is installed and its local HTTPS/login checks passed.")
        print("Address: " + origin(plan.get("hostname") or plan["ip"], plan["port"]))
        print("Administrator: " + plan["admin"])
        print(
            "Password is saved only in the protected file: "
            + str(directory / "admin-credentials.json")
        )
        if launcher:
            print(
                "Open the isolated trusted test browser: " + shlex.quote(str(launcher))
            )
        elif plan["mode"] == "local":
            print(
                "Install Chrome and NSS certutil, then resume to prepare a private test profile. Never bypass a certificate warning."
            )
        print("Manage this stack: " + shlex.quote(str(management)) + " ps  (or stop)")
        print("Resume: ./setup.sh --resume " + plan["slug"])
        print(
            "Browser message keys are created on the device at first unlock, never by this installer."
        )
        print(
            "Release remains BLOCKED for independent review and external qualification."
        )
        if plan["mode"] == "server":
            print(
                "Server messaging is gated. Local checks do not establish public reachability or client certificate trust."
            )
        return directory
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group()
    options.add_argument(
        "--resume",
        metavar="NAME",
        help="Resume this installation without replacing secrets or data",
    )
    options.add_argument(
        "--answers",
        type=Path,
        help="Protected JSON answers for reproducible local automation; no password arguments",
    )
    args = parser.parse_args()
    need(sys.version_info >= (3, 10), "Python 3.10 or newer is required")
    if args.resume:
        need(SLUG.fullmatch(args.resume), "Invalid installation name")
        plan = {"slug": args.resume}
    elif args.answers:
        plan = validate_plan(json.loads(read_private(args.answers)))
    else:
        need(
            sys.stdin.isatty(),
            "Run interactively, or supply a protected --answers JSON file",
        )
        plan = questionnaire()
    install(plan, resume=bool(args.resume), interactive=sys.stdin.isatty())


if __name__ == "__main__":
    try:
        main()
    except (SetupError, OSError, ValueError, KeyError, KeyboardInterrupt) as error:
        # Never dump request bodies, credentials or environment values on failure.
        print(
            "\nSetup stopped: "
            + (
                str(error)
                if isinstance(error, SetupError)
                else "Check your protected inputs and setup log; existing state/data were preserved."
            ),
            file=sys.stderr,
        )
        sys.exit(1)
