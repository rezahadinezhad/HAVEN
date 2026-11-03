# Migration, compatibility and recovery

**IMPLEMENTED_AND_TESTED** for isolated pre-upgrade schema and current clients; production deployment/backup drill NOT_RUN. No `.env` belonging to an existing installation or real backup was modified. Only `.local/test.env` received a previously missing independent disposable routing key.

## Before rollout

1. Keep the release gate closed. Review source/manifest and maintain owner-controlled, separately encrypted recoverable backups. Do not delete backup archives, credentials, vaults or pending outboxes.
2. Generate a distinct >=48-character `HAVEN_ROUTING_SECRET` and independent `HAVEN_DB_NOTIFICATION_PASSWORD` (>=32 characters, generated tooling uses 48 random bytes), protected like existing deployment secrets. Keep migration/bootstrap/runtime/notification roles/passwords distinct. `.env.example`, `create-secrets.py`, guided setup and validation describe the new configuration. Existing setup resumes must be explicitly upgraded; do not silently regenerate old secrets.
3. Use a coordinated frontend/API/worker rollout for the no-real-user installation. Drain pre-hardening raw-UUID WebSockets; old raw-label publishers/consumers are not compatible with new groups. HTTP sync is authoritative. The HMAC-key rotation sequence is in [routing](04-redis-metadata.md).
4. Provision roles with bootstrap credentials using `prepare_db_roles`, then run `migrate_haven` with migration-owner credentials. The latter verifies durability, applies 0017/0018 and applies restricted grants. Normal API/retention use the existing runtime login; outbox uses notification_settings and its independent login/routing key. Never give the worker migration/bootstrap credentials or the API signing key.

## Schema and state

0017 adds Device.introduction_generation with initial zero. No username, device UUID, public key, signed certificate/genesis/header, MLS group/epoch/ratchet, message request digest/ciphertext, ACK, attachment ledger or vault format changes. A deliberately irreversible no-op migration operation prevents reversing the counter: resetting it could revalidate a revoked grant. 0018 adds an owner-backed pending-recipient view; dropping/recreating that view alone is possible but old workers must be coordinated and regranted.

The isolated test builds schema 0016, seeds synthetic signed-byte/pending-envelope/membership/cursor fixtures, applies head, checks preserved values, increments a counter, reruns migrations and verifies rollback to 0016 raises IrreversibleError before the counter can be removed/reset. An attempted reverse can drop 0018 before hitting 0017's refusal; rerunning forward safely recreates it. Do not use --fake. Review actual migration plan before any reverse and never route production workers during partial rollback.

Attachment format 2 is additive encrypted metadata; current code reads legacy v1 and retries its exact ciphertext/AAD. Old v1-only frontend builds cannot render new v2 files; update clients together. Existing signed events, historical credentials and encrypted outboxes are not rewritten. A previous binary without introduction enforcement would reopen UUID discovery; it is not an acceptable privacy-preserving rollback target. Prefer a forward repair; keep current DB/vaults and release gate closed.

## Backup restoration

Restore into isolation first, preserve recovery/signing identities, confirm canonical trusted heads, membership/revocation, replay markers, view-once ledgers, quotas and pending accepted ciphertext before reopening. A DB restore can roll back per-device link revocation generations. Set a fresh OS-CSPRNG `HAVEN_CONTACT_LINK_EPOCH` outside PostgreSQL on every API process before serving a restored database. For example generate locally with Python `secrets.token_urlsafe(32)` and write the value to protected deployment configuration; do not put secrets in command output/logs. Its value is a signed namespace, not an encryption key. Old grants fail against the new namespace; new links can be issued without account/session/key rotation. Test `test_restore_epoch_invalidates_pre_restore_contact_grants_without_session_rotation` exercises this path.

This explicit operator fence does not automatically detect arbitrary malicious DB rollback or solve general signed-history rollback. Existing externally verified heads, recovery checks and documented restore/failover fences remain necessary. Reapplying migrations cannot recover old deleted data or prove physical erasure. Old archives/WAL/replicas retain their original graph. A new real encrypted archive/replica restoration was NOT_RUN.
