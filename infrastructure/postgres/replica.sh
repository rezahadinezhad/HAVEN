#!/usr/bin/env bash
set -euo pipefail
umask 077
: "${HAVEN_REPLICATION_PRIMARY_IP:?required}"
: "${HAVEN_REPLICATION_PASSWORD_FILE:?required}"
# Input is a literal IPv4 tunnel address; never invoke a resolver or accept connection-string injection.
[[ "$HAVEN_REPLICATION_PRIMARY_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || exit 1
[[ "${HAVEN_REPLICATION_PORT:-5432}" =~ ^[0-9]{1,5}$ ]] || exit 1
[[ "${HAVEN_REPLICATION_SLOT:-haven_standby}" =~ ^haven_[a-z0-9_]{1,40}$ ]] || exit 1
IFS=. read -ra octets <<< "$HAVEN_REPLICATION_PRIMARY_IP"
for octet in "${octets[@]}"; do
  [[ "$octet" == 0 || "$octet" != 0* ]] || exit 1
  (( 10#$octet <= 255 )) || exit 1
done
(( 10#${HAVEN_REPLICATION_PORT:-5432} >= 1 && 10#${HAVEN_REPLICATION_PORT:-5432} <= 65535 )) || exit 1
mkdir -p /run/haven
password=$(cat "$HAVEN_REPLICATION_PASSWORD_FILE")
[[ "$password" =~ ^[0-9a-f]{64,128}$ ]] || { echo 'Replication password must be random hexadecimal'; exit 1; }
printf '%s:%s:replication:haven_repl:%s\n' "$HAVEN_REPLICATION_PRIMARY_IP" "${HAVEN_REPLICATION_PORT:-5432}" "$password" > /run/haven/pgpass
unset password
chown postgres:postgres /run/haven/pgpass
mkdir -p "$PGDATA"
chown postgres:postgres "$PGDATA"
chmod 600 /run/haven/pgpass
export PGPASSFILE=/run/haven/pgpass
if [[ ! -f "$PGDATA/PG_VERSION" ]]; then
  [[ -z $(find "$PGDATA" -mindepth 1 -maxdepth 1 -print -quit) ]] || { echo 'Refusing to overwrite nonempty database directory'; exit 1; }
  gosu postgres pg_basebackup --checkpoint=fast --dbname="host=$HAVEN_REPLICATION_PRIMARY_IP port=${HAVEN_REPLICATION_PORT:-5432} user=haven_repl sslmode=verify-full sslrootcert=/etc/haven/db-tls/roots.pem" -D "$PGDATA" -R -X stream --create-slot --slot="${HAVEN_REPLICATION_SLOT:-haven_standby}"
fi
[[ -f "$PGDATA/standby.signal" ]] || { echo 'This checkout is no longer a standby. Select the promoted-primary deployment explicitly after fencing; refusing automatic writer startup.'; exit 1; }
exec gosu postgres postgres -D "$PGDATA" -c ssl=on -c ssl_cert_file=/etc/haven/db-tls/leaf.crt -c ssl_key_file=/etc/haven/db-tls/leaf.key
