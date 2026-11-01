"""Regression coverage for storage, discovery, proof reads and fair sign-in."""

import base64
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from core import models as m, protocol as p
from core.storage import account_key
from core.retention import retire_delivered
from .conftest import login, post as raw_post
from .test_security import setup_device, post
from .test_view_once import bound_client

pytestmark = pytest.mark.django_db


def conversation(client):
    cid = str(uuid.uuid4())
    response = post(client, "conversations", {"id": cid, "kind": "group", "group_id": cid})
    assert response.status_code == 201
    return cid


def body():
    return {
        "v": 1,
        "client_message_id": str(uuid.uuid4()),
        "epoch": 0,
        "ciphertext": base64.b64encode(b"x" * 120).decode(),
    }


def test_storage_limits_atomic_idempotency_and_retirement(client, credentials, settings, monkeypatch):
    settings.CRYPTO_READY = True
    device, _ = setup_device(client, credentials)
    cid = conversation(client)
    monkeypatch.setattr(p, "public_validate", lambda **kw: {"group_id": cid, "epoch": 0})
    settings.MESSAGE_ACCOUNT_PENDING_BYTES = 120
    data = body()
    assert post(client, f"conversations/{cid}/messages", data).status_code == 201
    before = m.StorageUsage.objects.get(key=account_key(device.user_id))
    assert before.pending_bytes == 120 and before.envelope_count == 1
    assert post(client, f"conversations/{cid}/messages", data).status_code == 200
    assert m.StorageUsage.objects.get(pk=before.pk).used_bytes == before.used_bytes
    # A correctly signed second envelope reaches the budget check.
    c = m.Conversation.objects.get(pk=cid)
    d = body()
    h = {
        "domain": "haven/envelope/v1",
        "v": 1,
        "conversation_id": cid,
        "group_id": cid,
        "sender_device": str(device.pk),
        "client_message_id": d["client_message_id"],
        "epoch": 0,
        "seq": 2,
        "previous_hash": c.head_hash,
        "ciphertext_hash": p.fingerprint(b"x" * 120),
        "transition": None,
    }
    d.update(header=h, signature=base64.b64encode(client.signing_key.sign(p.canonical(h))).decode())
    assert raw_post(client, f"conversations/{cid}/messages", d).status_code == 429
    c.refresh_from_db()
    assert c.last_seq == 1 and m.MessageEnvelope.objects.count() == 1
    assert m.NotificationOutbox.objects.count() == 1
    m.MessageEnvelope.objects.update(received_at=timezone.now() - timedelta(days=2))
    assert retire_delivered(timezone.now()) == 0  # No ACK: data and charge remain.
    assert post(client, f"conversations/{cid}/acks", {"seq": 1}).status_code == 200
    assert retire_delivered(timezone.now()) == 1
    after = m.StorageUsage.objects.get(pk=before.pk)
    assert after.used_bytes == before.used_bytes - 120 and after.pending_bytes == 0
    assert after.envelope_count == 1  # Signed metadata is still charged.


def test_service_budget_and_conversation_limit(client, credentials, settings):
    settings.CRYPTO_READY = True
    setup_device(client, credentials)
    settings.MAX_OWNED_CONVERSATIONS = 1
    conversation(client)
    cid = str(uuid.uuid4())
    assert post(client, "conversations", {"id": cid, "kind": "group", "group_id": cid}).status_code == 429
    settings.MAX_OWNED_CONVERSATIONS = 500
    settings.MESSAGE_SERVICE_BYTES = 4096
    assert post(client, "conversations", {"id": cid, "kind": "group", "group_id": cid}).status_code == 429
    assert m.Conversation.objects.count() == 1


def test_pagination_all_memberships_no_duplicates_and_device_binding(settings):
    settings.CRYPTO_READY = True
    a, ad = bound_client()
    b, _ = bound_client()
    for _ in range(205):
        c = m.Conversation.objects.create(creator=ad, kind="group", group_id=uuid.uuid4().hex)
        m.Membership.objects.create(conversation=c, device=ad, valid_from_epoch=0)
    ids, cursor = [], None
    for _ in range(3):
        response = a.get("/api/v1/conversations", {"cursor": cursor} if cursor else {}, secure=True)
        assert response.status_code == 200
        ids += [x["id"] for x in response.json()]
        cursor = response.headers.get("X-Haven-Next-Cursor")
        if len(ids) == 100:
            assert b.get("/api/v1/conversations", {"cursor": cursor}, secure=True).status_code == 400
    assert len(ids) == len(set(ids)) == 205 and cursor is None
    assert a.get("/api/v1/conversations", {"cursor": "tampered"}, secure=True).status_code == 400
    seen, cursor = [], None
    for _ in range(3):
        data = a.get("/api/v1/sync", {"cursor": cursor} if cursor else {}, secure=True).json()
        seen += [x["id"] for x in data["conversations"]]
        cursor = data["next_cursor"]
    assert seen == ids and cursor is None


def test_proofs_do_not_select_ciphertext_and_idle_ack_does_not_write(settings):
    settings.CRYPTO_READY = True
    a, ad = bound_client()
    c = m.Conversation.objects.create(creator=ad, kind="group", group_id=uuid.uuid4().hex, last_seq=1)
    m.Membership.objects.create(conversation=c, device=ad, valid_from_epoch=0)
    m.MessageEnvelope.objects.create(
        conversation=c,
        sender_device=ad,
        server_seq=1,
        client_message_id=uuid.uuid4(),
        group_epoch=0,
        ciphertext=b"x" * 150000,
        request_digest="x",
    )
    with CaptureQueriesContext(connection) as queries:
        response = a.get(f"/api/v1/conversations/{c.pk}/proofs", secure=True)
    assert response.status_code == 200 and len(response.json()["proofs"]) == 1
    envelope_queries = [q["sql"] for q in queries if 'FROM "core_messageenvelope"' in q["sql"]]
    assert len(envelope_queries) == 1 and '"ciphertext"' not in envelope_queries[0]
    raw_post(a, f"conversations/{c.pk}/acks", {"seq": 1})
    c.refresh_from_db()
    assert c.receipt_version == 1
    with CaptureQueriesContext(connection) as queries:
        assert raw_post(a, f"conversations/{c.pk}/acks", {"seq": 1}).status_code == 200
    assert not any(q["sql"].startswith("UPDATE") for q in queries)
    c.refresh_from_db()
    assert c.receipt_version == 1


def test_login_source_isolation_and_malformed_requests(client, credentials):
    for _ in range(10):
        assert raw_post(client, "auth/login", {}).status_code == 400
    assert login(client, credentials).status_code == 200
    for _ in range(5):
        response = raw_post(client, "auth/login", {"username": credentials[0].username, "password": "wrong"})
    assert response.status_code == 429
    client.defaults["REMOTE_ADDR"] = "192.0.2.2"
    assert login(client, credentials).status_code == 200


@pytest.mark.django_db(transaction=True)
def test_concurrent_message_quota_across_conversations(settings, monkeypatch):
    settings.CRYPTO_READY = True
    settings.MESSAGE_ACCOUNT_PENDING_BYTES = 120
    c1, d1 = bound_client()
    c2, d2 = bound_client(d1.user)
    # HTTP auth/session and signatures are real; isolate public MLS wire parsing.
    conversations = []
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    for client, device in [(c1, d1), (c2, d2)]:
        key = Ed25519PrivateKey.generate()
        device.public_key = key.public_key().public_bytes_raw()
        device.save(update_fields=["public_key"])
        client.signing_key, client.signing_device = key, device
        conversations.append((client, conversation(client)))

    def wire(**kw):
        # Distinct mock payloads identify the conversation without shared mutable state.
        return {"group_id": base64.b64decode(kw["ciphertext"])[0:36].decode(), "epoch": 0}

    monkeypatch.setattr(p, "public_validate", wire)
    gate = Barrier(2)

    def send(pair):
        client, cid = pair
        try:
            close_old_connections()
            data = body()
            data["ciphertext"] = base64.b64encode(cid.encode() + b"x" * 84).decode()
            gate.wait(timeout=10)
            return post(client, f"conversations/{cid}/messages", data).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(send, conversations)) == [201, 429]
    assert m.MessageEnvelope.objects.count() == 1
    assert m.StorageUsage.objects.get(key=account_key(d1.user_id)).pending_bytes == 120


@pytest.mark.django_db(transaction=True)
def test_migration_backfills_existing_ciphertext_control_and_metadata():
    from django.db.migrations.executor import MigrationExecutor
    from django.db.models import Sum
    import rfc8785

    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    old = ("core", "0010_credential_bound_sessions")
    new = ("core", "0011_storage_and_sync_budgets")
    try:
        executor.migrate([old])
        apps = executor.loader.project_state([old]).apps
        User, Device = apps.get_model("core", "User"), apps.get_model("core", "Device")
        Conv, Env = apps.get_model("core", "Conversation"), apps.get_model("core", "MessageEnvelope")
        Control = apps.get_model("core", "CryptoControlEvent")
        u = User.objects.create(username=uuid.uuid4().hex)
        d = Device.objects.create(user=u, public_key=b"x" * 32, expires_at=timezone.now())
        c = Conv.objects.create(creator=d, kind="group", group_id=uuid.uuid4().hex)
        header, transition = {"test": "signed header"}, {"test": "membership"}
        for seq, kind, cipher in [
            (1, "application", b"abc"),
            (2, "commit", b"commit"),
            (3, "application", b""),
        ]:
            e = Env.objects.create(
                conversation=c,
                sender_device=d,
                server_seq=seq,
                group_epoch=0,
                client_message_id=uuid.uuid4(),
                ciphertext=cipher,
                header=header,
                signature=b"s" * 64,
                kind=kind,
                request_digest="x",
                ciphertext_retired=seq == 3,
            )
            if kind == "commit":
                Control.objects.create(
                    envelope=e, transition=transition, signature=b"s" * 64, welcome=b"welcome"
                )
        executor = MigrationExecutor(connection)
        executor.migrate([new])
        expected = (
            4096 + 3 * (len(rfc8785.dumps(header)) + 64 + 4096) + 3 + 6 + len(rfc8785.dumps(transition)) + 7
        )
        account = m.StorageUsage.objects.get(key=account_key(u.pk))
        service = m.StorageUsage.objects.get(key="service")
        assert account.used_bytes == expected
        assert account.pending_bytes == 3 and account.envelope_count == 3 and account.conversation_count == 1
        # Other fixtures may have retained rows; the singleton must exactly sum accounts.
        assert (
            service.used_bytes
            == m.StorageUsage.objects.exclude(key="service").aggregate(total=Sum("used_bytes"))["total"]
        )
    finally:
        MigrationExecutor(connection).migrate(latest)


@pytest.mark.django_db(transaction=True)
def test_concurrent_service_budget_across_accounts(settings):
    from django.db import transaction
    from core.storage import reserve
    from rest_framework.exceptions import Throttled

    settings.MESSAGE_SERVICE_BYTES = 150
    gate = Barrier(2)

    def allocate(uid):
        try:
            close_old_connections()
            gate.wait(timeout=10)
            with transaction.atomic():
                reserve(uid, 100, pending=100, envelopes=1)
            return "accepted"
        except Throttled:
            return "full"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(allocate, [uuid.uuid4(), uuid.uuid4()])) == ["accepted", "full"]
    service = m.StorageUsage.objects.get(key="service")
    assert service.used_bytes == 100 and service.envelope_count == 1
