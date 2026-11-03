"""Separate, fsynced, authenticated deny journal. Never stores participant identifiers."""

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from . import protocol as p


def root():
    value = settings.RETIREMENT_JOURNAL_DIR
    if not value:
        raise PermissionDenied("Persistent retirement journal directory is required")
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir() or path.stat().st_mode & 0o077:
        raise PermissionDenied("Retirement journal must be an existing protected absolute directory")
    return path


def secret():
    value = settings.GRAPH_RETIREMENT_REPLAY_SECRET
    if len(value) < 48 or value in (
        settings.SECRET_KEY,
        settings.ROUTING_SECRET,
        settings.ROUTING_PREVIOUS_SECRET,
    ):
        raise PermissionDenied("Independent permanent retirement secret required")
    return value.encode()


def read(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if info.st_size > 2 * 1024 * 1024 or info.st_mode & 0o077:
                raise PermissionDenied("Unsafe retirement journal entry")
            body = json.load(stream)
        payload = body["payload"]
        expected = hmac.new(secret(), p.canonical(payload), hashlib.sha256).hexdigest()
        if not isinstance(body["mac"], str) or not hmac.compare_digest(expected, body["mac"]):
            raise PermissionDenied("Retirement journal authentication failed")
        return payload
    except (OSError, ValueError, TypeError, KeyError):
        raise PermissionDenied(
            "Retirement journal unavailable or malformed; restore the protected copy"
        ) from None


def write(path, payload):
    wire = p.canonical(
        {"payload": payload, "mac": hmac.new(secret(), p.canonical(payload), hashlib.sha256).hexdigest()}
    )
    if path.exists():
        if read(path) != payload:
            raise PermissionDenied("Permanent retirement journal conflict")
        return
    temporary = path.parent / (".pending-" + secrets.token_hex(16))
    try:
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(wire)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Never overwrite a permanent entry.
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except FileExistsError:
        if read(path) != payload:
            raise PermissionDenied("Concurrent journal conflict") from None
    finally:
        temporary.unlink(missing_ok=True)


def persist(payload):
    directory = root()
    read(directory / "key.json")
    write(directory / (payload["id"] + ".json"), payload)
    write(directory / (payload["group_tag"] + ".group"), {"id": payload["id"]})


def denied(cid, group_tag):
    directory = root()
    key = directory / "key.json"
    if not key.exists():
        raise PermissionDenied("Retirement journal is missing; restore its independent persistent volume")
    read(key)
    for path in (directory / (str(cid) + ".json"), directory / (group_tag + ".group")):
        if path.exists():
            read(path)
            return True
    return False


def entries():
    directory = root()
    if not (directory / "key.json").exists():
        raise PermissionDenied("Retirement journal is missing; refuse traffic until restored")
    read(directory / "key.json")
    for path in directory.glob("*.json"):
        if path.name != "key.json":
            yield read(path)


def reconcile():
    from . import models as m
    from .graph_retirement import retire_conversation

    for entry in entries():
        if m.Conversation.objects.filter(pk=entry["id"]).exists():
            # A separately authenticated journal is authority from the original
            # completed finality transaction, even if SQL was restored before it.
            retire_conversation(entry["id"], restored_marker=entry)
        elif not m.RetiredConversation.objects.filter(pk=entry["id"]).exists():
            restore_markers(entry)


def initialize():
    """Explicit installation bootstrap only; never invoked by server/restore/worker."""
    directory = root()
    write(directory / "key.json", {"domain": "haven/retirement/journal-key/v1"})


def restore_markers(entry):
    from django.db import transaction
    from django.db.models import F
    from . import models as m, closure

    with transaction.atomic():
        closure.creation_fence(entry["id"], entry["group_tag"])
        if m.RetiredConversation.objects.filter(pk=entry["id"]).exists():
            return
        m.StorageUsage.objects.get_or_create(key="service")
        m.StorageUsage.objects.get_or_create(key="retirement-replay")
        budgets = list(
            m.StorageUsage.objects.select_for_update()
            .filter(pk__in=["service", "retirement-replay"])
            .order_by("pk")
        )
        if (
            next(x for x in budgets if x.pk == "service").used_bytes + entry["replay_bytes"]
            > settings.MESSAGE_SERVICE_BYTES
        ):
            raise PermissionDenied("Restore exceeds permanent replay storage budget")
        commitment = hmac.new(secret(), b"haven/retirement/key-binding/v1", hashlib.sha256).hexdigest()
        binding, _ = m.RetirementReplayKey.objects.get_or_create(pk=1, defaults={"commitment": commitment})
        if binding.commitment != commitment:
            raise PermissionDenied("Restore replay key mismatch")
        m.RetiredConversation.objects.create(
            id=entry["id"], group_tag=entry["group_tag"], finality_digest=entry["finality_digest"]
        )
        m.AttachmentTombstone.objects.bulk_create(
            [m.AttachmentTombstone(id=x) for x in entry.get("attachment_ids", [])], ignore_conflicts=True
        )
        m.RetiredMessage.objects.bulk_create(
            [m.RetiredMessage(tag=x) for x in entry["message_tags"]], ignore_conflicts=True
        )
        m.StorageUsage.objects.filter(pk__in=["service", "retirement-replay"]).update(
            used_bytes=F("used_bytes") + entry["replay_bytes"]
        )


def group_tag(group_id):
    return hmac.new(
        secret(), p.canonical(["haven/retirement/replay/v1", "group", group_id]), hashlib.sha256
    ).hexdigest()
