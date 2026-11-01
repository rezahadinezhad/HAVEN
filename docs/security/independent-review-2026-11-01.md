# HAVEN independent security and performance review

Date: 2026-11-01. Reviewed revision: `61d77683d140daf26e087bd4c2f1971b7a2a97c1`.
The reviewed local revision has the same source tree as published GitHub `main` at `f539f47`; use that public commit to inspect the baseline.

This is a fresh source-based review with targeted reproductions, independent of the repository's prior security conclusions. It is an AI-assisted engineering review, not an external organizational audit or cryptographic certification. Application code was not changed. Evidence and reproducible probes are in [the evidence directory](../evidence/independent-review-2026-11-01/README.md).

**Assessment: keep the production release gate closed.** Seven actionable findings remain, chiefly involving availability, resource accounting, and growth behavior. I did not establish a plaintext disclosure, authentication bypass, or cryptographic primitive break in the inspected paths. That statement is limited to this review's scope and testing.

## Remediation status

Implementation fixes and regression coverage for all seven findings are recorded in [the follow-up remediation report](review-remediation-2026-11-01.md). The findings and evidence below describe the original reviewed revision and remain unchanged as a historical baseline.

## Findings, ordered by remediation priority

Severity reflects application impact and prerequisites, not a calculated CVSS score. “Reproduced” means the isolated experiment described below, not an attack against a live deployment.

| ID | Severity | Finding | Evidence |
| --- | --- | --- | --- |
| S1 | High | Authenticated malformed plaintext blocks subsequent conversation synchronization | Real MLS/signatures; production client with mocked I/O |
| P1 | High | Whole-vault size limit stops messaging well before the advertised event-count guard | Production worker size failure reproduced |
| S2 | High | Message ciphertext has no aggregate storage budget; a member can retain unbounded data | Source-confirmed; no disk-exhaustion test |
| S3 | Medium | Anonymous requests can consume a shared login budget and deny unrelated users | Actual rate helper plus HTTP test client |
| P2 | Medium | Idle polling performs three requests and an ACK write per conversation | Production client request trace |
| P3 | Medium | Proof-only queries fetch all ciphertext unnecessarily | Django SQL capture with synthetic rows |
| F1 | Medium | Conversation listings silently truncate at 100 without pagination | Actual API test-client responses |

### S1 — One malformed authenticated application message stalls the conversation

**Locations:** `apps/web/src/lib/messenger.ts:1274–1311`; server acceptance in `apps/api/core/views.py:858–941`.

A malicious approved participant can encrypt application plaintext such as `{`, wrap it in a correctly signed ordered envelope, and submit it through the normal message protocol. The server checks signature, public wire group/epoch, and ordering; it cannot inspect the encrypted application JSON. On the recipient, MLS processing succeeds, but `JSON.parse` or application-event validation throws before the updated ratchet, cursor, and head are persisted. Every retry loads the same durable state and encounters the same message. Later valid messages and membership changes in that conversation remain blocked. A modified peer client is required; no owner/moderator role is required to send application messages.

**Reproduction:** the client probe uses two real OpenMLS identities in one group, a retained checkpoint at sequence 1, malformed plaintext at sequence 2 and valid plaintext at sequence 3. Real delivery signatures and chain hashes pass. The native public verifier accepts the malformed message's MLS wire structure. Two calls to production `Messenger.sync()` throw the same JSON error; cursor stays at 1, no persistence occurs, and the later message is not received. HTTP/persistence adapters are mocked; live API acceptance was not tested end to end.

**Fix:** after successful cryptographic authentication, distinguish invalid application content from invalid transport, signature, membership, or MLS state. Durably record a bounded rejected-event marker and advance the authenticated ratchet/cursor atomically for invalid application content, without displaying it. Continue to reject unverifiable envelopes and unauthorized transitions. Test malformed JSON, schema errors, application identity mismatches, restart, and later valid traffic. Do not implement a generic “skip any failing ciphertext” fallback.

### P1 — A legal history can exceed the vault byte limit and stop persistence

**Locations:** `apps/web/src/lib/vault-worker.ts:49–50`; `apps/web/src/lib/messenger.ts:324–341, 451–455, 682–685, 1293–1311`; `apps/web/src/lib/events.ts`.

Every mutation clones the complete vault, posts it to a worker, serializes it, seals the complete snapshot, and replaces its IndexedDB record. The worker rejects plaintext above **16,000,000 bytes**, while the sender checks only **20,000 events**. Text events can contain 20,000 characters; incoming events have no equivalent total-history guard. Once a new event pushes the snapshot over the byte ceiling, receive persistence fails and the cursor cannot advance. Sending and saving drafts also fail when their snapshots exceed the same ceiling. A peer can accelerate this through otherwise valid large messages. Effects extend across conversations sharing the vault. Clearing sufficient delivered history can restore capacity; this is not established permanent key loss.

**Reproduction:** the actual worker source, compiled for Node, sealed minimal snapshots of 100 events (2,023,809 bytes) and 500 events (10,118,209 bytes). At 800 events (16,189,009 bytes), it returned `VAULT_REJECTED`. All texts were ASCII within the permitted per-event limit. This minimal snapshot excludes real MLS state, outbox data and memberships; realistic limits can be lower. This is a capacity experiment, not an exact message-count promise.

**Performance implication:** each small draft or ratchet update rewrites O(total vault bytes). Receiving M messages with an accumulating history incurs quadratic aggregate history-copy/seal work, apart from cryptographic state costs. The worker moves encryption off the UI thread, but the main-thread `structuredClone` and worker message copies still scale with history. Single-sample worker durations are in the evidence; they are not browser benchmarks.

**Fix:** store encrypted history in bounded records/pages, separate from the small atomic ratchet/cursor/outbox checkpoint; preserve crash consistency across them. Add byte accounting, reserved checkpoint space, bounded incoming history, and an explicit safe archival/eviction flow. A temporary lower event count alone is insufficient for variable-size text, group state, and outbox growth.

### S2 — Message retention can grow without a storage quota

**Locations:** `apps/api/core/views.py:858–896, 933–941`; `apps/api/core/retention.py:13–64`; `apps/api/core/models.py:107–129`.

Attachment creation has a serialized per-account byte quota. Message creation has only a per-minute request limit and per-envelope size validation; it has no cumulative byte, pending-byte, or retained-envelope budget. Delivered ciphertext retirement depends on eligible device ACKs. An admitted member can create a conversation, submit valid ciphertext repeatedly through a modified client, and withhold its ACK. Such ciphertext never becomes eligible for the normal delivered-message retirement path. Even retired envelopes retain signed metadata indefinitely. No conversation deletion or aggregate message-storage reclamation mechanism was identified in the reviewed code.

**Impact:** persistent PostgreSQL, WAL, replication and backup growth can exhaust the shared service's storage. Rate limiting bounds growth speed, not total growth. As a scale illustration only, 120 messages/minute with 120 KiB payloads corresponds to about **19.8 GiB/day** before database overhead. This is arithmetic within the endpoint's request budget, not measured sustained throughput. Client epoch-renewal and history guards do not constrain a modified sender.

**Fix:** enforce transactional per-account pending and total storage budgets, including signed-record overhead and conversation counts, plus service-wide low-disk backpressure and operator visibility. Reject new writes clearly when limits are reached; do not silently delete unsynchronized ciphertext and break the stated delivery contract. Verify concurrent quota reservations and withheld-ACK scenarios.

### S3 — Shared login throttling permits inexpensive denial of sign-in

**Locations:** `apps/api/core/views.py:179–184`; `infrastructure/nginx/nginx.conf`.

`login.total` has the constant identity `service` and is incremented before serializer validation. Anonymous callers can consume all 300 attempts in a minute, after which unrelated users receive 429 before their credentials are checked. An attacker can obtain a CSRF token normally. Invalid JSON objects accepted by the JSON parser still consume the global counter without triggering password hashing. The standard ingress permits 10 requests/second per address, so it does not prevent one address from consuming the 300/minute service budget. Separate account counters also permit targeted short lockouts; this is secondary to the service-wide issue.

**Reproduction:** seed the real rate helper with 300 attempts, then make an unrelated login through the real Django middleware/test client: HTTP 429. The experiment verifies counter coupling, not external network throughput. The production gate does not block the login endpoint, so this finding also applies while messaging is gated.

**Fix:** retain an emergency service protection budget while allocating fair per-source and per-account budgets, with progressive delays and a protected route for legitimate sign-in. Source identity must originate at trusted ingress; do not accept arbitrary forwarded headers. Avoid counting malformed requests against a shared credential-verification budget. Retest distributed abuse and many legitimate users behind one NAT.

### P2 — Idle synchronization scales with every conversation

**Locations:** `apps/web/src/lib/connection.ts:29–36`; `apps/web/src/app/ui.tsx:491–508`; `apps/web/src/lib/messenger.ts:1065–1068, 1316–1319`; `apps/api/core/views.py:1112–1117`.

Every periodic cycle fetches the conversation list and serially synchronizes each entry, even if sequence/head values have not changed. Each idle conversation requires a detail GET, an unconditional ACK POST, and a receipt GET. The ACK obtains a conversation lock and saves the cursor even if the sequence is unchanged. WebSocket hints do not suppress the periodic full sweep; the next poll is scheduled 5–6 seconds after the previous sweep completes.

**Reproduction:** one idle call to production `Messenger.sync()` emits exactly those three requests. For 100 conversations, the implementation requires at least **302 requests per sweep**, including health/list requests, plus occasional session/current-detail requests. This is a request-count derivation, not a measured requests/second rate. With low latencies the client's demand exceeds ingress's 10 requests/second budget, causing self-throttling or long sweeps. More clients also multiply ACK writes, lock contention, connection establishment, and Redis telemetry work.

**Fix:** expose a compact paginated delta of changed conversations and receipt versions; skip unchanged heads; batch ACK advancement and avoid unchanged cursor writes. Coalesce hints and prioritize the selected conversation. Preserve serialized MLS mutations and durable-before-ACK ordering; unrestricted parallel processing of a shared vault would introduce state races. Keep a less frequent bounded fallback poll.

### P3 — Proof endpoints unnecessarily read ciphertext blobs

**Locations:** `apps/api/core/views.py:951–956`; `apps/api/core/views.py:812–835`.

`Proofs.get()` fetches complete `MessageEnvelope` model rows even though `envelope_json(..., proof=True)` excludes ciphertext. Its 100-row query therefore transfers and materializes up to roughly 15 MB of unused ciphertext per page under the serializer's encoded-size bound, before returning relatively small signed metadata. Proof history is read before the message history, so catch-up duplicates expensive blob reads. The indexed sequence filter does not eliminate the unused column transfer.

**Reproduction:** with 100 synthetic 150,000-byte blobs, SQL capture confirms the proof SELECT includes `ciphertext`, and the endpoint returns 100 proofs. The synthetic bytes establish ORM column selection; they are not claimed to be valid MLS messages or a measured PostgreSQL TOAST benchmark.

**Fix:** select only the proof fields, or explicitly defer ciphertext and other unused columns. Assert that serialization does not trigger deferred-column reads. Inspect PostgreSQL execution/transfer behavior and peak worker memory during concurrent catch-up after this repair.

### F1 — Conversation discovery has a hard, unpageable cutoff

**Locations:** `apps/api/core/views.py:761, 1128`.

The conversation-list endpoint returns the newest 100 conversations, while `/sync` returns the oldest 100. Neither offers a continuation cursor. There is no corresponding maximum number of conversations enforced at creation. The UI uses the first endpoint for discovery and polling, so older conversations silently disappear and no longer receive normal background synchronization once the account exceeds 100 conversations. Direct access by a retained ID remains possible; this is not server-side history deletion.

**Reproduction:** create 101 memberships for one device. Both endpoints return 100 entries; their ID sets overlap in only 99 entries. No response allows requesting the omitted page.

**Fix:** add deterministic cursor pagination to both discovery and delta sync, including a stable tie-breaker, and consume all pages in the client. Separately enforce documented resource limits. Verify 101+ conversations with messages arriving in the oldest entry.

## Dependency and verification results

- **npm, all dependencies:** one underlying moderate advisory, surfaced as three affected dependency entries: `minimatch` → `@redocly/openapi-core` → `openapi-typescript`. The lockfile contains development-only `minimatch 5.1.9`. The audit database flags versions below 11.0.1; the advisory's described triggering path uses `optimizationLevel >= 2`. Reachability of that path through HAVEN's actual generator was not established. Treat this as development-tooling triage, not an established remote messaging vulnerability. See the [upstream advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249). Do not blindly apply npm's suggested major downgrade.
- **npm, production only:** zero reported vulnerabilities.
- **Python:** full pinned graph including development tools audited; no known vulnerabilities reported.
- **Rust:** no known vulnerabilities reported; `proc-macro-error2 2.0.1` has the unmaintained warning `RUSTSEC-2026-0173`.
- **TypeScript:** typecheck passed.
- **Selected API tests:** 9 authentication/invitation tests passed; 4 concurrency/migration tests deliberately excluded because the isolated test environment used SQLite/local-memory cache.
- **Native Rust:** 4 library tests passed, with empty binary/doc-test suites.

Existing source controls worth preserving include exact Origin/CSRF checks, credential-bound revocable sessions, signed enrollment and history, transactional send ordering, encrypted chunk binding, and serialized attachment quota reservations. These checks narrow attack paths but do not resolve the availability findings above.

## Scope, limits, and next validation

Reviewed server settings, session/authentication and enrollment/recovery paths, message/control authorization and ordering, attachments/view-once access, retention, WebSocket handling, ingress/container configuration, browser crypto/vault/sync paths, and selected rendering/data-flow code. Prior repository reports were used for architectural context, not accepted as proof of current correctness.

No running Docker services were available during the review. The complete PostgreSQL/Redis/TLS stack, production images, upstream cryptographic vectors, complete browser suite, installer/backup recovery, and physical mobile behavior were not requalified. Race behavior under PostgreSQL locking, live ASGI saturation, actual browser frame rates, and p50/p95/p99 latency remain unmeasured. No valid capacity or Core Web Vitals score can be inferred from this work. Browser-origin code compromise, metadata visibility, and view-once capture limits remain architectural boundaries already disclosed by HAVEN.

After repairing the first three findings, validate on a disposable production-like stack: malformed authenticated events followed by valid traffic; byte-boundary persistence with crash/restart; concurrent storage reservations and withheld ACKs; unrelated legitimate login during adversarial requests; and 1/10/100/101+ conversation idle/catch-up scenarios. Measure PostgreSQL connections/WAL/storage, Redis latency, API latency/error rates, process memory, browser long tasks and bytes written to IndexedDB. Re-run the existing PostgreSQL concurrency and full browser suites before reconsidering release.

For ASGI performance work, retain the current `CONN_MAX_AGE=0` behavior and evaluate supported bounded pooling rather than simply enabling persistent connections; this follows [Django's ASGI guidance](https://docs.djangoproject.com/en/5.2/topics/async/). Resource budgets and graceful exhaustion handling also align with [OWASP's denial-of-service guidance](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html).
