#!/usr/bin/env python3
"""Synthetic PG dump/restore and forward migration; refuses non-test infrastructure.

Full dumps remain owner-only under .local, never published as evidence. Printed
results contain counts and checksums, not records. No production DB is opened.
"""

import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

import psycopg
from psycopg import sql

import django
from django.conf import settings


root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "apps/api"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "haven.settings")

django.setup()

config = settings.DATABASES["default"]
if config["HOST"] != "127.0.0.1" or str(config["PORT"]) != "55432":
    raise SystemExit("Only loopback test PostgreSQL port 55432 is permitted")
container = "haven-test-db-1"
info = json.loads(subprocess.check_output(["docker", "inspect", container]))[0]
labels = info["Config"].get("Labels") or {}
if (
    labels.get("haven.test-only") != "true"
    or labels.get("com.docker.compose.service") != "db"
):
    raise SystemExit("Expected explicitly labelled test-only database")
name = "test_haven_metadata_" + secrets.token_hex(8)
restored = name + "_restore"
folder = root / ".local/metadata-dumps"
folder.mkdir(mode=0o700, exist_ok=True)
if folder.stat().st_mode & 0o077:
    raise SystemExit("Dump directory must be owner-only")


def manage(database, *args):
    result = subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=root / "apps/api",
        env={**os.environ, "POSTGRES_DB": database},
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("Isolated migration check failed: " + result.stderr)
    return result.stdout


def execute(database, code):
    return manage(database, "shell", "--no-imports", "-c", code)


seed = """
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from datetime import timedelta
import uuid
apps=MigrationExecutor(connection).loader.project_state([('core','0012_conversation_page_index')]).apps
get=lambda name:apps.get_model('core',name)
now=timezone.now()
users=[get('User').objects.create(username='synthetic_'+str(i),password='!',is_active=True) for i in range(3)]
devices=[get('Device').objects.create(user=u,label='Synthetic',identity=str(u.pk)+':synthetic',public_key=b'x'*32,trust_state='approved',expires_at=now+timedelta(days=1)) for u in users]
c=get('Conversation').objects.create(creator=devices[0],kind='group',group_id=uuid.uuid4().hex,last_seq=2,genesis={'members':[{'user_id':str(u.pk),'device_id':str(d.pk)} for u,d in zip(users,devices)]},genesis_signature=b's'*64,head_hash='h'*64,receipt_version=1)
for d in devices:get('Membership').objects.create(conversation=c,device=d,valid_from_epoch=0)
for seq,kind in [(1,'commit'),(2,'application')]:
 e=get('MessageEnvelope').objects.create(conversation=c,sender_device=devices[0],server_seq=seq,client_message_id=uuid.uuid4(),group_epoch=0,kind=kind,ciphertext=b'fixture-ciphertext-'+bytes([seq]),request_digest='d'*64,header={'seq':seq,'sender_device':str(devices[0].pk)},signature=b's'*64,chain_hash='h'*64)
 get('MessageEnvelope').objects.filter(pk=e.pk).update(received_at=now-timedelta(days=2))
 if kind=='commit':get('CryptoControlEvent').objects.create(envelope=e,transition={'members':[str(d.pk) for d in devices]},signature=b's'*64,welcome_device=devices[1],welcome=b'fixture-welcome')
get('DeliveryCursor').objects.create(device=devices[0],conversation=c,last_acked_seq=2)
get('DeliveryReceipt').objects.create(device=devices[0],envelope=e)
# Offline recipients deliberately have no cursor. No retirement is allowed.
get('NotificationOutbox').objects.create(envelope=e)
get('Session').objects.create(user=users[0],device=devices[0],token_hash='t'*64,auth_hash='a'*64,expires_at=now+timedelta(hours=1))
for expiry, payload in [(now-timedelta(days=1),b'expired'),(now+timedelta(days=1),b'live')]:
 get('DeviceKeyPackage').objects.create(device=devices[1],claimed_by=devices[0],consumed_at=now,package=payload,digest=uuid.uuid4().hex*2,expires_at=expiry)
a=get('EncryptedAttachment').objects.create(uploader_device=devices[0],conversation=c,epoch=0,ciphertext_size=32,chunk_count=1,view_once=True,status='complete',expires_at=now+timedelta(days=1))
get('AttachmentChunk').objects.create(attachment=a,chunk_index=0,content_hash='h'*64,byte_length=32,ciphertext=b'x'*32)
get('AttachmentView').objects.create(attachment=a,user=users[1],consumed=True,opened_by=devices[1],token_hash='v'*64,lease_expires_at=now+timedelta(minutes=5))
get('AttachmentView').objects.create(attachment=a,user=users[2],consumed=False)
get('StorageUsage').objects.create(key='service',used_bytes=12345,pending_bytes=20,envelope_count=2,conversation_count=1)
"""
inspect_code = """
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
import hashlib,json
apps=MigrationExecutor(connection).loader.project_state().apps
get=lambda name:apps.get_model('core',name)
fields={
'User':['id','password','security_generation','device_bootstrapped'],
'Device':['id','user_id','public_key','trust_state','approval_signature'],
'Conversation':['id','epoch','last_seq','genesis','genesis_signature','head_hash','receipt_version'],
'Membership':['conversation_id','device_id','valid_from_epoch','removed_at_epoch','start_seq','role'],
'MessageEnvelope':['id','conversation_id','sender_device_id','server_seq','client_message_id','group_epoch','kind','ciphertext','received_at','request_digest','header','signature','chain_hash','ciphertext_retired'],
'CryptoControlEvent':['envelope_id','transition','signature','welcome_device_id','welcome'],
'DeliveryCursor':['device_id','conversation_id','last_acked_seq'],
'Session':['token_hash','auth_hash','user_id','device_id','device_challenge'],
'AttachmentView':['attachment_id','user_id','consumed','opened_by_id','token_hash','lease_expires_at'],
'AttachmentChunk':['attachment_id','chunk_index','content_hash','byte_length','ciphertext'],
'StorageUsage':['key','used_bytes','pending_bytes','envelope_count','conversation_count'],
'NotificationOutbox':['envelope_id','sent_at','attempts']}
def encode(value):
 if isinstance(value,(bytes,memoryview)):return bytes(value).hex()
 return str(value)
material={name:list(get(name).objects.order_by('pk').values(*names)) for name,names in fields.items()}
checksum=hashlib.sha256(json.dumps(material,sort_keys=True,default=encode).encode()).hexdigest()
with connection.cursor() as cur:
 cur.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND (table_name,column_name) IN (('core_session','last_seen'),('core_deliverycursor','updated_at'),('core_attachmentchunk','stored_at'))")
 times=cur.fetchone()[0]
 cur.execute('SELECT count(DISTINCT (device_id,conversation_id)) FROM core_membership')
 edges=cur.fetchone()[0]
print(json.dumps({'invariant_sha256':checksum,'recoverable_activity_columns':times,'legacy_receipt_table': 'core_deliveryreceipt' in connection.introspection.table_names(),'membership_edges':edges,'keypackage_device_links':get('DeviceKeyPackage').objects.filter(device__isnull=False).count(),'keypackage_claim_links':get('DeviceKeyPackage').objects.filter(claimed_by__isnull=False).count()}))
"""


def snapshot(database):
    return json.loads(execute(database, inspect_code).strip().splitlines()[-1])


with psycopg.connect(
    dbname="postgres",
    user=config["USER"],
    password=config["PASSWORD"],
    host=config["HOST"],
    port=config["PORT"],
    autocommit=True,
) as admin:
    created = []
    try:
        for database in [name, restored]:
            admin.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
            )
            created.append(database)
        manage(name, "migrate", "core", "0012", "--noinput")
        execute(name, seed)
        before = snapshot(name)
        dump = subprocess.check_output(
            [
                "docker",
                "exec",
                container,
                "pg_dump",
                "-U",
                config["USER"],
                "-d",
                name,
                "--format=custom",
                "--no-owner",
                "--no-privileges",
            ]
        )
        path = folder / (name + ".dump")
        with path.open("xb") as out:
            os.chmod(path, 0o600)
            out.write(dump)
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                container,
                "pg_restore",
                "-U",
                config["USER"],
                "-d",
                restored,
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
            ],
            input=dump,
            check=True,
            capture_output=True,
        )
        assert snapshot(restored) == before
        manage(restored, "migrate", "--noinput")
        after_schema = snapshot(restored)
        assert after_schema["invariant_sha256"] == before["invariant_sha256"]
        execute(restored, "from core.retention import cleanup; cleanup()")
        after_cleanup = snapshot(restored)
        assert after_cleanup["invariant_sha256"] == before["invariant_sha256"]
        assert after_cleanup["membership_edges"] == before["membership_edges"] == 3
        assert after_cleanup["recoverable_activity_columns"] == 0
        assert not after_cleanup["legacy_receipt_table"]
        assert (
            after_cleanup["keypackage_device_links"]
            == after_cleanup["keypackage_claim_links"]
            == 1
        )
        # Production reverse migration must fail before executing any reverse DDL.
        reverse = subprocess.run(
            [sys.executable, "manage.py", "migrate", "core", "0012", "--noinput"],
            cwd=root / "apps/api",
            env={**os.environ, "POSTGRES_DB": restored},
            capture_output=True,
            text=True,
        )
        assert reverse.returncode and "IrreversibleError" in reverse.stderr
        assert snapshot(restored) == after_cleanup
        # Repeated migrate/cleanup after failure is idempotent.
        manage(restored, "migrate", "--noinput")
        execute(restored, "from core.retention import cleanup; cleanup()")
        assert snapshot(restored) == after_cleanup
        print(
            json.dumps(
                {
                    "before": before,
                    "after_schema": after_schema,
                    "after_cleanup": after_cleanup,
                    "synthetic_dump_sha256": hashlib.sha256(dump).hexdigest(),
                    "dump_bytes": len(dump),
                    "dump_restore": "PASS",
                    "invariants_preserved": "PASS",
                    "reverse_refused_without_changes": "PASS",
                    "restart_idempotent": "PASS",
                    "scope": "Synthetic schema/routing/retention fixture, not MLS ciphertext validity; no identity unlinkability claim",
                },
                indent=2,
            )
        )
    finally:
        for database in reversed(created):
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(database)
                )
            )
