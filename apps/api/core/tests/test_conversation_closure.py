# ruff: noqa: F811 -- pytest imports shared fixtures by name
"""Actual PostgreSQL and native MLS/signatures; no long workload or production deletion."""

import base64
from copy import deepcopy
import secrets
import uuid

import pytest

from core import closure as lifecycle, models as m, protocol as p
from .conftest import post
from .test_view_once import bound_client
from .test_native_privacy_boundaries import native, initialize, sign  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def pair(settings, native, request):
    settings.CRYPTO_READY = True
    settings.CONVERSATION_CLOSURE_READY = True
    a, ad = bound_client()
    b, bd = bound_client()
    for device in (ad, bd):
        initialize(native, device)
    choice = getattr(request, "param", lifecycle.POLICY)
    policy = choice.get("policy", lifecycle.POLICY) if isinstance(choice, dict) else choice
    kind = choice.get("kind", "direct") if isinstance(choice, dict) else "direct"
    cid, gid = str(uuid.uuid4()), uuid.uuid4().hex
    native(ad, "create", group_id=gid)
    genesis = {
        "domain": "haven/genesis/v1",
        "id": cid,
        "kind": kind,
        "group_id": gid,
        "members": [{**p.certificate(ad), "role": "owner"}],
        "closure_policy": policy,
        "closure_epoch": settings.CONVERSATION_CLOSURE_EPOCH,
    }
    result = post(
        a,
        "conversations",
        {
            "id": cid,
            "kind": kind,
            "group_id": gid,
            "header": genesis,
            "signature": sign(native, ad, genesis),
        },
    )
    assert result.status_code == 201, result.content
    conv = m.Conversation.objects.get(pk=cid)
    package = native(bd, "package")["key_package"]
    assert post(b, "crypto/key-packages", {"package": package}).status_code == 201
    a.defaults["HTTP_X_HAVEN_CONTACT"] = post(b, "devices/contact-introduction", {}).json()["token"]
    claim = post(a, f"crypto/key-packages/{bd.pk}", {}).json()
    added = native(ad, "add", group_id=gid, key_package=claim["package"])
    transition = {
        "action": "add",
        "device_id": str(bd.pk),
        "next_epoch": 1,
        "members": sorted(
            [{**p.certificate(ad), "role": "owner"}, {**p.certificate(bd), "role": "member"}],
            key=lambda x: x["id"],
        ),
        "welcome_hash": p.fingerprint(base64.b64decode(added["welcome"])),
        "state_hash": added["state_hash"],
    }
    body = envelope(native, ad, conv, added["commit"], transition)
    body.update(action="add", device_id=str(bd.pk), key_package_id=claim["id"], welcome=added["welcome"])
    assert post(a, f"conversations/{cid}/crypto-events", body).status_code == 201
    native(bd, "join", group_id=gid, welcome=added["welcome"])
    conv.refresh_from_db()
    wire = native(ad, "encrypt", group_id=gid, plaintext='{"synthetic":"text-only"}')["ciphertext"]
    send = envelope(native, ad, conv, wire)
    assert post(a, f"conversations/{cid}/messages", send).status_code == 201
    conv.refresh_from_db()
    return a, ad, b, bd, conv, send


def envelope(native, device, conv, wire, transition=None):
    mid = str(uuid.uuid4())
    header = {
        "domain": "haven/envelope/v1",
        "v": 1,
        "conversation_id": str(conv.pk),
        "group_id": conv.group_id,
        "sender_device": str(device.pk),
        "client_message_id": mid,
        "epoch": conv.epoch,
        "seq": conv.last_seq + 1,
        "previous_hash": conv.head_hash,
        "ciphertext_hash": p.fingerprint(base64.b64decode(wire)),
        "transition": transition,
    }
    return {
        "v": 1,
        "client_message_id": mid,
        "epoch": conv.epoch,
        "ciphertext": wire,
        "header": header,
        "signature": sign(native, device, header),
    }


def propose(pair, native):
    a, ad, _, _, conv, _ = pair
    transcript = lifecycle.transcript_for(conv, uuid.uuid4(), ad.pk)
    response = post(
        a,
        f"conversations/{conv.pk}/closure",
        {"transcript": transcript, "signature": sign(native, ad, transcript)},
    )
    assert response.status_code == 200, response.content
    return response.json()


def prepare(client, device, conv, native):
    closure = m.ConversationClosure.objects.get(conversation=conv)
    conv.refresh_from_db()
    snapshot = lifecycle.current_transcript(conv, closure)
    return post(
        client,
        f"conversations/{conv.pk}/closure?action=prepare",
        {
            "transcript": snapshot,
            "signature": sign(native, device, lifecycle.preparation_payload(snapshot, device.pk)),
        },
    )


def finalize(pair, native, receipts=True):
    a, ad, b, bd, conv, _ = pair
    propose(pair, native)
    assert prepare(a, ad, conv, native).status_code == 200
    assert prepare(b, bd, conv, native).status_code == 200
    conv.refresh_from_db()
    for client, device in ((a, ad), (b, bd)):
        assert post(client, f"conversations/{conv.pk}/acks", {"seq": conv.last_seq}).status_code == 200
        closure = m.ConversationClosure.objects.get(conversation=conv)
        archive_hash = secrets.token_hex(32)
        response = post(
            client,
            f"conversations/{conv.pk}/closure?action=consent",
            {
                "transcript_hash": lifecycle.transcript_hash(closure.transcript),
                "archive_hash": archive_hash,
                "signature": sign(
                    native, device, lifecycle.consent_payload(closure.transcript, device.pk, archive_hash)
                ),
            },
        )
        assert response.status_code == 200, response.content
    closure = m.ConversationClosure.objects.get(conversation=conv)
    if receipts:
        for client, device in ((a, ad), (b, bd)):
            response = post(
                client,
                f"conversations/{conv.pk}/closure?action=receipt",
                {
                    "finality_hash": lifecycle.finality_hash(closure),
                    "signature": sign(native, device, lifecycle.final_receipt_payload(closure, device.pk)),
                },
            )
            assert response.status_code == 200, response.content
    return m.ConversationClosure.objects.get(conversation=conv)


def test_mutual_archive_finality_preserves_history_and_idempotent_acceptance(pair, native):
    a, ad, b, bd, conv, send = pair
    original = list(
        m.MessageEnvelope.objects.filter(conversation=conv).values("header", "ciphertext", "signature")
    )
    closure = finalize(pair, native)
    lifecycle.validate_final_receipts(conv, closure)
    conv.refresh_from_db()
    assert conv.status == "closed"
    assert (
        list(m.MessageEnvelope.objects.filter(conversation=conv).values("header", "ciphertext", "signature"))
        == original
    )
    assert post(a, f"conversations/{conv.pk}/messages", send).status_code == 200
    wire = native(ad, "encrypt", group_id=conv.group_id, plaintext="blocked")["ciphertext"]
    assert post(a, f"conversations/{conv.pk}/messages", envelope(native, ad, conv, wire)).status_code == 403
    assert post(b, f"conversations/{conv.pk}/acks", {"seq": conv.last_seq}).status_code == 200
    assert post(a, f"conversations/{conv.pk}/closure?action=cancel", {}).status_code == 400


def test_peer_flushes_before_preparing_and_both_must_reagree_on_latest_head(pair, native):
    a, ad, b, bd, conv, _ = pair
    propose(pair, native)
    assert prepare(a, ad, conv, native).json()["state"] == "proposed"
    wire = native(bd, "encrypt", group_id=conv.group_id, plaintext="Previously pending peer send")[
        "ciphertext"
    ]
    response = post(b, f"conversations/{conv.pk}/messages", envelope(native, bd, conv, wire))
    assert response.status_code == 201
    assert prepare(b, bd, conv, native).json()["state"] == "proposed"
    conv.refresh_from_db()
    assert conv.status == "active"
    assert prepare(a, ad, conv, native).json()["state"] == "closing"
    conv.refresh_from_db()
    assert conv.status == "closing"


def test_forged_scope_stale_head_and_unsynced_archive_consent_are_rejected(pair, native):
    a, ad, b, bd, conv, _ = pair
    transcript = lifecycle.transcript_for(conv, uuid.uuid4(), ad.pk)
    forged = deepcopy(transcript)
    forged["final_hash"] = "0" * 64
    assert (
        post(
            a,
            f"conversations/{conv.pk}/closure",
            {"transcript": forged, "signature": sign(native, ad, forged)},
        ).status_code
        == 400
    )
    assert (
        post(
            a,
            f"conversations/{conv.pk}/closure",
            {"transcript": transcript, "signature": sign(native, bd, transcript)},
        ).status_code
        == 400
    )
    propose(pair, native)
    assert prepare(a, ad, conv, native).status_code == 200
    assert prepare(b, bd, conv, native).status_code == 200
    closure = m.ConversationClosure.objects.get(conversation=conv)
    ah = "a" * 64
    assert (
        post(
            a,
            f"conversations/{conv.pk}/closure?action=consent",
            {
                "transcript_hash": lifecycle.transcript_hash(closure.transcript),
                "archive_hash": ah,
                "signature": sign(native, ad, lifecycle.consent_payload(closure.transcript, ad.pk, ah)),
            },
        ).status_code
        == 403
    )
    assert not m.ConversationClosure.objects.get(conversation=conv).consents


def test_gate_uuid_knowledge_extra_device_and_restore_namespace_fail_closed(pair, native, settings):
    a, ad, b, bd, conv, _ = pair
    outsider, _ = bound_client()
    assert outsider.get(f"/api/v1/conversations/{conv.pk}/closure", secure=True).status_code == 404
    settings.CONVERSATION_CLOSURE_READY = False
    assert a.get(f"/api/v1/conversations/{conv.pk}/closure", secure=True).status_code == 403
    settings.CONVERSATION_CLOSURE_READY = True
    settings.CONVERSATION_CLOSURE_EPOCH = "restored-database-new-epoch"
    wire = native(ad, "encrypt", group_id=conv.group_id, plaintext="old restored group")["ciphertext"]
    assert post(a, f"conversations/{conv.pk}/messages", envelope(native, ad, conv, wire)).status_code == 403
    settings.CONVERSATION_CLOSURE_EPOCH = conv.genesis["closure_epoch"]
    bound_client(ad.user)
    assert a.get(f"/api/v1/conversations/{conv.pk}/closure", secure=True).status_code == 400


def test_text_only_uploads_are_rejected_before_storage_or_tombstone_creation(pair):
    a, _, _, _, conv, _ = pair
    for once in (False, True):
        aid = uuid.uuid4()
        response = post(
            a,
            "attachments/init",
            {
                "id": str(aid),
                "conversation_id": str(conv.pk),
                "ciphertext_size": 4112,
                "chunk_count": 1,
                "view_once": once,
            },
        )
        assert response.status_code == 403
        assert not m.EncryptedAttachment.objects.filter(pk=aid).exists()
        assert not m.AttachmentTombstone.objects.filter(pk=aid).exists()


def test_invalid_persisted_preparation_or_final_receipt_never_validates(pair, native):
    a, ad, _, _, conv, _ = pair
    propose(pair, native)
    assert prepare(a, ad, conv, native).status_code == 200
    closure = m.ConversationClosure.objects.get(conversation=conv)
    original = deepcopy(closure.preparations)
    closure.preparations[str(ad.pk)]["signature"] = base64.b64encode(b"x" * 64).decode()
    closure.save(update_fields=["preparations"])
    assert a.get(f"/api/v1/conversations/{conv.pk}/closure", secure=True).status_code == 400
    closure.preparations = original
    closure.save(update_fields=["preparations"])
    assert a.get(f"/api/v1/conversations/{conv.pk}/closure", secure=True).status_code == 200


def test_rekey_cannot_reopen_a_closed_conversation_and_receipt_tampering_blocks_retirement(pair, native):
    from django.db import transaction
    from rest_framework.exceptions import ValidationError
    from core.authorization import require_rekey

    closure = finalize(pair, native)
    conv = pair[4]
    with transaction.atomic():
        require_rekey(m.Conversation.objects.filter(pk=conv.pk))
    conv.refresh_from_db()
    assert conv.status == "closed"
    closure.final_receipts[str(pair[1].pk)] = base64.b64encode(b"x" * 64).decode()
    closure.save(update_fields=["final_receipts"])
    with pytest.raises(ValidationError, match="signature"):
        lifecycle.validate_final_receipts(conv, closure)


def test_idempotent_closed_retry_does_not_bypass_rekey_fence_for_new_messages(pair, native):
    a, ad, _, _, conv, accepted = pair
    conv.status = "rekey_required"
    conv.save(update_fields=["status"])
    # An identical durable acceptance is safe to recover; a new MLS ciphertext
    # must still wait for the required authenticated membership rekey.
    assert post(a, f"conversations/{conv.pk}/messages", accepted).status_code == 200
    wire = native(ad, "encrypt", group_id=conv.group_id, plaintext="must wait for rekey")["ciphertext"]
    before = (conv.last_seq, conv.head_hash)
    assert post(a, f"conversations/{conv.pk}/messages", envelope(native, ad, conv, wire)).status_code == 403
    conv.refresh_from_db()
    assert (conv.last_seq, conv.head_hash) == before
