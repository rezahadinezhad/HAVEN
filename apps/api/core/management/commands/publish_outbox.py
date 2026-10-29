import time
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from core.models import NotificationOutbox, Membership


class Command(BaseCommand):
    help = "At-least-once durable notification hints; clients use HTTP sync after any gap"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **opts):
        layer = get_channel_layer()
        while True:
            try:
                with transaction.atomic():
                    rows = (
                        NotificationOutbox.objects.select_for_update(skip_locked=True)
                        .filter(sent_at=None)
                        .select_related("envelope")[:100]
                    )
                    for row in rows:
                        users = (
                            Membership.objects.filter(
                                conversation_id=row.envelope.conversation_id, removed_at_epoch=None
                            )
                            .values_list("device__user_id", flat=True)
                            .distinct()
                        )
                        for uid in users:
                            async_to_sync(layer.group_send)("user." + str(uid), {"type": "sync.hint"})
                        row.sent_at = timezone.now()
                        row.attempts = F("attempts") + 1
                        row.save()
            except Exception:
                self.stderr.write("Notification unavailable; HTTP sync remains authoritative")
            if opts["once"]:
                break
            time.sleep(2)
