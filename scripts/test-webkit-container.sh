#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Public TEST certificate only; trust is confined to this disposable container.
context=$(mktemp -d)
trap 'rm -rf "$context"' EXIT
cp infrastructure/browser-tests/Dockerfile "$context/Dockerfile"
cp .local/tls/root.crt "$context/haven-test-root.crt"
docker build -t haven-browser-test:1.64.1 "$context"
docker run --rm --network host --cap-drop ALL --shm-size 128m --read-only --tmpfs /tmp:size=512m -v "$PWD/apps/web/node_modules:/work/node_modules:ro" -v "$PWD/infrastructure/browser-tests/webkit-smoke.mjs:/work/smoke.mjs:ro" haven-browser-test:1.64.1 node /work/smoke.mjs
