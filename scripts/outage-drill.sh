#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Stops only this repository's disposable Redis, never another project or production Redis.
set -a
source .local/test.env
set +a
trap 'docker compose --env-file .local/test.env -f infrastructure/compose.test.yml start redis > /dev/null' EXIT
apps/api/.venv/bin/python scripts/outage-drill.py
