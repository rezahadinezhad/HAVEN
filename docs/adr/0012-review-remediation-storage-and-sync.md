# ADR 0012: durable segmented history, resource budgets and change-aware sync

Date: 2026-11-01. Status: implemented; production qualification remains blocked.

The [source review](../security/independent-review-2026-11-01.md) identified seven availability, storage and synchronization issues. This decision records their remediation without changing MLS primitives, device trust or the release gate.

## Client storage and malformed content

The IndexedDB database upgrades to version 3. A vault checkpoint remains encrypted with its existing Argon2id/XChaCha20-Poly1305 profile. Its authenticated plaintext now names independently encrypted history records. Each immutable event version gets a fresh random record key; that key and the account scope are authenticated as record AAD. A previous version cannot replace a current record or a record from another account. Checkpoints retain ratchets, cursor/head, outbox and the history manifest. Record replacements/deletions and checkpoint replacement occur in one IndexedDB transaction, including explicit abort on synchronous write failures. Revision/nonce checks and Web Locks continue to reject stale writers. No ACK precedes durable persistence.

Only changed event versions are sealed/written. Committed events are immutable; draft-only writes reuse encrypted records. The cache is scoped to the account, revision and an in-memory secret tag, and is cleared on lock. Changing the secret rewrites all history records under the new key. No tag or plaintext event cache is stored outside memory. Lock-generation checks prevent asynchronous completion from repopulating cleared caches.

Legacy monolithic vaults are read without resuming a different ratchet and migrate atomically on their next successful write. Portable history exports use bounded encrypted pages, retain the existing history-only outer kit format, and still exclude ratchets, outbox, pending uploads and view-once keys. Old v1 encrypted kits remain readable. Recovery/import files are bounded to 256 MiB. The 16 MB worker bound remains per checkpoint/record, rather than applying to all historical message bodies. Browser disk quotas and bounded crypto/checkpoint state still exist; capacity failures preserve the last durable state and provide an export/clear-delivered-history recovery instruction. They never silently evict unacknowledged messages or ACK content that was not stored.

After successful transport signature, history chain, MLS sender, epoch/type and membership verification, invalid application JSON/schema/binding is recorded as a rejected event. Its authenticated ratchet/cursor advancement is durably committed and later valid traffic continues. Only 64 marker IDs/sequence positions are retained, with a cumulative count; no offending plaintext is copied into diagnostics. Cryptographic, transport, sender and membership failures remain fatal. The UI reports newly skipped content once without revealing protocol details.

## Server storage accounting

`StorageUsage` rows account for each sender account and the service. Reservations charge ciphertext, canonical signed header, signature, a conservative 4096-byte row/index allowance, and duplicated control-transition/welcome data. Conversation genesis reserves 4096 bytes. Bounds are:

| Budget | Default |
| --- | --- |
| Account logical message/conversation bytes | 256 MiB |
| Account unretired application ciphertext | 64 MiB |
| Service logical message/conversation bytes | 5 GiB |
| Account retained envelopes | 100,000 |
| Service retained envelopes | 2,000,000 |
| Conversations created per account | 500 |

Checks and reservations are transactional with acceptance. Both account and service rows lock in key order after the conversation lock, without acquiring a User lock. Retiring delivered application ciphertext refunds exactly its payload bytes in the same transaction; signed records and their count/overhead stay charged. Multi-sender refunds lock all accounts before the service row to preserve the same lock order. Retry/idempotency does not reserve twice, rejected writes do not advance the head, and existing unacknowledged ciphertext is retained at the limit. Over-limit imports/backfilled accounts are preserved but cannot add more charged data until capacity is reclaimed or policy is deliberately revised.

Migration 0011 backfills existing conversations, ciphertext and control records. Migration 0012 indexes discovery order. These are logical message budgets, not a physical PostgreSQL/WAL, attachment, backup or host-volume quota; operators must monitor those independently. Existing attachment reservation policy remains in force. The administrator status response exposes logical service counters alongside existing database-size telemetry. See the [operations notes](../security/review-remediation-2026-11-01.md).

## Discovery and polling

Both discovery endpoints use the same descending `(created_at, id)` keyset order, a signed one-hour device-bound continuation token and an upper creation-time boundary shared by the traversal. The array conversation endpoint returns continuation in `X-Haven-Next-Cursor` to preserve its existing body contract; the browser API helper follows all pages. `/sync` returns `next_cursor` in its object body. No OFFSET scan or invisible 100-conversation cap remains.

Fresh background discovery includes a receipt version. The client skips unchanged verified heads and unchanged receipts. Cursor ACKs are retried after unlock/lost responses but are not posted every idle cycle; the server does not update unchanged cursors or increment receipt versions for them. Explicit sync, send and membership/lost-ACK reconciliation always reread server detail. The unchanged-head shortcut is deliberately available only through `syncIfChanged`, called with a freshly fetched discovery snapshot. MLS mutations remain serialized. A role change updates only the affected memberships rather than rewriting the whole roster while holding the storage budget lock.

Proof reads explicitly defer ciphertext and unused payload columns. Their serializers must remain free of deferred-column reads; regression tests capture actual SQL.

## Sign-in fairness and privacy

The constant service-wide minute budget is removed. Malformed requests are rejected before credential counters. Account/source and source budgets plus four in-flight Argon2 operations bound work; public ingress additionally enforces source pacing. Only the exact login path receives a transport-derived forwarded source, overwritten by public ingress, or relayed by the allowlisted trusted backup bridge. Other paths continue stripping address headers. Counters use 120-second keyed HMAC labels; raw source addresses are not added to durable application data, audit logs or metrics. The API must stay on its trusted private/loopback upstream network. Shared NATs share ingress source budgets; no claim of immunity to distributed denial of service is made.

## Dependency tooling

The schema generator moves to `openapi-typescript 6.7.6` with its fetch dependency explicitly pinned to compatible maintained `undici 6.29.1`. This removes the vulnerable Redocly/minimatch path without an incompatible Redocly major override. Generated contracts and the typed API client are regenerated and typechecked, and full npm audits cover development tools. This choice is confined to development tooling. The lockfile still reports the existing `proc-macro-error2` maintenance notice via the conditional `cfg(hax)` proof-tool chain, absent from native/WASM shipping dependency trees. Its upstream `core-models` and `libcrux-intrinsics` releases still require it; it is not suppressed and no cryptographic provider fork was added merely to hide the notice.
