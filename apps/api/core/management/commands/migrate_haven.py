import os
from psycopg import sql
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verify actual PostgreSQL durability before applying migrations"

    def handle(self, *args, **kwargs):
        call_command("verify_durability")
        call_command("migrate", interactive=False)
        # Default privileges cover newly created tables; the runtime must never edit migration history.
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("REVOKE INSERT, UPDATE, DELETE ON public.django_migrations FROM {}").format(
                    sql.Identifier(os.environ.get("HAVEN_DB_RUNTIME_USER", "haven_app"))
                )
            )
