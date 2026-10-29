#!/usr/bin/env bash
# Read-only copy of disposable browser-test ciphertext. Never targets an operator database.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${HAVEN_BACKUP_RECIPIENT:?Independently verified TEST GPG recipient fingerprint}"
: "${HAVEN_BACKUP_DIR:?Protected TEST backup directory}"
[[ "$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' haven-test-db-1)" == haven-test ]] || { echo 'Disposable database identity mismatch'; exit 1; }
count=$(docker exec haven-test-db-1 psql -U haven -d haven -Atqc 'SELECT count(*) FROM core_messageenvelope')
[[ "$count" =~ ^[0-9]+$ && "$count" -gt 0 ]] || { echo 'Real browser ciphertext dataset required'; exit 1; }
umask 077
mkdir -p "$HAVEN_BACKUP_DIR"
chmod 700 "$HAVEN_BACKUP_DIR"
output="$HAVEN_BACKUP_DIR/ciphertext-$(date -u +%Y%m%dT%H%M%SZ)-$(openssl rand -hex 4).sql.gpg"
docker exec haven-test-db-1 pg_dump -U haven -d haven --format=custom --no-owner | gpg --batch --encrypt --recipient "$HAVEN_BACKUP_RECIPIENT" --output "$output"
sha256sum "$output" > "$output.sha256"
HAVEN_BACKUP_FILE="$output" HAVEN_RESTORE_MIN_ENVELOPES=1 bash scripts/restore-check.sh
echo 'PASS actual browser-test ciphertext backup/isolated restore; separate from the gated empty staging metadata check.'
