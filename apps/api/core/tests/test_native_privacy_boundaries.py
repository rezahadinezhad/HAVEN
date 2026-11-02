"""Real native MLS verifier and signatures; pre-approved session fixtures only."""

import base64
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import uuid

import pytest
from django.utils import timezone

from core import models as m, protocol as p
from core.retention import cleanup
from .conftest import post
from .test_view_once import bound_client

pytestmark = pytest.mark.django_db


@pytest.fixture
def native():
    root = Path(__file__).resolve().parents[4]
    binary = root / "packages/crypto-core/target/release/examples/protocol_client"
    if not binary.is_file():
        pytest.fail("Build the locked protocol_client example before this suite")
    process = subprocess.Popen(
        [str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
    )

    def call(device, op, **kw):
        process.stdin.write(json.dumps({"client": str(device.pk), "command": {"op": op, **kw}}) + "\n")
        process.stdin.flush()
        output = json.loads(process.stdout.readline())
        if output.get("ok") is not True:
            raise RuntimeError("Native test operation rejected")
        return output["result"]

    try:
        yield call
    finally:
        process.terminate()
        process.wait(timeout=5)


def initialize(native, device):
    result = native(device, "init", identity=device.identity)
    device.public_key = base64.b64decode(result["public_key"])
    device.save(update_fields=["public_key"])


def sign(native, device, header):
    return native(device, "sign", payload=base64.b64encode(p.canonical(header)).decode())["signature"]


@pytest.mark.django_db(transaction=True)
def test_slow_message_insert_does_not_hold_the_global_storage_budget(settings, native, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from django.db import close_old_connections

    settings.CRYPTO_READY = True
    operations = []
    for _ in range(2):
        client, device = bound_client()
        initialize(native, device)
        cid, gid = str(uuid.uuid4()), uuid.uuid4().hex
        native(device, "create", group_id=gid)
        genesis = {
            "domain": "haven/genesis/v1",
            "id": cid,
            "kind": "group",
            "group_id": gid,
            "members": [{**p.certificate(device), "role": "owner"}],
        }
        assert (
            post(
                client,
                "conversations",
                {
                    "id": cid,
                    "kind": "group",
                    "group_id": gid,
                    "header": genesis,
                    "signature": sign(native, device, genesis),
                },
            ).status_code
            == 201
        )
        conv = m.Conversation.objects.get(pk=cid)
        wire = native(device, "encrypt", group_id=gid, plaintext="Synthetic storage-lock test")["ciphertext"]
        mid = str(uuid.uuid4())
        header = {
            "domain": "haven/envelope/v1",
            "v": 1,
            "conversation_id": cid,
            "group_id": gid,
            "sender_device": str(device.pk),
            "client_message_id": mid,
            "epoch": 0,
            "seq": 1,
            "previous_hash": conv.head_hash,
            "ciphertext_hash": p.fingerprint(base64.b64decode(wire)),
            "transition": None,
        }
        operations.append(
            (
                client,
                cid,
                {
                    "v": 1,
                    "client_message_id": mid,
                    "epoch": 0,
                    "ciphertext": wire,
                    "header": header,
                    "signature": sign(native, device, header),
                },
            )
        )
    entered, release = Event(), Event()
    actual = m.NotificationOutbox.objects.create

    def delayed(**kwargs):
        if str(kwargs["envelope"].conversation_id) == operations[0][1]:
            entered.set()
            assert release.wait(10)
        return actual(**kwargs)

    monkeypatch.setattr(m.NotificationOutbox.objects, "create", delayed)

    def send(operation):
        client, cid, body = operation
        close_old_connections()
        try:
            return post(client, f"conversations/{cid}/messages", body).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as threads:
        first = threads.submit(send, operations[0])
        try:
            assert entered.wait(5)
            second = threads.submit(send, operations[1])
            assert second.result(timeout=2) == 201
        finally:
            release.set()
        assert first.result(timeout=5) == 201
    assert m.MessageEnvelope.objects.count() == m.NotificationOutbox.objects.count() == 2
    assert m.StorageUsage.objects.get(key="service").envelope_count == 2


def test_real_mls_rejections_preserve_budget_history_outbox_and_exact_retry(settings, native):
    settings.CRYPTO_READY = True
    client, device = bound_client()
    stranger, other = bound_client()
    for d in [device, other]:
        initialize(native, d)
    cid, gid = str(uuid.uuid4()), uuid.uuid4().hex
    native(device, "create", group_id=gid)
    genesis = {
        "domain": "haven/genesis/v1",
        "id": cid,
        "kind": "group",
        "group_id": gid,
        "members": [{**p.certificate(device), "role": "owner"}],
    }
    assert (
        post(
            client,
            "conversations",
            {
                "id": cid,
                "kind": "group",
                "group_id": gid,
                "header": genesis,
                "signature": sign(native, device, genesis),
            },
        ).status_code
        == 201
    )
    c = m.Conversation.objects.get(pk=cid)
    encrypted = native(device, "encrypt", group_id=gid, plaintext="Synthetic protocol-boundary event")[
        "ciphertext"
    ]
    mid = str(uuid.uuid4())
    header = {
        "domain": "haven/envelope/v1",
        "v": 1,
        "conversation_id": cid,
        "group_id": gid,
        "sender_device": str(device.pk),
        "client_message_id": mid,
        "epoch": 0,
        "seq": 1,
        "previous_hash": c.head_hash,
        "ciphertext_hash": p.fingerprint(base64.b64decode(encrypted)),
        "transition": None,
    }
    body = {
        "v": 1,
        "client_message_id": mid,
        "epoch": 0,
        "ciphertext": encrypted,
        "header": header,
        "signature": sign(native, device, header),
    }
    baseline = list(m.StorageUsage.objects.order_by("key").values())
    attacks = []
    forged = deepcopy(body)
    forged["signature"] = sign(native, other, header)
    attacks.append(forged)
    malformed = deepcopy(body)
    malformed["ciphertext"] = base64.b64encode(b"not an MLS wire").decode()
    malformed["header"]["ciphertext_hash"] = p.fingerprint(b"not an MLS wire")
    malformed["signature"] = sign(native, device, malformed["header"])
    attacks.append(malformed)
    hash_swap = deepcopy(body)
    hash_swap["header"]["ciphertext_hash"] = "0" * 64
    hash_swap["signature"] = sign(native, device, hash_swap["header"])
    attacks.append(hash_swap)
    unknown = deepcopy(body)
    unknown["recipient_account"] = str(other.user_id)
    attacks.append(unknown)
    native(device, "create", group_id="another-synthetic-group")
    swapped = deepcopy(body)
    swapped["ciphertext"] = native(
        device, "encrypt", group_id="another-synthetic-group", plaintext="Synthetic"
    )["ciphertext"]
    swapped["header"]["ciphertext_hash"] = p.fingerprint(base64.b64decode(swapped["ciphertext"]))
    swapped["signature"] = sign(native, device, swapped["header"])
    attacks.append(swapped)
    for attack in attacks:
        assert post(client, f"conversations/{cid}/messages", attack).status_code == 400
        c.refresh_from_db()
        assert c.last_seq == 0 and c.head_hash == body["header"]["previous_hash"]
        assert list(m.StorageUsage.objects.order_by("key").values()) == baseline
        assert not m.MessageEnvelope.objects.exists() and not m.NotificationOutbox.objects.exists()
    assert post(stranger, f"conversations/{cid}/messages", body).status_code == 404
    accepted = post(client, f"conversations/{cid}/messages", body)
    assert accepted.status_code == 201
    retry = post(client, f"conversations/{cid}/messages", body)
    assert retry.status_code == 200 and retry.json()["id"] == accepted.json()["id"]
    assert m.MessageEnvelope.objects.count() == m.NotificationOutbox.objects.count() == 1
    changed = deepcopy(body)
    changed["ciphertext"] = base64.b64encode(b"changed intent").decode()
    assert post(client, f"conversations/{cid}/messages", changed).status_code == 400
    assert m.MessageEnvelope.objects.count() == 1


def test_real_keypackage_expiry_disassociation_never_allows_reupload_or_reclaim(settings, native):
    settings.CRYPTO_READY = True
    owner, owner_device = bound_client()
    target, target_device = bound_client()
    for d in [owner_device, target_device]:
        initialize(native, d)
    package = native(target_device, "package")["key_package"]
    uploaded = post(target, "crypto/key-packages", {"package": package})
    assert uploaded.status_code == 201
    claimed = post(owner, f"crypto/key-packages/{target_device.pk}", {})
    assert claimed.status_code == 200 and claimed.json()["id"] == uploaded.json()["id"]
    m.DeviceKeyPackage.objects.filter(pk=uploaded.json()["id"]).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert cleanup()["packages"] == 1
    marker = m.DeviceKeyPackage.objects.get(pk=uploaded.json()["id"])
    assert marker.device_id is marker.claimed_by_id is None and not bytes(marker.package)
    assert post(target, "crypto/key-packages", {"package": package}).status_code == 400
    assert post(owner, f"crypto/key-packages/{target_device.pk}", {}).status_code == 409
    assert m.DeviceKeyPackage.objects.filter(digest=p.fingerprint(base64.b64decode(package))).count() == 1


@pytest.mark.django_db(transaction=True)
def test_add_waits_for_target_revocation_before_granting_membership(settings, native, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import time
    from django.db import close_old_connections, connection

    settings.CRYPTO_READY = True
    owner, owner_device = bound_client()
    target, target_device = bound_client()
    for device in [owner_device, target_device]:
        initialize(native, device)
    cid, gid = str(uuid.uuid4()), uuid.uuid4().hex
    native(owner_device, "create", group_id=gid)
    genesis = {
        "domain": "haven/genesis/v1",
        "id": cid,
        "kind": "group",
        "group_id": gid,
        "members": [{**p.certificate(owner_device), "role": "owner"}],
    }
    assert (
        post(
            owner,
            "conversations",
            {
                "id": cid,
                "kind": "group",
                "group_id": gid,
                "header": genesis,
                "signature": sign(native, owner_device, genesis),
            },
        ).status_code
        == 201
    )
    package = native(target_device, "package")["key_package"]
    assert post(target, "crypto/key-packages", {"package": package}).status_code == 201
    claim = post(owner, f"crypto/key-packages/{target_device.pk}", {}).json()
    added = native(owner_device, "add", group_id=gid, key_package=claim["package"])
    roster = sorted(
        [
            {**p.certificate(owner_device), "role": "owner"},
            {**p.certificate(target_device), "role": "member"},
        ],
        key=lambda x: x["id"],
    )
    transition = {
        "action": "add",
        "device_id": str(target_device.pk),
        "next_epoch": 1,
        "members": roster,
        "welcome_hash": p.fingerprint(base64.b64decode(added["welcome"])),
        "state_hash": added["state_hash"],
    }
    c = m.Conversation.objects.get(pk=cid)
    mid = str(uuid.uuid4())
    header = {
        "domain": "haven/envelope/v1",
        "v": 1,
        "conversation_id": cid,
        "group_id": gid,
        "sender_device": str(owner_device.pk),
        "client_message_id": mid,
        "epoch": 0,
        "seq": 1,
        "previous_hash": c.head_hash,
        "ciphertext_hash": p.fingerprint(base64.b64decode(added["commit"])),
        "transition": transition,
    }
    body = {
        "v": 1,
        "client_message_id": mid,
        "epoch": 0,
        "ciphertext": added["commit"],
        "header": header,
        "signature": sign(native, owner_device, header),
        "action": "add",
        "device_id": str(target_device.pk),
        "key_package_id": claim["id"],
        "welcome": added["welcome"],
    }
    revoked_uncommitted, resume = Event(), Event()
    add_pid = []
    from core import views

    original_rekey = views.require_rekey

    def pause_after_rekey(conversations):
        original_rekey(conversations)
        revoked_uncommitted.set()
        assert resume.wait(10)

    monkeypatch.setattr(views, "require_rekey", pause_after_rekey)

    def revoke():
        close_old_connections()

        try:
            return post(target, f"devices/{target_device.pk}/revoke", {})
        finally:
            close_old_connections()

    def add():
        close_old_connections()

        def observed(execute, sql, params, many, context):
            if '"core_user"' in sql and "FOR UPDATE" in sql:
                add_pid.append(connection.connection.info.backend_pid)
            return execute(sql, params, many, context)

        try:
            with connection.execute_wrapper(observed):
                return post(owner, f"conversations/{cid}/crypto-events", body)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        revoking = pool.submit(revoke)
        try:
            assert revoked_uncommitted.wait(10)
            adding = pool.submit(add)
            deadline = time.monotonic() + 5
            blocked = False
            while time.monotonic() < deadline and not adding.done():
                if add_pid:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s", [add_pid[-1]]
                        )
                        row = cursor.fetchone()
                    if row and row[0] == "Lock":
                        blocked = True
                        break
                time.sleep(0.01)
        finally:
            resume.set()
        assert revoking.result(timeout=10).status_code == 200
        assert adding.result(timeout=10).status_code == 403
        assert blocked, "membership grant did not wait for the target account authority fence"
    assert not m.Membership.objects.filter(conversation_id=cid, device=target_device).exists()
    c.refresh_from_db()
    assert c.epoch == c.last_seq == 0 and not m.MessageEnvelope.objects.exists()
