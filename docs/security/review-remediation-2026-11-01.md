# Review remediation — 2026-11-01

All seven findings in the [independent source review](independent-review-2026-11-01.md) have implementation fixes and regression coverage. This is source-level engineering remediation, not an external security certification or authorization to open production onboarding. `CRYPTO_READY=False` and the existing external release requirements remain.

| Finding | Resolution |
| --- | --- |
| S1: malformed authenticated application content | Quarantine bounded metadata only after cryptographic verification; commit ratchet/cursor and continue valid traffic. Bad ciphertext remains fatal. |
| P1: monolithic vault ceiling/write amplification | Account-bound encrypted history records, atomic checkpoint/history commits, incremental writes, legacy migration and paged history-only exports. |
| S2: unbounded retained message growth | Transactional account/service byte and record budgets, conversation-creation budget, migration backfill, exact delivered-payload refunds and admission backpressure. |
| S3: shared sign-in budget exhaustion | Transport-derived source isolation, malformed-body rejection before counters, ingress pacing and bounded concurrent password hashing. |
| P2: per-conversation idle request/ACK storm | Fresh-discovery unchanged-head shortcut, receipt versions, ACK retry state and no unchanged cursor writes. Control reconciliation always refreshes detail. |
| P3: proof reads fetch unused ciphertext | Explicit deferred payload columns, verified with SQL capture. |
| F1: unpageable 100-conversation truncation | Signed device-bound keyset pagination on both endpoints; browser helper follows every page. |

The development dependency advisory is also remediated: the contract generator and its compatible fetch dependency are pinned to a graph with zero npm audit findings. Python and Rust audits report no known vulnerabilities. The existing Rust maintenance warning in conditional proof tooling remains visible; it is not a shipping runtime vulnerability or an advisory suppression.

See [ADR 0012](../adr/0012-review-remediation-storage-and-sync.md) for storage format, authentication, lock order, quota and sync decisions. Reproducible regression tests are in `apps/api/core/tests/test_review_remediation.py`, `apps/web/tests/review-remediation.spec.ts` and `apps/web/tests/vault-storage.spec.ts`.

## Upgrade and operations

1. Back up the database and retain the previous application images/source. Stop API writers and maintenance/outbox workers before the migration. Use the existing migration-role deployment flow to apply migrations 0011 and 0012, then start the updated API and background workers alongside the web assets. Do not run old writers against the new accounting model: old code does not reserve storage or maintain receipt versions.
2. Account and service counters are backfilled from existing records. Existing data above a budget is preserved; additional charged writes return 429 without changing conversation heads or dropping ciphertext. Inspect `logical_message_storage` and `database_bytes` in administrator system status. Investigate retained pending devices/ACKs, database capacity and retention before deliberately changing the fixed limits in reviewed settings. Removing database rows or resetting counters is not a quota-management procedure.
3. Logical message accounting includes conservative metadata allowance, not actual disk allocation. Provision and monitor PostgreSQL data/TOAST bloat, WAL, attachment storage, backups, replication slots and free host space separately. Existing attachment quotas remain separate. Restrict or stop admission before physical storage is exhausted; do not delete pending ciphertext to make space. Establish operator alerts appropriate to the deployment.
4. Close other HAVEN tabs before opening the updated client, so older IndexedDB connections cannot block the schema upgrade. Browser storage upgrades locally on open; legacy checkpoints are preserved until the first atomic successful write. Do not reset IndexedDB, clear browser site data or restore an old live ratchet as a migration step. Keep the vault secret/password-manager entry and separate recovery key. History-only exports support bounded encrypted pages; existing v1 kits still import. Browser quota failure leaves the last durable state intact and directs the user to export, then explicitly clear delivered history. Browser-specific disk recovery/forensic erasure is not promised.
5. Public login ingress now forwards the observed source only for that exact path and overwrites spoofed input. Keep the API private, use the supplied primary/standby/bridge configurations consistently, and do not place an untrusted proxy directly on the API listener. Review the updated [retention/privacy disclosure](server-data-retention.md). Production container logs still omit request bodies and addresses; source rate labels remain HMAC-scoped and short-lived.
6. Deploy the newly built worker and service-worker/offline manifest with the application. Rebuild artifacts using pinned dependencies; regenerate the source manifest after review. The generated contract body remains an array for conversation listing; callers outside this browser must follow `X-Haven-Next-Cursor`, or `next_cursor` on `/sync`.

## Validation

Final run details and limitations are retained in [the remediation evidence](../evidence/review-remediation-2026-11-01/README.md). The source review's earlier probes/results remain historical baseline evidence and are not silently rewritten to imply they ran against the repaired code.

Actual PostgreSQL/Redis tests cover concurrent per-account and service reservation, idempotent acceptance, withheld ACK retention, delivered-payload refunds, rollback of rejected writes, existing-record migration backfill, 205-entry discovery, signed cursor/device validation, proof SQL, no-op ACKs and source-separated sign-in. Browser regressions exercise real OpenMLS and live HTTP for quarantined messages, later valid traffic, reload and fatal ciphertext tampering; real IndexedDB tests cover a >16 MB history, record reuse, injected atomic write failure, record substitution, legacy migration, encrypted export, secret rotation, and cancellation during hashing or while queued behind a Web Lock.

These tests do not establish production capacity, an independent cryptographic audit, physical mobile behavior, secure memory erasure or host/infrastructure qualification. The original review's conclusions about those unmeasured areas still apply.

The local drill tooling now verifies an explicit `haven.test-only=true` Compose database label before copying a source database; isolated projects are selected with `COMPOSE_PROJECT_NAME`/`HAVEN_DRILL_SOURCE`. This avoids targeting the default development stack during a separate remediation run. Disposable TLS fixtures were renewed under their test-only CA, preserving previous files and keeping browser certificate verification enabled. No system CA trust, production deployment or existing production database was changed.

## Existing staging deployment upgraded

The existing `haven` staging project was upgraded at the owner's request. Migrations 0011 and 0012 were applied with the migration role after an authenticated encrypted database backup passed an isolated restore check. Every original row across 29 existing data tables matched its pre-upgrade fingerprint after migration; Django added the expected new content type and four model permissions. Storage accounting was independently recomputed and runtime permissions verified. No pending migrations remain.

Matching versioned API and web images are running with the ingress and all workers on the existing loopback endpoint `https://127.0.0.1:8444`. The existing TLS key was retained and its expired test leaf renewed under the same local test CA. Live HTTPS, CSP, Origin checks, offline assets, deployed source/worker/WASM hashes and a sandboxed browser sign-in-screen check passed. Existing deployment settings and account credentials were preserved except for the intended image tags. The normal production gate remains intact. See [sanitized deployment evidence](../evidence/review-remediation-2026-11-01/staging-upgrade.json).

Protected backup/recovery information and previous configuration snapshots are retained outside the checkout. The protected local completion record is located through `.local/review-upgrade-location`. The local `.local/manage-staging.sh` wrapper selects the existing project and its existing local-staging overlay explicitly. Browser vaults remain under their owners' control and migrate on the next successful save after unlocking; close other HAVEN tabs before opening the updated client.
