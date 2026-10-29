from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Fail closed if PostgreSQL is configured to acknowledge nondurable writes"

    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            values = {}
            for name in ["fsync", "synchronous_commit", "full_page_writes", "data_checksums"]:
                cursor.execute("SHOW " + name)
                values[name] = cursor.fetchone()[0]
        if (
            values["fsync"] != "on"
            or values["synchronous_commit"] != "on"
            or values["full_page_writes"] != "on"
        ):
            raise CommandError("Unsafe PostgreSQL durability settings; migration/startup refused")
        self.stdout.write(str(values))
