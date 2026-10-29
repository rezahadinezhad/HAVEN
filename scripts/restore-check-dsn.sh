#!/usr/bin/env bash
set -euo pipefail
: "${HAVEN_BACKUP_FILE:?Set encrypted backup path}"
: "${HAVEN_RESTORE_DSN:?Set DSN for a NEW isolated scratch database}"
# Explicitly reject the application's database by requiring a scratch database naming convention.
python3 - <<'PY'
import os,urllib.parse
u=urllib.parse.urlparse(os.environ['HAVEN_RESTORE_DSN'])
assert u.scheme in ('postgres','postgresql') and u.path.startswith('/haven_restore_'), 'Scratch database must start haven_restore_'
PY
sha256sum --check "$HAVEN_BACKUP_FILE.sha256"
gpg --decrypt "$HAVEN_BACKUP_FILE" | pg_restore --exit-on-error --no-owner --dbname="$HAVEN_RESTORE_DSN"
psql "$HAVEN_RESTORE_DSN" -v ON_ERROR_STOP=1 -c 'SELECT count(*) AS encrypted_envelopes FROM core_messageenvelope; SELECT count(*) AS migrations FROM django_migrations;'
echo 'SQL restore completed; crypto continuity and latest-ACK reconciliation still require client tests.'
