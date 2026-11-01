"""Real PostgreSQL boundaries; these fixtures do not claim MLS interoperability."""

import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import pytest
from django.core.management import call_command
from django.db import close_old_connections, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core import models as m
from core.retention import cleanup, delete_attachments
from .test_privacy import delivery

pytestmark = pytest.mark.django_db


def test_obsolete_columns_absent_and_authoritative_cursors_retained():
    for table, removed in [
        ("core_session", "last_seen"),
        ("core_deliverycursor", "updated_at"),
        ("core_attachmentchunk", "stored_at"),
    ]:
        with connection.cursor() as cursor:
            columns = {c.name for c in connection.introspection.get_table_description(cursor, table)}
        assert removed not in columns
    assert "core_deliveryreceipt" not in connection.introspection.table_names()
    assert m.DeliveryCursor._meta.get_field("last_acked_seq")


def test_expired_package_disassociation_includes_previously_scrubbed_rows():
    _, ad, _, bd, _, _ = delivery()
    now = timezone.now()
    packages = []
    for payload in [b"", b"expired-package"]:
        packages.append(
            m.DeviceKeyPackage.objects.create(
                device=bd,
                claimed_by=ad,
                consumed_at=now,
                package=payload,
                digest=secrets.token_hex(32),
                expires_at=now - timedelta(seconds=1),
            )
        )
    live = m.DeviceKeyPackage.objects.create(
        device=bd,
        claimed_by=ad,
        consumed_at=now,
        package=b"live-package",
        digest=secrets.token_hex(32),
        expires_at=now + timedelta(days=1),
    )
    assert cleanup(batch_size=1)["packages"] == 1
    assert cleanup()["packages"] == 1
    assert cleanup()["packages"] == 0
    for package in packages:
        package.refresh_from_db()
        assert package.device_id is package.claimed_by_id is package.consumed_at is None
        assert not bytes(package.package)
        assert m.DeviceKeyPackage.objects.filter(digest=package.digest).exists()
    live.refresh_from_db()
    assert live.device_id == bd.pk and live.claimed_by_id == ad.pk and bytes(live.package)


def test_notification_worker_never_loads_message_content_or_signed_history():
    _, _, _, _, _, messages = delivery()
    outbox = m.NotificationOutbox.objects.create(envelope=messages[1])
    with CaptureQueriesContext(connection) as queries:
        call_command("publish_outbox", once=True)
    selects = [q["sql"] for q in queries if q["sql"].lstrip().startswith("SELECT")]
    envelope_reads = [q for q in selects if "core_messageenvelope" in q]
    assert envelope_reads
    for query in envelope_reads:
        for column in [
            "ciphertext",
            "header",
            "signature",
            "request_digest",
            "received_at",
            "sender_device_id",
        ]:
            assert f'"{column}"' not in query
    outbox.refresh_from_db()
    assert outbox.sent_at and outbox.attempts == 1
    assert bytes(m.MessageEnvelope.objects.get(pk=messages[1].pk).ciphertext)


def test_message_api_does_not_expose_or_select_acceptance_time(settings):
    settings.CRYPTO_READY = True
    client, _, _, _, conv, messages = delivery()
    # Request only the application envelope; control fixtures here are not MLS events.
    with CaptureQueriesContext(connection) as queries:
        response = client.get(f"/api/v1/conversations/{conv.pk}/messages?after_seq=1", secure=True)
    assert response.status_code == 200
    envelope = response.json()["messages"][0]
    assert "received_at" not in envelope and "request_digest" not in envelope
    assert envelope["header"] == messages[1].header and envelope["signature"]
    reads = [
        q["sql"] for q in queries if q["sql"].startswith("SELECT") and "core_messageenvelope" in q["sql"]
    ]
    assert reads and all('"received_at"' not in query and '"request_digest"' not in query for query in reads)


@pytest.mark.django_db(transaction=True)
def test_cleanup_rechecks_abandoned_upload_after_concurrent_completion():
    _, ad, _, _, conv, _ = delivery()
    now = timezone.now()
    attachment = m.EncryptedAttachment.objects.create(
        uploader_device=ad,
        conversation=conv,
        epoch=0,
        ciphertext_size=32,
        chunk_count=1,
        expires_at=now + timedelta(days=1),
    )
    m.EncryptedAttachment.objects.filter(pk=attachment.pk).update(created_at=now - timedelta(hours=2))
    m.AttachmentChunk.objects.create(
        attachment=attachment,
        chunk_index=0,
        content_hash="a" * 64,
        byte_length=32,
        ciphertext=b"x" * 32,
    )
    waiting = Event()

    def collect():
        close_old_connections()

        def observed(execute, sql, params, many, context):
            if "core_encryptedattachment" in sql and "FOR UPDATE" in sql:
                waiting.set()
            return execute(sql, params, many, context)

        try:
            with connection.execute_wrapper(observed):
                return delete_attachments(now, 500)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            row = m.EncryptedAttachment.objects.select_for_update().get(pk=attachment.pk)
            row.status = "complete"
            row.save(update_fields=["status"])
            future = pool.submit(collect)
            assert waiting.wait(5), "cleanup did not reach the shared row lock"
        assert future.result(timeout=10) == 0
    assert m.EncryptedAttachment.objects.get(pk=attachment.pk).status == "complete"
    assert m.AttachmentChunk.objects.filter(attachment=attachment).exists()
