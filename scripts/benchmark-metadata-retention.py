#!/usr/bin/env python3
"""Real synthetic PG expiry index/backlog drill; no production data or Redis writes."""

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

import django
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps/api"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "haven.settings")
django.setup()
from django.conf import settings  # noqa: E402

config = settings.DATABASES["default"]
if config["HOST"] != "127.0.0.1" or str(config["PORT"]) != "55432":
    raise SystemExit("Only isolated loopback test PG is permitted")
info = json.loads(subprocess.check_output(["docker", "inspect", "haven-test-db-1"]))[0]
if (info["Config"].get("Labels") or {}).get("haven.test-only") != "true":
    raise SystemExit("Test infrastructure provenance required")
name = "test_haven_metadata_backlog_" + secrets.token_hex(8)
code = """
import json, time, uuid
from datetime import timedelta
from django.db import connection
from django.utils import timezone
from core import models as m
from core.retention import delete_pending_devices
now=timezone.now()
u=m.User.objects.create(username='synthetic_cleanup',password='!')
for start in range(0,10000,1000):
 rows=[]
 for i in range(1000):
  did=uuid.uuid4()
  rows.append(m.Device(id=did,user=u,identity=f'{u.pk}:{did}',label='Synthetic pending',public_key=b'x'*32,expires_at=now-timedelta(days=1)))
 m.Device.objects.bulk_create(rows)
with connection.cursor() as cur:
 cur.execute('ANALYZE core_device')
query=m.Device.objects.filter(trust_state='pending',revoked_at=None,expires_at__lte=now).order_by('expires_at','pk').values_list('pk','user_id')[:500]
plan=json.loads(query.explain(format='json',analyze=True,buffers=True))
def sizes():
 with connection.cursor() as cur:
  cur.execute("SELECT pg_total_relation_size('core_device'),pg_total_relation_size('core_deviceenrollmenttombstone')")
  return dict(zip(['device_relation_bytes','marker_relation_bytes'],cur.fetchone()))
before=sizes()
samples=[]
while True:
 started=time.monotonic()
 deleted,protected=delete_pending_devices(now,500)
 samples.append({'deleted':deleted,'protected':protected,'milliseconds':(time.monotonic()-started)*1000})
 if not deleted:break
 assert deleted<=500 and protected==0
assert sum(s['deleted'] for s in samples)==10000
assert m.Device.objects.count()==0 and m.DeviceEnrollmentTombstone.objects.count()==10000
print(json.dumps({'synthetic_expired_pending':10000,'batch_limit':500,'batches':samples,'first_candidate_query_plan':plan,'before':before,'after':sizes(),'scope':'Actual isolated PG index and bounded logical cleanup; opaque pending fixtures, not cryptographic approval or physical erasure; shared host; no global WAL attribution'},indent=2))
"""
with psycopg.connect(
    dbname="postgres",
    user=config["USER"],
    password=config["PASSWORD"],
    host=config["HOST"],
    port=config["PORT"],
    autocommit=True,
) as admin:
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        env = {**os.environ, "POSTGRES_DB": name}
        subprocess.run(
            [sys.executable, "manage.py", "migrate", "--noinput"],
            cwd=ROOT / "apps/api",
            env=env,
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            [sys.executable, "manage.py", "shell", "--no-imports", "-c", code],
            cwd=ROOT / "apps/api",
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        print(result.stdout.strip())
    finally:
        admin.execute(
            sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
        )
