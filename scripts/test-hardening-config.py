#!/usr/bin/env python3
"""Inspect rendered Compose using generated synthetic credentials; never starts services."""

import json
import os
import secrets
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
keys = {
    name: secrets.token_urlsafe(48)
    for name in (
        "HAVEN_SECRET_KEY",
        "HAVEN_ROUTING_SECRET",
        "HAVEN_RETIREMENT_REPLAY_SECRET",
        "POSTGRES_PASSWORD",
        "HAVEN_DB_MIGRATION_PASSWORD",
        "HAVEN_DB_RUNTIME_PASSWORD",
        "HAVEN_DB_NOTIFICATION_PASSWORD",
    )
}
env = {
    **os.environ,
    **keys,
    "HAVEN_HOSTS": "127.0.0.1",
    "HAVEN_ORIGINS": "https://127.0.0.1",
    "HAVEN_TLS_DIR": "/synthetic-not-mounted",
}
started = time.monotonic()
result = subprocess.run(
    [
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "-f",
        "infrastructure/compose/compose.yml",
        "config",
        "--format",
        "json",
    ],
    cwd=root,
    env=env,
    capture_output=True,
    text=True,
    timeout=15,
    check=False,
)
if result.returncode:
    raise SystemExit("FAIL: Compose configuration rejected; credentials withheld")
services = json.loads(result.stdout)["services"]
worker = services["outbox"]
wenv = worker["environment"]
assert wenv["DJANGO_SETTINGS_MODULE"] == "haven.notification_settings"
assert wenv["POSTGRES_PASSWORD"] == keys["HAVEN_DB_NOTIFICATION_PASSWORD"]
assert wenv["POSTGRES_USER"] == "haven_notify"
assert wenv["HAVEN_ROUTING_SECRET"] == keys["HAVEN_ROUTING_SECRET"]
assert not worker.get("volumes")
assert "HAVEN_SECRET_KEY" not in wenv
assert keys["HAVEN_SECRET_KEY"] not in wenv.values()
assert keys["HAVEN_DB_RUNTIME_PASSWORD"] not in wenv.values()
assert (
    services["api"]["environment"]["POSTGRES_PASSWORD"]
    == keys["HAVEN_DB_RUNTIME_PASSWORD"]
)
assert worker["read_only"] and worker["cap_drop"] == ["ALL"]
assert (
    services["prepare-db-roles"]["environment"]["HAVEN_DB_NOTIFICATION_PASSWORD"]
    == keys["HAVEN_DB_NOTIFICATION_PASSWORD"]
)
print(
    json.dumps(
        {
            "status": "PASS",
            "seconds": round(time.monotonic() - started, 4),
            "claim": "Rendered notification service has independent DB credentials/routing key and no API signing key or certificate mount",
            "deployed": False,
        }
    )
)
