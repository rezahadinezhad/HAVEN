#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
source .local/test.env
set +a
node scripts/build-integration.mjs
pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM
(cd apps/api && HAVEN_ORIGINS=https://127.0.0.1:8443,https://127.0.0.1:8445 DJANGO_SETTINGS_MODULE=haven.integration_settings exec .venv/bin/uvicorn haven.asgi:application --host 127.0.0.1 --port 8101 --no-access-log --proxy-headers) & pids+=("$!")
(cd apps/api && exec .venv/bin/python manage.py maintain_privacy) & pids+=("$!")
HAVEN_DEV_PORT=8445 HAVEN_DEV_API_PORT=8101 HAVEN_INTEGRATION=1 node scripts/dev-proxy.mjs & pids+=("$!")
echo 'TEST ONLY integrated messenger: https://127.0.0.1:8445. Requires make dev for Next/PostgreSQL/Redis.'
wait -n "${pids[@]}"
