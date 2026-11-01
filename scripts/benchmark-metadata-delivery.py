#!/usr/bin/env python3
"""Compare baseline/current APIs with synthetic MLS browsers in disposable PostgreSQL DBs.

Requires running local web/harness on 3100; touches no production data. Keeps all
credentials and child logs owner-only under .local. Outputs aggregate metrics.
"""

import io
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tarfile
import time
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
    raise SystemExit("Only isolated loopback PostgreSQL port 55432 is permitted")
info = json.loads(subprocess.check_output(["docker", "inspect", "haven-test-db-1"]))[0]
if (info["Config"].get("Labels") or {}).get("haven.test-only") != "true":
    raise SystemExit("Test-only database provenance required")
for port in (8110, 8111, 8450, 8451):
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(
                f"Isolated benchmark port {port} is already in use"
            ) from None
folder = root / ".local/metadata-delivery-benchmark"
folder.mkdir(mode=0o700, exist_ok=True)
if folder.stat().st_mode & 0o077:
    raise SystemExit("Private benchmark directory required")
archive = subprocess.check_output(["git", "archive", "0240706", "apps/api"])
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    tar.extractall(folder / "baseline", filter="data")
python = str(root / "apps/api/.venv/bin/python")
uvicorn = str(root / "apps/api/.venv/bin/uvicorn")
fields = [
    "xact_commit",
    "blks_read",
    "blks_hit",
    "tup_returned",
    "tup_fetched",
    "tup_inserted",
    "tup_updated",
    "tup_deleted",
    "temp_bytes",
    "deadlocks",
]
results = {}


def stats(admin, name):
    admin.execute("SELECT pg_stat_clear_snapshot()")
    row = admin.execute(
        sql.SQL("SELECT {} FROM pg_stat_database WHERE datname=%s").format(
            sql.SQL(",").join(map(sql.Identifier, fields))
        ),
        (name,),
    ).fetchone()
    return dict(zip(fields, row))


def cpu(pid):
    values = Path(f"/proc/{pid}/stat").read_text().split()
    return (int(values[13]) + int(values[14])) / os.sysconf("SC_CLK_TCK")


with psycopg.connect(
    dbname="postgres",
    user=config["USER"],
    password=config["PASSWORD"],
    host=config["HOST"],
    port=config["PORT"],
    autocommit=True,
) as admin:
    for index, kind in enumerate(["baseline", "current"]):
        name = "test_haven_metadata_bench_" + secrets.token_hex(8)
        work = folder / "baseline/apps/api" if kind == "baseline" else root / "apps/api"
        origin = f"https://127.0.0.1:{8450 + index}"
        environment = {
            **os.environ,
            "POSTGRES_DB": name,
            "HAVEN_ORIGINS": origin,
            "HAVEN_HOSTS": "127.0.0.1",
            "DJANGO_SETTINGS_MODULE": "haven.integration_settings",
            "MLS_PUBLIC_VERIFIER": str(
                root / "packages/crypto-core/bin/haven-public-verify-x86_64-linux"
            ),
        }
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        children = []
        try:
            subprocess.run(
                [python, "manage.py", "migrate", "--noinput"],
                cwd=work,
                env=environment,
                check=True,
                capture_output=True,
            )
            credentials = {
                "origin": origin,
                "username": "bench_" + secrets.token_hex(5),
                "password": secrets.token_urlsafe(40),
            }
            code = (
                "from core.models import User; User.objects.create_user(username="
                + repr(credentials["username"])
                + ",password="
                + repr(credentials["password"])
                + ',role="superadmin")'
            )
            subprocess.run(
                [python, "manage.py", "shell", "--no-imports", "-c", code],
                cwd=work,
                env=environment,
                check=True,
                capture_output=True,
            )
            private = folder / (kind + ".json")
            fd = os.open(private, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as out:
                json.dump(credentials, out)
            log = folder / (kind + ".txt")
            fd = os.open(log, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as logs:
                api = subprocess.Popen(
                    [
                        uvicorn,
                        "haven.asgi:application",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(8110 + index),
                        "--no-access-log",
                        "--proxy-headers",
                    ],
                    cwd=work,
                    env=environment,
                    stdout=logs,
                    stderr=logs,
                )
                children.append(api)
                proxy = subprocess.Popen(
                    ["node", "scripts/dev-proxy.mjs"],
                    cwd=root,
                    env={
                        **environment,
                        "HAVEN_DEV_PORT": str(8450 + index),
                        "HAVEN_DEV_API_PORT": str(8110 + index),
                        "HAVEN_INTEGRATION": "1",
                    },
                    stdout=logs,
                    stderr=logs,
                )
                children.append(proxy)
                for _ in range(40):
                    ready = subprocess.run(
                        [
                            "curl",
                            "--silent",
                            "--fail",
                            "--cacert",
                            str(root / ".local/tls/root.crt"),
                            origin + "/api/v1/health",
                        ],
                        capture_output=True,
                    )
                    if ready.returncode == 0:
                        break
                    time.sleep(0.25)
                else:
                    raise RuntimeError("Isolated benchmark did not start")
                browser = subprocess.Popen(
                    ["node", "scripts/benchmark-metadata-delivery.mjs"],
                    cwd=root,
                    env={**os.environ, "HAVEN_BENCH_CONFIG": str(private)},
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=logs,
                    text=True,
                )
                children.append(browser)
                if browser.stdout.readline().strip() != "READY":
                    raise RuntimeError(
                        "Browser setup failed; inspect private benchmark log"
                    )
                time.sleep(1.2)
                before = stats(admin, name)
                before_cpu = cpu(api.pid)
                output, _ = browser.communicate(input="measure\n", timeout=180)
                returncode = browser.returncode
                if returncode:
                    raise RuntimeError(
                        "Browser benchmark failed; inspect private benchmark log"
                    )
                data = json.loads(output.strip().splitlines()[-1])
                cpu_seconds = cpu(api.pid) - before_cpu
                rss = [
                    line
                    for line in Path(f"/proc/{api.pid}/status").read_text().splitlines()
                    if line.startswith("VmHWM:")
                ][0].split()[1]
                time.sleep(1.2)
                after = stats(admin, name)
                data["api_cpu_seconds"] = cpu_seconds
                data["api_peak_rss_kib"] = int(rss)
                data["postgres_counters"] = {
                    field: after[field] - before[field] for field in fields
                }
                results[kind] = data
        finally:
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )
print(
    json.dumps(
        {
            "baseline_revision": "0240706",
            "same_current_client": True,
            "scope": "one sequential baseline then current trial; synthetic localhost services/shared host; no production capacity inference",
            "results": results,
        },
        indent=2,
    )
)
