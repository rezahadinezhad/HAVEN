from django.core.management.base import BaseCommand, CommandError
from core.retirement_journal import initialize


class Command(BaseCommand):
    help = "Initialize an independent journal ONLY for a new installation; never after data loss"

    def add_arguments(self, parser):
        parser.add_argument("--new-installation", action="store_true")

    def handle(self, *args, **options):
        if not options["new_installation"]:
            raise CommandError(
                "Use --new-installation only during initial setup; restore a missing established journal"
            )
        initialize()
        self.stdout.write("Independent retirement journal initialized")
