"""Bounded opt-in closure endpoints. No retirement HTTP endpoint exists."""

import base64
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from . import closure as lifecycle, models as m, serializers as s
from .views import View, trusted_device, membership, data, rate
from .protocol import canonical


class ConversationClosure(View):
    def mutation_accounts(self, request, **kwargs):
        lifecycle.feature_gate()
        device = trusted_device(request)
        if not m.Membership.objects.filter(
            conversation_id=kwargs["cid"], device=device, removed_at_epoch=None
        ).exists():
            raise PermissionDenied()
        return tuple(
            m.Membership.objects.filter(conversation_id=kwargs["cid"]).values_list(
                "device__user_id", flat=True
            )
        )

    def get(self, request, cid):
        lifecycle.feature_gate()
        rate(request, "closure_read", 60)
        conversation, _ = membership(request, cid)
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
        conversation, member = membership(request, cid, lock=True, control=True, allow_closure=True)
        lifecycle.eligibility(conversation)
        did = str(member.device_id)
        closure = m.ConversationClosure.objects.select_for_update().filter(conversation=conversation).first()
        if action == "propose":
            payload = data(request, s.ClosureProposal)
            transcript = payload["transcript"]
            if not isinstance(transcript, dict) or len(canonical(transcript)) > 8192:
                raise ValidationError("Invalid closure proposal")
            if closure:
                if (
                    transcript != closure.proposal
                    or bytes(closure.proposal_signature) != payload["signature"]
                ):
                    raise ValidationError("Another closure proposal already exists")
            else:
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
                participants = {item["id"] for item in expected["participants"]}
                if set(closure.preparations) == participants and all(
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
                if not acknowledged:
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
                if len(closure.consents) == 2:
                    closure.state = "finalized"
                    conversation.status = "closed"
                    conversation.save(update_fields=["status"])
            closure.save(update_fields=["transcript", "preparations", "consents", "state", "final_receipts"])
        lifecycle.validate_closure(conversation, closure, require_final=closure.state == "finalized")
        return Response(lifecycle.closure_json(closure, conversation))
