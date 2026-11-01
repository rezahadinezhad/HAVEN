import time
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.core.cache import cache
from core.retention import cleanup


class Command(BaseCommand):
    help = "Five-minute retention worker; independent of notification delivery"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            try:
                counts = cleanup()
                # Only aggregate status, no identities, paths or message IDs.
                cache.set("privacy:maintenance", {"status": "ok", "counts": counts}, timeout=900)
                self.stdout.write("Privacy maintenance completed")
            except Exception:
                try:
                    cache.set("privacy:maintenance", {"status": "unavailable"}, timeout=900)
                except Exception:
                    pass  # Redis can be unavailable too; stale status expires.
                self.stderr.write("Privacy maintenance unavailable; inspect aggregate health")
                if options["once"]:
                    raise SystemExit(1) from None
            if options["once"]:
                return
            time.sleep(300)
