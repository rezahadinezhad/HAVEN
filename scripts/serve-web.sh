#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
repository_dir="$PWD"
mkdir -p .local
runtime_dir=$(mktemp -d "$repository_dir/.local/web-runtime.XXXXXXXX")
# A running server must never depend on .next files replaced by the next build.
# Next's standalone output is relocatable; static/public assets are copied explicitly.
cp -a apps/web/.next/standalone/. "$runtime_dir/"
mkdir -p "$runtime_dir/.next"
cp -a apps/web/public "$runtime_dir/"
cp -a apps/web/.next/static "$runtime_dir/.next/"
export PORT="${PORT:-3100}" HOSTNAME="${HOSTNAME_OVERRIDE:-127.0.0.1}" NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
cd "$runtime_dir"
exec node server.js
