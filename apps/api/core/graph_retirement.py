"""Account-authorized graph retirement with an independent durable deny journal."""

from collections import defaultdict
import hashlib
import hmac
from django.db import transaction
from django.conf import settings
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import closure as lifecycle, models as m, protocol as p
from .storage import account_key, CONVERSATION_OVERHEAD


def retirement_plan(conversation):
    closure = m.ConversationClosure.objects.get(conversation=conversation)
    members = lifecycle.validate_closure(conversation, closure, require_final=True)
    lifecycle.validate_final_receipts(conversation, closure)
    if conversation.status != "closed":
        raise PermissionDenied("Conversation is not closed")
    if conversation.genesis["closure_policy"] == lifecycle.POLICY and any(
        not m.DeliveryCursor.objects.filter(
            conversation=conversation, device_id=x.device_id, last_acked_seq__gte=conversation.last_seq
        ).exists()
        for x in members
    ):
        raise PermissionDenied("All final durable ACKs are required")
    if m.NotificationOutbox.objects.filter(envelope__conversation=conversation, sent_at=None).exists():
        raise PermissionDenied("Pending notification delivery must finish first")
    if m.AuditEvent.objects.filter(
        target_opaque_id__in=[str(conversation.pk), conversation.group_id]
    ).exists():
        raise PermissionDenied("Retained security audit still references this conversation")
    devices = [row.device_id for row in members]
    if (
        conversation.genesis["closure_policy"] == lifecycle.POLICY
        and m.DeviceKeyPackage.objects.filter(
            device_id__in=devices, claimed_by_id__in=devices, expires_at__gt=timezone.now()
        ).exists()
    ):
        raise PermissionDenied("A live KeyPackage claim still links the participants")
    attachments = m.EncryptedAttachment.objects.filter(conversation=conversation)
    if (
        attachments.filter(status="uploading").exists()
        or m.AttachmentView.objects.filter(
            attachment__conversation=conversation, lease_expires_at__gt=timezone.now()
        ).exists()
    ):
        raise PermissionDenied("Pending upload or active view-once lease must settle before retirement")
    rows, charges, tags, devices = storage_plan(conversation)
    return closure, rows, charges, tags, devices


def storage_plan(conversation):
    devices = list(m.Membership.objects.filter(conversation=conversation).values_list("device_id", flat=True))
    rows = lifecycle.proof_rows(conversation)
    charges = defaultdict(
        lambda: {"used_bytes": 0, "pending_bytes": 0, "envelope_count": 0, "conversation_count": 0}
    )
    owners = dict(m.Device.objects.filter(pk__in=devices).values_list("id", "user_id"))

    def charge(uid, **values):
        for key in (account_key(uid), "service"):
            for name, amount in values.items():
                charges[key][name] += amount

    charge(conversation.creator.user_id, used_bytes=CONVERSATION_OVERHEAD, conversation_count=1)
    message_tags = []
    for row in rows:
        size = row.ciphertext_bytes + len(p.canonical(row.header)) + len(bytes(row.signature)) + 4096
        pending = row.ciphertext_bytes if row.kind == "application" else 0
        if row.kind == "commit":
            event = m.CryptoControlEvent.objects.get(envelope=row)
            size += len(p.canonical(event.transition)) + len(bytes(event.welcome))
        charge(owners[row.sender_device_id], used_bytes=size, pending_bytes=pending, envelope_count=1)
        message_tags.append(lifecycle.tag("message", [str(row.sender_device_id), str(row.client_message_id)]))
    return rows, dict(charges), message_tags, devices


def retire_synthetic_conversation(cid, *, fixture_nonce):
    return retire_conversation(cid, fixture_nonce=fixture_nonce)


@transaction.atomic
def retire_conversation(cid, *, fixture_nonce=None, restored_marker=None):
    lifecycle.feature_gate()
    synthetic = fixture_nonce is not None
    if synthetic:
        lifecycle.synthetic_guard(fixture_nonce)
    if restored_marker is not None:
        from .retirement_journal import read, root

        if read(root() / (str(cid) + ".json")) != restored_marker:
            raise PermissionDenied("Restore authority must match the independently authenticated journal")
    if not synthetic and not settings.GRAPH_RETIREMENT_READY:
        raise PermissionDenied("Conversation retirement is unavailable")
    if m.RetiredConversation.objects.filter(pk=cid).exists():
        return {"state": "retired", "changed": False}
    # Same global account -> conversation -> storage ordering as normal writes.
    users = list(m.Membership.objects.filter(conversation_id=cid).values_list("device__user_id", flat=True))
    list(m.User.objects.select_for_update().filter(pk__in=users).order_by("pk").values_list("pk", flat=True))
    if m.RetiredConversation.objects.filter(pk=cid).exists():
        return {"state": "retired", "changed": False}
    group_id = m.Conversation.objects.values_list("group_id", flat=True).get(pk=cid)
    lifecycle.creation_fence(cid, group_id)
    if m.RetiredConversation.objects.filter(pk=cid).exists():
        return {"state": "retired", "changed": False}
    conversation = m.Conversation.objects.select_for_update().select_related("creator").get(pk=cid)
    if (
        not synthetic
        and restored_marker is None
        and conversation.genesis.get("closure_policy") != lifecycle.ACCOUNT_POLICY
    ):
        raise PermissionDenied("Legacy closure did not authorize normal-product server deletion")
    if restored_marker is None:
        closure, rows, charges, tags, devices = retirement_plan(conversation)
    else:
        marker = restored_marker
        if lifecycle.tag("group", conversation.group_id) != marker["group_tag"]:
            raise PermissionDenied("Restored conversation contradicts permanent journal")
        expected = (
            marker["genesis_hash"]
            if conversation.last_seq == 0
            else (
                marker["heads"][conversation.last_seq - 1]
                if conversation.last_seq <= len(marker["heads"])
                else None
            )
        )
        if expected != conversation.head_hash:
            raise PermissionDenied("Restored conversation is not a prefix of the retired history")
        closure = m.ConversationClosure.objects.filter(conversation=conversation).first()
        rows, charges, tags, devices = storage_plan(conversation)
    replay_bytes = (
        0
        if synthetic
        else 8192
        + 512 * len(tags)
        + 256 * m.EncryptedAttachment.objects.filter(conversation=conversation).count()
    )
    if restored_marker:
        replay_bytes = restored_marker["replay_bytes"]
    if not synthetic:
        m.StorageUsage.objects.get_or_create(key="retirement-replay")
        charges.setdefault("retirement-replay", {})
    budgets = {
        row.key: row
        for row in m.StorageUsage.objects.select_for_update().filter(key__in=charges).order_by("key")
    }
    for key, amounts in charges.items():
        if key not in budgets or any(
            getattr(budgets[key], name) < amount for name, amount in amounts.items()
        ):
            raise ValidationError("Accounting cannot be reconciled exactly; retain the graph")
    if (
        not synthetic
        and budgets["service"].used_bytes - charges["service"]["used_bytes"] + replay_bytes
        > settings.MESSAGE_SERVICE_BYTES
    ):
        raise ValidationError("Permanent replay storage budget reached; retain the conversation")
    # Standard expired-package minimization; keep permanent digest reuse markers.
    m.DeviceKeyPackage.objects.filter(
        device_id__in=devices, claimed_by_id__in=devices, expires_at__lte=timezone.now()
    ).update(package=b"", device=None, claimed_by=None, consumed_at=None)
    secret = settings.GRAPH_RETIREMENT_REPLAY_SECRET
    commitment = hmac.new(secret.encode(), b"haven/retirement/key-binding/v1", hashlib.sha256).hexdigest()
    binding, _ = m.RetirementReplayKey.objects.get_or_create(pk=1, defaults={"commitment": commitment})
    if not hmac.compare_digest(binding.commitment, commitment):
        raise PermissionDenied("Retirement replay key mismatch")
    marker = restored_marker or {
        "id": str(cid),
        "group_tag": lifecycle.tag("group", conversation.group_id),
        "finality_digest": p.fingerprint(p.canonical(lifecycle.closure_json(closure))),
        "message_tags": tags,
        "heads": [x.chain_hash for x in rows],
        "genesis_hash": p.chain_hash(conversation.genesis, bytes(conversation.genesis_signature)),
        "replay_bytes": replay_bytes,
        "attachment_ids": [
            str(x)
            for x in m.EncryptedAttachment.objects.filter(conversation=conversation).values_list(
                "id", flat=True
            )
        ],
    }
    if not synthetic and restored_marker is None:
        from .retirement_journal import persist

        persist(marker)
    m.RetiredConversation.objects.create(
        id=cid, group_tag=marker["group_tag"], finality_digest=marker["finality_digest"]
    )
    m.RetiredMessage.objects.bulk_create(
        [m.RetiredMessage(tag=tag) for tag in marker["message_tags"]], ignore_conflicts=True
    )
    attachment_ids = list(
        m.EncryptedAttachment.objects.filter(conversation=conversation).values_list("pk", flat=True)
    )
    m.AttachmentTombstone.objects.bulk_create(
        [m.AttachmentTombstone(id=aid) for aid in {*attachment_ids, *marker.get("attachment_ids", [])}],
        ignore_conflicts=True,
    )
    m.EncryptedAttachment.objects.filter(pk__in=attachment_ids).delete()
    ids = [row.pk for row in rows]
    m.NotificationOutbox.objects.filter(envelope_id__in=ids).delete()
    m.CryptoControlEvent.objects.filter(envelope_id__in=ids).delete()
    m.MessageEnvelope.objects.filter(pk__in=ids).delete()
    m.DeliveryCursor.objects.filter(conversation=conversation).delete()
    m.Membership.objects.filter(conversation=conversation).delete()
    if closure:
        closure.delete()
    conversation.delete()
    for key, amounts in charges.items():
        if amounts:
            m.StorageUsage.objects.filter(pk=key).update(
                **{name: F(name) - amount for name, amount in amounts.items()}
            )
    if replay_bytes:
        m.StorageUsage.objects.filter(pk__in=["service", "retirement-replay"]).update(
            used_bytes=F("used_bytes") + replay_bytes
        )
    return {
        "state": "retired",
        "changed": True,
        "envelopes": len(rows),
        "direct_membership_edges_removed": len(devices),
    }
