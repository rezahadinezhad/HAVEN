import re
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from core.models import BackupManifest, SoftwareRelease


class Command(BaseCommand):
    help = "Record verified operational metadata; does not itself verify signatures or backups"

    def add_arguments(self, parser):
        parser.add_argument("kind", choices=["backup", "restored", "release"])
        parser.add_argument("checksum")
        parser.add_argument("--reference", required=True)
        parser.add_argument("--release-version")

    def handle(self, *args, **options):
        checksum = options["checksum"]
        reference = options["reference"]
        if not re.fullmatch(r"[0-9a-f]{64}", checksum) or not re.fullmatch(
            r"[a-zA-Z0-9_.:/-]{1,100}", reference
        ):
            raise CommandError("Expected checksum and opaque reference; never pass keys or credentials")
        if options["kind"] == "backup":
            BackupManifest.objects.get_or_create(
                encrypted_checksum=checksum, defaults={"location": reference}
            )
        elif options["kind"] == "restored":
            if not BackupManifest.objects.filter(encrypted_checksum=checksum).update(
                tested_restore_at=timezone.now()
            ):
                raise CommandError("Unknown backup checksum")
        else:
            if not options["release_version"] or not re.fullmatch(
                r"[a-zA-Z0-9_.-]{1,40}", options["release_version"]
            ):
                raise CommandError("Release version required")
            SoftwareRelease.objects.update_or_create(
                version=options["release_version"],
                defaults={
                    "manifest_hash": checksum,
                    "signing_public_key_ref": reference,
                    "build_timestamp": timezone.now(),
                    "status": "operator_verified_unreviewed",
                },
            )
        self.stdout.write("Operational evidence metadata recorded; no independent certification implied.")
