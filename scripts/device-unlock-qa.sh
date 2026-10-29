#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .local/test.env && -f .local/ui-credentials.json ]] || {
  echo 'Local test environment and QA bootstrap credentials are required.' >&2
  exit 1
}
bash scripts/dev-hostname-cert.sh
python3 - <<'PY'
import socket
for port in (3101, 8102, 8446):
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"Port {port} is already in use; stop the prior hostname QA stack first")
PY
npm --prefix apps/web run build
set -a
source .local/test.env
set +a
export HAVEN_HOSTS=127.0.0.1,localhost
export HAVEN_ORIGINS=https://127.0.0.1:8445,https://localhost:8446
export HAVEN_OPTIONAL_HOSTNAME=localhost
export DJANGO_SETTINGS_MODULE=haven.integration_settings
mkdir -p .local
pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM
PORT=3101 HOSTNAME_OVERRIDE=127.0.0.1 bash scripts/serve-web.sh > .local/device-unlock-hostname-web.log 2>&1 & pids+=("$!")
(cd apps/api && exec .venv/bin/uvicorn haven.asgi:application --host 127.0.0.1 --port 8102 --no-access-log --proxy-headers) > .local/device-unlock-hostname-api.log 2>&1 & pids+=("$!")
HAVEN_DEV_PORT=8446 HAVEN_DEV_API_PORT=8102 HAVEN_DEV_WEB_PORT=3101 HAVEN_INTEGRATION=1 \
  HAVEN_DEV_TLS_KEY=.local/tls/localhost-test.key HAVEN_DEV_TLS_CERT=.local/tls/localhost-test.crt \
  node scripts/dev-proxy.mjs > .local/device-unlock-hostname-proxy.log 2>&1 & pids+=("$!")
ready=0
for attempt in $(seq 1 60); do
  if curl --fail --silent --show-error --cacert .local/tls/root.crt \
    https://localhost:8446/api/v1/health >/dev/null 2>&1 \
    && curl --fail --silent --show-error --cacert .local/tls/root.crt \
      https://localhost:8446/ >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
[[ "$ready" == 1 ]] || {
  echo 'Trusted hostname test stack did not become ready.' >&2
  exit 1
}
curl --fail --silent --show-error --cacert .local/tls/root.crt \
  https://127.0.0.1:8446/ >/dev/null
wrong_host=$(curl --silent --show-error --cacert .local/tls/root.crt \
  -H 'Host: other.localhost' -o /dev/null -w '%{http_code}' \
  https://localhost:8446/api/v1/health)
wrong_web_host=$(curl --silent --show-error --cacert .local/tls/root.crt \
  -H 'Host: other.localhost' -o /dev/null -w '%{http_code}' \
  https://localhost:8446/)
wrong_origin=$(curl --silent --show-error --cacert .local/tls/root.crt \
  -H 'Origin: https://other.localhost' -H 'Content-Type: application/json' \
  --data '{}' -o /dev/null -w '%{http_code}' \
  https://localhost:8446/api/v1/auth/login)
[[ "$wrong_host" == 400 && "$wrong_web_host" == 400 && "$wrong_origin" == 403 ]] || {
  echo "Exact Host/Origin check failed: API=$wrong_host web=$wrong_web_host origin=$wrong_origin" >&2
  exit 1
}
(cd apps/web && HAVEN_HOSTNAME_QA_ORIGIN=https://localhost:8446 \
  npx playwright test tests/device-unlock-ui.spec.ts --reporter=line)
