#!/usr/bin/env python3
# ruff: noqa: E402
"""Synthetic native MLS/HTTP/WSS workload. Private pipes/checkpoints, aggregate output.

Run through benchmark-metadata-isolated.py, never against an existing deployment.
Native client exercises real MLS; it is not the browser vault or physical phones.
"""

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from contextlib import ExitStack
from datetime import timedelta
import hashlib
from http.client import HTTPSConnection, HTTPException
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import threading
import time
import uuid

from metadata_load_instruments import CryptoPool, Timings, WaitSampler, process_usage

import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import websockets

ROOT = Path(__file__).resolve().parent.parent
if os.environ.get("HAVEN_ISOLATED_LOAD") != "synthetic-only":
    raise SystemExit("Use the isolated orchestrator")
sys.path.insert(0, os.environ["HAVEN_LOAD_API"])
os.environ["DJANGO_SETTINGS_MODULE"] = "haven.integration_settings"
import django

django.setup()
from django.conf import settings
from django.db import connection
from django.utils import timezone
from core import models as m
from core.middleware import digest

if str(settings.DATABASES["default"]["PORT"]) != "55434" or settings.ORIGINS != [
    "https://127.0.0.1:8454"
]:
    raise SystemExit("Isolated ports required")
ORIGIN = settings.ORIGINS[0]
PRIVATE = Path(os.environ["HAVEN_LOAD_PRIVATE"])
if PRIVATE.stat().st_mode & 0o077:
    raise SystemExit("Private directory required")
SSL = ssl.create_default_context(cafile=str(ROOT / ".local/tls/root.crt"))
timings = Timings()
crypto = CryptoPool(
    ROOT / "packages/crypto-core/target/release/examples/protocol_client",
    int(os.environ.get("HAVEN_LOAD_CRYPTO_WORKERS", "10")),
    timings,
)
checkpoint_key = AESGCM.generate_key(bit_length=256)
# Synthetic recovery custody, outside the DB and never published. This is a
# protected test fixture key, not a claim about browser/passphrase key custody.
key_fd = os.open(
    PRIVATE / "checkpoint.key", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
)
with os.fdopen(key_fd, "wb") as key_file:
    key_file.write(checkpoint_key)
    key_file.flush()
    os.fsync(key_file.fileno())
metrics_lock = threading.Lock()
metrics = {
    "http_requests": 0,
    "retry_429": 0,
    "accepted": 0,
    "delivered": 0,
    "updates": 0,
    "ws_connected": 0,
    "ws_peak": 0,
    "ws_errors": 0,
    "heartbeats": 0,
}
send_latencies, delivery_latencies = [], []
stop = threading.Event()
measuring = threading.Event()
reconnect_latencies = []
RESILIENCE = os.environ.get("HAVEN_LOAD_RECONNECT") == "1"


def native(client, op, **kw):
    value = crypto.exchange(
        client.shard, {"client": client.id, "command": {"op": op, **kw}}
    )
    client.state = value["state"]
    return value["result"]


def b64(value):
    return base64.b64encode(value).decode()


def fingerprint(value):
    return hashlib.sha256(value).hexdigest()


def chain(header, signature):
    return fingerprint(rfc8785.dumps({"header": header, "signature": signature}))


class Client:
    def __init__(self, user, n):
        self.user, self.id, self.state = user, str(uuid.uuid4()), ""
        self.identity = f"{user.pk}:{self.id}"
        # Two accounts form one ten-device group; keep that group on one worker.
        self.shard = (n // 2) % len(crypto.workers)
        self.ip = f"127.0.2.{n + 1}"
        self.token = secrets.token_urlsafe(48)
        self.cookies = {settings.SESSION_COOKIE_NAME: self.token}
        self.http_lock = threading.Lock()
        self.csrf = ""
        self.contact_grants = {}
        self.http = HTTPSConnection(
            "127.0.0.1", 8454, context=SSL, timeout=30, source_address=(self.ip, 0)
        )
        self.public_key = native(self, "init", identity=self.identity)["public_key"]
        self.device = m.Device.objects.create(
            id=self.id,
            user=user,
            identity=self.identity,
            public_key=base64.b64decode(self.public_key),
            label="Synthetic load device",
            trust_state="approved",
            challenge=secrets.token_hex(32),
            expires_at=timezone.now() + timedelta(hours=12),
        )
        m.Session.objects.create(
            user=user,
            device=self.device,
            token_hash=digest(self.token),
            expires_at=timezone.now() + timedelta(hours=12),
        )

    def certificate(self, role):
        return {
            "id": self.id,
            "user_id": str(self.user.pk),
            "identity": self.identity,
            "public_key": self.public_key,
            "role": role,
        }

    def request(self, path, method="GET", body=None, expected=(200,), raw=False):
        started = time.monotonic()
        with self.http_lock:
            acquired = time.monotonic()
            timings.record("http_client_lock_wait", acquired - started)
            try:
                return self._request(path, method, body, expected, raw)
            finally:
                timings.record("http_request_total", time.monotonic() - acquired)

    def _request(self, path, method, body, expected, raw):
        payload = (
            body
            if raw
            else (
                json.dumps(body, separators=(",", ":")).encode()
                if body is not None
                else None
            )
        )
        for attempt in range(6):
            headers = {
                "Origin": ORIGIN,
                "Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items()),
            }
            if method != "GET":
                headers.update(
                    {
                        "X-CSRFToken": self.csrf,
                        "Content-Type": "application/octet-stream"
                        if raw
                        else "application/json",
                    }
                )
            if path in self.contact_grants:
                headers["X-Haven-Contact"] = self.contact_grants[path]
            attempt_started = time.monotonic()
            try:
                self.http.request(method, "/api/v1/" + path, payload, headers)
                response = self.http.getresponse()
                data = response.read()
            except (OSError, HTTPException):
                self.http.close()
                if attempt == 5:
                    raise RuntimeError("Transport retry exhausted") from None
                with metrics_lock:
                    metrics["transport_retries"] = (
                        metrics.get("transport_retries", 0) + 1
                    )
                timings.record(
                    "http_failed_transport_attempt", time.monotonic() - attempt_started
                )
                continue  # The exact pending request is durable and idempotent.
            timings.record(
                "http_successful_transport_attempt", time.monotonic() - attempt_started
            )
            for name, value in response.getheaders():
                if name.lower() == "set-cookie":
                    cookie = SimpleCookie()
                    cookie.load(value)
                    self.cookies.update({k: v.value for k, v in cookie.items()})
            with metrics_lock:
                metrics["http_requests"] += 1
            if response.status == 429 and attempt < 5:
                with metrics_lock:
                    metrics["retry_429"] += 1
                time.sleep(min(int(response.getheader("Retry-After", "1")), 5))
                continue  # Same exact body and MLS ciphertext, no re-encryption.
            if response.status not in expected:
                raise RuntimeError(
                    f"HTTP {response.status} on {method} {path.split('/')[0]}"
                )
            return data if raw else json.loads(data)
        raise RuntimeError("Request retry exhausted")

    def sign(self, header):
        return native(self, "sign", payload=b64(rfc8785.dumps(header)))["signature"]

    def checkpoint(self, group, seq, head, pending=None):
        # Atomic encrypted durable state before ACK/send. No plaintext ratchets on disk.
        started = time.monotonic()
        clear = json.dumps(
            {"state": self.state, "seq": seq, "head": head, "pending": pending}
        ).encode()
        nonce = secrets.token_bytes(12)
        aad = f"haven-load-checkpoint/v1:{self.id}:{group}".encode()
        sealed = nonce + AESGCM(checkpoint_key).encrypt(nonce, clear, aad)
        encrypted_at = time.monotonic()
        timings.record("checkpoint_encode_encrypt", encrypted_at - started)
        temp, target = PRIVATE / (self.id + ".tmp"), PRIVATE / (self.id + ".checkpoint")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(sealed)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, target)
        directory = os.open(PRIVATE, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        timings.record(
            "checkpoint_write_fsync_replace", time.monotonic() - encrypted_at
        )


class Group:
    def __init__(self, clients, kind="group"):
        self.clients, self.owner = clients, clients[0]
        self.recipient_pool = None
        self.id, self.gid = str(uuid.uuid4()), uuid.uuid4().hex
        self.epoch, self.seq, self.messages = 0, 0, 0
        self.state_hash = native(self.owner, "create", group_id=self.gid)["state_hash"]
        self.roster = [self.owner.certificate("owner")]
        genesis = {
            "domain": "haven/genesis/v1",
            "id": self.id,
            "kind": kind,
            "group_id": self.gid,
            "members": self.roster,
        }
        signature = self.owner.sign(genesis)
        self.head = chain(genesis, signature)
        self.owner.request(
            "conversations",
            "POST",
            {
                "id": self.id,
                "kind": kind,
                "group_id": self.gid,
                "header": genesis,
                "signature": signature,
            },
            expected=(201,),
        )
        joined = [self.owner]
        for member_index, client in enumerate(clients[1:]):
            if member_index and member_index % 25 == 0:
                # Fixture preparation respects existing per-owner claim/control
                # limits. This is outside the measurement handshake and does
                # not change or retry away workload-time rate-limit failures.
                time.sleep(61)
            kp = native(client, "package")["key_package"]
            client.request(
                "crypto/key-packages", "POST", {"package": kp}, expected=(201,)
            )
            claim_path = "crypto/key-packages/" + client.id
            if hasattr(m.Device, "introduction_generation"):
                self.owner.contact_grants[claim_path] = client.request(
                    "devices/contact-introduction", "POST", {}
                )["token"]
            claim = self.owner.request(claim_path, "POST", {})
            result = native(
                self.owner, "add", group_id=self.gid, key_package=claim["package"]
            )
            self.state_hash = result["state_hash"]
            self.roster = sorted(
                self.roster + [client.certificate("member")], key=lambda x: x["id"]
            )
            transition = {
                "action": "add",
                "device_id": client.id,
                "next_epoch": self.epoch + 1,
                "members": self.roster,
                "welcome_hash": fingerprint(base64.b64decode(result["welcome"])),
                "state_hash": result["state_hash"],
            }
            body = self.envelope(result["commit"], transition)
            body.update(
                action="add",
                device_id=client.id,
                key_package_id=claim["id"],
                welcome=result["welcome"],
            )
            self.accept(body, "crypto-events")
            for recipient in joined[1:]:
                processed = native(
                    recipient, "process", group_id=self.gid, ciphertext=result["commit"]
                )
                self.check_roster(processed, self.epoch + 1)
            processed = native(
                client, "join", group_id=self.gid, welcome=result["welcome"]
            )
            self.check_roster(processed, self.epoch + 1)
            joined.append(client)
            self.epoch += 1
        for client in clients:
            client.checkpoint(self.id, self.seq, self.head)
            client.request(f"conversations/{self.id}/acks", "POST", {"seq": self.seq})

    def check_roster(self, result, epoch=None):
        actual = sorted((x["identity"], x["public_key"]) for x in result["members"])
        expected = sorted((x["identity"], x["public_key"]) for x in self.roster)
        if (
            actual != expected
            or result["state_hash"] != self.state_hash
            or result["epoch"] != (self.epoch if epoch is None else epoch)
        ):
            raise RuntimeError("MLS credential/roster/epoch confirmation mismatch")

    def envelope(self, ciphertext, transition=None, mid=None):
        mid = mid or str(uuid.uuid4())
        header = {
            "domain": "haven/envelope/v1",
            "v": 1,
            "conversation_id": self.id,
            "group_id": self.gid,
            "sender_device": self.owner.id,
            "client_message_id": mid,
            "epoch": self.epoch,
            "seq": self.seq + 1,
            "previous_hash": self.head,
            "ciphertext_hash": fingerprint(base64.b64decode(ciphertext)),
            "transition": transition,
        }
        return {
            "v": 1,
            "client_message_id": mid,
            "epoch": self.epoch,
            "ciphertext": ciphertext,
            "header": header,
            "signature": self.owner.sign(header),
        }

    def accept(self, body, endpoint):
        self.owner.checkpoint(self.id, self.seq, self.head, body)
        result = self.owner.request(
            f"conversations/{self.id}/{endpoint}", "POST", body, expected=(200, 201)
        )
        env = result["envelope"]
        expected_head = chain(body["header"], body["signature"])
        if (
            result["seq"] != self.seq + 1
            or env["chain_hash"] != expected_head
            or env["header"] != body["header"]
        ):
            raise RuntimeError("Accepted chain mismatch")
        self.seq += 1
        self.head = expected_head
        self.owner.checkpoint(self.id, self.seq, self.head)
        self.owner.request(f"conversations/{self.id}/acks", "POST", {"seq": self.seq})

    def deliver(self, body, plaintext=None):
        started = time.monotonic()
        previous, seq = body["header"]["previous_hash"], self.seq

        def deliver_recipient(recipient):
            page = recipient.request(
                f"conversations/{self.id}/messages?after_seq={seq - 1}"
            )
            if len(page["messages"]) != 1:
                raise RuntimeError("Fetch sequence mismatch")
            env = page["messages"][0]
            header = env["header"]
            if (
                header != body["header"]
                or header["previous_hash"] != previous
                or env["chain_hash"] != self.head
            ):
                raise RuntimeError("Recipient chain mismatch")
            wire = base64.b64decode(env["ciphertext"])
            if fingerprint(wire) != header["ciphertext_hash"]:
                raise RuntimeError("Ciphertext hash mismatch")
            Ed25519PublicKey.from_public_bytes(
                base64.b64decode(self.owner.public_key)
            ).verify(base64.b64decode(env["signature"]), rfc8785.dumps(header))
            processed = native(
                recipient, "process", group_id=self.gid, ciphertext=env["ciphertext"]
            )
            transition = body["header"]["transition"]
            self.check_roster(
                processed, transition["next_epoch"] if transition else self.epoch
            )
            if processed["sender"] != self.owner.identity:
                raise RuntimeError("MLS sender mismatch")
            if plaintext is not None and processed["plaintext"] != plaintext:
                raise RuntimeError("Plaintext mismatch")
            recipient.checkpoint(self.id, seq, self.head)
            recipient.request(f"conversations/{self.id}/acks", "POST", {"seq": seq})
            if plaintext is not None:
                with metrics_lock:
                    metrics["delivered"] += 1

        if self.recipient_pool is None:
            for recipient in self.clients[1:]:
                deliver_recipient(recipient)
        else:
            # Independent clients receive concurrently. Keep the group lane
            # blocked until every recipient durably checkpoints and ACKs, so
            # each client's MLS state and the group's next event stay ordered.
            futures = [
                self.recipient_pool.submit(deliver_recipient, client)
                for client in self.clients[1:]
            ]
            for future in futures:
                future.result(timeout=120)
        timings.record("nine_recipient_delivery_total", time.monotonic() - started)

    def send(self, scheduled, submitted):
        timings.record("executor_queue_wait", time.monotonic() - submitted)
        actual_start = time.monotonic()
        if (
            self.messages
            and self.messages % int(os.environ.get("HAVEN_LOAD_REKEY_EVERY", "100"))
            == 0
        ):
            updated = native(self.owner, "update", group_id=self.gid)
            self.state_hash = updated["state_hash"]
            transition = {
                "action": "update",
                "device_id": None,
                "next_epoch": self.epoch + 1,
                "members": self.roster,
                "welcome_hash": fingerprint(b""),
                "state_hash": updated["state_hash"],
            }
            body = self.envelope(updated["commit"], transition)
            body["action"] = "update"
            self.accept(body, "crypto-events")
            self.deliver(body)
            self.epoch += 1
            with metrics_lock:
                metrics["updates"] += 1
        mid = str(uuid.uuid4())
        plain = json.dumps(
            {
                "id": mid,
                "conversation_id": self.id,
                "sender": self.owner.id,
                "time": timezone.now().isoformat(),
                "type": "text",
                "text": "Synthetic load " + "x" * 128,
            },
            separators=(",", ":"),
        )
        encrypted = native(self.owner, "encrypt", group_id=self.gid, plaintext=plain)
        body = self.envelope(encrypted["ciphertext"], mid=mid)
        self.accept(body, "messages")
        accepted = time.monotonic()
        timings.record("message_start_to_accept", accepted - actual_start)
        with metrics_lock:
            metrics["accepted"] += 1
            send_latencies.append((accepted - scheduled) * 1000)
        self.deliver(body, plain)
        with metrics_lock:
            delivery_latencies.append((time.monotonic() - scheduled) * 1000)
        self.messages += 1


async def sockets(clients, ready):
    semaphore = asyncio.Semaphore(20)

    async def one(client):
        attempts, reconnect_started = 0, None
        while not stop.is_set():
            connected, recoverable = False, False
            try:
                async with semaphore:
                    ws = await websockets.connect(
                        ORIGIN.replace("https:", "wss:") + "/ws/v1",
                        ssl=SSL,
                        origin=ORIGIN,
                        additional_headers={
                            "Cookie": f"{settings.SESSION_COOKIE_NAME}={client.token}"
                        },
                        local_addr=(client.ip, 0),
                        proxy=None,
                        ping_interval=None,
                        open_timeout=30,
                    )
                    hello = json.loads(await asyncio.wait_for(ws.recv(), 30))
                    if hello.get("kind") != "hello":
                        raise RuntimeError("WSS hello rejected")
                    with metrics_lock:
                        metrics["ws_connected"] += 1
                        connected = True
                        metrics["ws_peak"] = max(
                            metrics["ws_peak"], metrics["ws_connected"]
                        )
                        if reconnect_started is not None:
                            metrics["ws_reconnects"] = (
                                metrics.get("ws_reconnects", 0) + 1
                            )
                            reconnect_latencies.append(
                                (time.monotonic() - reconnect_started) * 1000
                            )
                async with ws:
                    next_heartbeat = 0
                    while not stop.is_set():
                        if time.monotonic() >= next_heartbeat:
                            await ws.send(json.dumps({"v": 1, "kind": "heartbeat"}))
                            next_heartbeat = time.monotonic() + 20
                        try:
                            reply = json.loads(await asyncio.wait_for(ws.recv(), 1))
                        except TimeoutError:
                            continue
                        kind = reply.get("kind")
                        if kind not in ("heartbeat", "sync.required"):
                            raise RuntimeError("WSS frame mismatch")
                        with metrics_lock:
                            key = (
                                "heartbeats"
                                if kind == "heartbeat"
                                else "notification_hints"
                            )
                            metrics[key] = metrics.get(key, 0) + 1
                        if metrics["ws_connected"] == len(clients):
                            ready.set()
            except Exception as exc:
                if stop.is_set():
                    break
                received = getattr(exc, "rcvd", None)
                code = getattr(received, "code", None)
                reason = getattr(received, "reason", "")
                # Only known static transport reasons enter aggregate evidence.
                category = (
                    "keepalive_timeout"
                    if reason == "keepalive ping timeout"
                    else "other_or_unspecified"
                )
                label = (
                    type(exc).__name__ + (f":{code}" if code else "") + ":" + category
                )
                established = metrics["ws_peak"] == len(clients)
                recoverable = (
                    RESILIENCE
                    and established
                    and attempts < 3
                    and code in (None, 1001, 1006, 1011, 1012, 1013)
                    and not isinstance(exc, ssl.SSLError)
                    and getattr(getattr(exc, "response", None), "status_code", None)
                    not in (401, 403)
                )
                with metrics_lock:
                    metrics["ws_errors"] += 1
                    errors = metrics.setdefault("ws_error_classes", {})
                    errors[label] = errors.get(label, 0) + 1
                    if not recoverable:
                        metrics["ws_unrecoverable"] = (
                            metrics.get("ws_unrecoverable", 0) + 1
                        )
                ready.set()
                reconnect_started = time.monotonic()
            finally:
                if connected:
                    with metrics_lock:
                        metrics["ws_connected"] -= 1
                        if measuring.is_set() and not stop.is_set():
                            metrics["ws_min_connected"] = min(
                                metrics.get("ws_min_connected", len(clients)),
                                metrics["ws_connected"],
                            )
            if not recoverable:
                break
            attempts += 1
            await asyncio.sleep(min(2**attempts, 5))

    await asyncio.gather(*(one(client) for client in clients))


def media_fixture(command):
    result = subprocess.run(
        ["node", str(ROOT / "scripts/metadata-load-media.mjs")],
        input=json.dumps(command),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise RuntimeError("Synthetic attachment crypto failed")
    return json.loads(result.stdout)


def transfer_file(group, barrier, uploader=None, recipient=None):
    uploader = uploader or group.clients[1]
    recipient = recipient or group.clients[min(5, len(group.clients) - 1)]
    aid = str(uuid.uuid4())
    encrypted = media_fixture({"op": "encrypt", "cid": group.id, "id": aid})
    barrier.wait(timeout=60)
    started = time.monotonic()
    uploader.request(
        "attachments/init",
        "POST",
        {
            "id": aid,
            "conversation_id": group.id,
            "ciphertext_size": 1024 * 1024 + 32,
            "chunk_count": 2,
            "view_once": False,
        },
        expected=(201,),
    )
    for i, chunk in enumerate(encrypted["chunks"]):
        uploader.request(
            f"attachments/{aid}/chunks/{i}", "PUT", base64.b64decode(chunk), raw=True
        )
    uploader.request(f"attachments/{aid}/complete", "POST", {})
    chunks = [
        b64(recipient.request(f"attachments/{aid}/chunks/{i}", raw=True))
        for i in range(2)
    ]
    decrypted = media_fixture(
        {**encrypted, "chunks": chunks, "op": "decrypt", "cid": group.id, "id": aid}
    )
    if decrypted["sha256"] != fingerprint(b"Z" * (1024 * 1024)):
        raise RuntimeError("Synthetic attachment roundtrip mismatch")
    return (time.monotonic() - started) * 1000


def stats():
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_stat_clear_snapshot()")
        output = {}
        for name, query in {
            "wal": "SELECT row_to_json(x) FROM (SELECT wal_records,wal_fpi,wal_bytes,wal_buffers_full,wal_write,wal_sync,wal_write_time,wal_sync_time FROM pg_stat_wal) x",
            "io": "SELECT json_agg(x) FROM (SELECT backend_type,object,context,reads,read_time,writes,write_time,writebacks,writeback_time,extends,extend_time,op_bytes,hits,evictions,fsyncs,fsync_time FROM pg_stat_io) x",
            "db": "SELECT row_to_json(x) FROM (SELECT xact_commit,xact_rollback,blks_read,blks_hit,tup_returned,tup_fetched,tup_inserted,tup_updated,tup_deleted,deadlocks,temp_bytes FROM pg_stat_database WHERE datname=current_database()) x",
        }.items():
            cursor.execute(query)
            output[name] = cursor.fetchone()[0]
        cursor.execute("SELECT pg_database_size(current_database())")
        output["database_bytes"] = cursor.fetchone()[0]
        cursor.execute("SELECT pg_current_wal_lsn()::text")
        output["wal_lsn"] = cursor.fetchone()[0]
        cursor.execute(
            "SELECT name,setting FROM pg_settings WHERE name IN ('fsync','synchronous_commit','full_page_writes','data_checksums','track_io_timing','track_wal_io_timing','max_connections')"
        )
        output["settings"] = dict(cursor.fetchall())
    return output


def summarize(samples):
    ordered = sorted(samples)
    if not ordered:
        return {"samples": 0}
    return {
        "samples": len(ordered),
        "median_ms": ordered[len(ordered) // 2],
        "p95_ms": ordered[max(0, int(len(ordered) * 0.95) - 1)],
        "max_ms": ordered[-1],
    }


def run_legacy():
    try:
        clients, groups = [], []
        # Provision only synthetic approved fixtures. Enrollment/login costs are not measured.
        password = (
            m.User.objects.make_random_password()
            if hasattr(m.User.objects, "make_random_password")
            else secrets.token_urlsafe(32)
        )
        from django.contrib.auth.hashers import make_password

        encoded = make_password(password)
        for n in range(100):
            user = m.User.objects.create(
                username="load_" + uuid.uuid4().hex,
                display_name="Synthetic load",
                password=encoded,
                device_bootstrapped=True,
            )
            devices = [Client(user, n) for _ in range(5)]
            for device in devices[1:]:
                signature = native(
                    devices[0],
                    "sign",
                    payload=b64(
                        f"haven/enrollment/v1:{user.pk}:{device.id}:{device.public_key}:{device.device.challenge}".encode()
                    ),
                )["signature"]
                m.Device.objects.filter(pk=device.id).update(
                    approved_by=devices[0].device,
                    approval_signature=base64.b64decode(signature),
                )
            clients.extend(devices)
        for client in clients:
            client.csrf = client.request("auth/csrf")["csrf"]
        for n in range(0, len(clients), 10):
            groups.append(Group(clients[n : n + 10]))
            (PRIVATE / "fixture-progress.json").write_text(
                json.dumps({"groups": len(groups), "target": 50})
            )
        ready = threading.Event()
        ws_thread = threading.Thread(
            target=lambda: asyncio.run(sockets(clients, ready)), daemon=True
        )
        ws_thread.start()
        if not ready.wait(90) or metrics["ws_peak"] != 500 or metrics["ws_errors"]:
            raise RuntimeError("500 authenticated WSS sessions were not established")
        print("READY", flush=True)
        if sys.stdin.readline().strip() != "GO":
            raise RuntimeError("Measurement handshake rejected")
        with metrics_lock:
            metrics.update(
                http_requests=0,
                retry_429=0,
                accepted=0,
                delivered=0,
                updates=0,
                heartbeats=0,
                transport_retries=0,
                notification_hints=0,
            )
        before = stats()
        crypto_before = crypto.usage()
        driver_before = process_usage(os.getpid())
        sampler = WaitSampler(settings.DATABASES["default"])
        sampler.start()
        timings.reset()
        measuring.set()
        start = time.monotonic()
        duration = int(os.environ.get("HAVEN_LOAD_SECONDS", "120"))
        rate = float(os.environ.get("HAVEN_LOAD_RATE", "20"))
        pending = deque()
        offered, backpressure_stop, stop_reason = 0, False, None
        # Each conversation has its own ordered lane. A slow conversation cannot
        # block scheduling unrelated groups; oldest unfinished work still has the
        # original strict ten-second bound. No generated message is discarded.
        with ExitStack() as stack:
            file_pool = stack.enter_context(ThreadPoolExecutor(max_workers=5))
            recipient_workers = int(
                os.environ.get("HAVEN_LOAD_RECIPIENT_WORKERS", "100")
            )
            recipient_pool = (
                stack.enter_context(ThreadPoolExecutor(max_workers=recipient_workers))
                if recipient_workers
                else None
            )
            for group in groups:
                group.recipient_pool = recipient_pool
            lanes = [
                stack.enter_context(ThreadPoolExecutor(max_workers=1)) for _ in groups
            ]
            barrier = threading.Barrier(5)
            files = [
                file_pool.submit(transfer_file, group, barrier) for group in groups[:5]
            ]
            for index in range(int(duration * rate)):
                scheduled = start + index / rate
                time.sleep(max(0, scheduled - time.monotonic()))
                while pending and pending[0][1].done():
                    pending.popleft()[1].result(timeout=0)
                backlog_expired = bool(
                    pending and time.monotonic() - pending[0][0] > 10
                )
                if (
                    backlog_expired
                    or time.monotonic() - scheduled > 10
                    or metrics.get("ws_unrecoverable", 0)
                    or (metrics["ws_errors"] and not RESILIENCE)
                ):
                    backpressure_stop = True
                    stop_reason = (
                        "oldest_unfinished_over_ten_seconds"
                        if backlog_expired
                        else "scheduler_lag_or_socket_failure"
                    )
                    break  # Stop offering new work; drain every generated message.
                timings.record(
                    "scheduler_lag_before_group_wait", time.monotonic() - scheduled
                )
                group = groups[index % len(groups)]
                submitted = time.monotonic()
                timings.record("scheduler_lag_at_submission", submitted - scheduled)
                future = lanes[index % len(groups)].submit(
                    group.send, scheduled, submitted
                )
                pending.append((scheduled, future))
                offered += 1
                if index % max(1, int(rate * 30)) == 0:
                    (PRIVATE / "progress.json").write_text(
                        json.dumps(
                            {"elapsed_seconds": time.monotonic() - start, **metrics}
                        )
                    )
            for _, future in pending:
                future.result(timeout=120)
            file_ms = [future.result(timeout=120) for future in files]
        elapsed = time.monotonic() - start
        timings.enabled.clear()
        wait_profile = sampler.finish()
        crypto_after = crypto.usage()
        driver_after = process_usage(os.getpid())
        generator_usage = {
            "driver_cpu_seconds": driver_after["cpu_seconds"]
            - driver_before["cpu_seconds"],
            "driver_peak_rss_kib": driver_after["peak_rss_kib"],
            "crypto_workers": len(crypto.workers),
            "recipient_workers": recipient_workers,
            "crypto_worker_cpu_seconds": [
                a["cpu_seconds"] - b["cpu_seconds"]
                for a, b in zip(crypto_after, crypto_before)
            ],
            "crypto_worker_peak_rss_kib": [a["peak_rss_kib"] for a in crypto_after],
        }
        stop.set()
        ws_thread.join(timeout=35)
        if ws_thread.is_alive():
            raise RuntimeError("WSS soak failed")
        time.sleep(1.2)
        after = stats()
        # Read an actual encrypted durable snapshot and restore the native provider.
        restored_client, restored_group = clients[-1], groups[-1]
        sealed = (PRIVATE / (restored_client.id + ".checkpoint")).read_bytes()
        aad = f"haven-load-checkpoint/v1:{restored_client.id}:{restored_group.id}".encode()
        checkpoint = json.loads(
            AESGCM((PRIVATE / "checkpoint.key").read_bytes()).decrypt(
                sealed[:12], sealed[12:], aad
            )
        )
        if (
            checkpoint["seq"] != restored_group.seq
            or checkpoint["head"] != restored_group.head
        ):
            raise RuntimeError("Restored checkpoint chain mismatch")
        crypto.exchange(
            restored_client.shard,
            {
                "client": restored_client.id,
                "op": "restore",
                "state": checkpoint["state"],
                "group_id": restored_group.gid,
            },
        )
        restored_group.check_roster(
            native(restored_client, "inspect", group_id=restored_group.gid)
        )
        if (
            metrics["accepted"] != offered
            or metrics["delivered"] != 9 * metrics["accepted"]
        ):
            raise RuntimeError("Delivery cardinality mismatch")
        print(
            json.dumps(
                {
                    "metrics": metrics,
                    "generator_timings": timings.snapshot(),
                    "generator_usage": generator_usage,
                    "postgres_wait_sampling": wait_profile,
                    "instrumentation_scope": "Constant-space aggregate histograms; phase times overlap across concurrent work; CPU separate for driver/crypto/API; no request or SQL text",
                    "resilience_mode": RESILIENCE,
                    "websocket_reconnect": summarize(reconnect_latencies),
                    "zero_socket_error_gate": "FAIL"
                    if metrics["ws_errors"]
                    else "PASS",
                    "offered_messages": offered,
                    "target_status": "NOT_SUSTAINED"
                    if backpressure_stop
                    else "COMPLETED",
                    "websocket_status": "FAILED" if metrics["ws_errors"] else "PASS",
                    "backpressure_stop_seconds": 10,
                    "backpressure_stop_reason": stop_reason,
                    "scheduler": "50 independent ordered conversation lanes; oldest unfinished work and dispatcher lag both bounded to ten seconds",
                    "rekey_every_application_messages_per_group": int(
                        os.environ.get("HAVEN_LOAD_REKEY_EVERY", "100")
                    ),
                    "encrypted_native_checkpoint_restore": "PASS",
                    "configured_seconds": duration,
                    "configured_messages_per_second": rate,
                    "five_concurrent_encrypted_1mib_files": summarize(file_ms),
                    "elapsed_seconds": elapsed,
                    "achieved_messages_per_second": metrics["accepted"] / elapsed,
                    "send_scheduled_to_accepted": summarize(send_latencies),
                    "scheduled_to_all_nine_durable_acks": summarize(delivery_latencies),
                    "postgres_before": before,
                    "postgres_after": after,
                    "scope": "100 synthetic accounts / 500 native MLS clients / 50 ten-device groups / 500 authenticated WSS; encrypted fsynced native checkpoints, not browser IndexedDB or physical devices; fixture enrollment and login excluded",
                }
            ),
            flush=True,
        )
    finally:
        stop.set()
        crypto.close()


if __name__ == "__main__":
    run_legacy()
