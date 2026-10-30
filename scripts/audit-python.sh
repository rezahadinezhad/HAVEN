#!/usr/bin/env bash
# Audit the complete pinned graph, including development/testing dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
requirements=$(mktemp "${TMPDIR:-/tmp}/haven-python-audit.XXXXXXXX")
trap 'rm -f "$requirements"' EXIT
uv lock --project apps/api --check
uv export --project apps/api --frozen --all-groups --no-emit-project --output-file "$requirements" > /dev/null
uv run --project apps/api --frozen pip-audit --strict --disable-pip --require-hashes --progress-spinner off --requirement "$requirements" "$@"
