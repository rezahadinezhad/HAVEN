"""Transactional logical storage budgets. Never discard unacknowledged ciphertext."""

from django.conf import settings
from django.db.models import F
from django.db.models.functions import Greatest
from rest_framework.exceptions import Throttled
from .models import StorageUsage

CONVERSATION_OVERHEAD = 4096


def account_key(uid):
    return f"account:{uid}"


def reserve(uid, size, pending=0, envelopes=0, conversations=0):
    # Caller holds its conversation lock (if any). Lock budget rows in the same
    # order for sends, creation and retirement; never acquire a User lock here.
    keys = [account_key(uid), "service"]
    for key in keys:
        StorageUsage.objects.get_or_create(key=key)
    rows = list(StorageUsage.objects.select_for_update().filter(key__in=keys).order_by("key"))
    for row in rows:
        service = row.key == "service"
        if (
            row.used_bytes + size
            > (settings.MESSAGE_SERVICE_BYTES if service else settings.MESSAGE_ACCOUNT_BYTES)
            or (not service and row.pending_bytes + pending > settings.MESSAGE_ACCOUNT_PENDING_BYTES)
            or row.envelope_count + envelopes
            > (settings.MESSAGE_SERVICE_ENVELOPES if service else settings.MESSAGE_ACCOUNT_ENVELOPES)
            or (not service and row.conversation_count + conversations > settings.MAX_OWNED_CONVERSATIONS)
        ):
            raise Throttled(
                detail="Storage budget reached. Delivery remains durable; contact the operator.", wait=300
            )
    for row in rows:
        row.used_bytes += size
        row.pending_bytes += pending
        row.envelope_count += envelopes
        row.conversation_count += conversations
        row.save()


def release_ciphertexts(charges):
    totals = {}
    for uid, size in charges:
        for key in (account_key(uid), "service"):
            totals[key] = totals.get(key, 0) + size
    # Lock all accounts before service, matching reserve(). Releasing several
    # senders in one transaction must not hold service while waiting on an account.
    list(StorageUsage.objects.select_for_update().filter(key__in=totals).order_by("key"))
    for key in sorted(totals):
        size = totals[key]
        StorageUsage.objects.filter(key=key).update(
            used_bytes=Greatest(0, F("used_bytes") - size),
            pending_bytes=Greatest(0, F("pending_bytes") - size),
        )
