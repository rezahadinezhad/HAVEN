#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for tool in python3 node npm cargo rustup docker openssl uv; do command -v "$tool"; done
node --version
python3 --version
rustc --version
docker info --format '{{.ServerVersion}}'
rustup target list --installed
free -h
df -h .
echo 'Capacity UNQUALIFIED. No thermal/physical-device/2-hour soak qualification has occurred.'
python3 scripts/release-gate.py
