# Installation, upgrade and restore

## Normal deployment

Use a coordinated API/client/worker upgrade. Apply migrations through **0020**; 0019 introduced the closure/replay records and 0020 indexes the bounded retirement queue. New conversations use the v2 signed policy by default. No test-settings import or disposable-database nonce is required for ordinary retirement.

Generate `HAVEN_RETIREMENT_REPLAY_SECRET` independently of application and routing keys, with at least 48 random characters. Keep it permanently with the protected retirement journal; do not rotate it as an ordinary application secret. SQL stores a commitment that rejects mismatched keys. The journal is HMAC-authenticated, fsynced before destructive SQL, append-only by application convention, mode 0700 with 0600 entries, and mounted separately from PostgreSQL. It contains opaque conversation IDs, keyed group/message exclusions, attachment tombstones, signed-chain hashes and a finality digest, never participant/account/device identifiers.

Compose supplies the named `retirement` volume. API access is read-only; the retirement worker is the writer. The notification worker receives neither the journal nor retirement key. The privacy worker receives no journal/key. Provision and back up this volume independently of SQL, with operational access restricted to the service owner. A volume alone is not an independent backup.

Only for a genuinely new retirement installation, after building images and preparing the required environment:

```sh
docker compose --env-file .env -f infrastructure/compose/compose.yml --profile bootstrap run --rm retirement-init
docker compose --env-file .env -f infrastructure/compose/compose.yml up -d api web outbox privacy retirement ingress
```

Run existing role/migration setup first using the guided installer/runbook. The updated guided setup generates the independent secret and explicitly initializes the journal once. It records completion and refuses silently recreating an established journal. Existing installations require this coordinated upgrade; this change did not modify the running `haven-*` containers on the development host.

The regular `python manage.py retire_conversations` worker processes bounded batches of 25 with a 30-second polling interval and fair keyset traversal. `--once` supports bounded maintenance; `--conversation UUID` targets one authorized conversation. It verifies all consent/final receipts and authorization again, settles outstanding obligations and charges permanent replay storage before publication. There is no public destructive HTTP endpoint or timer that grants consent. Permanent budget exhaustion retains the graph. Existing privacy maintenance continues to expire abandoned uploads, finished view-once leases and security audit data under their established policies.

Do not use `initialize_retirement_journal --new-installation` to repair a missing established journal. Restore the protected current volume/key. Missing, corrupt or conflicting journal state fails closed. A crash after journal fsync but before SQL commit may leave SQL history present; writes are denied by the journal and startup reconciliation finishes the deletion safely.

## SQL restore

1. Stop **all** API, retirement, privacy and notification writers and fence the old primary. Restore SQL without exposing it to users.
2. Restore/mount the latest independent retirement journal and its original secret. **Never roll it back together with the SQL snapshot.** Retain the original volume when restoring an older database. A total rollback/loss of all current copies is outside this guarantee.
3. Set fresh random `HAVEN_CONTACT_LINK_EPOCH` and `HAVEN_CLOSURE_EPOCH` values before reopening. Existing nonretired closure attempts become read-only rather than reusing rolled-back consent. Review fresh-device/recovery requirements; never restore client ratchets as active state.
4. Apply matching migrations and start the API using `python -m haven.server`, as Compose does. It authenticates the journal and reconciles before accepting traffic. A restored conversation is removed only when its SQL signed head is an authenticated prefix of the retired journal. A contradictory head blocks startup. Snapshots older than the conversation itself still reinstall permanent deny markers and storage charges.
5. Verify reconciliation and health, then resume other workers and ingress. Retain the failed instance for operator diagnosis if reconciliation fails; do not empty the journal to make startup succeed.

The service cannot revoke already exported recipient archives or erase old SQL backups in place. Set backup retention and storage destruction separately. `make release-check` verifies operational source activation; `python3 scripts/release-gate.py --qualification` still reports missing independent/deployment assurance without disabling the product.
