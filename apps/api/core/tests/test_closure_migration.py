"""Additive closure upgrade preserves legacy signed bytes and refuses unsafe reversal."""

import uuid
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.exceptions import IrreversibleError
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)


def test_closure_upgrade_preserves_legacy_history_and_finality_on_reverse(migration_database):
    before = [("core", "0018_notification_worker_view")]
    after = [("core", "0019_experimental_conversation_closure")]
    executor = MigrationExecutor(connection)
    executor.migrate(before)
    old = executor.loader.project_state(before).apps
    user = old.get_model("core", "User").objects.create(username="legacy_closure", password="fixture")
    device = old.get_model("core", "Device").objects.create(
        user=user,
        identity="fixture",
        public_key=b"p" * 32,
        credential=b"exact credential",
        challenge="c" * 64,
        trust_state="approved",
        expires_at=timezone.now(),
    )
    genesis = {"domain": "haven/genesis/v1", "immutable": "legacy signed bytes"}
    conversation = old.get_model("core", "Conversation").objects.create(
        creator=device,
        kind="direct",
        group_id=uuid.uuid4().hex,
        genesis=genesis,
        genesis_signature=b"exact genesis signature",
        head_hash="a" * 64,
    )
    envelope = old.get_model("core", "MessageEnvelope").objects.create(
        conversation=conversation,
        sender_device=device,
        server_seq=1,
        client_message_id=uuid.uuid4(),
        group_epoch=0,
        ciphertext=b"exact accepted pending ciphertext",
        header={"exact": "signed header"},
        signature=b"exact envelope signature",
        request_digest="b" * 64,
    )
    executor = MigrationExecutor(connection)
    executor.migrate(after)
    current = executor.loader.project_state(after).apps
    conv = current.get_model("core", "Conversation").objects.get(pk=conversation.pk)
    retained = current.get_model("core", "MessageEnvelope").objects.get(pk=envelope.pk)
    assert conv.genesis == genesis and bytes(conv.genesis_signature) == b"exact genesis signature"
    assert "closure_policy" not in conv.genesis and conv.status == "active"
    assert bytes(retained.ciphertext) == b"exact accepted pending ciphertext"
    assert retained.header == {"exact": "signed header"}
    assert bytes(retained.signature) == b"exact envelope signature"
    marker = current.get_model("core", "RetiredConversation").objects.create(
        id=uuid.uuid4(),
        group_tag="c" * 64,
        finality_digest="d" * 64,
    )
    with pytest.raises(IrreversibleError):
        MigrationExecutor(connection).migrate(before)
    assert current.get_model("core", "RetiredConversation").objects.filter(pk=marker.pk).exists()
    assert current.get_model("core", "MessageEnvelope").objects.filter(pk=envelope.pk).exists()
    MigrationExecutor(connection).migrate(after)
