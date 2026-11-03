"""Bounded opt-in closure endpoints. No retirement HTTP endpoint exists."""

import base64
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from . import closure as lifecycle, models as m, serializers as s
from .views import View, trusted_device, data, rate
from .protocol import canonical


def closure_membership(request, cid, lock=False):
    device = trusted_device(request)
    query = m.Conversation.objects.select_for_update() if lock else m.Conversation.objects
    conversation = get_object_or_404(query, pk=cid, membership__device=device)
    member = m.Membership.objects.select_related("device").get(conversation=conversation, device=device)
    member.device = device
    return conversation, member


class ConversationClosure(View):
    def mutation_accounts(self, request, **kwargs):
        lifecycle.feature_gate()
        device = trusted_device(request)
        if not m.Membership.objects.filter(conversation_id=kwargs["cid"], device=device).exists():
            raise PermissionDenied()
        return tuple(
            m.Membership.objects.filter(conversation_id=kwargs["cid"]).values_list(
                "device__user_id", flat=True
            )
        )

    def get(self, request, cid):
        lifecycle.feature_gate()
        rate(request, "closure_read", 60)
        conversation, _ = closure_membership(request, cid)
        lifecycle.eligibility(conversation)
        closure = m.ConversationClosure.objects.filter(conversation=conversation).first()
        if closure:
            lifecycle.validate_closure(conversation, closure, require_final=closure.state == "finalized")
            return Response(lifecycle.closure_json(closure, conversation))
        candidate = None
        if request.query_params.get("nonce"):
            candidate = lifecycle.transcript_for(
                conversation, request.query_params["nonce"], request._request.device.pk
            )
        return Response(
            {
                "state": "active",
                "proposal": None,
                "transcript": candidate,
                "proposal_signature": "",
                "preparations": {},
                "consents": {},
                "final_receipts": {},
            }
        )

    @transaction.atomic(savepoint=False)
    def post(self, request, cid):
        lifecycle.feature_gate()
        rate(request, "closure", 10)
        action = request.query_params.get("action", "propose")
        if action not in ("propose", "prepare", "consent", "receipt"):
            raise ValidationError("Unsupported closure action; reopening/deletion is not available")
        conversation, member = closure_membership(request, cid, lock=True)
        lifecycle.eligibility(conversation)
        did = str(member.device_id)
        closure = m.ConversationClosure.objects.select_for_update().filter(conversation=conversation).first()
        if action == "propose":
            payload = data(request, s.ClosureProposal)
            transcript = payload["transcript"]
            if not isinstance(transcript, dict) or len(canonical(transcript)) > 128 * 1024:
                raise ValidationError("Invalid closure proposal")
            if closure:
                if (
                    transcript != closure.proposal
                    or bytes(closure.proposal_signature) != payload["signature"]
                ):
                    raise ValidationError("Another closure proposal already exists")
            else:
                if (
                    conversation.kind == "group"
                    and not m.Membership.objects.filter(
                        conversation=conversation,
                        device__user_id=request.user.pk,
                        removed_at_epoch=None,
                        role__in=["owner", "moderator"],
                    ).exists()
                ):
                    raise PermissionDenied("A current group owner or moderator must propose closure")
                expected = lifecycle.transcript_for(conversation, transcript.get("nonce"), did)
                if transcript != expected:
                    raise ValidationError("HEAD_CONFLICT: synchronize before proposing closure")
                lifecycle.verify(member.device.public_key, payload["signature"], expected)
                closure = m.ConversationClosure.objects.create(
                    conversation=conversation,
                    proposal=expected,
                    transcript={},
                    proposal_signature=payload["signature"],
                )
                closure.transcript = lifecycle.current_transcript(conversation, closure)
                closure.save(update_fields=["transcript"])
        else:
            closure = get_object_or_404(
                m.ConversationClosure.objects.select_for_update(), conversation=conversation
            )
            lifecycle.validate_closure(conversation, closure, require_final=closure.state == "finalized")
            lifecycle.require_representative(closure, did)
            if action == "prepare":
                payload = data(request, s.ClosureProposal)
                expected = lifecycle.current_transcript(conversation, closure)
                if payload["transcript"] != expected:
                    raise ValidationError("HEAD_CONFLICT: synchronize before preparing closure")
                signature = base64.b64encode(payload["signature"]).decode()
                lifecycle.verify(
                    member.device.public_key,
                    payload["signature"],
                    lifecycle.preparation_payload(expected, did),
                )
                record = {"transcript_hash": lifecycle.transcript_hash(expected), "signature": signature}
                if closure.state != "proposed" and closure.preparations.get(did) != record:
                    raise PermissionDenied("Closure is already frozen")
                closure.preparations = {**closure.preparations, did: record}
                closure.transcript = expected
                if lifecycle.quorum(expected, closure.preparations) and all(
                    x["transcript_hash"] == record["transcript_hash"] for x in closure.preparations.values()
                ):
                    if closure.state == "proposed":
                        closure.state = "closing"
                        conversation.status = "closing"
                        conversation.save(update_fields=["status"])
            elif action == "receipt":
                payload = data(request, s.ClosureFinalReceipt)
                if closure.state != "finalized" or payload["finality_hash"] != lifecycle.finality_hash(
                    closure
                ):
                    raise PermissionDenied("Final certificate mismatch")
                lifecycle.verify(
                    member.device.public_key,
                    payload["signature"],
                    lifecycle.final_receipt_payload(closure, did),
                )
                signature = base64.b64encode(payload["signature"]).decode()
                if did in closure.final_receipts and closure.final_receipts[did] != signature:
                    raise ValidationError("Final receipt is immutable")
                closure.final_receipts = {**closure.final_receipts, did: signature}
            else:
                payload = data(request, s.ClosureConsent)
                if closure.state not in ("closing", "finalized") or payload[
                    "transcript_hash"
                ] != lifecycle.transcript_hash(closure.transcript):
                    raise PermissionDenied("Both devices must prepare the same frozen head")
                acknowledged = m.DeliveryCursor.objects.filter(
                    conversation=conversation, device=member.device, last_acked_seq__gte=conversation.last_seq
                ).exists()
                if not acknowledged and conversation.genesis["closure_policy"] == lifecycle.POLICY:
                    raise PermissionDenied("Persist verified history before archive consent")
                lifecycle.verify(
                    member.device.public_key,
                    payload["signature"],
                    lifecycle.consent_payload(closure.transcript, did, payload["archive_hash"]),
                )
                record = {
                    "archive_hash": payload["archive_hash"],
                    "signature": base64.b64encode(payload["signature"]).decode(),
                }
                if did in closure.consents and closure.consents[did] != record:
                    raise ValidationError("Archive consent is immutable; retry the same persisted request")
                closure.consents = {**closure.consents, did: record}
                if lifecycle.quorum(closure.transcript, closure.consents):
                    closure.state = "finalized"
                    conversation.status = "closed"
                    conversation.save(update_fields=["status"])
            closure.save(update_fields=["transcript", "preparations", "consents", "state", "final_receipts"])
        lifecycle.validate_closure(conversation, closure, require_final=closure.state == "finalized")
        return Response(lifecycle.closure_json(closure, conversation))


class ClosureProofs(View):
    def get(self, request, cid):
        lifecycle.feature_gate()
        conversation, _ = closure_membership(request, cid)
        if conversation.genesis.get("closure_policy") != lifecycle.ACCOUNT_POLICY:
            raise PermissionDenied("Historical finality proofs require the account-wide policy")
        rate(request, "closure_proof", 120)
        try:
            after = max(0, int(request.query_params.get("after_seq", "0")))
        except ValueError:
            raise ValidationError("Invalid proof cursor") from None
        rows = (
            m.MessageEnvelope.objects.filter(conversation=conversation, server_seq__gt=after)
            .defer("ciphertext")
            .order_by("server_seq")[:100]
        )
        return Response(
            {
                "proofs": [lifecycle.proof_json(x) for x in rows],
                "genesis": conversation.genesis,
                "genesis_signature": __import__("base64")
                .b64encode(bytes(conversation.genesis_signature))
                .decode(),
            }
        )


class PendingClosures(View):
    def get(self, request):
        lifecycle.feature_gate()
        device = trusted_device(request)
        from .views import conversation_json

        query = m.Conversation.objects.filter(
            membership__device=device, conversationclosure__isnull=False
        ).distinct()
        after = request.query_params.get("after")
        if after:
            import uuid

            try:
                query = query.filter(pk__gt=uuid.UUID(after))
            except ValueError:
                raise ValidationError("Invalid closure cursor") from None
        rows = list(query.order_by("pk")[:51])
        return Response(
            {
                "items": [conversation_json(x) for x in rows[:50]],
                "next_cursor": str(rows[49].pk) if len(rows) > 50 else None,
            }
        )
