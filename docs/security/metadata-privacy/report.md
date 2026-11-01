# HAVEN metadata privacy engineering report

Date: 2026-11-02. Baseline: `0240706` (merged PR #18). Branch: `codex/metadata-privacy-hardening`. **Production release status: BLOCKED.** Local hardening is implemented; the original external assurance/field gates and the unmeasured performance dimensions below remain open. No merge, deployment, production schema change or deletion of existing backups was performed.

## 1. Executive summary

Implemented concrete metadata minimization across persisted schema, application responses, SQL processing, transient Redis routing and MLS message framing. The server no longer needs to store three redundant activity-time columns or an unused per-message receipt table; expired KeyPackages lose owner/claim relationships; API recipients no longer receive exact server acceptance time; notification routing does not fetch message content/proof columns; stale account-channel associations expire after two minutes; new MLS messages use authenticated 256-byte padding. A shared-lock recheck fixes abandoned-upload cleanup racing completion. Failure telemetry is aggregate and replaces stale cached success.

This is meaningful reduction of specific stored/processed information, **not elimination of HAVEN's social graph**. Opaque mailbox, blind credential, PIR and anonymity transports are isolated research specifications. No custom crypto primitive, mandatory relay, new identity provider or foreign runtime dependency is introduced. Existing approved-device, MLS, signed history, anti-replay, transactional quotas, atomic encrypted vault/outbox and durable ACK boundaries remain.

## 2. Original metadata exposure

Baseline already included TLS/E2EE/local worker key custody, privacy defaults, signed/order/epoch/device verification, segmented atomic browser persistence, source-isolated login, scoped short-lived HMAC rate labels, generic sync hints, strict log/ingress policies and ACK-safe retirement. Those protections are not claimed as newly implemented.

A current DB dump could join account→device→membership→conversation→sender and reconstruct the same edges from signed genesis/header/transition JSON. Device credentials contain stable account/device identifiers. Cursors, KeyPackage claims, media/view ledgers, outbox and account-keyed resource accounting supply independent associations. Baseline retained exact ACK/chunk/session-save times, an unused receipt schema, expired package owner links and API acceptance times. Channels-redis group links defaulted to a day after a crashed connection. Message length was close to plaintext length plus framing. See [198 field classifications](inventory.csv), [complete flows](flows.md) and [before/after comparison](leakage.md).

## 3. Architecture changes

Central authenticated routing is retained because authorization, ordering, asynchronous membership, device revocation, ACK eligibility, recovery and accounting depend on it. Removing stable IDs from one table while signed proof JSON still contains them would not hide relationships. A server-held encryption key would not protect A4. ADR 0013 compares five candidate families across all requested security/privacy/operation dimensions and specifies why advanced redesign is not deployed.

OpenMLS applies its native authenticated content padding. New group create/join configs use 256-byte blocks. On first new encryption, the adapter upgrades only its known exact legacy default configuration, with unknown legacy configs that need a padding change failing closed instead of resetting secret retention or ratchets; already padded configs are preserved. Already queued ciphertext/signatures are unchanged; valid unpadded legacy messages remain accepted. No browser schema migration or protocol-semantic change is needed. Ciphertext length remains coarse and correlated, especially across TLS traffic and unpadded attachments.

Expiry cleanup retains permanent replay digests while removing no-longer-needed device/claim links. A partial expiry/ID index excludes fully scrubbed tombstones from cleanup indexing. Redis groups expire in 120 seconds and valid frames renew or repair membership; revoked sessions cannot renew. Redis errors close the socket for reconnect while authenticated HTTP remains authoritative.

## 4. Source changes

| Files | Change and reason |
|---|---|
| `apps/api/core/models.py`, migrations `0013_metadata_minimization.py`, `0014_keypackage_privacy_index.py` | Remove unused metadata; permit expired package disassociation; index remaining expiry work. 0013 deliberately refuses reversal |
| `core/retention.py` | Bounded owner/claim/payload scrub including legacy blank payloads; retain deletion predicates; take/recheck shared attachment lock before cascade deletion |
| `core/views.py`, `apps/web/src/lib/api.ts`, `scripts/generate-contracts.py`, generated OpenAPI/TypeScript | Remove acceptance timestamp serialization, project message reads, keep monotonic ACK seq without time writes; generated field was optional and client unused |
| `core/management/commands/publish_outbox.py`, `maintain_privacy.py` | Read necessary routing fields; replace cached success on failure without sensitive diagnostics |
| `haven/settings.py`, `core/consumers.py` | Bound Redis group association TTL and renew only after session validation; fail safely to reconnect/HTTP |
| `packages/crypto-core/src/lib.rs`, `examples/metadata_benchmark.rs`, rebuilt public WASM/offline manifests | Native bounded padding and legacy config handling; native roundtrip/replay/tamper/epoch/max-size tests and repeatable benchmark |
| `core/tests/test_metadata_privacy.py`, `test_websocket.py`, `test_privacy.py`; migration fixture and prior migration tests | Actual PG schema/API/SQL/concurrency and Redis TTL/revocation tests; preserve old migration assertions using fresh forward-only test databases |
| `apps/web/tests/metadata-privacy.spec.ts`, `crypto.spec.ts`, shared Firefox fixtures and four existing browser test imports | Real padded WASM reload/rekey; use private trust profile consistently; genuine fake-device capture instead of unsupported Firefox permission; no certificate-validation bypass |
| `apps/web/src/app/ui.tsx` | Real Firefox regression exposed recorder MIME reset on stop; retain actual blob MIME/extension so an encrypted voice note stays playable, with no server plaintext metadata |
| `scripts/check-metadata-inventory.py`, `test-metadata-migration.py` | Detect field inventory drift; actual isolated synthetic dump/restore, selected-state comparison, reverse refusal and retry evidence |
| Dedicated privacy docs, ADR, top-level status/changelog/report and runbooks | Field/flow inventory, A1–A8 model, research alternatives, bilingual disclosure, migration/recovery and measured limits |

No application dependency or browser vault/identity format changed. No real environment was upgraded. Reviewed source manifest is refreshed for the resulting files.

## 5. Privacy improvements

Synthetic DB experiment: three activity columns→zero; receipt table present→absent; expired+live package owner links 2→1 and claimant links 2→1; live package retained. All three membership edges remain reconstructable. A selected-field state hash is identical across restored baseline, migration and cleanup, including old pending ciphertext with offline recipients, signed structures, session binding, consumed/unopened media, cursors, outbox and budget state. This is consistency evidence, not a cryptographic proof.

Actual response/SQL assertions demonstrate no acceptance-time serialization/select and no content/proof/sender material fetched for outbox routing. Real Redis demonstrates TTL, missing-key renewal and no renewal after revocation. The fixed native workload's 1/16/64/128-byte samples collapse from four wire lengths to 320 bytes, while larger buckets remain distinguishable. No universal traffic-analysis resistance is asserted.

## 6. Security tests

The [evidence index](../../evidence/metadata-privacy-2026-11-01/README.md) records commands and authoritative outputs. Backend baseline 78 passed; final PostgreSQL/Redis suite 84 passed. Native Rust five library tests pass, including generated Unicode/replay/public-frame properties and new legacy-padding/tamper/max-size/rekey behavior. Exact upstream OpenMLS vectors: 205 passed, three ignored, 91 filtered. TypeScript, Ruff/format, migration drift, production web/WASM build, installer tests, real Nginx and Linux WebKit smoke pass. Full Chromium passes 38 with two optional skips; full Firefox passes 34 with six unsupported/optional skips. A final focused Chromium crypto rerun passes all three tests after correcting URL-safe tamper encoding. The separate trusted-hostname/virtual-PRF test passes.

Initial full backend run: 80 passed, two failed because old tests reversed across deliberately irreversible 0013. Corrected the test isolation to use fresh real PostgreSQL databases; did not weaken the reversal gate or assertions. Later 83 and final 84 pass as tests were added. Initial Firefox full run: 26 passed, six failed, eight skipped; failures included untrusted default profiles and unsupported microphone permission, rather than a TLS bypass. Shared fixtures were corrected. An additional Firefox UI timeout exposed an unattended persistent-storage prompt; test profiles use Firefox’s own test preferences to answer that prompt, and the final rerun is recorded in the evidence index; failed logs are retained. A Chromium rerun also exposed a pre-existing probabilistic tamper test: replacing the first Base64 character with A sometimes made no change. It now flips an actual ciphertext byte and preserves URL-safe Base64 encoding and the rejection assertion; this was a test bug, not an observed AEAD acceptance of altered bytes. Offline-shell harness initially used the wrong path/interpreter and then wrong working directory; the correct existing Node harness passes. Formatting the newly generated 0014 migration preceded the successful full rerun. The extended Firefox voice flow then exposed a real compatibility issue: MediaRecorder.mimeType resets at stop while Blob.type remains audio/ogg. The client now derives the MIME and file extension from the actual recorded blobs; full playback is rerun. No failed run is reclassified as a pass.

The synthetic migration drill uses actual pg_dump/pg_restore, then forward migrations/cleanup and an intentionally refused reverse. It never points at the running deployment; only its randomized test DBs are dropped. Existing 0007→latest consumption/TTL migration drill also passes. Full browser tests separately cover real cryptography, encrypted persistence, idempotent retry, media, concurrent membership, process kill, Redis outage, TLS/fencing and view-once behavior. Self-review/automated tests are not third-party cryptographic review.

## 7. Compatibility

Use [the coordinated upgrade/runbook](upgrade.md). Stop old API/outbox/privacy workers and fence writers before migration. Existing sessions, active claims, approved devices, epochs, signed history, pending outboxes, media leases/consumption and quotas are preserved. No vault clear, identity rotation or ratchet rewind is authorized. Known old configs upgrade inside the returned speculative state; already queued sends retain exact bytes. Unknown legacy configs needing a padding change fail closed and require investigation; already padded configs retain their other settings.

0013 cannot honestly reconstruct removed data by reverse DDL; it intentionally refuses reversal. 0014 is a schema-only partial index. Failure before transaction commit rolls back DDL; forward correction is preferred after commit. Restoring older state requires reconciliation of delivery/replay/revocation/consumption ledgers and must not reopen viewed media or discard accepted messages. Backups/WAL/provider copies are not physically erased by row/column deletion.

## 8. Performance

[Native paired comparison](performance.md) provides nine sizes, 40 roundtrips/size, three alternating baseline/current runs, per-operation median/p95 and process CPU/peak RSS/elapsed time on the same host. New content padding is bounded to 0–255 bytes; wire vector framing can add bytes. No extra browser cover loop/poll is introduced. Notification projection avoids unnecessary content reads; ACK no longer writes time. The partial package index prevents scrubbed tombstones accumulating in the cleanup index. One local Redis group renewal is added per validated incoming frame (existing admission ≤60/minute/socket).

**Performance qualification is partial.** A separate real browser workload against isolated baseline/current APIs now measures 30 send/receive/draft samples, ten idle syncs/reconnects, API CPU/peak RSS, per-database counters and API body bytes. Both use the same current client, so native and API comparisons isolate different components. Download bodies fall 3960 bytes with the same 370 requests in this small workload. Saturated/backlog throughput, physical DB/WAL write amplification, whole-session TLS/header bandwidth, physical-phone battery/thermals and production load/soak remain unqualified. Shared-host sample percentiles are not SLA or causal speedup evidence. No invented speedup, p95 guarantee or emergency-connectivity capacity claim follows.

## 9. Residual threats

A1 still sees account/password hashes, public device credentials, full signed social graph, message order/epoch, sizes and necessary live metadata; password guessing remains possible. A2 may recover deleted links/times/content from old backups/WAL/pages and replay stale consumption/auth state if an unsafe restore is performed. A3/A4 see authenticated live routing and can instrument it; A4 can supply hostile browser code to users who load/unlock. At-rest server encryption cannot fix that boundary. A5 hosting sees connection/ingress state; A6/A7 observe service use, timing and volumes and can correlate or disrupt traffic. A8 participating/compromised clients can capture plaintext and group metadata. See [the capability matrix](threat-model.md).

No complete anonymity, unlinkable session/routing, nationwide-surveillance defeat, physical erasure, global rollback protection, full malicious-server fork proof or view-once capture prevention is claimed. Optional activity still discloses live conversation hints if enabled. Signed pagination tokens are authenticated, not encrypted. Existing signed history and account-charged budgets retain fundamental associations.

## 10. Release readiness

The bounded implemented hardening has reviewable source, migration/recovery procedures and local evidence. It does not satisfy the entire production/field definition of done: external independent crypto/integration review, physical Safari/Android, real public/domestic carrier/TLS/provider/failover qualification, complete adversarial matrices and performance/soak remain open. `CRYPTO_READY=False` is unchanged; `release-gate.py` exits one as expected. Test-only loopback settings are not deployment authorization. No merge/deployment is requested or performed.

## 11. Deferred research

[The routing specification](routing-research.md) defines scoped possession credentials, authenticated encrypted roster/order proofs, device revocation fencing, replay/epoch/nonce scope, atomic ACK/checkpoints, quota reservation/spend/refund, discovery/recovery, migration and downgrade obligations. It is explicitly not a completed protocol or deployed prototype. Blind issuance, PIR and independent mix transport require audited constructions, independent analysis and measured reliability/bandwidth/battery costs. No unproven bearer mailbox replaces existing controls. A separately reviewed account-label AEAD/login-index/key-rotation migration could reduce A1 graph labeling; it is not implemented and would not hide the graph or A4 plaintext. ADR 0013 records its narrower benefit and key-custody/migration obligations.

## 12. Final verification checklist

| Requirement | Status | Evidence / limitation |
|---|---|---|
| Source-backed persisted field coverage | PASS | 190 current + eight retired fields, 30 application/framework/automatic models, drift checker |
| End-to-end metadata lifecycle and existing protections | PASS (source review scope) | Flows, duplication/graph analysis; host/provider custom telemetry not audited |
| A1–A8 assumptions/disclosures/residuals | PASS analytical model | No network anonymity or independent proof inferred |
| Safe high-priority implemented minimization | PASS local scope | Schema/SQL/API/package/Redis/padding evidence; graph replacement deferred |
| Necessary metadata justified / custody model explicit | PASS design documentation | Current routing/identity/history remains visible and cannot be removed by aliases |
| Safe forward migration, dump restore, retry and reverse refusal | PASS synthetic local scope | Actual PG drill, preserved selected-state hash, no production upgrade |
| Unacknowledged ciphertext, signatures, quotas, consumption state | PASS tested cases | Dump consistency + existing actual browser/PG regressions; not exhaustive proof |
| New features regression coverage | PASS implemented paths | Native/WASM/PG/API/Redis/concurrency/query tests |
| Full backend/native/upstream tests | PASS with ignored cases disclosed | 84 backend, five native, 205 upstream; three upstream ignored |
| Full Chromium/Firefox final runs | PASS with disclosed skips | 38 Chromium / 34 Firefox; two/six optional or unsupported skips; hostname PRF one pass separately; final Chromium crypto three pass |
| Build/contracts/format/provider/ingress/offline checks | PASS recorded scope | Production build is not production release |
| Privacy before/after measurement | PASS bounded experiment | Counts/SQL/API/TTL/wire sizes; graph unchanged, not a privacy score |
| Performance comparison | PARTIAL | Native plus isolated browser/API latency, CPU/RSS, vault/idle/reconnect and body counters measured; physical IO/mobile/soak dimensions NOT TESTED |
| Independent second review | BLOCKED externally | Separate second-pass self-review performed; third-party assurance not available |
| Physical browsers/domestic network/provider qualification | BLOCKED externally | Requires devices, infrastructure and field evidence |
| Physical erasure / anonymity / unlinkable routing | NOT IMPLEMENTED / not claimed | Logical deletion limits and separate research specification |
| Domestic-only runtime compatibility | PASS source/configuration scope | No dependency or runtime service added; no Iranian field test |
| Release gate and no unauthorized deployment | PASS | Source gate unchanged; release command deliberately BLOCKED |

Second-pass self-review traced null package tombstones through reupload/claim/Add guards; inspected active claims and epoch checks; verified all removed fields had no runtime readers after edits; compared signed/cursor/session/view/quota bytes in the restore drill; inspected lock order, the cleanup predicate and partial index; verified native config migration does not change secret-retention defaults; checked expired/forged/cross-account/revoked scope through existing regressions; and checked generated contracts/artifacts and normal source gate. This is not an independent human cryptographic audit. No known critical delivery or cryptographic regression is accepted as a completed feature.
