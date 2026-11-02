#!/usr/bin/env python3
"""Real pooled transaction, revocation, timeout and recovery drill in an owned DB."""

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent
if (
    os.environ.get("POSTGRES_HOST", "127.0.0.1") != "127.0.0.1"
    or os.environ.get("POSTGRES_PORT", "55432") != "55432"
):
    raise SystemExit("Only loopback test PostgreSQL permitted")
info = json.loads(subprocess.check_output(["docker", "inspect", "haven-test-db-1"]))[0]
if (info["Config"].get("Labels") or {}).get("haven.test-only") != "true":
    raise SystemExit("Test database provenance required")
os.umask(0o077)
folder = ROOT / ".local" / ("pool-drill-" + secrets.token_hex(8))
folder.mkdir(mode=0o700)
name = "test_haven_pool_" + secrets.token_hex(8)
environment = {
    **os.environ,
    "POSTGRES_DB": name,
    "HAVEN_DB_POOL_SIZE": "2",
    "DJANGO_SETTINGS_MODULE": "haven.runtime_settings",
}
code = """
import json,secrets,time,threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import psycopg
from django.db import connection,transaction,DatabaseError,connections
from django.utils import timezone
from core import models as m
from core.middleware import resolve_session,digest

def pid():
 with connection.cursor() as cur:
  cur.execute('SELECT pg_backend_pid()')
  return cur.fetchone()[0]

with connection.cursor() as cur:cur.execute('CREATE TABLE pool_probe(id integer PRIMARY KEY)')
seen=set()
for _ in range(20):
 seen.add(pid());connection.close()
assert len(seen)<=2 and connection.pool.get_stats()['connections_num']<=2
u=m.User.objects.create_user(username='synthetic_pool',password=secrets.token_urlsafe(32))
token=secrets.token_urlsafe(48)
s=m.Session.objects.create(user=u,token_hash=digest(token),expires_at=timezone.now()+timedelta(hours=1))
assert resolve_session(token) is not None
connection.close()
assert pid() in seen
m.Session.objects.filter(pk=s.pk).update(revoked_at=timezone.now())
connection.close()
assert resolve_session(token) is None
try:
 with transaction.atomic():
  with connection.cursor() as cur:
   cur.execute('INSERT INTO pool_probe VALUES(1)')
   cur.execute('SELECT 1/0')
except DatabaseError:pass
else:raise AssertionError('Real database error required')
connection.close()
with connection.cursor() as cur:
 cur.execute('SELECT count(*) FROM pool_probe');assert cur.fetchone()[0]==0
 cur.execute('SHOW synchronous_commit');assert cur.fetchone()[0]=='on'
assert connection.get_autocommit()
backend=pid()
marker='synthetic_parameter_'+secrets.token_hex(8)
with connection.cursor() as cur:
 cur.execute('SELECT %s::text',[marker]);assert cur.fetchone()[0]==marker
c=connection.settings_dict
with psycopg.connect(host=c['HOST'],port=c['PORT'],dbname=c['NAME'],user=c['USER'],password=c['PASSWORD'],autocommit=True) as admin:
 query=admin.execute('SELECT query FROM pg_stat_activity WHERE pid=%s',[backend]).fetchone()[0]
 assert marker not in query and '$1' in query
victim=pid();connection.close()
c=connection.settings_dict
with psycopg.connect(host=c['HOST'],port=c['PORT'],dbname=c['NAME'],user=c['USER'],password=c['PASSWORD'],autocommit=True) as admin:
 assert c['NAME'].startswith('test_haven_pool_')
 assert admin.execute('SELECT pg_terminate_backend(%s)',[victim]).fetchone()[0]
for _ in range(6):
 assert pid()!=victim
 connection.close()
assert connection.pool.get_stats().get('connections_lost',0)>=1
release=threading.Event()
ready=[threading.Event(),threading.Event()]
def hold(index):
 try:
  with transaction.atomic():
   pid();ready[index].set();assert release.wait(8)
 finally:connections.close_all()
with ThreadPoolExecutor(max_workers=2) as threads:
 futures=[threads.submit(hold,i) for i in range(2)]
 try:
  assert all(e.wait(5) for e in ready)
  begin=time.monotonic()
  try:pid()
  except DatabaseError:elapsed=time.monotonic()-begin
  else:raise AssertionError('Pool exhaustion must fail closed')
  assert 2.5<=elapsed<5
 finally:release.set()
 for future in futures:future.result(timeout=5)
assert pid()>0
stats=connection.pool.get_stats()
assert stats['pool_size']<=2
connection.close()
connection.close_pool()
print(json.dumps({'physical_connection_reused':'PASS','bound_values_absent_from_idle_query_text':'PASS','live_revocation_on_reuse':'PASS','real_sql_error_rolled_back':'PASS','autocommit_and_sync_commit':'PASS','terminated_idle_connection_replaced':'PASS','two_slot_exhaustion_failed_closed':'PASS','timeout_seconds':elapsed,'post_exhaustion_recovery':'PASS','pool_peak_bound':2,'scope':'Synthetic isolated PostgreSQL; no auth caching, transaction replay or weakened durability'},indent=2))
"""
with psycopg.connect(
    host="127.0.0.1",
    port=55432,
    dbname="postgres",
    user=os.environ.get("POSTGRES_USER", "haven"),
    password=os.environ["POSTGRES_PASSWORD"],
    autocommit=True,
) as admin:
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        for command, env in [
            (
                [sys.executable, "manage.py", "migrate", "--noinput"],
                {**environment, "DJANGO_SETTINGS_MODULE": "haven.settings"},
            ),
            (
                [sys.executable, "manage.py", "shell", "--no-imports", "-c", code],
                environment,
            ),
        ]:
            result = subprocess.run(
                command, cwd=ROOT / "apps/api", env=env, capture_output=True, text=True
            )
            if result.returncode:
                (folder / "private-error.txt").write_text(result.stdout + result.stderr)
                raise RuntimeError("Pool drill failed; protected diagnostics retained")
        print(result.stdout.strip())
    finally:
        admin.execute(
            sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
        )
