#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo 'HAVEN setup requires Python 3.10 or newer.' >&2; exit 1; }
exec python3 scripts/setup.py "$@"
