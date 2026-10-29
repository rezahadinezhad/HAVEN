#!/usr/bin/env python3
"""Disposable PostgreSQL migration drill. Refuses non-loopback/non-test DB settings."""

import os
import secrets
import subprocess
import sys
from pathlib import Path
import psycopg
from psycopg import sql

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "apps/api"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "haven.settings")
import django
django.setup()
from django.conf import settings

db = settings.DATABASES["default"]
if db["HOST"] != "127.0.0.1" or str(db["PORT"]) != "55432":
    raise SystemExit("Only the isolated loopback test database on port 55432 is permitted")
name = "haven_privacy_migration_" + secrets.token_hex(6)
env = {**os.environ, "POSTGRES_DB": name}


def manage(*args):
    result = subprocess.run([sys.executable, "manage.py", *args], cwd=root / "apps/api", env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


with psycopg.connect(dbname="postgres", user=db["USER"], password=db["PASSWORD"],
                      host=db["HOST"], port=db["PORT"], autocommit=True) as admin:
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        manage("migrate", "core", "0007", "--noinput")
        manage("shell", "--no-imports", "-c", """
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from datetime import timedelta
import uuid
a=MigrationExecutor(connection).loader.project_state([('core','0007_attachmenttombstone')]).apps
U,D,C,A,V=(a.get_model('core',n) for n in ['User','Device','Conversation','EncryptedAttachment','AttachmentView'])
u=U.objects.create(username='migration-fixture',display_name='Synthetic')
d=D.objects.create(user=u,label='Fixture',identity='synthetic',public_key=b'x'*32,expires_at=timezone.now()+timedelta(days=1))
c=C.objects.create(creator=d,kind='direct',group_id=uuid.uuid4().hex)
blob=A.objects.create(uploader_device=d,conversation=c,epoch=0,ciphertext_size=32,chunk_count=1,view_once=True,status='complete',expires_at=timezone.now()+timedelta(days=30))
V.objects.create(attachment=blob,user=u,opened_at=timezone.now(),opened_by=d,token_hash='a'*64,lease_expires_at=timezone.now()+timedelta(minutes=5))
other=U.objects.create(username='unopened-fixture',display_name='Synthetic')
V.objects.create(attachment=blob,user=other)
"""
        )
        manage("migrate", "--noinput")
        manage("shell", "--no-imports", "-c", """
from core.models import AttachmentView,EncryptedAttachment
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.exceptions import IrreversibleError
from datetime import timedelta
assert AttachmentView.objects.get(user__username='migration-fixture').consumed is True
assert AttachmentView.objects.get(user__username='migration-fixture').token_hash == 'a'*64
assert AttachmentView.objects.get(user__username='unopened-fixture').consumed is False
a=EncryptedAttachment.objects.get()
assert a.expires_at <= a.created_at+timedelta(days=7)
try:
    MigrationExecutor(connection).migrate([('core','0007_attachmenttombstone')])
except IrreversibleError:
    pass
else:
    raise AssertionError('Unsafe reverse migration was allowed')
assert AttachmentView.objects.get(user__username='migration-fixture').consumed
"""
        )
        print("PASS: real 0007-to-0008 migration preserves consumed/unopened states and live capability, caps existing TTL, and refuses unsafe rollback")
    finally:
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
