"""Concurrent upload reservations must share one account-wide quota."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta

import pytest
from django.db import close_old_connections
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from core import models as m
from .test_security import post, setup_device


@pytest.mark.django_db(transaction=True)
@override_settings(CRYPTO_READY=True)
def test_concurrent_uploads_in_different_chats_share_account_quota(client, credentials):
    device, _ = setup_device(client, credentials)
    conversations = []
    for _ in range(2):
        cid = str(uuid.uuid4())
        assert post(client, "conversations", {"id": cid, "kind": "group", "group_id": cid}).status_code == 201
        conversations.append(cid)
    quota = 250 * 1024 * 1024
    m.EncryptedAttachment.objects.create(
        uploader_device=device,
        conversation_id=conversations[0],
        epoch=0,
        ciphertext_size=quota - 1024 * 1024,
        chunk_count=64,
        expires_at=timezone.now() + timedelta(days=1),
    )
    barrier = Barrier(2)
    cookies = client.cookies.copy()

    def reserve(cid):
        close_old_connections()
        try:
            c = APIClient(enforce_csrf_checks=True)
            c.defaults.update(HTTP_HOST="127.0.0.1:8443", HTTP_ORIGIN="https://127.0.0.1:8443")
            c.cookies = cookies.copy()
            barrier.wait(timeout=10)
            return post(
                c,
                "attachments/init",
                {
                    "id": str(uuid.uuid4()),
                    "conversation_id": cid,
                    "ciphertext_size": 768 * 1024,
                    "chunk_count": 1,
                },
            ).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, conversations)) == [201, 400]
    assert m.EncryptedAttachment.objects.count() == 2
