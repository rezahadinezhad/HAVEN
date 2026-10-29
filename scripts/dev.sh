#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .local/test.env ]] || { echo 'Run make prepare first'; exit 1; }
set -a
source .local/test.env
set +a
export NEXT_TELEMETRY_DISABLED=1
scripts/dev-cert.sh
docker compose --env-file .local/test.env -f infrastructure/compose.test.yml up -d --wait
(cd apps/api && .venv/bin/python manage.py migrate --noinput)
pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM
(cd apps/api && exec .venv/bin/uvicorn haven.asgi:application --host 127.0.0.1 --port 8100 --no-access-log --proxy-headers) & pids+=("$!")
(cd apps/api && exec .venv/bin/python manage.py maintain_privacy) & pids+=("$!")
(exec bash scripts/serve-web.sh) & pids+=("$!")
node scripts/dev-proxy.mjs & pids+=("$!")
echo 'Local development: https://127.0.0.1:8443. Trust TEST root only in an isolated test profile; see runbook.'
wait -n "${pids[@]}"
