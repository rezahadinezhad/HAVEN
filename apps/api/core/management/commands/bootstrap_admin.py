import sys
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from core.models import User


class Command(BaseCommand):
    help = "Idempotent initial superadmin; password from stdin or protected secret file"

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--secret-file")

    def handle(self, *args, **options):
        username = options["username"]
        if User.objects.filter(username=username).exists():
            self.stdout.write("Account exists; no credentials changed")
            return
        if User.objects.exists():
            raise CommandError("Initial bootstrap is closed")
        if options["secret_file"]:
            import os
            import stat

            p = options["secret_file"]
            if stat.S_IMODE(os.stat(p).st_mode) & 0o077:
                raise CommandError("Secret file must be mode 0600")
            with open(p) as stream:
                secret = stream.read().rstrip("\n")
        else:
            secret = sys.stdin.readline().rstrip("\n")
        user = User(
            username=username, display_name=username, role="superadmin", is_staff=True, is_superuser=True
        )
        try:
            validate_password(secret, user)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from None
        user.set_password(secret)
        user.save()
        self.stdout.write("Initial superadmin created")
