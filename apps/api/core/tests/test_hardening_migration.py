"""Forward migration from a disposable pre-hardening schema; no real data or backups."""

import uuid
from datetime import timedelta
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.exceptions import IrreversibleError
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)


def test_preupgrade_signatures_outbox_cursors_and_revocation_generation(migration_database):
    before = [("core", "0016_session_challenge_context")]
    head = [("core", "0018_notification_worker_view")]
    executor = MigrationExecutor(connection)
    executor.migrate(before)
    old = executor.loader.project_state(before).apps
    user = old.get_model("core", "User").objects.create(
        username="legacy_handle", display_name="Legacy pseudonym", password="synthetic unused password hash"
    )
    Device = old.get_model("core", "Device")
    device = Device.objects.create(
        user=user,
        label="legacy",
        identity="fixed-identity",
        public_key=b"p" * 32,
        credential=b"signed legacy placeholder",
        approval_signature=b"approval bytes",
        challenge="c" * 64,
        trust_state="approved",
        expires_at=timezone.now() + timedelta(days=1),
    )
    genesis = {"members": [{"id": str(device.pk), "user_id": str(user.pk)}]}
    conv = old.get_model("core", "Conversation").objects.create(
        creator=device,
        kind="direct",
        group_id=uuid.uuid4().hex,
        genesis=genesis,
        genesis_signature=b"genesis signature",
        head_hash="h" * 64,
    )
    old.get_model("core", "Membership").objects.create(conversation=conv, device=device, valid_from_epoch=0)
    env = old.get_model("core", "MessageEnvelope").objects.create(
        conversation=conv,
        sender_device=device,
        server_seq=1,
        client_message_id=uuid.uuid4(),
        group_epoch=0,
        ciphertext=b"pending exact ciphertext",
        header={"signed": "immutable"},
        signature=b"envelope signature",
        request_digest="d" * 64,
    )
    outbox = old.get_model("core", "NotificationOutbox").objects.create(envelope=env)
    old.get_model("core", "DeliveryCursor").objects.create(device=device, conversation=conv, last_acked_seq=0)
    executor = MigrationExecutor(connection)
    executor.migrate(head)
    current = executor.loader.project_state(head).apps
    upgraded = current.get_model("core", "Device").objects.get(pk=device.pk)
    assert bytes(upgraded.public_key) == b"p" * 32 and bytes(upgraded.approval_signature) == b"approval bytes"
    assert (
        bytes(upgraded.credential) == b"signed legacy placeholder" and upgraded.identity == "fixed-identity"
    )
    assert upgraded.introduction_generation == 0
    retained = current.get_model("core", "MessageEnvelope").objects.get(pk=env.pk)
    assert bytes(retained.ciphertext) == b"pending exact ciphertext" and retained.header == {
        "signed": "immutable"
    }
    assert bytes(retained.signature) == b"envelope signature"
    assert current.get_model("core", "Conversation").objects.get(pk=conv.pk).genesis == genesis
    assert current.get_model("core", "DeliveryCursor").objects.get(device_id=device.pk).last_acked_seq == 0
    with connection.cursor() as cursor:
        cursor.execute("SELECT user_id FROM haven_notification_targets WHERE outbox_id=%s", [outbox.pk])
        assert cursor.fetchone()[0] == user.pk
    upgraded.introduction_generation = 1
    upgraded.save()
    MigrationExecutor(connection).migrate(head)  # Interrupted operation/retry does not reset the generation.
    assert current.get_model("core", "Device").objects.get(pk=device.pk).introduction_generation == 1
    with pytest.raises(IrreversibleError):
        MigrationExecutor(connection).migrate(before)
    assert current.get_model("core", "Device").objects.get(pk=device.pk).introduction_generation == 1
    # 0018 is safely recreatable; an attempted reverse cannot remove revocation state in 0017.
    MigrationExecutor(connection).migrate(head)
