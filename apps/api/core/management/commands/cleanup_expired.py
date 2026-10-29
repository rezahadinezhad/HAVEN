from django.core.management.base import BaseCommand
from core.retention import cleanup


class Command(BaseCommand):
    help = "Minimize retained delivery data without discarding unread ciphertext or MLS proofs"

    def handle(self, *args, **options):
        counts = cleanup()
        self.stdout.write("Retention cleanup: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
