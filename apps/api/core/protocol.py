"""Public delivery authentication. MLS secrets are exclusively client-side."""

import base64
import hashlib
import json
import subprocess
import rfc8785
from django.conf import settings
from rest_framework.exceptions import ValidationError


def canonical(value):
    try:
        return rfc8785.dumps(value)
    except (ValueError, TypeError):
        raise ValidationError("Invalid canonical value") from None


def fingerprint(value):
    return hashlib.sha256(value).hexdigest()


def chain_hash(header, signature):
    return fingerprint(canonical({"header": header, "signature": base64.b64encode(signature).decode()}))


def public_validate(**command):
    # No shell, fixed executable, bounded stdin/stdout and deadline. Inputs are public MLS structures only.
    try:
        result = subprocess.run(
            [settings.MLS_PUBLIC_VERIFIER],
            input=json.dumps(command).encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=True,
        )
        if len(result.stdout) > 1000:
            raise ValueError()
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ValidationError("MLS public structure rejected") from None


def certificate(device):
    return {
        "id": str(device.pk),
        "user_id": str(device.user_id),
        "identity": device.identity,
        "public_key": base64.b64encode(bytes(device.public_key)).decode(),
    }


def roster(conversation):
    from .models import Membership

    return sorted(
        [
            {**certificate(m.device), "role": m.role}
            for m in Membership.objects.select_related("device").filter(
                conversation=conversation, removed_at_epoch=None
            )
        ],
        key=lambda x: x["id"],
    )
