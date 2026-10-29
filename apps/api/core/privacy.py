"""Bounded policy and non-reversible cache labels; never message cryptography."""

import hashlib
import hmac
import json
from django.conf import settings


def rate_key(category, identity, minute):
    # The secret is outside Redis/DB. A plain SHA256(IP) is enumerable offline.
    value = json.dumps(["haven/rate/v1", category, str(identity), minute], separators=(",", ":"))
    tag = hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"rate:{minute}:{tag}"


def policy():
    return {
        "delivered_ciphertext_grace_hours": settings.DELIVERED_CIPHERTEXT_GRACE_HOURS,
        "attachment_days": settings.ATTACHMENT_RETENTION_DAYS,
        "abandoned_upload_hours": 1,
        "audit_days": settings.AUDIT_RETENTION_DAYS,
        "cleanup_interval_seconds": 300,
        "unsynced_ciphertext_expires": False,
        "signed_history_retained": True,
        "accounts_and_membership_retained": True,
        "ingress_observes_ip": True,
        "independent_review": False,
    }
