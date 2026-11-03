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
        "mutual_account_retirement": settings.GRAPH_RETIREMENT_READY,
        "retirement_scope": "all-affected-accounts-one-approved-participating-device-per-account",
        "archive_scope": "available-device-history-with-explicit-account-wide-release",
    }


def routing_groups(account_id):
    """Consumers join current only; publishers use both keys during rotation."""
    import uuid
    from django.core.exceptions import ImproperlyConfigured

    keys = [settings.ROUTING_SECRET, settings.ROUTING_PREVIOUS_SECRET]
    if len(keys[0]) < 48 or any(key and len(key) < 48 for key in keys):
        raise ImproperlyConfigured("Configure independent routing secrets >=48 characters")
    if any(key == settings.SECRET_KEY for key in keys if key):
        raise ImproperlyConfigured("Routing secrets must differ from the application signing key")
    value = b"haven/channels/account/v1\x00" + uuid.UUID(str(account_id)).bytes
    return tuple(
        dict.fromkeys(
            "route." + hmac.new(key.encode(), value, hashlib.sha256).hexdigest() for key in keys if key
        )
    )
