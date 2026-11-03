"""Bounded normal-product worker; a missing consent never becomes a timeout approval."""

import time
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.conf import settings
from core.models import ConversationClosure
from core.graph_retirement import retire_conversation
from core.retirement_journal import root, secret, read
from rest_framework.exceptions import APIException


class Command(BaseCommand):
    help = "Retire mutually authorized conversations; retain independent authenticated deny journal"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--conversation", type=str)

    def handle(self, *args, **options):
        if not settings.GRAPH_RETIREMENT_READY:
            raise CommandError("Conversation retirement is unavailable")
        secret()
        read(root() / "key.json")
        cursor = None
        while True:
            close_old_connections()
            retired = blocked = 0
            query = ConversationClosure.objects.filter(
                state="finalized", conversation__genesis__closure_policy="account-wide-retirement-v2"
            )
            if options.get("conversation"):
                import uuid

                query = query.filter(conversation_id=uuid.UUID(options["conversation"]))
            if cursor:
                query = query.filter(conversation_id__gt=cursor)
            batch = list(query.order_by("conversation_id").values_list("conversation_id", flat=True)[:25])
            if not batch:
                cursor = None
            for cid in batch:
                cursor = cid
                try:
                    retired += bool(retire_conversation(cid)["changed"])
                except APIException:
                    blocked += 1
            self.stdout.write(f"Conversation retirement: retired={retired} pending={blocked}")
            if options["once"]:
                return
            time.sleep(30)
