"""Opaque view-once access state. Never accepts media decryption keys or plaintext.

Call finish_if_consumed only while holding the attachment row lock. Opening is
consumed before download, not a claim that a human actually saw any pixels.
"""

from django.utils import timezone
from . import models as m


def finish_if_consumed(attachment):
    if not attachment.view_once or attachment.status != "complete":
        return
    views = attachment.views.all()
    if views.filter(consumed=False).exists():
        return
    if views.filter(lease_expires_at__gt=timezone.now()).exists():
        return
    m.AttachmentChunk.objects.filter(attachment=attachment).delete()
    attachment.status = "consumed"
    attachment.save(update_fields=["status"])
    # The attachment-level consumed marker and ID tombstone prevent reopening.
    # Individual recipient/device/opening records are no longer necessary.
    views.delete()
