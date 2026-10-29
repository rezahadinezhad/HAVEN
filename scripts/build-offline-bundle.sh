#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${HAVEN_RELEASE_SIGNING_KEY:?Path to protected Ed25519 release signing key, outside this repository}"
bundle="${HAVEN_BUNDLE_DIR:-.local/offline-bundle}"
if [[ -e "$bundle" ]]; then echo 'Refusing to overwrite bundle' >&2; exit 1; fi
mkdir -p "$bundle/runtime"
cp -R infrastructure "$bundle/runtime/"
cp -R scripts "$bundle/runtime/"
cp .env.example SECURITY_STATUS.md RELEASE_CHECKLIST.md "$bundle/runtime/"
# Include current reviewable sources without secrets, dependency caches, or generated private test data.
tar --exclude='*/.venv' --exclude='*/node_modules' --exclude='*/.next' --exclude='*/target' --exclude='*/test-results' --exclude='*/__pycache__' --exclude='*/.pytest_cache' --exclude='*/.ruff_cache' --exclude='*.tsbuildinfo' --exclude='*/.env*' --exclude='*.key' -czf "$bundle/source.tar.gz" .agents skills-lock.json DESIGN.md PRODUCT.md apps packages scripts infrastructure rust-toolchain.toml .nvmrc .python-version .dockerignore .gitignore .env.example SOURCE_MANIFEST.sha256 EMERGENCY_MESSENGER_CODEX_MASTER_SPEC.md CODEX_START_HAVEN.md SHA256SUMS.txt Makefile README.md CHANGELOG.md SECURITY_STATUS.md TEST_REPORT.md IMPLEMENTATION_STATUS.md RELEASE_CHECKLIST.md THIRD_PARTY_NOTICES.md docs
if [[ -n "${HAVEN_OFFLINE_DEPENDENCIES:-}" ]]; then
  cp -R "$HAVEN_OFFLINE_DEPENDENCIES" "$bundle/deps"
  # Package fetch logs are unnecessary for installation and may contain workstation metadata.
  rm -rf "$bundle/deps/npm-cache/_logs"
  rm -f "$bundle/deps/npm-cache/_update-notifier-last-checked"
fi
{ docker compose --env-file .env -f infrastructure/compose/compose.yml config --images; sed -n 's/^FROM \([^ ]*\).*/\1/p' apps/api/Dockerfile apps/web/Dockerfile; } | sort -u > "$bundle/images.txt"
mapfile -t images < "$bundle/images.txt"
docker image save "${images[@]}" -o "$bundle/runtime.images.tar"
# Bind all artifact paths to the signed manifest; no secrets or CA private keys included.
python3 scripts/manifest.py "$bundle" > "$bundle/MANIFEST.json"
openssl pkeyutl -sign -rawin -inkey "$HAVEN_RELEASE_SIGNING_KEY" -in "$bundle/MANIFEST.json" -out "$bundle/MANIFEST.sig"
echo 'Bundle built. Transfer on encrypted media. Validate public signing key through independent channel.'
