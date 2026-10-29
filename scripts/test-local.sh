#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export NEXT_TELEMETRY_DISABLED=1
set -a
source .local/test.env
set +a
node scripts/build-integration.mjs
(cd apps/api && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/python manage.py makemigrations --check --dry-run && .venv/bin/pytest -q)
cargo fmt --manifest-path packages/crypto-core/Cargo.toml --check
HAVEN_GOLDEN_FILE="$PWD/.local/native-wasm-golden.json" cargo test --manifest-path packages/crypto-core/Cargo.toml --locked -j 2
npm run typecheck --prefix apps/web
npm test --prefix apps/web
