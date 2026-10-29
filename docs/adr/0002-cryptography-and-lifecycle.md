# ADR 0002 — RFC 9420 browser integration and release gate

Use OpenMLS 0.9.2, RustCrypto/basic credential/memory storage 0.6.0, tls_codec 0.5.0 and wasm-bindgen 0.2.105. Suite 0x0001 uses X25519, AES-128-GCM, SHA-256 and Ed25519. Cargo.lock pins the exact graph. libsodium wrappers/sumo 0.7.15 supplies Argon2id and XChaCha20-Poly1305, not a substitute messaging protocol. No external messaging service is involved.

The original feasibility slice evolved into an actual browser/API integration. Native tests and generated Unicode/serialization/replay/public-parser properties, Chrome/Firefox browser crypto and full delivery tests, isolated Linux WebKit smoke, a native-to-WASM golden fixture and upstream known-answer tests have been executed; see TEST_REPORT.md. No independent review is present. Linux WebKit is not physical iOS Safari.

## State and acceptance

The adapter exports whole-provider SECRET snapshots to the browser integration only; private snapshots never enter the delivery API. Each operation reconstructs OpenMLS state. Normal application sends prepare a candidate, encrypt it with pending ciphertext into the vault, then transmit the exact ciphertext. A storage failure does not adopt the speculative state. Vault writes use Web Locks and an IndexedDB revision comparison; conflicting tabs must lock/reload.

Membership controls retain a candidate snapshot without replacing active state until a signed durable acceptance is authenticated. The outbox records a digest of the base provider state. Unresolved controls fence other cryptographic mutations. A stale commit is discarded only after server conflict, followed by verified synchronization and explicit retry. An operator/user cancellation is a local reconciliation request, not a guarantee of network recall. If the exact cancelled candidate was accepted, it may be adopted only while the provider still matches its recorded base; otherwise fail closed. No silent provider snapshot rollback.

Backend admission verifies public MLS structures, signer approval and routing/group/epoch binding. Clients additionally validate pinned credentials, signed genesis, ordered canonical headers and complete authorized role/roster transitions, then compare actual OpenMLS membership and the hashed epoch authenticator. RFC8785 JCS is shared between Python and TypeScript. These signatures bind delivery/policy metadata; MLS remains responsible for content encryption. This is application integration requiring independent review, not a new cipher or replacement ratchet.

The retained checkpoint binds signed genesis hash and conversation kind as well as sequence, epoch, roster and chain hash. Existing v2 vaults missing the additive public checkpoint fields verify full history before caching them; ratchets are not reset or restored. Established clients verify the suffix after their retained checkpoint. Synchronization uses the captured detail sequence as a fixed upper bound; concurrently arriving later envelopes wait for the next pass. Gaps, contradictory heads and stale snapshots fail closed without discarding the retained checkpoint.

Headers form a signed hash chain. Retained checkpoints detect contradictions, truncation and rollback relative to local state; they do not provide global key transparency or prevent mutually censored forks without independent gossip. No such stronger claim is made.

## Enrollment, revocation and recovery

Every device has a separate MLS credential. First enrollment requires self-proof and only the initial ever-enrolled device can use the first-device policy. Later devices require an existing approved device's signature and independent fingerprint comparison. Existing devices rebind password-authenticated sessions using a fresh purpose-bound server challenge. A revoked history cannot reopen first-device trust. Current members can look up historical revoked certificates from their shared groups for independent signature verification. This does not grant fresh membership, package claims or trust; the UI labels them historical-only. Unknown historical fingerprints can still pause a new join until independently verified.

Public one-use KeyPackages are cryptographically validated, atomically claimed and replenished after successful join, including a durable pending-replenishment flag for interrupted joins.

Revocation pauses groups until authorized MLS removal. Leave is a signed request and requires owner/moderator removal; ownership must transfer before an owner leaves. Loss of the final authority requires a fresh independently verified replacement group. Existing members cannot silently grant a replacement identity old history.

Recovery uses an offline random seed whose Ed25519 public key was pre-provisioned by an approved device. A signed challenge binds fresh device credentials, rotated recovery key and new account-password hash. It revokes all old devices/sessions, increments security generation and pauses groups. Saved history is local-only. No old ratchets, pending messages or cursors are resumed. Additional-device history import copies only validated local events. An additional device without the original recovery authority can export a history-only kit; it cannot overwrite account recovery authority. Interrupted recovery must preserve its prepared local vault; first try unlocking/rebinding the fresh identity, never revert to the old ratchets.

The raw provider snapshot rollback characterization remains reproducible; recovery policy mitigates application restore paths, but is not a proof against malicious profile rollback or malicious origin code.

## Vault and media

Argon2id uses three passes, 64 MiB and one lane in a worker. The derived key may remain only in that worker while unlocked; salt is reused for that vault and every save uses a fresh random 192-bit AEAD nonce. Lock fences asynchronous saves and clears retained candidate/file-key references; stale callbacks cannot repopulate the active UI. Audio playback is stopped and object URLs revoked on lock. JS strings/GC and WASM snapshots prevent reliable secure erasure. Phone memory/KDF qualification remains blocked.

Attachments use independent random 32-byte keys, random 16-byte nonce prefixes and a 64-bit big-endian chunk counter. AAD binds domain, v1, conversation, opaque file ID, chunk index and count. Bounds: 512 KiB plaintext chunks, 25 MiB files, 50 chunks. Keys, names and MIME are only inside authenticated MLS events. Upload ciphertext is prepared before transport and resumes from IndexedDB. Downloads authenticate chunks before caching ciphertext and can resume interrupted transfer; partial plaintext is never persisted. Four incomplete downloads are allowed. General files are explicit downloads; no server preview/decryption/transcoding. Voice capture is capped at two minutes/25 MiB.

Ciphertext chunks are held in PostgreSQL rather than a separate object store for atomic scoped access and backup simplicity. This increases DB/WAL/backup volume and requires storage/load qualification. No cross-user plaintext deduplication.

Rekey policy is provisionally seven days or 1,000 ordered envelopes since the last epoch transition. Further sending pauses until owner/moderator refresh. These conservative safety limits require physical-device/performance review; they are not a formal security bound. Outbox is capped at 100 entries and local sent history at 20,000 events. Export/explicit clearing preserves live keys and pending sends.

## Gate

Normal CRYPTO_READY remains source-level false. The exact-loopback integration module enables actual implementation only for test/evaluation; authentication, TLS, public MLS verification and trust checks remain real. Public/physical TLS, complete acceptance and independent integration review remain release gates. No environment toggle, certificate bypass, plaintext fallback, static sealed-box replacement or server E2EE key is accepted.
