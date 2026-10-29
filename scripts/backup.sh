#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${HAVEN_BACKUP_RECIPIENT:?Set an independently verified GPG recipient fingerprint}"
: "${HAVEN_BACKUP_DIR:?Set protected backup directory outside the checkout}"
mkdir -p "$HAVEN_BACKUP_DIR"
chmod 700 "$HAVEN_BACKUP_DIR"
umask 077
stamp=$(date -u +%Y%m%dT%H%M%SZ)
output="$HAVEN_BACKUP_DIR/haven-$stamp.sql.gpg"
# No plaintext backup touches disk. Includes all encrypted blobs held in PostgreSQL.
docker compose --env-file .env -f infrastructure/compose/compose.yml exec -T db sh -c 'pg_dump --format=custom --no-owner -U "$POSTGRES_USER" "$POSTGRES_DB"' | gpg --batch --encrypt --recipient "$HAVEN_BACKUP_RECIPIENT" --output "$output"
sha256sum "$output" > "$output.sha256"
checksum=$(sha256sum "$output" | cut -d' ' -f1)
docker compose --env-file .env -f infrastructure/compose/compose.yml exec -T api python manage.py record_operational_evidence backup "$checksum" --reference "backup-$stamp"
printf 'Encrypted backup created: %s\n' "$output"
echo 'Backup metadata recorded. Client vaults/keys are separate.'
echo 'Review old encrypted archives with scripts/prune-backups.py --directory "$HAVEN_BACKUP_DIR"; use --apply only after reviewing the plan and verifying recovery copies.'
