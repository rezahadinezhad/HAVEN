# Coordinated upgrade and recovery: migrations 0013/0014/0015/0016

This procedure is prepared for operator review; **no staging/production deployment, role change or backup deletion was performed**. Existing normal crypto/release gates remain closed. Do not apply test-only integration settings to a real endpoint.

## Preflight

1. Record source revision, current migration state and sole-writer/fencing status. Supported starting states include core 0012 or the previously hardened 0013/0014/0015; inspect any local forks/custom code for references to removed fields/DeliveryReceipt, nonstandard OpenMLS configs, direct Device writes and unusual KeyPackage writes. Reject unreviewed extensions.
2. Verify a separately protected encrypted backup and an actual restore in an isolated database. Inventory WAL archives, replicas, filesystem/provider snapshots and backup copies. Save deployment/configuration and keys separately with appropriate access controls. Do not delete them automatically.
3. Count old metadata, expired pending enrollments and KeyPackage backlog using authorized local SQL or aggregate queries. Check disk/WAL headroom and long transactions. 0013 has PostgreSQL transactional DDL and can require exclusive table locks; schedule a controlled outage rather than forcing locks against active traffic. Ciphertexts, signed history, quotas, active sessions, leases and cursors must survive.
4. Build matching API and web artifacts, regenerate contracts, include the rebuilt WASM and offline manifest, verify source checksums, tests and release status. The old release classification is not improved by local passes. No browser DB migration is needed.

## Upgrade order

Stop API, outbox and privacy workers, including promotion/standby copies that could write. Fence competing database writers. Apply migrations using the migration role and existing `migrate_haven`/deployment procedure; runtime must remain unable to perform DDL or mutate migration history. **Do not run old ORM processes against 0013.**

0013 drops three unused time columns and the unused receipt table; it permits NULL for expired KeyPackage.device. It changes no message bytes, signature, MLS epoch, ordering hash, cursor seq, auth binding, view consumption or StorageUsage. A forward-only RunPython marker makes reversal fail before reverse DDL. No destructive data rewrite of cryptographic state is performed. Migration atomicity allows a failed DDL transaction to roll back; investigate the underlying lock/disk/SQL failure before retrying. Do not use `--fake` to disguise failure.

0014 adds a partial `(expires_at, id)` index over packages with remaining payload/identity/claim state, so permanently scrubbed replay tombstones do not grow the cleanup index. Apply it in the same controlled upgrade.

0015 adds the ID-only DeviceEnrollmentTombstone table and partial pending-device expiry index. It deletes no Device rows during migration. Matching cleanup locks account then device, rechecks expiration/pending trust, writes the marker and deletes only an unreferenced never-approved pending enrollment. Approved/revoked/historical devices remain. Unexpected PROTECT references roll back the marker/deletion and increment aggregate `pending_devices_protected`; investigate them without deleting related trust/history/consumption records. Repeated passes can be needed. Both enrollment and verified recovery reject marker IDs. Reversal refuses before dropping the marker table/index, since losing exclusion IDs can reopen expired enrollments.

**Do not mix old APIs with the new cleanup worker.** Old enrollment code does not consult replay markers. Preserve the marker table through backup/restore reconciliation. New request fences also serialize authenticated writes with credential/device changes and lock affected accounts/conversations in sorted order. An already fenced mutation can finish before a waiting revocation; a later stale request fails. Read responses already in flight cannot be recalled.

0016 widens Session.device_challenge from 64 to 67 characters for an explicit internal `v2:` nonce prefix. It preserves old raw 64-hex nonces byte-for-byte. New challenges use a fresh nonce-scoped HMAC encoded as digits in the existing strict v1 signing grammar, without disclosing the global session PK. Old raw records alone use the old verifier; a newly issued challenge cannot opt into it. Unknown stored encodings fail closed and require a fresh challenge with the same device key. Do not truncate/strip version prefixes or mix old/new API writers; reverse migration refuses before narrowing the column. No browser storage clear, identity reset or new server encryption key is needed.

Start matching API/outbox/privacy, then web/ingress. Verify authenticated policy, static normal `crypto_ready=false`, approved-device enforcement and correct runtime grants. One bounded privacy pass clears expired package links, at most 500 per pass, including already-empty legacy payloads; migration alone does not clear that backlog. Inspect aggregate `privacy_maintenance` status and repeat bounded passes only on the fenced intended deployment. New `unavailable` status is failure-aware but Redis status is approximate and expires after 900 seconds.

Redis channel groups now expire after 120 seconds. Authenticated browser heartbeats refresh them and rebuild a missing group after transient Redis loss. Redis failure closes that socket with 1013; HTTP polling/reconnect remains authoritative. Do not treat the lack of a WebSocket hint as lost durable ciphertext. Rate-label keys retain their existing TTL and authentication scope.

Old browsers can receive RFC-compliant padded PrivateMessages, and new code can process old unpadded messages. Already-encrypted outbox entries retain exact ciphertext/signatures and must retry as-is. Old senders continue leaking finer sizes until updated; the server does not silently enforce a padding-only protocol. Known legacy group config upgrades on first new encryption without changing state version or keys; an unknown config fails closed and requires investigation, not automatic reset. Browser recovery/vaults must not be cleared.

## Verify and recover

Exercise pending/offline delivery, one exact duplicate retry, durable ACK, multi-device Add/Remove and rekey, encrypted vault reload, view-once consumed/unopened states, and secret rotation against synthetic accounts first. Reconcile durable sequence/head/checkpoints before reintroducing offline devices after restore. Watch quotas, disk/WAL and cleanup backlog.

If the deployment fails after commit, keep writers fenced. Correct the matching source/configuration forward. Reverse migration is intentionally refused because removed timestamps/receipts cannot be recreated honestly, replay markers must remain, and active versioned challenges must not be truncated. An older backup is for reviewed recovery only: restoring it can resurrect token/consumption state, lose accepted messages and rewind signed histories. Compare all relevant consumption/replay/revocation/checkpoint ledgers; never simply restore and resume traffic. No physical erasure or rollback resistance follows from a restore check.

## Reproduce synthetic migration and leakage evidence

With `.local/test.env` exported, run:

```bash
apps/api/.venv/bin/python scripts/test-metadata-migration.py
apps/api/.venv/bin/python scripts/test-privacy-migration.py
```

The new drill refuses non-loopback port 55432 and requires the Docker database's explicit `haven.test-only=true` provenance. It creates randomized disposable databases, seeds three synthetic active accounts/devices, a signed-structure fixture, offline recipients, live/expired packages, active consumed/unopened media ledgers, an expired pending device and resource state. It creates an owner-only custom PG dump in `.local/metadata-dumps`, restores it to a second randomized database, migrates 0012→latest, runs cleanup and compares a hash of selected preserved fields. It checks the expired enrollment account link disappears while the ID-only marker remains. It verifies reversal refusal, repeated migration/cleanup and drops only its own databases. Raw fixture dumps are local, not published evidence; they are not real MLS-valid ciphertext. Browser tests separately exercise real OpenMLS.

The older 0007→latest drill checks original consumption/TTL migration and reverse refusal. Forward-only tests for 0010/0011 now use fresh PostgreSQL databases rather than reversing the destructive 0013 schema. Their assertions and production reversal gate remain intact.
