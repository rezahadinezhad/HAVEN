#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# This prepares an isolated Linux WebKit image with the public TEST root only.
bash scripts/test-webkit-container.sh
docker run --rm --network host --cap-drop ALL --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp:size=512m,mode=1777 \
  -v "$PWD/apps/web/node_modules:/work/node_modules:ro" \
  -v "$PWD/infrastructure/browser-tests/webkit-select-repro.mjs:/work/repro.mjs:ro" \
  haven-browser-test:1.64.1 node /work/repro.mjs
# Match host UID to read the mode-0600 disposable QA credentials without broadening permissions.
docker run --rm --network host --cap-drop ALL --user "$(id -u):$(id -g)" \
  -e NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt \
  --shm-size 128m --read-only --tmpfs /tmp:size=512m,mode=1777 \
  -v "$PWD/apps/web/node_modules:/work/node_modules:ro" \
  -v "$PWD/infrastructure/browser-tests/webkit-ui.mjs:/work/ui.mjs:ro" \
  -v "$PWD/.local/ui-credentials.json:/run/haven-test-login.json:ro" \
  -v "$PWD/docs/evidence:/reports" haven-browser-test:1.64.1 node /work/ui.mjs
