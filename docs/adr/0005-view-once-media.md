# View-once photos and videos

Status: implemented for engineering evaluation; release remains BLOCKED and no independent review is claimed.

## Contract and boundary

One opening means one bounded **viewing session per recipient account**, across all its devices. Each other group recipient has their own opening. The sender cannot reopen the sent item through HAVEN. It is not a claim that plaintext was physically destroyed or that the person actually saw it. A claim consumes the opening before download/display, including interrupted or failed loads. The UI explains this before opening. Maximum session lifetime is ten minutes, including load time.

This is access control plus cooperating-client behavior, not cryptographic remote erasure. A modified client, screen recording, another camera, compromised browser/origin/OS, copies of the original file, old backups, or rollback of the authoritative consumption database can defeat stronger expectations. Browser strings, Blob/decoder/GPU memory, database pages/WAL and backup media cannot be reliably securely erased by this feature. Do not advertise screenshot prevention or guaranteed destruction.

## Server state and concurrency

ADR 0006/migration 0008 supersedes opening timestamp retention: a consumed boolean preserves the view budget, ended capabilities/device links are cleared, and per-recipient records are discarded after all openings finish. Existing and new files use the shorter seven-day TTL. ID-only tombstones remain.

Migrations 0006/0007 add an immutable-at-init `EncryptedAttachment.view_once` policy and `AttachmentView` rows with a unique attachment/account constraint. Eligible approved recipient accounts are snapshotted at upload initialization; later joins are excluded, even if they obtain old metadata. This conservatively preserves the existing attachment epoch boundary. If membership changes during a long upload, send a fresh upload for newly joined recipients.

An identifier-only `AttachmentTombstone` is recorded with every view-once initialization and backfilled for existing items. It contains no account, conversation, key or opening time. It survives TTL deletion and blocks recycling the same ID under either ordinary or view-once mode. Cleanup therefore cannot reset a view budget. Retain these markers when migrating/restoring the consumption ledger.

The API claim transaction locks the conversation, attachment and recipient row. It verifies the existing trusted device/session, current membership, attachment epoch, status/expiry, CSRF and TLS gates. Simultaneous claims by two approved devices of one account cannot both succeed. Redis is used for the existing rate limit, never as the durable consumption ledger. Normal crypto release gating is unchanged.

The browser creates a random 256-bit temporary token. The database stores only its SHA-256 hash and binds it to the claiming approved device, account, attachment and ten-minute expiry. This is an **access capability, not a file decryption key**. It stays in viewer memory and is sent in POST bodies and the `X-Haven-View-Token` chunk header, never URLs, local storage, the vault or exports. An exact same-device/same-token retry while the lease lives is idempotent for a lost response. A different token, another device, closed session or expired lease cannot open again. The stock viewer never resumes a consumed session after reload.

Chunk GET verifies the capability and normal authorization. Generic attachment download, the uploader and other accounts cannot use that session. Closing invalidates the token; all-consumed attachments lose their ciphertext chunks after the last active lease closes. An abandoned/crashed lease expires without restoring an opening, and `cleanup_expired` finishes cleanup. Other recipients' unopened media is retained; the seven-day attachment TTL (ADR 0006) ultimately removes expired rows/chunks. Run the documented periodic cleanup job. Deleting database rows does not physically erase WAL/backups.

No individual opening result is broadcast to the sender. The sender's status endpoint returns only `sent`; recipient status is their own `available`/`opened`. The server necessarily learns the policy, eligible accounts, claim time and claiming device even if optional read receipts are off; the composer discloses this.

## Cryptography and local storage

Existing OpenMLS carries the policy and random per-file key in its authenticated encrypted application payload. The existing libsodium XChaCha20-Poly1305 chunk encryption, random 32-byte key, 16-byte random nonce prefix plus 64-bit chunk counter remain in use. View-once chunks use the separate AAD domain `haven-view-once-attachment`; normal attachments retain `haven-attachment`. Both bind version, conversation ID, attachment ID, chunk index and total chunk count. No cipher/protocol substitute or server-held plaintext key is introduced. [Libsodium documents the construction and authenticated additional data](https://doc.libsodium.org/secret-key_cryptography/aead/chacha20-poly1305/xchacha20-poly1305_construction).

Before claiming, the client durably marks a local consumed tombstone and removes the displayed history copy of its key/prefix/name. Failure to persist stops before the claim or media download. This deliberately fails closed if acceptance is uncertain; a local attempt may be lost even if no pixels were displayed. Outgoing history loses its key after the authenticated envelope is encrypted; its existing encrypted outbox remains retryable.

Received view-once chunks bypass IndexedDB entirely, including interrupted downloads. They pass all normal AEAD, chunk-size and whole-file-size checks before a Blob is displayed. Existing workers/service worker cache no API responses or media plaintext. Raster JPEG/PNG/WebP/GIF/AVIF and MP4/WebM/Ogg video MIME types are allowed; actual codec support depends on the browser. HTML, SVG, documents and audio notes cannot use this viewer. The existing 25 MiB limit remains.

New plaintext history exports omit all view-once events. New encrypted recovery kits also omit those events, pending upload keys/outboxes, drafts and live ratchets; recovery was already history-only and creates a fresh identity. Import/recovery skip supplied historical view-once events. These exclusions cannot retract any older/manual vault snapshots, retained keys, ciphertext or captures.

The native modal has no save/download/forward or thumbnail UI. It closes immediately on Escape/close, video end, page hide, vault lock or component removal, with a ten-minute cap. It aborts pending downloads, stops video and revokes its Blob URL. Revocation releases the URL reference; it is not secure memory erasure. A development Firefox run reloaded a revoked URL from decoded-image memory; the final code also removes the image source explicitly before revocation. Tests verify the actual revocation call and record engine reload behavior, without treating cache eviction as a security guarantee. [Browser object URL lifecycle](https://developer.mozilla.org/en-US/docs/Web/API/URL/revokeObjectURL_static). Dialog keyboard focus is browser managed; private pixels are not animated through screenshot-based view transitions. Native save/cast/PiP controls are restricted as UX affordances, not security guarantees.

## Deployment and review

Deploy migration/API before updated clients: older servers reject the added policy field; older strict clients reject the view-once authenticated metadata rather than silently treating it as an ordinary attachment. No extra dependency or external service is required. Default database privileges must cover both new tables and the claim-row sequence for the runtime role.

Consume-state durability must be preserved during replication/failover/restore. Restoring an older database may restore an unused opening; local tombstones alone cannot protect other devices. Do not enable view-once claims against an uncertain/stale consumption ledger. The existing production release gate stays closed pending independent review and qualified operations/physical devices.

Row locking follows [Django's transaction-bound select_for_update behavior](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update). Automated race tests use real PostgreSQL and distinct connections, not an in-memory Redis lock or mocked view counter. See TEST_REPORT.md for exact browser/backend evidence and its limits.
