#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${HAVEN_BUNDLE_DIR:?Verified prepared bundle directory}"
: "${HAVEN_RELEASE_PUBLIC_KEY:?Independently verified signing public key}"
: "${HAVEN_OFFLINE_WORKDIR:?New directory for extracted source and dependency cache}"
openssl pkeyutl -verify -rawin -pubin -inkey "$HAVEN_RELEASE_PUBLIC_KEY" -in "$HAVEN_BUNDLE_DIR/MANIFEST.json" -sigfile "$HAVEN_BUNDLE_DIR/MANIFEST.sig"
python3 scripts/manifest.py "$HAVEN_BUNDLE_DIR" | cmp - "$HAVEN_BUNDLE_DIR/MANIFEST.json"
[[ ! -e "$HAVEN_OFFLINE_WORKDIR" ]] || { echo 'Refusing to overwrite work directory'; exit 1; }
[[ -d "$HAVEN_BUNDLE_DIR/deps/wheels" && -d "$HAVEN_BUNDLE_DIR/deps/npm-cache" ]] || { echo 'Prepared dependency cache missing'; exit 1; }
mkdir -m 700 -p "$HAVEN_OFFLINE_WORKDIR"
tar -xzf "$HAVEN_BUNDLE_DIR/source.tar.gz" -C "$HAVEN_OFFLINE_WORKDIR"
cp -R "$HAVEN_BUNDLE_DIR/deps" "$HAVEN_OFFLINE_WORKDIR/offline-deps"
# Fail before the builder could try resolving an absent base through a registry.
while IFS= read -r image; do
  docker image inspect "$image" > /dev/null 2>&1 || { echo 'Required pinned base image absent; load the verified bundle first'; exit 1; }
done < <(sed -n 's/^FROM \([^ ]*\).*/\1/p' "$HAVEN_OFFLINE_WORKDIR/infrastructure/compose/Dockerfile.api-offline" "$HAVEN_OFFLINE_WORKDIR/infrastructure/compose/Dockerfile.web-offline" | sort -u)
# No online dependency fetching; cached base images must have been loaded from the verified bundle.
docker build --network=none --pull=false -f "$HAVEN_OFFLINE_WORKDIR/infrastructure/compose/Dockerfile.api-offline" -t haven-api:offline "$HAVEN_OFFLINE_WORKDIR"
docker build --network=none --pull=false -f "$HAVEN_OFFLINE_WORKDIR/infrastructure/compose/Dockerfile.web-offline" -t haven-web:offline "$HAVEN_OFFLINE_WORKDIR"
echo 'Offline application source rebuild completed using the bundled prebuilt Rust/WASM cryptographic artifacts.'
