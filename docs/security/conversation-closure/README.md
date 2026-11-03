# Experimental mutual conversation closure and synthetic graph retirement

Phase 10 now has an executable implementation and local verification. **Production activation and general graph retirement remain disabled.** This supersedes the design-only status at commit `21d8cbf`; it is not an independent security certification or a production deletion rollout.

The supported scope is a newly created, explicitly opted-in, text-only direct conversation between two accounts, each with exactly one approved device. Existing conversations and their signed bytes are unchanged. The signed genesis advertises `mutual-local-archive-v1` and a restore namespace. A past removal, leave, role/ownership change, extra approved device, recovery/revocation, attachment obligation, or missing local history blocks this prototype. Epoch Update remains supported.

Implemented behavior:

1. Either participant signs a proposal anchored to verified history. A proposal alone does not freeze the peer's queued sends.
2. Each device flushes pending sends, synchronizes, verifies every signed proof, and durably saves a complete encrypted local archive before submitting its signed preparation. A prepared device stops writing. If the peer advances the head before preparing, both devices must prepare the new exact head.
3. Matching preparations freeze the conversation. Both devices explicitly consent to the same transcript and their own archive commitments after durable delivery ACKs. The server then marks the conversation closed, retaining its complete history.
4. Each device saves the complete mutual final certificate before sending a separate signed receipt. A missing or failed certificate save prevents that receipt and blocks retirement.
5. A guarded Python prototype can retire this graph **only in a nonce-marked disposable loopback test database**, after both final receipts and all dependency checks. There is no deletion HTTP endpoint, normal management command, retention-worker invocation, or production deletion switch.

Closure bounds are 500 signed envelopes, 512 KiB of public proofs, a 4 MiB complete local archive, and eight archives per vault. Operations are serialized with existing encrypted vault writes and sorted account/conversation locks. Accepted retries and mandatory ACKs remain available after closure. There is no timeout consent, cancellation, reopening, automatic device exclusion, or silent draft/outbox discard.

Encrypted archives can be exported, restored and read offline from Recovery kit. Import verifies the archive commitment, signed chain and mutual finality certificate. It restores no MLS ratchets, credentials, pins, cursors, queued requests or live authorization; mathematical signature verification does not independently establish a friend's real-world identity. A conflicting archive is refused. Export before clearing browser data; losing the vault and all backups loses the local archive.

The normal source constants `CRYPTO_READY`, `CONVERSATION_CLOSURE_READY`, and `GRAPH_RETIREMENT_SYNTHETIC_ONLY` remain false. Only the already restricted loopback integration settings enable closure for evaluation; destructive tests additionally mark their own disposable database. Merely setting an environment variable does not enable production closure or deletion.

[Protocol and invariants](protocol.md) · [Migration, restore and replay keys](recovery.md) · [Verification and limitations](verification.md) · [Before/after graph evidence](graph-evidence.md)
