"""Idempotently provision separate migration and runtime roles using a bootstrap connection."""

import os
import re
import psycopg
from psycopg import sql
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Provision least-privilege database roles (bootstrap credentials only)"

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        roles = [
            (
                os.environ.get("HAVEN_DB_MIGRATION_USER", "haven_migrate"),
                os.environ.get("HAVEN_DB_MIGRATION_PASSWORD", ""),
            ),
            (
                os.environ.get("HAVEN_DB_RUNTIME_USER", "haven_app"),
                os.environ.get("HAVEN_DB_RUNTIME_PASSWORD", ""),
            ),
        ]
        if (
            any(
                not re.fullmatch(r"haven_[a-z_]{1,30}", role) or len(password) < 32
                for role, password in roles
            )
            or roles[0][0] == roles[1][0]
        ):
            raise CommandError("Distinct haven_ roles and random passwords >=32 characters are required")
        with psycopg.connect(
            dbname=db["NAME"], user=db["USER"], password=db["PASSWORD"], host=db["HOST"], port=db["PORT"]
        ) as conn:
            with conn.cursor() as cursor:
                for role, password in roles:
                    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
                    if not cursor.fetchone():
                        cursor.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(role)))
                    cursor.execute(
                        sql.SQL(
                            "ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
                        ).format(sql.Identifier(role), sql.Literal(password))
                    )
                owner, runtime = (sql.Identifier(x[0]) for x in roles)
                database = sql.Identifier(db["NAME"])
                cursor.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(database))
                cursor.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(database, owner, runtime)
                )
                cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
                cursor.execute(sql.SQL("ALTER SCHEMA public OWNER TO {}").format(owner))
                cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(runtime))
                # Upgrade existing application tables only. Never reassign system schemas or unrelated databases.
                cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                for (table,) in cursor.fetchall():
                    if table.startswith(("core_", "auth_", "django_")):
                        cursor.execute(
                            sql.SQL("ALTER TABLE public.{} OWNER TO {}").format(sql.Identifier(table), owner)
                        )
                cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                for (table,) in cursor.fetchall():
                    if table.startswith(("core_", "auth_", "django_")):
                        cursor.execute(
                            sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON public.{} TO {}").format(
                                sql.Identifier(table), runtime
                            )
                        )
                if cursor.execute("SELECT to_regclass('public.django_migrations')").fetchone()[0]:
                    cursor.execute(
                        sql.SQL("REVOKE INSERT, UPDATE, DELETE ON public.django_migrations FROM {}").format(
                            runtime
                        )
                    )
                cursor.execute(
                    sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(runtime)
                )
                cursor.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
                    ).format(owner, runtime)
                )
                cursor.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}"
                    ).format(owner, runtime)
                )
        self.stdout.write("Database roles configured; runtime has no DDL or administrative privileges.")
