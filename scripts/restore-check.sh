#!/usr/bin/env bash
set -euo pipefail
: "${HAVEN_BACKUP_FILE:?Set encrypted backup file}"
sha256sum --check "$HAVEN_BACKUP_FILE.sha256"
minimum="${HAVEN_RESTORE_MIN_ENVELOPES:-0}"
[[ "$minimum" =~ ^[0-9]{1,8}$ ]] || { echo 'Invalid minimum envelope count'; exit 1; }
name="haven-restore-$(openssl rand -hex 6)"
# Disposable, networkless, RAM-backed test PostgreSQL. Trust is local to this isolated container only.
trap 'docker rm -f "$name" > /dev/null 2>&1 || true' EXIT
docker run -d --name "$name" --network none --label haven.restore-test=true --tmpfs /var/lib/postgresql/data -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16.14-bookworm@sha256:64154d0babcb1741988719e703419af0382b19953706149f9872fbd0f438efa8 > /dev/null
ready=false
for attempt in {1..40}; do
  # The image's temporary initialization server accepts Unix sockets only.
  # Wait for final TCP readiness so it cannot stop between ready and restore.
  if docker exec "$name" pg_isready -h 127.0.0.1 -U postgres > /dev/null 2>&1; then ready=true; break; fi
  sleep 1
done
[[ "$ready" == true ]] || { echo 'Isolated database did not become ready'; exit 1; }
gpg --decrypt "$HAVEN_BACKUP_FILE" | docker exec -i "$name" pg_restore --exit-on-error --no-owner --no-privileges -U postgres --dbname=postgres
docker exec "$name" psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c 'SELECT count(*) AS encrypted_envelopes FROM core_messageenvelope; SELECT count(*) AS migrations FROM django_migrations;'
docker exec "$name" psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DO \$\$ BEGIN IF (SELECT count(*) FROM core_messageenvelope) < $minimum THEN RAISE EXCEPTION 'Expected ciphertext dataset absent'; END IF; END \$\$;"
echo 'PASS: isolated schema/data restore. This does not qualify client epoch continuity or failover.'
