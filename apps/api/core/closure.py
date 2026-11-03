"""Experimental mutual closure. No production deletion or MLS primitive changes."""

import base64
import hashlib
import hmac
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.conf import settings
from django.db import connection
from django.db.models.functions import Length
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import models as m, protocol as p

POLICY = "mutual-local-archive-v1"
MAX_ENVELOPES = 500
MAX_PROOF_BYTES = 512 * 1024


def feature_gate():
    if not settings.CRYPTO_READY or not settings.CONVERSATION_CLOSURE_READY:
        raise PermissionDenied("Experimental conversation closure is disabled")


def write_fence(conversation, device_id=None):
    if conversation.status in ("closing", "closed"):
        raise PermissionDenied(
            "Conversation closure freezes new writes; history and durable ACKs remain available"
        )
    if conversation.genesis.get("closure_policy") == POLICY:
        if conversation.genesis.get("closure_epoch") != settings.CONVERSATION_CLOSURE_EPOCH:
            raise PermissionDenied(
                "Restored closure-capable conversation is read-only; verify recovery before continuing"
            )
        pending = m.ConversationClosure.objects.filter(conversation=conversation, state="proposed").first()
        if pending and str(device_id) in pending.preparations:
            raise PermissionDenied(
                "This device prepared closure; synchronize and finish mutual closure before further writes"
            )


def verify(public_key, signature, payload):
    try:
        wire = base64.b64decode(signature, validate=True) if isinstance(signature, str) else bytes(signature)
        Ed25519PublicKey.from_public_bytes(bytes(public_key)).verify(wire, p.canonical(payload))
    except (ValueError, TypeError, InvalidSignature):
        raise ValidationError("Closure signature rejected") from None


def tag(purpose, value):
    secret = settings.GRAPH_RETIREMENT_REPLAY_SECRET
    if len(secret) < 48 or secret in (
        settings.SECRET_KEY,
        settings.ROUTING_SECRET,
        settings.ROUTING_PREVIOUS_SECRET,
    ):
        raise PermissionDenied("Independent permanent retirement replay secret required")
    binding = m.RetirementReplayKey.objects.filter(pk=1).values_list("commitment", flat=True).first()
    commitment = hmac.new(secret.encode(), b"haven/retirement/key-binding/v1", hashlib.sha256).hexdigest()
    if binding is None and (m.RetiredConversation.objects.exists() or m.RetiredMessage.objects.exists()):
        raise PermissionDenied("Retirement replay key binding is missing; retain fail-closed state")
    if binding is not None and not hmac.compare_digest(binding, commitment):
        raise PermissionDenied("Retirement replay key changed; restore its original protected value")
    return hmac.new(
        secret.encode(), p.canonical(["haven/retirement/replay/v1", purpose, value]), hashlib.sha256
    ).hexdigest()


def check_retired_conversation(cid, group_id):
    if m.RetiredConversation.objects.filter(pk=cid).exists():
        raise PermissionDenied("Retired conversation IDs cannot be reused")
    if m.RetiredConversation.objects.exists():
        if m.RetiredConversation.objects.filter(group_tag=tag("group", group_id)).exists():
            raise PermissionDenied("Retired MLS group IDs cannot be reused")


def check_retired_message(device_id, message_id):
    if (
        m.RetiredMessage.objects.exists()
        and m.RetiredMessage.objects.filter(pk=tag("message", [str(device_id), str(message_id)])).exists()
    ):
        raise ValidationError("Retired message ID cannot be reused by this device")


def proof_rows(conversation):
    rows = list(
        m.MessageEnvelope.objects.filter(conversation=conversation)
        .defer("ciphertext", "request_digest", "received_at")
        .annotate(ciphertext_bytes=Length("ciphertext"))
        .order_by("server_seq")[: MAX_ENVELOPES + 1]
    )
    if len(rows) > MAX_ENVELOPES or len(rows) != conversation.last_seq:
        raise ValidationError("Closure history exceeds the bounded prototype or has a gap")
    return rows


def proof_json(envelope):
    return {
        "id": str(envelope.pk),
        "client_message_id": str(envelope.client_message_id),
        "sender_device": str(envelope.sender_device_id),
        "v": envelope.protocol_version,
        "seq": envelope.server_seq,
        "epoch": envelope.group_epoch,
        "kind": envelope.kind,
        "header": envelope.header,
        "signature": base64.b64encode(bytes(envelope.signature)).decode(),
        "chain_hash": envelope.chain_hash,
    }


def eligibility(conversation):
    if conversation.kind != "direct" or conversation.genesis.get("closure_policy") != POLICY:
        raise ValidationError("Only explicitly opted-in direct conversations support closure")
    if conversation.genesis.get("closure_epoch") != settings.CONVERSATION_CLOSURE_EPOCH:
        raise PermissionDenied("Closure restore epoch changed; keep history and use verified recovery")
    if conversation.status not in ("active", "closing", "closed"):
        raise ValidationError("Resolve rekey/recovery before proposing closure")
    members = list(
        m.Membership.objects.select_related("device__user")
        .only(
            "conversation_id",
            "device_id",
            "removed_at_epoch",
            "leave_signature",
            "role",
            "device__id",
            "device__user_id",
            "device__public_key",
            "device__identity",
            "device__revoked_at",
            "device__trust_state",
            "device__user__id",
            "device__user__is_active",
            "device__user__security_generation",
        )
        .filter(conversation=conversation)
        .order_by("device_id")
    )
    if len(members) != 2 or len({x.device.user_id for x in members}) != 2:
        raise ValidationError("Prototype requires exactly two participant accounts")
    if any(
        x.removed_at_epoch is not None
        or bytes(x.leave_signature)
        or x.device.revoked_at
        or x.device.trust_state != "approved"
        or not x.device.user.is_active
        for x in members
    ):
        raise PermissionDenied("Participant authorization changed; retirement is blocked")
    users = {x.device.user_id for x in members}
    approved = m.Device.objects.filter(user_id__in=users, trust_state="approved", revoked_at=None).count()
    if approved != 2:
        raise ValidationError("Prototype requires one approved device per account")
    if m.EncryptedAttachment.objects.filter(conversation=conversation).exists():
        raise ValidationError("Attachment and view-once obligations block this text-only prototype")
    envelopes = proof_rows(conversation)
    controls = [row.header.get("transition") for row in envelopes if row.kind == "commit"]
    if len([x for x in controls if x and x.get("action") == "add"]) != 1 or any(
        not x or x.get("action") not in ("add", "update") for x in controls
    ):
        raise ValidationError("Membership/authority changes are outside this prototype")
    if sum(len(p.canonical(proof_json(row))) for row in envelopes) > MAX_PROOF_BYTES:
        raise ValidationError("Closure proof archive exceeds bounded size")
    return members, envelopes


def transcript_for(conversation, nonce, proposer, proposal_hash=None):
    members, _ = eligibility(conversation)
    try:
        nonce = str(uuid.UUID(str(nonce)))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid closure nonce") from None
    return {
        **({"proposal_hash": proposal_hash} if proposal_hash else {}),
        "domain": "haven/closure/snapshot/v1" if proposal_hash else "haven/closure/proposal/v1",
        "v": 1,
        "conversation_id": str(conversation.pk),
        "group_id": conversation.group_id,
        "closure_policy": POLICY,
        "restore_epoch": settings.CONVERSATION_CLOSURE_EPOCH,
        "nonce": nonce,
        "proposer_device": str(proposer),
        "genesis_hash": p.chain_hash(conversation.genesis, bytes(conversation.genesis_signature)),
        "final_seq": conversation.last_seq,
        "final_epoch": conversation.epoch,
        "final_hash": conversation.head_hash,
        "archive_policy": "complete-text-history-on-each-device-v1",
        "participants": [
            {
                **p.certificate(row.device),
                "role": row.role,
                "security_generation": row.device.user.security_generation,
            }
            for row in members
        ],
    }


def transcript_hash(transcript):
    return p.fingerprint(p.canonical(transcript))


def consent_payload(transcript, device_id, archive_hash):
    return {
        "domain": "haven/closure/archive-consent/v1",
        "transcript_hash": transcript_hash(transcript),
        "device_id": str(device_id),
        "archive_hash": archive_hash,
    }


def preparation_payload(transcript, device_id):
    return {
        "domain": "haven/closure/prepare/v1",
        "transcript_hash": transcript_hash(transcript),
        "device_id": str(device_id),
    }


def current_transcript(conversation, closure):
    return transcript_for(
        conversation,
        closure.proposal["nonce"],
        closure.proposal["proposer_device"],
        transcript_hash(closure.proposal),
    )


def validate_closure(conversation, closure, require_final=False):
    members, rows = eligibility(conversation)
    proposal = closure.proposal
    expected = transcript_for(conversation, proposal.get("nonce"), proposal.get("proposer_device"))
    # The proposal anchors an earlier verified head; peers may still flush
    # previously queued ciphertext before preparing the common final head.
    seq = proposal.get("final_seq")
    if not isinstance(seq, int) or not 1 <= seq <= len(rows):
        raise ValidationError("Invalid proposal checkpoint")
    anchor = rows[seq - 1]
    expected.update(
        final_seq=seq,
        final_hash=anchor.chain_hash,
        final_epoch=anchor.group_epoch + (anchor.kind == "commit"),
    )
    if proposal != expected:
        raise PermissionDenied("Closure proposal or participant authorization changed")
    by_id = {str(row.device_id): row.device for row in members}
    proposer = by_id.get(proposal["proposer_device"])
    if proposer is None:
        raise PermissionDenied("Unknown closure proposer")
    verify(proposer.public_key, closure.proposal_signature, proposal)
    transcript = current_transcript(conversation, closure)
    if closure.state != "proposed" and closure.transcript != transcript:
        raise PermissionDenied("Frozen closure checkpoint changed; retain history")
    for did, record in closure.preparations.items():
        if did not in by_id or set(record) != {"transcript_hash", "signature"}:
            raise ValidationError("Invalid closure preparation")
        if closure.state != "proposed":
            if record["transcript_hash"] != transcript_hash(transcript):
                raise ValidationError("Devices prepared different closure heads")
        verify(
            by_id[did].public_key,
            record["signature"],
            {
                "domain": "haven/closure/prepare/v1",
                "transcript_hash": record["transcript_hash"],
                "device_id": did,
            },
        )
    for did, record in closure.consents.items():
        if did not in by_id or set(record) != {"archive_hash", "signature"}:
            raise ValidationError("Invalid closure consent set")
        if (
            not isinstance(record["archive_hash"], str)
            or len(record["archive_hash"]) != 64
            or any(c not in "0123456789abcdef" for c in record["archive_hash"])
        ):
            raise ValidationError("Invalid archive commitment")
        verify(
            by_id[did].public_key,
            record["signature"],
            consent_payload(transcript, did, record["archive_hash"]),
        )
    if closure.state != "proposed" and set(closure.preparations) != set(by_id):
        raise PermissionDenied("Both device preparations are required")
    if require_final and (closure.state != "finalized" or set(closure.consents) != set(by_id)):
        raise PermissionDenied("Both device archive consents are required")
    for did, signature in closure.final_receipts.items():
        if closure.state != "finalized" or did not in by_id:
            raise ValidationError("Invalid final certificate receipt set")
        verify(by_id[did].public_key, signature, final_receipt_payload(closure, did))
    return members


def closure_json(closure, conversation=None):
    transcript = (
        current_transcript(conversation, closure)
        if conversation and closure.state == "proposed"
        else closure.transcript
    )
    return {
        "state": closure.state,
        "proposal": closure.proposal,
        "transcript": transcript,
        "proposal_signature": base64.b64encode(bytes(closure.proposal_signature)).decode(),
        "preparations": closure.preparations,
        "consents": closure.consents,
        "final_receipts": closure.final_receipts,
    }


def synthetic_guard(nonce):
    feature_gate()
    if not settings.GRAPH_RETIREMENT_SYNTHETIC_ONLY or not settings.CONVERSATION_CLOSURE_READY:
        raise PermissionDenied("Graph retirement is restricted to explicit synthetic fixtures")
    config = connection.settings_dict
    if not config["NAME"].startswith("test_") or config["HOST"] != "127.0.0.1" or len(nonce) < 32:
        raise PermissionDenied("Disposable loopback test database required")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_database(), shobj_description(oid, 'pg_database') FROM pg_database WHERE datname=current_database()"
        )
        actual, comment = cursor.fetchone()
    if actual != config["NAME"] or comment != "HAVEN-DISPOSABLE-GRAPH:" + nonce:
        raise PermissionDenied("Disposable database marker does not match")


def finality_hash(closure):
    certificate = closure_json(closure)
    certificate.pop("final_receipts")
    return p.fingerprint(p.canonical(certificate))


def final_receipt_payload(closure, device_id):
    return {
        "domain": "haven/closure/final-certificate-receipt/v1",
        "finality_hash": finality_hash(closure),
        "device_id": str(device_id),
    }


def validate_final_receipts(conversation, closure):
    members = validate_closure(conversation, closure, require_final=True)
    by_id = {str(row.device_id): row.device for row in members}
    if set(closure.final_receipts) != set(by_id):
        raise PermissionDenied("Both devices must durably retain the complete final certificate")
    for did, signature in closure.final_receipts.items():
        verify(by_id[did].public_key, signature, final_receipt_payload(closure, did))


def creation_fence(cid, group_id):
    # Serialization only, never a privacy alias. Lock both scopes before checking
    # reuse markers so deletion cannot race a create under a different account.
    values = [
        int.from_bytes(
            hashlib.sha256(p.canonical(["haven/conversation-create/v1", kind, str(value)])).digest()[:8],
            "big",
            signed=True,
        )
        for kind, value in (("conversation", cid), ("group", group_id))
    ]
    with connection.cursor() as cursor:
        for value in sorted(set(values)):
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [value])
