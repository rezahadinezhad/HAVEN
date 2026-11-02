# Implementation status

## Follow-up dependency qualification — 2026-11-03

Follow-up runtime/dependency changes and old/new encrypted-vault regression coverage are implemented for review. The source gate remains closed. [Decisions and evidence](docs/security/dependency-followup-2026-11-03.md).

## Dependency qualification — 2026-11-02

Reviewed update graph, canonical-signature compatibility, sha2 fingerprint conversion, pinned Node 26 online/offline images and additional functional CI are implemented and pass local qualification. [Qualification and final disposition](docs/security/dependency-maintenance-2026-11-02.md).

## Runtime and realistic workload continuation — 2026-11-02

Bounded API execution/database reuse, fresh authority checks, shorter storage/ACK critical sections and batched notification delivery have implementation fixes and regression evidence. Both backend settings pass 132 tests. The realistic natural combined case passes local gates with 100 people, two trusted devices each, 120 initially online identities, 500 initial sockets, a 20-message/s burst, five encrypted files and 30% intermittent accounts. The completed two-hour 2/s soak passes all local gates: 14,400 messages, 60,414 durable recipient copies, 108 MLS updates, 200 restored checkpoints and zero socket errors/deadlocks. [Results and scope](docs/security/metadata-privacy/workload-results.md) retain failed stress/latency/availability attempts. These are shared-workstation native observations; reference-production, physical-device and external assurance gates remain unqualified. Production remains BLOCKED and `CRYPTO_READY=False`. No real deployment was performed.

## Metadata continuation — 2026-11-02

New enrollment proofs hide the global session ordinal using nonce-scoped HMAC context while preserving strict existing browser validation. Migration 0016 versions nonce storage and prevents legacy verification from becoming a guessing oracle; old in-flight proofs remain valid.

Implemented transactional authority refresh and sorted cross-account/conversation locks; rollback of handled API errors; SQL field minimization; replay-safe cleanup of expired unfinished enrollments and signed-recovery exclusion. Migrations 0015/0016 require matching API/workers and refuse unsafe reversal. New one-use scoped enrollment handles preserve strict client signing checks without exposing the global session ordinal. Added real PG/native/browser failure/race and isolated TLS/WAL/I/O load evidence. [Completion report and acceptance scope](docs/security/metadata-privacy/completion-report.md). No production deployment or release-gate change.

## Metadata privacy — 2026-11-02

Implemented migration 0013 metadata removal and expired-package disassociation; 0014 adds a partial expiry index excluding scrubbed tombstones. Added API/worker projections, bounded Redis group retention with authenticated renewal, native MLS padding with legacy-config handling, concurrency and actual dump/restore regression evidence. API contracts/WASM/offline assets are regenerated; browser storage and identity formats remain compatible. [Inventory, threat model, decisions, upgrade and report](docs/security/metadata-privacy/README.md) distinguish implemented hardening from research-only routing. The central social graph, online-service trust and external release blockers remain. No production/staging upgrade was performed for this initiative.

## Review remediation — 2026-11-01

Implemented the seven source-review fixes across API admission/accounting, encrypted browser persistence and background synchronization. Migrations 0011/0012 backfill budgets and index keyset discovery; browser storage v3 migrates legacy vaults atomically and preserves active ratchets. See [implementation decisions](docs/adr/0012-review-remediation-storage-and-sync.md), [upgrade steps](docs/security/review-remediation-2026-11-01.md) and [current evidence](docs/evidence/review-remediation-2026-11-01/README.md). This supersedes older monolithic-snapshot and idle-polling behavior below; the production/external qualification gate is unchanged.

Release label: **BLOCKED**. The working loopback integration is substantially beyond the initial scaffold, but the complete release-1 acceptance and external security gates have not passed. The production source gate remains closed.

Minimal-retention hardening is implemented: ACK-safe ciphertext retirement, short-lived auth/security/media metadata, view-once consumption minimization, separate cleanup worker, IP-header/log/spooling controls and explicit EN/FA policy. The current account/membership/signed proof graph remains server-visible. See ADR 0006, docs/security/server-data-retention.md and the latest test report. No independent assurance or anonymity claim is added.

Guided first-chat onboarding now supports ordinary members and administrators through browser setup/unlock, bounded private invitations/friend links, full-code comparison and actual direct messaging. Incoming chats guide verification; names and retry intents stay encrypted locally. Administrator invitation controls and source-level crypto/TLS gates remain intact. Migration 0009 deliberately enables bounded member issuance by default, as requested by the owner; administrators can opt out. See ADR 0007 and the updated onboarding guide.

New-browser setup now has optional local unlock-passphrase generation, explicit reveal/copy and saved confirmation, regeneration/manual-entry reset and clipboard-denial handling. Existing-vault unlock, messaging cryptography, server metadata and release gates remain unchanged. The generated passphrase is separate from account credentials and recovery-kit keys; see ADR 0008 for browser/clipboard limitations.

The media composer now provides category-specific native pickers, actual local photo/video/audio previews before upload, explicit unsupported/decoder failure states and preview resource cleanup. Chat tips no longer occupies the composer; guidance is under Connection & help.

View-once mode is now file-scoped: it appears only inside a selected photo/video’s confirmation box, defaults off on each new/replacement selection, and is explicitly passed to preparation; normal chat/documents/audio have no permanent viewing-mode control.

Conversation UX now includes a polished thread/composer, local previews/unread filtering, contextual message actions, readable reply/edit flows, explicit attachment confirmation, ordinary photo/video preview, recording cancellation, mobile chat focus and three-step browser approval guidance. Draft consumption is limited to sending its text; media and message actions retain unrelated writing. See docs/ui-ux/conversation-experience.md for the before/after review, engineering evidence and explicit feature/physical-device/large-history limits. This does not make the release independently qualified or establish full Telegram feature parity.

| Stage | Current engineering output | Exit state |
|---|---|---|
| 0 | Repository baseline commit; architecture, threat/risk records, pinned dependencies | Local work recorded |
| 1 | Actual Rust/WASM MLS on Chrome/Firefox/Linux WebKit; persistence, membership/replay/tamper tests; upstream KATs and native/WASM golden fixture | Physical Safari/Android and independent review blocked |
| 2 | PostgreSQL migrations, Redis coordination, sessions/roles/invitations, admin metadata, separate DB roles | Local checks pass; hardened public-host qualification blocked |
| 3 | Actual direct/group delivery, signed ordering, durable acceptance/outbox, HTTP sync/WS hints, offline queue | Local integration exercised; full fault/property matrix outstanding |
| 4 | Verified enrollment/multi-device, add/remove/leave, moderator/ownership controls, rekey, fresh-identity recovery | Local flows exercised; broader adversarial and field qualification outstanding |
| 5 | Encrypted chunked uploads/downloads, resumable ciphertext, quotas, voice capture/play | Desktop flows exercised; physical permissions/performance outstanding |
| 6 | Responsive EN/FA, all required screen areas, local search/edit/reply/delete/reactions, encrypted kit/history import, offline shell/settings | Desktop/mobile viewport evidence; full accessibility and physical-device acceptance outstanding |
| 7 | Compose, offline root/intermediate/IP leaf procedures, encrypted backup/restore, replication templates, fenced local promotion with prepared two-IP browser continuity and verified TLS bridge, signed offline runtime/source bundles | Local drills; real provider/network/fencing/air-gap gates blocked |
| 8 | Automated tests, production builds, application/OS scans and remediation, generated contracts, evidence and release documents | Ongoing acceptance gaps recorded in controls CSV; no full green release claim |
| 9 | Independent security review and physical/domestic qualification | BLOCKED: external evidence absent |

The loopback integration module enables the actual implementation only for isolated exact-IP HTTPS testing. It does not mock authentication, TLS or MLS validation. Normal production images remain gated; there is no runtime bypass setting.

Remaining work is explicitly tracked in SECURITY_STATUS.md and docs/security/controls.csv. In particular, do not infer field compatibility, performance, complete ASVS coverage, key transparency, strong malicious-origin protection, production failover or independent verification from passing local tests. No TODO-only endpoint is presented as a passed release feature.

## Interface redesign — 2026-10-24

Installed all 14 Neshino frontend/testing skills with provenance and implemented the iOS-inspired Liquid Calm interface, adaptive navigation, dark/light themes, local Persian font/RTL and reduced-motion fallbacks. Current UI/regression results are in TEST_REPORT.md and docs/UI_REDESIGN.md. Linux WebKit's native-select CSP warning is reproduced separately and retained as a limitation. The offline shell is bound to its build revision across worker restarts; a lifecycle harness and real browser offline regression cover separate aspects of this behavior. Existing signed QA archives predate the redesign; release remains BLOCKED.

## View-once media — engineering implementation

Added view-once photos/videos with an authenticated policy, durable per-account consumption and device-bound temporary download authorization, native temporary viewer, export/import exclusions and cleanup. Usage and security limits are in docs/user-onboarding/view-once.md and docs/adr/0005-view-once-media.md. Independent review, physical Safari/Android and qualified production ledger durability remain outstanding; overall release stays BLOCKED.
