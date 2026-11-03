# ruff: noqa: F811 -- pytest imports shared fixtures by name
"""Actual destructive prototype exercises only an explicitly nonce-marked pytest DB."""

from contextlib import contextmanager
from copy import deepcopy
import secrets
from unittest.mock import patch
import uuid

import pytest
from psycopg import sql
from django.db import connection
from django.db.models.query import QuerySet
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from core import models as m, closure as lifecycle
from core.graph_retirement import retire_synthetic_conversation
from .test_conversation_closure import pair, native, finalize  # noqa: F401
from .conftest import post

pytestmark = pytest.mark.django_db(transaction=True)


@contextmanager
def disposable_marker(settings):
    config = connection.settings_dict
    assert config["NAME"].startswith("test_") and config["HOST"] == "127.0.0.1"
    nonce = secrets.token_hex(24)
    settings.GRAPH_RETIREMENT_SYNTHETIC_ONLY = True
    settings.GRAPH_RETIREMENT_REPLAY_SECRET = secrets.token_urlsafe(48)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()"
        )
        original = cursor.fetchone()[0]
        cursor.execute(
            sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                sql.Identifier(config["NAME"]), sql.Literal("HAVEN-DISPOSABLE-GRAPH:" + nonce)
            )
        )
    try:
        yield nonce
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                    sql.Identifier(config["NAME"]), sql.Literal(original)
                )
            )


def settled(pair, native):
    closure = finalize(pair, native)
    m.NotificationOutbox.objects.filter(envelope__conversation=pair[4]).update(sent_at=timezone.now())
    return closure


def test_retirement_removes_redundant_graph_but_preserves_replay_and_exact_budgets(pair, native, settings):
    a, ad, b, bd, conv, send = pair
    settled(pair, native)
    cid, gid, genesis, signature = (
        conv.pk,
        conv.group_id,
        deepcopy(conv.genesis),
        bytes(conv.genesis_signature),
    )
    assert m.MessageEnvelope.objects.filter(conversation=conv).count() == 2
    assert m.DeviceKeyPackage.objects.filter(device=bd, claimed_by=ad).exists()
    with disposable_marker(settings) as nonce:
        result = retire_synthetic_conversation(cid, fixture_nonce=nonce)
        assert result["changed"] and result["direct_membership_edges_removed"] == 2
        assert retire_synthetic_conversation(cid, fixture_nonce=nonce) == {
            "state": "retired",
            "changed": False,
        }
        for model in (
            m.Conversation,
            m.Membership,
            m.MessageEnvelope,
            m.CryptoControlEvent,
            m.DeliveryCursor,
            m.NotificationOutbox,
            m.ConversationClosure,
        ):
            assert model.objects.count() == 0
        assert m.DeviceKeyPackage.objects.filter(device__isnull=False, claimed_by__isnull=False).count() == 0
        assert m.RetiredConversation.objects.count() == 1 and m.RetiredMessage.objects.count() == 2
        assert m.User.objects.count() == m.Device.objects.count() == 2
        assert all(
            row[name] == 0
            for row in m.StorageUsage.objects.values()
            for name in ("used_bytes", "pending_bytes", "envelope_count", "conversation_count")
        )
        assert (
            post(
                a,
                "conversations",
                {
                    "id": str(cid),
                    "kind": "direct",
                    "group_id": gid,
                    "header": genesis,
                    "signature": __import__("base64").b64encode(signature).decode(),
                },
            ).status_code
            == 403
        )
        lifecycle.check_retired_message(bd.pk, send["client_message_id"])
        with pytest.raises(Exception, match="Retired message ID"):
            lifecycle.check_retired_message(ad.pk, send["client_message_id"])
        settings.GRAPH_RETIREMENT_REPLAY_SECRET = secrets.token_urlsafe(48)
        with pytest.raises(PermissionDenied, match="key changed"):
            lifecycle.check_retired_message(ad.pk, send["client_message_id"])


def test_retirement_refuses_unmarked_database_missing_final_receipt_and_retained_audit(
    pair, native, settings
):
    cid = pair[4].pk
    with pytest.raises(PermissionDenied):
        retire_synthetic_conversation(cid, fixture_nonce="x" * 48)
    finalize(pair, native, receipts=False)
    with disposable_marker(settings) as nonce:
        with pytest.raises(PermissionDenied, match="complete final certificate"):
            retire_synthetic_conversation(cid, fixture_nonce=nonce)
    assert m.Conversation.objects.filter(pk=cid).exists()


def test_partial_deletion_failure_rolls_back_graph_markers_and_accounting(pair, native, settings):
    settled(pair, native)
    cid = pair[4].pk
    counts = {
        model: model.objects.count()
        for model in (
            m.Conversation,
            m.Membership,
            m.MessageEnvelope,
            m.CryptoControlEvent,
            m.NotificationOutbox,
            m.DeliveryCursor,
            m.ConversationClosure,
        )
    }
    budget = list(m.StorageUsage.objects.order_by("key").values())
    original_delete = QuerySet.delete

    def fail_after_envelopes(query):
        if query.model is m.Membership:
            raise RuntimeError("Synthetic interruption after envelope deletion")
        return original_delete(query)

    with disposable_marker(settings) as nonce:
        with patch.object(QuerySet, "delete", fail_after_envelopes):
            with pytest.raises(RuntimeError, match="Synthetic interruption"):
                retire_synthetic_conversation(cid, fixture_nonce=nonce)
        assert all(model.objects.count() == count for model, count in counts.items())
        assert not m.RetiredConversation.objects.exists() and not m.RetiredMessage.objects.exists()
        assert list(m.StorageUsage.objects.order_by("key").values()) == budget
        assert retire_synthetic_conversation(cid, fixture_nonce=nonce)["changed"]


def test_dependency_scanner_blocks_audit_and_unsent_hints_without_deleting_either(pair, native, settings):
    finalize(pair, native)
    cid = pair[4].pk
    with disposable_marker(settings) as nonce:
        with pytest.raises(PermissionDenied, match="notification"):
            retire_synthetic_conversation(cid, fixture_nonce=nonce)
        m.NotificationOutbox.objects.update(sent_at=timezone.now())
        audit = m.AuditEvent.objects.create(
            actor=pair[1].user, category="synthetic.security", target_opaque_id=str(cid)
        )
        with pytest.raises(PermissionDenied, match="audit"):
            retire_synthetic_conversation(cid, fixture_nonce=nonce)
        assert (
            m.AuditEvent.objects.filter(pk=audit.pk).exists()
            and m.Conversation.objects.filter(pk=cid).exists()
        )


def test_creation_cannot_race_retirement_and_resurrect_the_old_mls_group(pair, native, settings):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event
    from django.db import close_old_connections
    from core import graph_retirement
    from .test_view_once import bound_client
    from .test_native_privacy_boundaries import initialize, sign

    settled(pair, native)
    old = pair[4]
    outsider, device = bound_client()
    initialize(native, device)
    cid = str(uuid.uuid4())
    header = {
        "domain": "haven/genesis/v1",
        "id": cid,
        "kind": "direct",
        "group_id": old.group_id,
        "members": [
            {**__import__("core.protocol", fromlist=["certificate"]).certificate(device), "role": "owner"}
        ],
        "closure_policy": lifecycle.POLICY,
        "closure_epoch": settings.CONVERSATION_CLOSURE_EPOCH,
    }
    body = {
        "id": cid,
        "kind": "direct",
        "group_id": old.group_id,
        "header": header,
        "signature": sign(native, device, header),
    }
    entered, release = Event(), Event()
    actual = graph_retirement.retirement_plan

    def paused(conv):
        result = actual(conv)
        entered.set()
        if not release.wait(5):
            raise RuntimeError("Synthetic retirement barrier timed out")
        return result

    def retire(nonce):
        try:
            return retire_synthetic_conversation(old.pk, fixture_nonce=nonce)
        finally:
            close_old_connections()

    def create():
        try:
            return post(outsider, "conversations", body).status_code
        finally:
            close_old_connections()

    with disposable_marker(settings) as nonce:
        with (
            patch.object(graph_retirement, "retirement_plan", paused),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            retiring = pool.submit(retire, nonce)
            try:
                assert entered.wait(3)
                creating = pool.submit(create)
                with pytest.raises(TimeoutError):
                    creating.result(timeout=0.15)
            finally:
                release.set()
            assert retiring.result(timeout=5)["changed"]
            assert creating.result(timeout=5) == 403
        assert not m.Conversation.objects.filter(pk=cid).exists()
