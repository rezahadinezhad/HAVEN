import time
import asyncio
from channels.layers import channel_layers
from django.core.management.base import BaseCommand
from django.db import transaction, close_old_connections, connection
from django.db.models import F
from django.utils import timezone
from core.models import NotificationOutbox
from core.privacy import routing_groups


class Command(BaseCommand):
    help = "At-least-once durable notification hints; clients use HTTP sync after any gap"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    @staticmethod
    async def notify(layer, users):
        for uid in users:
            for group in routing_groups(uid):
                await layer.group_send(group, {"type": "sync.hint"})

    def publish_batch(self, layer, runner):
        with transaction.atomic():
            rows = list(
                NotificationOutbox.objects.select_for_update(skip_locked=True)
                .filter(sent_at=None)
                .only("id", "envelope_id", "sent_at", "attempts")[:100]
            )
            if not rows:
                return 0
            with connection.cursor() as cursor:
                # The worker login cannot query the underlying graph tables.
                cursor.execute(
                    "SELECT DISTINCT user_id FROM haven_notification_targets WHERE outbox_id = ANY(%s)",
                    [[row.pk for row in rows]],
                )
                users = [uid for (uid,) in cursor.fetchall()]
            # A hint means "sync", not "one message". Coalesce each account's
            # hints, but mark every claimed outbox row only after all sends.
            # Failure rolls the whole batch back; duplicate retry hints are safe.
            runner.run(self.notify(layer, users))
            NotificationOutbox.objects.filter(pk__in=[row.pk for row in rows]).update(
                sent_at=timezone.now(), attempts=F("attempts") + 1
            )
            return len(rows)

    def handle(self, *args, **opts):
        # Own the backend and one loop for the command's entire lifetime.
        # Reuse Redis transports without touching an API process's loop/cache.
        layer = channel_layers.make_backend("default")
        with asyncio.Runner() as runner:
            try:
                while True:
                    try:
                        count = self.publish_batch(layer, runner)
                    except Exception:
                        self.stderr.write("Notification unavailable; HTTP sync remains authoritative")
                        close_old_connections()
                        count = 0
                    if opts["once"]:
                        break
                    if not count:
                        time.sleep(0.5)
            finally:
                close = getattr(layer, "close_pools", None)
                if close is not None:
                    runner.run(close())
