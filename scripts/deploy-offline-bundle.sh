#!/usr/bin/env bash
set -euo pipefail
: "${HAVEN_BUNDLE_DIR:?Set bundle directory}"
: "${HAVEN_RELEASE_PUBLIC_KEY:?Independently verified public signing key path}"
root=$(cd "$(dirname "$0")/.." && pwd)
openssl pkeyutl -verify -rawin -pubin -inkey "$HAVEN_RELEASE_PUBLIC_KEY" -in "$HAVEN_BUNDLE_DIR/MANIFEST.json" -sigfile "$HAVEN_BUNDLE_DIR/MANIFEST.sig"
python3 "$root/scripts/manifest.py" "$HAVEN_BUNDLE_DIR" | cmp - "$HAVEN_BUNDLE_DIR/MANIFEST.json"
docker image load -i "$HAVEN_BUNDLE_DIR/runtime.images.tar"
echo 'Verified images loaded without package fetches. Configure protected .env and independently trusted IP TLS before starting.'
echo 'Production onboarding remains BLOCKED; run scripts/release-gate.py before any real deployment.'
