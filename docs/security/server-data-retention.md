# Server data minimization

Engineering hardening, not an anonymity claim or an independent security review.
No extra user device, user-operated relay, Tor requirement or external runtime
service is introduced. Existing direct HTTPS-by-IP browser messaging is preserved.

## What cleanup removes

| Data | Policy |
|---|---|
| Application ciphertext | Eligible after 24 hours from acceptance, only after every eligible active approved device ACKs its durable local state |
| Exact receipt time on a retired application envelope | Cleared with its ciphertext |
| Unsynchronized application ciphertext | Retained; never discarded by this cleanup |
| MLS control events, Welcome, signed genesis/history, membership | Preserved for authenticated synchronization and replay/fork checks |
| Encrypted files/voice notes | Seven-day maximum; abandoned uploads one hour; deletion requests remove chunks immediately |
| View-once media | Chunks removed after all eligible openings finish or leases expire; consumption survives as an attachment marker and ID-only tombstone |
| Individual view-once records | No permanent opening timestamp; device/token/expiry removed on close or cleanup; recipient rows removed after all openings finish |
| Expired/revoked sessions, used/revoked/expired invitations, expired/consumed recovery challenges | Removed on the next cleanup pass |
| Successful login audit rows | No longer written; legacy rows removed by cleanup |
| Security audit events | Seven days |
| Sent notification outbox rows | One hour; unsent rows preserved |
| Expired public key-package payload/claim link | Removed; package digest/device replay tombstone retained indefinitely |
| Redis rate-limit labels | Keyed HMAC with a server secret outside Redis/DB, scoped by purpose/identity/minute; 120-second TTL |

Cleanup runs in a dedicated `privacy` service every five minutes, with at most
500 candidates per category/pass. A backlog can take multiple passes. Retention
deletion is independent of Redis notifications. Admin system status shows
`privacy_maintenance`; missing status may mean worker, DB, Redis or scheduling
failure and must be investigated. Redis status is approximate and not a durable
security attestation. One-shot maintenance exits nonzero on failure without
printing sensitive exception details. The authenticated policy API is
`GET /api/v1/privacy-policy`, also shown in English/Persian Settings.

Eligibility excludes later-epoch joins and devices that are removed/revoked,
unapproved, or whose account is inactive. Every eligible device needs its own
cursor: another device of the same person is insufficient. Membership changes,
sends, ACKs and retirement serialize on the conversation row; eligibility is
rechecked under the lock. Signed headers, sequence, ciphertext digest and
idempotency digest remain unchanged. This does not delete messages from devices.
An old/restored vault requesting retired ciphertext gets HTTP 410 and must enroll
a verified fresh device; the client never skips missing ratchet history. A current
persisted vault can reload, rekey and continue.

## What a stolen database still reveals

Account IDs, usernames/display names, password hashes, roles, device labels and
public credentials, conversation graph/membership, signed sender/order proofs,
pending ciphertext lengths/timing and necessary synchronization state remain.
Used-package and attachment replay tombstones also remain. View-once policy and
active lease state reveal access metadata while needed. This reduces the amount
and age of retained data; it does not hide the full social graph. Password hashes
permit offline guessing. Authentication does not itself supply old E2EE keys.

Removing central identities or the signed delivery graph requires a separately
designed and reviewed delivery protocol. Hashing a username or encrypting a disk
with an automatically available key is not proof of anonymity. E2EE keeps message
decryption keys on devices, subject to implementation/endpoint assumptions.

## IPs, logs and memory

Supplied primary/backup/bridge Nginx configurations remove common client address
headers before forwarding to Django/Next; the dev proxy does the same. Ingress
still sees network addresses in live connections and volatile rate/connection
limits. Root/kernel/provider observation cannot be prevented by switching off
logs. No IP is added to a Django model. Login limits use account-specific keyed
labels plus a service budget, avoiding one five-login budget on the entire
community after IP-header removal. Per-IP ingress abuse controls remain.

Nginx request/error logs and request/response spooling are disabled. Supplied
PostgreSQL statement/bind-parameter/connection logging and query process titles
are disabled. Error summaries, aggregate metrics and short-lived connection state
remain. Redis has no RDB/AOF persistence. Container logs have bounded rotation and
process core limits are zero; review host journaling, swap/hibernation, crash
handlers, disk encryption, snapshots and provider collection independently.
RAM-only data can still be observed by a running-host intruder. Host-owned
settings are not configured or verified by these application tests.

Django's default Redis pickle serializer is replaced with bounded JSON-only
decoding, preserving atomic integer counters. A tampered Redis value cannot use
that cache decoder to instantiate Python objects. A new cache namespace avoids
reading legacy pickles; old ephemeral keys expire. Cache connection/read timeouts
are bounded so a failed Redis status write cannot indefinitely stall maintenance.
Redis can still interfere with rate limits and notification availability if
compromised; it is never authoritative for durable messages or view-once claims.

## Upgrade, backup and restore

1. Verify an encrypted recovery backup; protect its decryption key separately.
2. Stop old API/outbox/privacy processes before migration. This is not a rolling
   mixed-schema upgrade. Migration 0008 preserves consumed openings, removes
   opening timestamps, and caps existing attachment expiry to creation + seven
   days. Files older than that become unavailable.
3. Build/deploy matching API/UI, apply migrations with the migration role, and
   start `api`, `outbox`, `privacy`, `web`, `ingress` on the sole writer.
4. Check health, `privacy_maintenance`, actual policy, proxy/TLS and message sync.
   Cold standby profiles keep privacy/API/outbox stopped until fenced promotion.
5. Stop maintenance before rollback. Migration 0008 is intentionally irreversible:
   restoring removed opening timestamps as empty could reopen consumed media.
   Never simply downgrade the schema. Review recovery/consumption ledgers and
   retained client checkpoints before restoring an older database.

Existing backups/snapshots can preserve removed information. On the protected
backup workstation run:

```bash
python3 scripts/prune-backups.py --directory /absolute/protected/backups
# Review the plan and verify recovery copies before applying:
python3 scripts/prune-backups.py --directory /absolute/protected/backups --apply
```

Defaults expire archives older than seven days while preserving at least three
newest checksum-verified archives. Minimum recovery copies may be kept longer.
Only HAVEN archive/checksum pairs are handled; symlinks, corrupt/missing checksums
and nonprivate directories stop rotation. Unrelated files are untouched. Checksums
do not prove decryptability, restore success or consumption-ledger freshness. No
existing operator archive is deleted automatically by this implementation.
Protect/rotate offsite copies and provider snapshots separately. Row deletion
does not erase old PostgreSQL pages, WAL, replicas or storage snapshots.

## Unchanged security boundaries

A compromised origin can deliver altered JS/WASM and steal keys/plaintext when a
user loads it and unlocks. HTTPS, CSP, PWA installation, signed bundles and cleanup
do not eliminate that boundary. Device compromise and recipient capture remain.
Independent crypto/application review, physical devices, real public TLS/domestic
networks, provider recovery/capacity qualification and OS advisory triage remain
required; normal `CRYPTO_READY=False` stays in place.

## Reproduce the checks

Use isolated `.local/test.env`, never production credentials, for API tests and
the migration drill:

```bash
cd apps/api && .venv/bin/pytest -q
# From repository root with test.env exported:
apps/api/.venv/bin/python scripts/test-privacy-migration.py
python3 scripts/test-privacy-infrastructure.py
npm test --prefix apps/web
HAVEN_BROWSER=firefox npm test --prefix apps/web -- tests/crypto.spec.ts tests/integration.spec.ts tests/privacy.spec.ts tests/design.spec.ts tests/view-once.spec.ts
```

The migration drill creates/removes only a randomized disposable database on
loopback test PostgreSQL. The proxy drill uses temporary pinned Nginx and loopback
echo services with verified test-CA TLS; it never disables verification. Evidence
and qualifications are in TEST_REPORT.md.

Session hardening (ADR 0011 / migration 0010) adds a server-only credential-binding HMAC to session rows so password updates invalidate older bearer tokens. It is neither a plaintext password nor an E2E key. Unfinished sign-ins are limited to five rows per account at new issuance, deleting the oldest unfinished rows; bound device sessions are excluded. Existing expiry/revocation cleanup remains. No IP, location, user-agent fingerprint or per-poll presence timestamp was added by this change; password hashes, credential-binding tags and account/device linkage remain visible in a stolen database. It is not an anonymity guarantee.
