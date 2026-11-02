"""Request authority fences. No new identity or routing credential is introduced."""

from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from .models import User, Conversation
from .middleware import resolve_session


def authorize_current_session(request, extra_accounts=(), lock=False):
    original = request.auth
    if lock:
        # Every protected mutation takes its account fence before object locks.
        # Cross-account administration takes both fences in deterministic order.
        list(
            User.objects.select_for_update()
            .filter(pk__in={request.user.pk, *extra_accounts})
            .order_by("pk")
            .values_list("pk", flat=True)
        )
    current = resolve_session(request.COOKIES.get(settings.SESSION_COOKIE_NAME))
    if not current or not original or current.pk != original.pk or current.user_id != request.user.pk:
        raise PermissionDenied("Session changed; sign in again")
    request.user, request.auth = current.user, current
    raw = request._request
    raw.user, raw.haven_session, raw.device = current.user, current, current.device


def require_rekey(conversations):
    # Account fences precede this operation. Lock every affected conversation
    # in one order, including when two different accounts share several groups.
    ids = list(
        Conversation.objects.filter(pk__in=conversations.values("pk"))
        .select_for_update()
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    Conversation.objects.filter(pk__in=ids).update(status="rekey_required")
