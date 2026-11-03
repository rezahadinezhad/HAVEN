# Dependency-ordered implementation

0. Establish clean revision, inspect existing controls, bounded baseline and threat inventory (done before edits).
1. Optional pseudonymous registration; minimal UUID-only offline unlock pointer; no cached roles/profile.
2–3. Separate own/peer/admin contracts; require own/shared-history or explicitly shared expiring introduction for lookup and new claims; preserve signed proof bytes and independent fingerprint verification; no default real name in links.
4. Dedicated HMAC routing key, purpose separator, canonical UUID, dual-key publisher transition, authenticated heartbeat repair.
5. Real notification-only PostgreSQL login, pending-target view, explicit outbox columns, remove API DB/signing secret from worker environment. Retention remains broad because it genuinely performs cross-table locking and cleanup.
6. One-click privacy profile using current off preferences; preserve mandatory ACKs.
7. Versioned bucketed attachment AEAD; legacy decrypt; encrypted true length, exact chunk validation, quotas on padded bytes; focused small measurements.
8–9. Audit failure paths, retention/log redaction and browser/CSP/worker lifecycle; retain proven controls, repair concrete gaps only.
10. Complete closure/finality adversarial specification, no destructive runtime feature.
11–12. Source-backed review; disposable DB migration/grant tests, real browser/native compatibility tests; no multi-hour runs.
13. Update manifests, contracts, before/after evidence, security review and final status. Production source gate remains closed. No push/merge/deploy.

Tests have explicit timeout ceilings (120s unit/Redis, 180s DB/crypto, 300s browser, 30s micro measurements), single browser worker and limited build parallelism. Any timeout is NOT_VERIFIED. See final results for executed commands, durations and gaps.
