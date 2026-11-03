# ruff: noqa: F811 -- shared pytest fixtures
"""Real MLS account-wide quorum, production worker, media and independent restore journal."""

import base64
import secrets
from io import StringIO
from unittest.mock import patch
import uuid
import pytest
from django.core.management import call_command
from django.utils import timezone
from django.db.models.query import QuerySet
from rest_framework.exceptions import PermissionDenied
from core import closure as lifecycle, models as m, protocol as p
from core.graph_retirement import retire_conversation
from core.retirement_journal import initialize, reconcile
from .test_conversation_closure import pair, native, propose, prepare, envelope  # noqa: F401
from .test_native_privacy_boundaries import initialize as init_device, sign
from .test_view_once import bound_client
from .conftest import post

pytestmark = pytest.mark.django_db(transaction=True)


def add_member(pair, native, client, device):
    a, ad, _, _, conv, _ = pair
    init_device(native, device)
    package = native(device, "package")["key_package"]
    assert post(client, "crypto/key-packages", {"package": package}).status_code == 201
    a.defaults["HTTP_X_HAVEN_CONTACT"] = post(client, "devices/contact-introduction", {}).json()["token"]
    claim = post(a, f"crypto/key-packages/{device.pk}", {}).json()
    wire = native(ad, "add", group_id=conv.group_id, key_package=claim["package"])
    conv.refresh_from_db()
    transition = {
        "action": "add",
        "device_id": str(device.pk),
        "next_epoch": conv.epoch + 1,
        "members": sorted(
            [*p.roster(conv), {**p.certificate(device), "role": "member"}], key=lambda x: x["id"]
        ),
        "welcome_hash": p.fingerprint(base64.b64decode(wire["welcome"])),
        "state_hash": wire["state_hash"],
    }
    body = envelope(native, ad, conv, wire["commit"], transition)
    body.update(action="add", device_id=str(device.pk), key_package_id=claim["id"], welcome=wire["welcome"])
    assert post(a, f"conversations/{conv.pk}/crypto-events", body).status_code == 201
    native(device, "join", group_id=conv.group_id, welcome=wire["welcome"])
    conv.refresh_from_db()


def finalize_accounts(pair, native, actors):
    conv = pair[4]
    propose(pair, native)
    for client, device in actors:
        response = prepare(client, device, conv, native)
        assert response.status_code == 200, response.content
    closure = m.ConversationClosure.objects.get(conversation=conv)
    assert closure.state == "closing"
    for client, device in actors:
        ah = secrets.token_hex(32)
        response = post(
            client,
            f"conversations/{conv.pk}/closure?action=consent",
            {
                "transcript_hash": lifecycle.transcript_hash(closure.transcript),
                "archive_hash": ah,
                "signature": sign(
                    native, device, lifecycle.consent_payload(closure.transcript, device.pk, ah)
                ),
            },
        )
        assert response.status_code == 200, response.content
    closure.refresh_from_db()
    for client, device in actors:
        response = post(
            client,
            f"conversations/{conv.pk}/closure?action=receipt",
            {
                "finality_hash": lifecycle.finality_hash(closure),
                "signature": sign(native, device, lifecycle.final_receipt_payload(closure, device.pk)),
            },
        )
        assert response.status_code == 200, response.content
    closure.refresh_from_db()
    return closure


@pytest.fixture
def journal(settings, tmp_path):
    settings.GRAPH_RETIREMENT_READY = True
    settings.GRAPH_RETIREMENT_REPLAY_SECRET = secrets.token_urlsafe(48)
    settings.RETIREMENT_JOURNAL_DIR = str(tmp_path)
    initialize()
    return tmp_path


@pytest.mark.parametrize("pair", [lifecycle.ACCOUNT_POLICY], indirect=True)
def test_one_of_multiple_devices_represents_account_and_freezes_its_other_devices(pair, native):
    a, ad, b, bd, conv, _ = pair
    a2, ad2 = bound_client(ad.user)
    add_member(pair, native, a2, ad2)
    closure = finalize_accounts(pair, native, [(a, ad), (b, bd)])
    assert len(closure.transcript["participants"]) == 3
    assert len(closure.consents) == len(closure.final_receipts) == 2
    assert prepare(a2, ad2, conv, native).status_code == 403
    conv.refresh_from_db()
    wire = native(ad2, "encrypt", group_id=conv.group_id, plaintext="unsent on other device")["ciphertext"]
    assert post(a2, f"conversations/{conv.pk}/messages", envelope(native, ad2, conv, wire)).status_code == 403


@pytest.mark.parametrize("pair", [{"policy": lifecycle.ACCOUNT_POLICY, "kind": "group"}], indirect=True)
def test_group_requires_each_account_not_owner_or_duplicate_device_votes(pair, native):
    a, ad, b, bd, conv, _ = pair
    # The fixture creates this kind in its signed genesis for this test.
    c, cd = bound_client()
    add_member(pair, native, c, cd)
    propose(pair, native)
    assert prepare(a, ad, conv, native).status_code == 200
    assert prepare(b, bd, conv, native).status_code == 200
    assert m.ConversationClosure.objects.get(conversation=conv).state == "proposed"
    assert prepare(c, cd, conv, native).status_code == 200
    assert m.ConversationClosure.objects.get(conversation=conv).state == "closing"


@pytest.mark.parametrize("pair", [lifecycle.ACCOUNT_POLICY], indirect=True)
def test_normal_worker_deletes_media_and_leaves_durable_replay_journal(pair, native, journal):
    a, ad, b, bd, conv, _ = pair
    aid = uuid.uuid4()
    attachment = m.EncryptedAttachment.objects.create(
        id=aid,
        uploader_device=ad,
        conversation=conv,
        epoch=conv.epoch,
        ciphertext_size=16,
        chunk_count=1,
        status="complete",
        view_once=True,
        expires_at=timezone.now(),
    )
    m.AttachmentView.objects.create(attachment=attachment, user=bd.user, consumed=True)
    m.AttachmentChunk.objects.create(
        attachment=attachment,
        chunk_index=0,
        ciphertext=b"fixture ciphertext",
        byte_length=18,
        content_hash="a" * 64,
    )
    finalize_accounts(pair, native, [(a, ad), (b, bd)])
    m.NotificationOutbox.objects.update(sent_at=timezone.now())
    call_command("retire_conversations", once=True, stdout=StringIO())
    assert not m.Conversation.objects.filter(pk=conv.pk).exists()
    assert m.AttachmentTombstone.objects.filter(pk=aid).exists()
    assert not m.AttachmentView.objects.exists() and not m.AttachmentChunk.objects.exists()
    assert (journal / (str(conv.pk) + ".json")).exists()
    assert m.StorageUsage.objects.get(pk="retirement-replay").used_bytes > 0
    with pytest.raises(PermissionDenied):
        lifecycle.check_retired_conversation(uuid.uuid4(), conv.group_id)


@pytest.mark.parametrize("pair", [lifecycle.ACCOUNT_POLICY], indirect=True)
def test_journal_write_survives_sql_rollback_and_reconcile_finishes_deletion(pair, native, journal):
    a, ad, b, bd, conv, _ = pair
    finalize_accounts(pair, native, [(a, ad), (b, bd)])
    m.NotificationOutbox.objects.update(sent_at=timezone.now())
    original = QuerySet.delete

    def fail(query):
        if query.model is m.MessageEnvelope:
            raise RuntimeError("injected crash after journal fsync")
        return original(query)

    with patch.object(QuerySet, "delete", fail), pytest.raises(RuntimeError):
        retire_conversation(conv.pk)
    assert m.Conversation.objects.filter(pk=conv.pk).exists()
    assert not m.RetiredConversation.objects.exists()
    with pytest.raises(PermissionDenied):
        lifecycle.write_fence(conv, ad.pk)
    reconcile()
    assert not m.Conversation.objects.filter(pk=conv.pk).exists()
    assert m.RetiredConversation.objects.filter(pk=conv.pk).exists()


@pytest.mark.parametrize("pair", [lifecycle.ACCOUNT_POLICY], indirect=True)
def test_missing_or_corrupt_independent_journal_fails_closed(pair, native, journal):
    (journal / "key.json").write_text('{"payload":{},"mac":"invalid"}')
    with pytest.raises(PermissionDenied):
        lifecycle.check_retired_conversation(uuid.uuid4(), pair[4].group_id)


@pytest.mark.parametrize("pair", [{"policy": lifecycle.ACCOUNT_POLICY, "kind": "group"}], indirect=True)
def test_former_account_can_consent_without_access_to_later_ciphertext(pair, native, journal):
    a, ad, b, bd, conv, _ = pair
    c, cd = bound_client()
    add_member(pair, native, c, cd)
    removed = native(ad, "remove", group_id=conv.group_id, index=2)
    transition = {
        "action": "remove",
        "device_id": str(cd.pk),
        "next_epoch": conv.epoch + 1,
        "members": [x for x in p.roster(conv) if x["id"] != str(cd.pk)],
        "welcome_hash": p.fingerprint(b""),
        "state_hash": removed["state_hash"],
    }
    body = envelope(native, ad, conv, removed["commit"], transition)
    body.update(action="remove", device_id=str(cd.pk))
    response = post(a, f"conversations/{conv.pk}/crypto-events", body)
    assert response.status_code == 201, response.content
    conv.refresh_from_db()
    assert c.get(f"/api/v1/conversations/{conv.pk}/messages", secure=True).status_code == 404
    assert c.get(f"/api/v1/conversations/{conv.pk}/closure/proofs", secure=True).status_code == 200
    assert (
        "ciphertext"
        not in c.get(f"/api/v1/conversations/{conv.pk}/closure/proofs", secure=True).json()["proofs"][0]
    )
    closure = finalize_accounts(pair, native, [(a, ad), (b, bd), (c, cd)])
    assert len(closure.consents) == 3
    m.NotificationOutbox.objects.update(sent_at=timezone.now())
    call_command("retire_conversations", once=True, conversation=str(conv.pk), stdout=StringIO())
    assert m.RetiredConversation.objects.filter(pk=conv.pk).exists()


@pytest.mark.parametrize("pair", [lifecycle.ACCOUNT_POLICY], indirect=True)
def test_journal_reinstalls_deny_markers_after_sql_snapshot_before_creation(pair, native, journal):
    a, ad, b, bd, conv, _ = pair
    finalize_accounts(pair, native, [(a, ad), (b, bd)])
    m.NotificationOutbox.objects.update(sent_at=timezone.now())
    retire_conversation(conv.pk)
    # Simulate an older SQL snapshot with no group or deny markers, preserving
    # the separately protected current journal and its key.
    m.RetiredConversation.objects.all().delete()
    m.RetiredMessage.objects.all().delete()
    m.RetirementReplayKey.objects.all().delete()
    m.StorageUsage.objects.filter(pk__in=["service", "retirement-replay"]).update(used_bytes=0)
    reconcile()
    assert m.RetiredConversation.objects.filter(pk=conv.pk).exists()
    assert m.RetiredMessage.objects.count() == 2
    with pytest.raises(Exception, match="Retired message"):
        lifecycle.check_retired_message(ad.pk, pair[5]["client_message_id"])


def test_normal_product_defaults_are_enabled(client):
    health = client.get("/api/v1/health", secure=True).json()
    assert health["crypto_ready"] and health["experimental_closure"]
    assert health["release_status"] == "ACTIVE_REVIEW_PENDING"


@pytest.mark.parametrize("pair", [lifecycle.ACCOUNT_POLICY], indirect=True)
def test_preparation_fences_other_account_devices_before_global_freeze(pair, native):
    a, ad, b, bd, conv, accepted = pair
    a2, ad2 = bound_client(ad.user)
    add_member(pair, native, a2, ad2)
    propose(pair, native)
    assert prepare(a, ad, conv, native).status_code == 200
    assert m.ConversationClosure.objects.get(conversation=conv).state == "proposed"
    wire = native(
        ad2, "encrypt", group_id=conv.group_id, plaintext="account preparation must stop this device"
    )["ciphertext"]
    assert post(a2, f"conversations/{conv.pk}/messages", envelope(native, ad2, conv, wire)).status_code == 403
    assert prepare(a2, ad2, conv, native).status_code == 403
    assert post(a, f"conversations/{conv.pk}/messages", accepted).status_code == 200


@pytest.mark.parametrize("pair", [lifecycle.ACCOUNT_POLICY], indirect=True)
def test_unauthenticated_restore_dictionary_cannot_bypass_account_consent(pair, native, journal):
    with pytest.raises(PermissionDenied):
        retire_conversation(pair[4].pk, restored_marker={"id": str(pair[4].pk), "group_tag": "0" * 64})
    assert m.Conversation.objects.filter(pk=pair[4].pk).exists()


@pytest.mark.parametrize("pair", [lifecycle.ACCOUNT_POLICY], indirect=True)
def test_replay_budget_blocks_deletion_before_journal_publication(pair, native, journal, settings):
    from rest_framework.exceptions import ValidationError

    a, ad, b, bd, conv, _ = pair
    finalize_accounts(pair, native, [(a, ad), (b, bd)])
    m.NotificationOutbox.objects.update(sent_at=timezone.now())
    settings.MESSAGE_SERVICE_BYTES = 0
    with pytest.raises(ValidationError, match="replay storage budget"):
        retire_conversation(conv.pk)
    assert m.Conversation.objects.filter(pk=conv.pk).exists()
    assert not (journal / (str(conv.pk) + ".json")).exists()


@pytest.mark.parametrize("pair", [lifecycle.ACCOUNT_POLICY], indirect=True)
def test_live_view_once_lease_can_settle_after_finalization_before_deletion(pair, native, journal):
    from datetime import timedelta
    from core.middleware import digest

    a, ad, b, bd, conv, _ = pair
    token = secrets.token_hex(32)
    aid = uuid.uuid4()
    attachment = m.EncryptedAttachment.objects.create(
        id=aid,
        uploader_device=ad,
        conversation=conv,
        epoch=conv.epoch,
        ciphertext_size=16,
        chunk_count=1,
        status="complete",
        view_once=True,
        expires_at=timezone.now() + timedelta(days=1),
    )
    m.AttachmentTombstone.objects.create(pk=aid)
    m.AttachmentView.objects.create(
        attachment=attachment,
        user=bd.user,
        consumed=True,
        opened_by=bd,
        token_hash=digest(token),
        lease_expires_at=timezone.now() + timedelta(minutes=1),
    )
    finalize_accounts(pair, native, [(a, ad), (b, bd)])
    m.NotificationOutbox.objects.update(sent_at=timezone.now())
    with pytest.raises(PermissionDenied, match="lease"):
        retire_conversation(conv.pk)
    assert post(b, f"attachments/{aid}/view-once/close", {"token": token}).status_code == 200
    assert retire_conversation(conv.pk)["changed"]
    assert m.AttachmentTombstone.objects.filter(pk=aid).exists()
