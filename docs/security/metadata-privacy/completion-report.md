# HAVEN metadata privacy — completion and qualification report

## Later runtime and workload continuation

The original performance sections below retain their historical five-device stress population and results. [ADR 0015](../../adr/0015-bounded-api-runtime-and-storage-locks.md) and the [runtime investigation](throughput-fixes.md) add reproduced executor, query, storage-budget and ACK contention fixes. A revised notification publisher batches only coarse hints, reuses its owned Redis loop and preserves whole-batch retry. Both backend settings now pass 132 tests; earlier browser checks retain their exact pre-notification source scope.

The [workload plan](workload-plan.md) corrects the ordinary population to 100 people, two trusted identities each and 120 initially online devices, with independent asynchronous recipients. It separates a 20/s burst from steady endurance and distinguishes socket count from cryptographic fan-out. Local mixed and five-file burst cases pass; initial handoff, group stress and 82-minute endurance failures are retained. Inspect the [revised case outcomes](../../evidence/metadata-realistic-workload-2026-11-02/README.md) for completion and qualification scope. These observations do not qualify reference-production, physical devices or domestic networking.

Continuation of the [original hardening report](report.md), baseline `0240706` (PR #18), with previously merged hardening at `71b2ba0`. New work is on `codex/metadata-privacy-completion`. **Production remains BLOCKED; `CRYPTO_READY=False`.** No production/staging data, deployment, backup, or key custody was changed. Local evidence is not independent certification or Iranian field qualification.

## 1. Executive summary

The continuation remediates three reproduced authorization races and an additional unnecessary retained identity association. New enrollment challenges replace the exposed global session number with a nonce-scoped HMAC inside the unchanged strict wire grammar. A revoked device can no longer use a stale authenticated request to ACK; a logged-out session cannot claim view-once media; membership grants now serialize with the target account's revocation/recovery. Protected HTTP mutations have a current-session/account transaction fence, deterministic cross-account/conversation lock order, and rollback on handled API errors. Expired unfinished enrollments lose their account/key/label/challenge association, retaining only a replay-exclusion UUID. Authentication, membership, roster and public-target queries now omit unnecessary account profile/password/enrollment columns outside their purpose.

The original timestamp/receipt/KeyPackage/API/SQL/Redis/padding hardening remains implemented. No social-graph anonymity, anonymous credential protocol, server-label encryption, or network anonymity is claimed. Advanced routing remains an isolated architecture specification rather than unreviewed production crypto.

## 2. Original metadata exposure

The baseline stored redundant session/ACK/chunk timestamps, unused receipts, expired package ownership and claim relationships, exact API acceptance time and longer stale Redis associations. Original hardening removed or bounded those surfaces. Current complete inventory: **191 current fields plus eight retired fields** across application/framework/automatic models. All fields include purpose, classification, relationships, access, exposure, retention and reconstruction limitations in [inventory.csv](inventory.csv); the checker reports schema drift without reading records.

This continuation found expired pending Devices retained account/name/key/identity/challenge/time data indefinitely. It also found stale request authority could mutate delivery/consumption ledgers after revocation, and an Add could create a membership across the target's uncommitted revocation. These were correctness/privacy boundary failures, not a break of MLS or Ed25519.

## 3. Architecture changes

[ADR 0014](../../adr/0014-request-authority-and-enrollment-retention.md) defines account fences, linearization points, target-account controls, ordered conversation locking, transactional error responses and enrollment replay exclusion. Public login/recovery protocols keep their existing proof checks and account locks. Reads refresh authority before their handler; they do not recall already-authorized data in flight. WebSocket validation remains unchanged.

Central routing, signed public rosters, stable approved-device credentials and account-based quotas remain essential to the selected asynchronous design. [ADR 0013](../../adr/0013-metadata-privacy.md), the [A1–A8 model](threat-model.md), [flows](flows.md) and [routing specification](routing-research.md) distinguish DB-only, live-server and network adversaries. Deterministic aliases do not hide those joins. A server-held encryption key is not A4 protection.

## 4. Source changes

- `core/authorization.py`, `core/views.py`: current session/account/device refresh; sorted actor/target account fences; sorted affected conversations before rekey; bounded pre-lock body; transactional rollback for every handled rejection; recovery rejects previously used enrollment IDs.
- `core/models.py`, `core/retention.py`, migration `0015_pending_enrollment_privacy.py`: ID-only replay markers, partial pending expiry index, bounded account/device-locked cleanup, PROTECT reference preservation and aggregate counts. No records are deleted by schema migration alone. Reverse DDL refuses before discarding markers.
- Migration `0016_session_challenge_context.py` widens the one-use nonce column for explicit internal versioning. New nonces select scoped-HMAC proofs; only preserved pre-upgrade raw nonces select legacy verification. No caller can request an old ordinal response or use the compatibility branch to guess it. Old browsers retain their strict validator; API contracts and client identity/vault formats stay compatible.
- Backend regression files cover controlled real PostgreSQL races, real signed recovery, actual native MLS Add/signature/wire/KeyPackage boundaries and error rollback. The existing concurrent password test now synchronizes before account locking rather than deadlocking its own test barrier.
- `packages/crypto-core/examples/protocol_client.rs` and isolated load/TLS/media scripts provide real protocol clients, encrypted fsynced checkpoints, authentic HTTP/WSS, matching XChaCha20-Poly1305 media, WAL/I/O counters and TLS record byte measurements. Private keys/provider states/cookies/fixture logs stay owner-only in `.local`; no server receives private MLS provider state. `prepare.sh` and `test-local.sh` build the locked helper before native-backed API regressions.
- Existing browser retention regression now additionally rewinds only its synthetic conversation head in PostgreSQL and checks rejection with unchanged memory/durable checkpoints and no ACK, then restores the test head. This is not a global coordinated-rollback proof.

No application dependency, client/vault storage version, message contract shape, MLS primitive or production gate changed in this continuation. The earlier generated contracts/WASM remain applicable.

## 5. Privacy improvements

The actual dump/restore drill now seeds an expired pending enrollment as well as trusted devices, signed structures, old unacknowledged ciphertext, active/offline cursors, sessions, media consumption and budgets. Pending enrollment account links go **1→0**, with **one ID-only replay marker**. Selected invariant hashes match before schema migration, after migration and after cleanup. The prior three activity columns disappear and expired package owner/claim links reduce 2→1 while live claims remain. All three synthetic membership edges remain reconstructable; this is not a privacy score or erasure claim.

A fresh DB-only copy cannot recover a deleted pending enrollment's key/label/account from its UUID marker alone. Earlier dumps, WAL/pages, external UUID knowledge or a live server can still correlate it. Trusted/historical Devices remain necessary for signatures, pinning and replay exclusion. Unexpected references preserve the pending record instead of deleting ledgers.

## 6. Security tests

Authoritative commands, failed reproductions and reruns are indexed in [the continuation evidence](../../evidence/metadata-completion-2026-11-02/README.md). Original evidence remains available separately. The suite uses real PostgreSQL/Redis and native/WASM cryptography where those properties are under test; pre-approved-session/opaque-ciphertext fixtures are explicitly scoped. No failed reproduction, interrupted load run, ignored test or unsupported browser is relabeled as a security pass.

Covered additions: both mutation/logout orders; stale read/current-role denial; cross-admin and shared-group concurrent revocations; real Add versus uncommitted target revocation; handled validation/PG/Redis/unexpected rollback; bounded body before account locking; expired enrollment replay, protected references and concurrent approval; actual signed recovery rejecting old ID then accepting a fresh identity; malformed/wrong-signature/wrong-group/hash substitution/foreign-member attempts and exact accepted retry; actual expired KeyPackage reupload/reclaim rejection.

The final backend run passes 111 tests; Rust has five passing library tests and the exact upstream vectors have 205 passing with three ignored/91 filtered. The final TypeScript/build and measured results are recorded in the evidence index. Chromium passes 39 tests with two optional skips; the initial final-source Firefox suite passes 34 with six skips and one offline-probe timeout. That test assumed a 20-second wait despite a possible in-flight response restarting the 30-second auth interval; its bound now covers the actual interval plus polling. Focused Firefox/Chromium reruns pass, followed by a complete Firefox rerun: **35 passed, six skips**. The earlier failure remains indexed. No cryptographic/authentication assertion or production behavior was relaxed. Self-review and automated tests do not constitute an independent third-party cryptographic audit.

## 7. Compatibility and migration

Follow [the updated upgrade/recovery runbook](upgrade.md). Fence API/worker/standby writers, preserve separately protected encrypted backups, migrate using the migration role, and start matching API and workers together. Do not mix an old API that lacks tombstone guards with a cleanup worker that creates them. Migration 0015 adds an index/table only; cleanup is bounded and separately observable. Migration 0016 widens and explicitly versions session nonce storage, preserving existing raw challenges and strict browser signing checks. Neither migration deletes message, key or session records. Existing expired enrollments receive their prior error and require an explicit fresh device; no browser vault or identity is automatically reset.

Retain approved/revoked/historical identities and all required message/consumption/replay ledgers. Do not reverse 0015/0016, discard replay markers, use `--fake`, restore an old DB and resume traffic, or delete old backups automatically. A reviewed restore must reconcile accepted messages, device/session revocation, consumption and client checkpoints. Logical deletion does not erase WAL, replicas, old pages, SSD remnants or provider snapshots.

## 8. Performance and reliability

The isolated load workload provisions 100 synthetic accounts, five real native MLS identities/sessions each, 50 ten-device groups and 500 authenticated TLS WebSockets. It retains actual source/connection/rate/storage limits, uses per-account loopback source addresses, real outer signatures/public verification, recipient signature/order/MLS/roster checks and encrypted fsynced native checkpoints before ACK. Five concurrent encrypted 1 MiB files roundtrip through actual attachment endpoints. It measures WAL LSN/statistics, PostgreSQL I/O timings/counters, container block I/O, API/worker CPU, API peak RSS and TLS records including HTTP/WSS headers/payloads. Baseline and current APIs use the same current native client; padding's separate native baseline comparison remains in the original evidence.

The first 20 message/s validation run built backlog and lost WebSockets; it was interrupted and is **not a capacity pass**. Bounded subsequent stress trials stop offering new work at ten seconds of schedule lag or a socket failure and drain all already-generated messages. Missing a target stays a failed capacity target. No limits are relaxed and no generated message is silently discarded to improve throughput.

The final two-hour 1 message/s run completed 7,200 sends, 64,800 durable recipient copies, 50 real MLS updates, 500 authenticated sockets and zero socket errors; five encrypted files and encrypted checkpoint restoration passed. An earlier strict run stopped after six code-1011 socket closures at 671 seconds, with all 670 generated messages/6,030 copies durable; it remains a failed soak. The completed run permitted reconnection but needed none. This qualifies only the measured lower-rate native workload. The final matched 120-message trials complete with zero socket errors on both APIs: API CPU 87.90→103.54 seconds, scheduled-send p95 458.51→220.55 ms and all-nine-durable-ACK p95 2,686.44→1,717.15 ms. This small shared-host pair has mixed resource/latency outcomes and establishes no causal speedup or budget. The paired workload and full stress/endurance outputs, actual achieved rates and limits are in [performance.md](performance.md) and the evidence index. These are co-located synthetic host observations, not physical-browser battery, thermals, mobile storage, domestic carrier, SLA or reference-production capacity qualification. The native fixture key is held outside PostgreSQL in a protected test file; this is not evidence about production browser/passphrase key custody. Native checkpoint restoration is checked separately from browser vault regressions.

## 9. Residual threats

A1 still sees approved identities/account names, password hashes, signed social-graph/history, sequence/epoch, ciphertext sizes, quotas and required ledgers. A2 may recover erased fields and reopen old credentials/consumption if an unsafe restore is used. A3/A4 can observe live authenticated routing; A4 can serve malicious browser code. A5/A6/A7 see service connection/timing/volume and may correlate or disrupt traffic. A8 can capture participant plaintext and metadata. Body/padding/TTL minimization and transaction fences do not change those boundaries.

A browser with a newer retained authenticated checkpoint can reject an older server head; restoring all copies of state together still needs an independent durable anchor or a reviewed reset/recovery ceremony. Restoring an old OpenMLS provider can resurrect ratchets; tests characterize this limitation, rather than claim the library prevents complete state rollback. View-once cannot prevent capture by a participating device.

## 10. Release readiness

Safe implemented changes are reviewable and have local regression/migration evidence. Production remains **BLOCKED**. A missed local load target is an engineering limitation, not an external certification pass. Physical Safari/Android, low-end phone/battery/thermal qualification, real Iranian/domestic-only infrastructure, public TLS/provider/standby/fencing/RPO/RTO, independent cryptographic/integration review and complete hostile-resource/censored-fork qualification remain separate gates. No production gate, deploy, merge or backup deletion is authorized by local passes.

## 11. Deferred research and exact blockers

Unlinkable routing requires independently reviewed issuance/revocation/quota/order/ACK/recovery/migration semantics and audited constructions before replacing current authorization. Current signed proof JSON and device credentials duplicate graph associations; deleting join columns or adding bearer mailboxes cannot establish unlinkability. PIR/mix/anonymous credential options remain specifications, with no mandatory foreign relay or service added.

Account-label AEAD could narrow A1 graph labeling; it is not implemented. The needed safe deliverable is a separately reviewed normalized lookup/uniqueness, field/row/version binding, key IDs, overlapping rotation, missing-key failure, role/authentication compatibility, backup custody and restore migration. It would not hide graph edges or A4 plaintext. This remains explicit design work rather than a falsely completed privacy feature.

Independent review needs a genuinely separate reviewer; physical/domestic qualification needs devices and separately operated infrastructure. Global rollback/fork/anonymity claims need stronger protocol/trust assumptions and independent analysis. These cannot be manufactured by expanding a local test count.

## 12. Verification checklist

[requirements.csv](requirements.csv) maps each original directive phase/deliverable to scope, evidence and PASS/PARTIAL/BLOCKED/NOT IMPLEMENTED status. Inventory/flows/threat model, implemented minimization, transaction/replay boundaries, migrations, tests, before/after evidence, performance limitations, runbooks, bilingual notice and release gating are individually inspectable. The review branch has separate descriptive source and evidence commits, with a refreshed source manifest and evidence digests. Production qualification is not inferred from completion of the source-hardening work.

The final [realistic results](workload-results.md) include a passing natural combined 20/s burst and a complete 7,200-second 2/s soak: 14,400 applications, 60,414 durable recipient copies, 108 MLS updates and 200 restored native checkpoints. Failed stress, latency and availability attempts remain indexed. These are local native cases, with reference-production and external release gates unqualified.
