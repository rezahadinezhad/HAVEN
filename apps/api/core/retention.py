"""Logical retention, not physical erasure. MLS proofs/control messages stay intact."""

from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from . import models as m
from .attachment_lifecycle import finish_if_consumed
from .storage import release_ciphertexts
from django.db.models.functions import Length


def retire_delivered(now, batch_size=500):
    # Nested OuterRef refers to the envelope, not the membership. Every eligible
    # device must ACK its own durable vault transaction; an account ACK is insufficient.
    acknowledged = m.DeliveryCursor.objects.filter(
        conversation_id=OuterRef("conversation_id"),
        device_id=OuterRef("device_id"),
        last_acked_seq__gte=OuterRef(OuterRef("server_seq")),
    )
    waiting = (
        m.Membership.objects.filter(
            conversation_id=OuterRef("conversation_id"),
            valid_from_epoch__lte=OuterRef("group_epoch"),
            start_seq__lt=OuterRef("server_seq"),
            removed_at_epoch=None,
            device__trust_state="approved",
            device__revoked_at=None,
            device__user__is_active=True,
        )
        .annotate(acknowledged=Exists(acknowledged))
        .filter(acknowledged=False)
    )
    eligible = (
        m.MessageEnvelope.objects.filter(
            kind="application",
            ciphertext_retired=False,
            received_at__lte=now - timedelta(hours=settings.DELIVERED_CIPHERTEXT_GRACE_HOURS),
        )
        .annotate(waiting=Exists(waiting))
        .filter(waiting=False)
    )
    candidates = list(eligible.order_by("server_seq").values_list("pk", "conversation_id")[:batch_size])
    by_conversation = {}
    for eid, cid in candidates:
        by_conversation.setdefault(cid, []).append(eid)
    retired = 0
    for cid, ids in by_conversation.items():
        with transaction.atomic():
            # Same lock as membership transitions, sends, and ACKs. Recheck after
            # acquiring it: an approval/change could have introduced another device.
            m.Conversation.objects.select_for_update().get(pk=cid)
            releasing = list(
                eligible.filter(pk__in=ids)
                .annotate(size=Length("ciphertext"))
                .values_list("sender_device__user_id", "size")
            )
            retired += eligible.filter(pk__in=ids).update(
                ciphertext=b"",
                received_at=None,
                ciphertext_retired=True,
            )
            release_ciphertexts(releasing)
    return retired


def delete_batch(query, batch_size):
    ids = list(query.order_by("pk").values_list("pk", flat=True)[:batch_size])
    if ids:
        query.model.objects.filter(pk__in=ids).delete()
    return len(ids)


def cleanup(batch_size=500):
    now = timezone.now()
    counts = {}
    expired_views = list(
        m.EncryptedAttachment.objects.filter(
            view_once=True,
            status="complete",
            views__consumed=True,
            views__lease_expires_at__lte=now,
        )
        .values_list("pk", flat=True)
        .distinct()[:batch_size]
    )
    for aid in expired_views:
        with transaction.atomic():
            a = m.EncryptedAttachment.objects.select_for_update().filter(pk=aid).first()
            if a:
                # Ended capabilities cannot be used again; retain only the boolean
                # consumption ledger while another recipient still has an opening.
                a.views.filter(consumed=True, lease_expires_at__lte=now).update(
                    token_hash="",
                    opened_by=None,
                    lease_expires_at=None,
                )
                finish_if_consumed(a)
    counts["attachments"] = delete_batch(
        m.EncryptedAttachment.objects.filter(
            Q(expires_at__lte=now)
            | Q(status="uploading", created_at__lte=now - timedelta(hours=1))
            | Q(status="deleted")
        ),
        batch_size,
    )
    counts["challenges"] = delete_batch(
        m.RecoveryChallenge.objects.filter(Q(expires_at__lte=now) | Q(consumed_at__isnull=False)), batch_size
    )
    counts["sessions"] = delete_batch(
        m.Session.objects.filter(Q(expires_at__lte=now) | Q(revoked_at__isnull=False)), batch_size
    )
    counts["invitations"] = delete_batch(
        m.Invitation.objects.filter(
            Q(expires_at__lte=now) | Q(revoked_at__isnull=False) | Q(consumed_at__isnull=False)
        ),
        batch_size,
    )
    counts["audit"] = delete_batch(
        m.AuditEvent.objects.filter(
            Q(timestamp__lt=now - timedelta(days=settings.AUDIT_RETENTION_DAYS)) | Q(category="login")
        ),
        batch_size,
    )
    counts["notifications"] = delete_batch(
        m.NotificationOutbox.objects.filter(sent_at__lte=now - timedelta(hours=1)), batch_size
    )
    # Claims must remain retryable until expiry. Digest tombstones are not deleted.
    expired = list(
        m.DeviceKeyPackage.objects.filter(expires_at__lte=now)
        .exclude(package=b"")
        .values_list("pk", flat=True)[:batch_size]
    )
    counts["packages"] = m.DeviceKeyPackage.objects.filter(pk__in=expired).update(
        package=b"",
        claimed_by=None,
        consumed_at=None,
    )
    counts["ciphertexts"] = retire_delivered(now, batch_size)
    return counts
