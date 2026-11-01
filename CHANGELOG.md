# Changelog

## Unreleased — 2026-11-02

- Extended Firefox regressions found and fixed a voice-note format bug: retain recorded blob MIME after MediaRecorder resets its type at stop. Private attachment metadata and actual playback stay intact. Correct the AEAD negative test to always flip a ciphertext byte rather than occasionally making no change.

- Minimize metadata: remove unused ACK/upload/session timestamps and receipt table; disassociate expired KeyPackage owners/claimants with a partial expiry index; omit exact acceptance time from responses and project routing reads.
- Bound stale Redis account-channel associations to two minutes with authenticated renewal; preserve authoritative HTTP delivery during Redis failure.
- Use native OpenMLS 256-byte application padding, preserving existing state/queued ciphertext and rejecting unknown configuration resets. Rebuild WASM/contracts/offline assets.
- Serialize abandoned-upload cleanup with completion, report aggregate maintenance failures, and add PostgreSQL/Redis/browser/native/dump-restore regressions and accurate EN/FA privacy disclosures. Coordinated migration 0013/0014 required; normal production gate stays closed.

## Unreleased — 2026-11-01

- Resolve all seven source-review findings: malformed application content no longer blocks later messages; encrypted history commits in separate records with the ratchet checkpoint; server message quotas preserve unsynchronized data; login throttling isolates sources; idle synchronization avoids per-conversation traffic/writes; proof queries omit ciphertext; conversation discovery follows signed continuation cursors.
- Preserve legacy vault/recovery compatibility, enforce atomic history updates and lock cancellation, and reencrypt history when the secret changes. Add PostgreSQL migration/concurrency and Chromium/Firefox regressions.
- Replace the vulnerable development-only schema-generator dependency path, regenerate API contracts, and document coordinated API/client migration. Production onboarding remains gated.

## Unreleased — Visible attachment previews and media-type picker

The paperclip now offers Photos & videos, Audio and File choices with matching native picker filters. Pending photos render their actual local pixels; videos and audio have native playback controls before Send. Unsupported/undecodable content has a clear fallback, and SVG/HTML/documents are never embedded as active content. Replacement, removal, send, lock and navigation release preview resources. The confirmation panel keeps Send available while content scrolls. Music/audio attachments have appropriate playback labels. Chat tips was removed from the composer and guidance moved to Connection & help. File-scoped view-once intent and the existing encryption/consumption/TLS gates remain intact. No new dependency, server schema or cryptographic primitive.

## Unreleased — Per-attachment view-once selection

Moved View once into the selected photo/video confirmation box and removed it from the ordinary chat footer. Unsupported files have no viewing-mode control. Mode belongs to a single local file selection, defaults to ordinary sending, resets on replacement/removal/send, and is passed explicitly to attachment preparation. Capture/opening disclosures remain inside the confirmation box when enabled. Existing consumption, account-wide one-view, encryption, approval and TLS gates remain unchanged.

## Unreleased — Conversation experience and contextual guidance

Redesigned the conversation list and chat surface with local message previews, unread filters, date/sender grouping, accessible delivery indicators, native message-action popovers, reply previews, growing text input, IME-safe desktop shortcuts, emoji insertion, full phone chat layout, EN/FA copy and reduced-motion support. Ordinary raster photos/videos open through explicit locally decrypted previews; files now require a filename/viewing-mode confirmation before sending. Recording has a discard action and stops on navigation. File replies retain their context, while edits/reactions/receipts/files preserve unrelated encrypted text drafts.

Browser approval now lists actual trusted browsers and gives three concrete steps, an explanation of the comparison code and recovery limits; pending browsers no longer trigger unrelated background-conversation warnings. Signed approval, fingerprint comparison, TLS and release gates remain authoritative. No account was reset or auto-approved, no server schema/dependency/crypto primitive changed, and no independent security verification is claimed. Detailed review and remaining product/testing limits are in docs/ui-ux/conversation-experience.md.

## Unreleased — Optional local unlock-passphrase generator

Added an explicit new-vault generator using 32 browser-CSPRNG bytes, masked reveal/copy controls, clipboard-denial recovery, saved confirmation after access, regeneration/manual-entry reset and EN/FA guidance. Existing vaults retain original-secret unlock and the existing cryptographic/TLS gates. Generated values are not sent to the server or stored in plaintext browser storage. Clipboard/history, compromised-origin/device and secure-erasure limitations remain explicit; release stays BLOCKED. No new dependency or server migration.

## Unreleased — Guided first chat and bounded member invitations

Added Start a chat for members and administrators: saved-vault detection, setup/unlock, single-use signup/friend links and local QR codes, explicit full-code verification, automatic direct-chat creation, incoming verification and encrypted local contact names. Failed setup preserves keys; lost-response/reload and concurrent retries reuse the same chat intent. Technical fingerprint failures now direct people to verification. Added English/Persian copy and responsive layouts.

At the owner's request, approved proof-bound members may issue three one-use signup invitations per UTC day, at most three pending and at most 24 hours each, subject to administrator pause/disable controls. Added migration 0009, idempotent own-invitation revocation, transactional quota/audit checks and generated API contracts. This deliberately expands the old admin-only invitation policy; it grants no administrative role. Links do not establish identity or bypass device/MLS/TLS gates. Local URLs remain local. Independent review and real remote deployment remain blocked. Fixed the restore drill's temporary PostgreSQL initialization readiness race by waiting for final TCP readiness.

## Unreleased — Minimal server retention and privacy hardening

Added acknowledgment-safe application ciphertext retirement, exact receipt-time removal, seven-day media/audit retention, shorter ephemeral-record retention, a dedicated bounded cleanup worker and authenticated EN/FA retention settings. Replaced permanent view-once opening timestamps with consumption flags, cleared ended capabilities and discarded individual rows after all openings finish while preserving replay tombstones. Added a consumption-preserving, intentionally irreversible migration and existing-media TTL cap.

Removed client-address forwarding in primary/standby/dev proxies, keyed/minute-scoped rate labels, JSON-only cache decoding with bounded timeouts, disabled browsable API/form parsing and request-bearing SQL/exception logging, disabled proxy disk spooling and bounded container logs/core limits. Preserved per-IP ingress controls and account-specific login limits. Added guarded encrypted-backup rotation, real proxy/TLS and migration drills, PostgreSQL retention tests and browser MLS reload/rekey after ciphertext retirement. No extra device/relay or new cryptographic protocol. Accounts/routing/signed proofs, live-host/origin observation and old-backup limits remain explicit; release stays BLOCKED.

## Unreleased — View-once photos and videos

Added a photo/video view-once composer option and native temporary viewer, with one server-enforced opening per recipient account across its approved devices. Added migrations 0006/0007, identifier-only replay tombstones, unique recipient claims, token/device/expiry checks, automatic viewer closure, ciphertext cleanup after recipients finish, client key redaction and history/recovery export exclusion. Ordinary attachments, TLS, trusted-device and cryptographic release gates remain intact. Server opening metadata and interruption/capture/backup/rollback/secure-erasure limits are documented; no independent security verification is claimed. Existing signed QA bundles predate this feature and must be rebuilt/reviewed before distribution.

## Unreleased — Liquid Calm interface redesign

Installed the 14 Neshino frontend/testing skills locally with provenance. Replaced the previous olive interface with an iOS-inspired glass navigation system, modern typography/icons, adaptive conversation layout, clear device setup, mobile navigation/popover and chat back navigation, accessible local Persian font, dark/light themes and reduced-motion/transparency handling. Preserved TLS, crypto/release gates, device approval and local-only data boundaries.

The service worker now changes with its immutable shell manifest and remains bound to that build after browser worker restarts. A mismatched manifest is rejected; old shell caches cannot be selected arbitrarily. The previously signed 0.2.0 QA bundle records the pre-redesign source; regenerate/review release artifacts before distributing this UI.

## 0.2 engineering implementation — 2026-10-24 (BLOCKED for release)

Integrated browser OpenMLS with signed genesis/ordered headers, approved credential/roster policy, native public-structure verification, durable candidate/outbox state, concurrency reconciliation, device session proofs and fresh-identity recovery. Added real direct/group/multi-device browser tests, upstream KATs and native/WASM compatibility evidence.

Implemented resumable encrypted media preparation/transport/download, voice capture/playback, offline public shell and encrypted queued messages, optional typing/presence/read receipts, local search/history import/export/clearing, expanded English/Persian UI and metadata administration. Added separate PostgreSQL roles/durability checks, cleanup/operational evidence commands, replication/fencing templates, a real local standby promotion and prepared two-IP browser continuity drill with verified private TLS, protected backup/restore and signed offline source/runtime bundle workflows.

Fixed failures found during integration: revoked-last-device first-enrollment reopening, missing fresh session proof on re-login, pending membership candidate adoption, blocked reads after delivery errors, depleted KeyPackages across conversations, recovery authority on additional devices, test TLS-port collision, backup command argument collision stale offline connection messaging, lock/persistence resurrection, revoked historical credential verification, UI ordering/mobile logout, standalone live-build file deletion, rapid certificate reload test caching and host-specific restore ACLs.

Moved application containers to digest-pinned Debian 13/Python 3.12.15/Node 24.22.1, removed unused runtime package managers, disabled Nginx request-bearing error logs, and recorded full remaining OS scan findings.

Normal cryptography release gate remains closed. Independent review, physical devices, public TLS/domestic routing, production failure-domain recovery/capacity and complete acceptance matrices are outstanding. Local automated successes are not production approval.

## 0.1 baseline

Preserved the earlier gated engineering package in the initial Git commit before continuation. It included real MLS feasibility code and substantial auth/transport/UI scaffolding, with incomplete integration and recorded release blockers. Historical evidence remains under docs/evidence.
