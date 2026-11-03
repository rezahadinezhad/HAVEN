"""Effective permissions with an actual disposable PostgreSQL login, not SET ROLE mocks."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
import secrets
import string
import uuid

import psycopg
from psycopg import sql
import pytest
from django.db import connection
from core.database_privileges import grant_notification_worker
from core.management.commands.publish_outbox import Command
from core import models as m
from .test_privacy_hardening import approved

pytestmark = pytest.mark.django_db(transaction=True)


def test_notification_login_can_publish_but_cannot_read_graph_or_payload():
    config = connection.settings_dict
    assert config["NAME"].startswith("test_") and config["HOST"] == "127.0.0.1"
    role = "haven_notify_" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(12))
    password = secrets.token_urlsafe(48)
    _, device, _ = approved("narrow_worker")
    conv = m.Conversation.objects.create(creator=device, kind="direct", group_id=uuid.uuid4().hex)
    m.Membership.objects.create(conversation=conv, device=device, valid_from_epoch=0)
    env = m.MessageEnvelope.objects.create(
        conversation=conv,
        sender_device=device,
        server_seq=1,
        client_message_id=uuid.uuid4(),
        group_epoch=0,
        ciphertext=b"private ciphertext",
        request_digest="b" * 64,
    )
    row = m.NotificationOutbox.objects.create(envelope=env)
    args = dict(
        dbname=config["NAME"],
        user=config["USER"],
        password=config["PASSWORD"],
        host=config["HOST"],
        port=config["PORT"],
        autocommit=True,
    )
    with psycopg.connect(**args) as owner:
        try:
            owner.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
                ).format(sql.Identifier(role), sql.Literal(password))
            )
            owner.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(config["NAME"]), sql.Identifier(role)
                )
            )
            # A table-level revoke alone would leave this column grant alive.
            owner.execute(sql.SQL("GRANT SELECT (password) ON core_user TO {}").format(sql.Identifier(role)))
            with owner.cursor() as cursor:
                grant_notification_worker(cursor, role)
                grant_notification_worker(cursor, role)
            with psycopg.connect(**{**args, "user": role, "password": password}) as narrow:
                assert (
                    narrow.execute(
                        "SELECT user_id FROM haven_notification_targets WHERE outbox_id=%s", [row.pk]
                    ).fetchone()[0]
                    == device.user_id
                )
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    narrow.execute("SELECT password FROM core_user")
                for table in (
                    "core_user",
                    "core_session",
                    "core_device",
                    "core_membership",
                    "core_conversation",
                    "core_messageenvelope",
                    "core_cryptocontrolevent",
                    "core_deliverycursor",
                    "core_storageusage",
                    "core_encryptedattachment",
                    "core_auditevent",
                    "core_recoverychallenge",
                ):
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        narrow.execute(sql.SQL("SELECT * FROM {} LIMIT 1").format(sql.Identifier(table)))
                for query in (
                    "DELETE FROM core_notificationoutbox",
                    "UPDATE core_notificationoutbox SET envelope_id=envelope_id",
                    "CREATE TABLE forbidden_worker_table (id int)",
                ):
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        narrow.execute(query)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    narrow.execute("SELECT * FROM django_migrations")
            # Execute the actual worker ORM and view query under the narrow login.
            # Existing approved API connections are closed; no cached privileged connection.
            connection.close()
            connection.close_pool()
            old_user, old_password = config["USER"], config["PASSWORD"]
            config["USER"], config["PASSWORD"] = role, password

            class Layer:
                async def group_send(self, group, event):
                    assert group.startswith("route.") and str(device.user_id) not in group

            try:
                with asyncio.Runner() as runner:
                    assert Command().publish_batch(Layer(), runner) == 1
            finally:
                connection.close()
                connection.close_pool()
                config["USER"], config["PASSWORD"] = old_user, old_password
            row.refresh_from_db()
            assert row.sent_at and row.attempts == 1
            with psycopg.connect(**{**args, "user": role, "password": password}) as narrow:
                assert (
                    narrow.execute(
                        "SELECT * FROM haven_notification_targets WHERE outbox_id=%s", [row.pk]
                    ).fetchall()
                    == []
                )
            # Independent worker process, actual Redis backend, no API signing secret.
            m.NotificationOutbox.objects.filter(pk=row.pk).update(sent_at=None)
            process_env = {
                **os.environ,
                "DJANGO_SETTINGS_MODULE": "haven.notification_settings",
                "POSTGRES_DB": config["NAME"],
                "POSTGRES_USER": role,
                "POSTGRES_PASSWORD": password,
                "POSTGRES_HOST": config["HOST"],
                "POSTGRES_PORT": str(config["PORT"]),
            }
            process_env.pop("HAVEN_SECRET_KEY", None)
            completed = subprocess.run(
                [sys.executable, "manage.py", "publish_outbox", "--once"],
                cwd=Path(__file__).resolve().parents[2],
                env=process_env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert completed.returncode == 0 and "unavailable" not in completed.stderr
            assert password not in completed.stdout + completed.stderr
            row.refresh_from_db()
            assert row.sent_at and row.attempts == 2
        finally:
            owner.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
            owner.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
