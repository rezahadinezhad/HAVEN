# Security design: decisions, consequences and evidence

HAVEN's security work connects encryption to the operations around it. This guide explains why the implemented controls exist, how they cooperate, and what they do not establish. The [architecture](../architecture/README.md) describes component/data flow; [security status](../../SECURITY_STATUS.md) records outstanding assurance.

## Identity, login and unlock

A server account, an approved device and an unlocked local vault authorize different things. Password-bound sessions protect account access. Signed enrollment and current device authority control participation. Fingerprint comparison binds peers to the identities they intend to trust. The local secret unlocks saved private state.

That separation matters after loss or compromise. An account password reset does not recreate old message keys or silently bless a replacement identity. Recovery establishes fresh credentials/device state; peers need to verify the change. Readable history imports do not install live ratchets, trusted pins or resumed outbox state.

**Review:** [session/key lifecycle](../adr/0011-session-and-browser-key-lifecycle.md), [authorization](../../apps/api/core/authorization.py), [messenger](../../apps/web/src/lib/messenger.ts), [onboarding](../user-onboarding/README.md).

## Interrupted delivery must not corrupt local state

A message can be encrypted successfully even when its network reply is lost. Re-encrypting after uncertain acceptance would treat a network failure as a new cryptographic operation. HAVEN instead checkpoints the resulting private state and pending encrypted request together, then retries those saved bytes. Server ordering/idempotency and later reconciliation distinguish acceptance from uncertainty.

Recipients verify authenticated history, sender, epoch and membership before storing the resulting local state. They acknowledge only durable local progress. Redis hints improve responsiveness but cannot replace the authoritative history exchange.

This is a durable retry design, not exactly-once networking or a proof of global consistency across all client views. [Atomic storage/sync decision](../adr/0012-review-remediation-storage-and-sync.md), [client implementation](../../apps/web/src/lib/messenger.ts), [protocol](../../apps/api/core/protocol.py), [verification index](../../TEST_REPORT.md).

## Local history needs a storage model, not just a cipher

One encrypted object containing all historical content becomes expensive and eventually bounded by record size. HAVEN uses independently encrypted history records with an authenticated manifest in the checkpoint. Changes to records and the checkpoint commit atomically; unchanged records can be reused. Draft edits do not require rewriting every old message.

The worker derives a 32-byte key through Argon2id with 64 MiB of memory and three passes, then uses authenticated XChaCha20-Poly1305 encryption. Revision/Web Lock checks and lock-generation checks protect against stale writers and late asynchronous completion. Capacity failure preserves the last durable state rather than silently evicting unacknowledged messages. Authenticated malformed application content can be quarantined after the security checks, allowing later valid content to proceed.

An encrypted vault does not protect plaintext while a compromised browser is unlocked, eliminate browser quotas, or guarantee memory erasure. [Vault worker](../../apps/web/src/lib/vault-worker.ts), [segmented history decision](../adr/0012-review-remediation-storage-and-sync.md).

## Permission checks must survive races

Authority can change between authentication and a write: a session expires, a device is revoked, or a member is removed. HAVEN refreshes current authority and uses explicit account/conversation fences for affected operations. Shared transaction behavior rolls back partial work on handled failures. Media completion, leases and cleanup coordinate through their required locks.

The bounded runtime uses explicit pools and worker limits rather than unlimited concurrency. Storage accounting reserves within transactions and refuses excess work without weakening the durability or authorization checks. These limits control resources; they are not evidence of production capacity.

**Review:** [request authority](../adr/0014-request-authority-and-enrollment-retention.md), [bounded runtime/storage](../adr/0015-bounded-api-runtime-and-storage-locks.md), [race tests](../../apps/api/core/tests/test_authorization_fences.py).

## Minimize incidental disclosure without claiming anonymity

The service still needs authenticated routing, active relationships, order and delivery state. Privacy hardening removes redundant timestamps and plaintext profile caches, scopes discovery/contact introductions, narrows API/worker SQL reads, expires temporary associations and buckets new encrypted sizes. HMAC routing labels reduce directly readable account identifiers in Redis. A separate notification credential can read only its required pending hints/outbox projection.

Those controls reduce collection, copies and unnecessary access. They do not hide the active social graph from the main service, prevent a privileged operator from instrumenting processing, erase old backups, or defeat traffic correlation by an ISP/broad observer. Keeping secrets outside Redis or SQL helps only against the actor who lacks those secrets.

**Review:** [metadata threat model](metadata-privacy/threat-model.md), [hardening inventory](privacy-hardening/README.md), [threat matrix](privacy-hardening/threat-matrix.md), [role isolation](../../infrastructure/compose/compose.yml).

## Ordinary retention and mutual retirement solve different problems

Routine cleanup ages out eligible delivered ciphertext after each eligible device has acknowledged durable local state. Public signed/control history needed for synchronization remains. Another device of the same account does not replace that device's ACK for routine cleanup.

Mutual v2 closure instead asks whether every historically affected **account** agrees to end a conversation and release its server history. One approved participating device can represent an account. Groups include former members; owner action, a majority, silence or timeout cannot substitute for their consent.

Representatives save available encrypted archives, prepare matching heads, explicitly consent, and save the complete mutual final certificate before returning signed receipts. The service retires eligible records only when safety dependencies settle. Preparation pauses sending for the account and currently cannot be cancelled or transferred. Withheld consent can leave a paused, undeletable conversation; the system does not delete history to resolve that stall.

The archive discloses unavailable history/media and excludes view-once material. Other devices may keep previously delivered local records. A returning offline device preserves rejected/unconfirmed queued material as read-only local history rather than reopening retired conversation state.

**Review:** [retention policy](server-data-retention.md), [closure behavior and bounds](account-closure/README.md), [client closure protocol](../../apps/web/src/lib/closure-protocol.ts), [real browser/backend verification](account-closure/verification.md).

## SQL restoration must not undo retirement

Deleting conversation records from a live database does not stop an older backup from containing them. HAVEN records an authenticated retirement exclusion in a protected independent journal before SQL removal. Restore operations authenticate that current journal and use its exclusions to reject resurrection, including snapshots predating a retired conversation's creation.

The journal does not retain participant identifiers. Minimal opaque replay exclusions have a bounded charged budget; exhaustion refuses further retirement rather than discarding replay protection. Accounts/devices and necessary tombstones remain.

The guarantee depends on retaining the correct independent journal/key and replay authority. Loss or rollback of every independent copy cannot be repaired by the protocol. This is not physical erasure of disks, operator backups, WAL, recipient copies or past observations.

**Review:** [retirement implementation](../../apps/api/core/graph_retirement.py), [journal](../../apps/api/core/retirement_journal.py), [restore operations](account-closure/operations.md), [failure/restore checks](account-closure/verification.md).

## Client code is a separate trust boundary

A website that supplies encryption code can also replace it. CSP and locally served dependencies constrain exposure, but a compromised containing page can supply a different policy or program. This is why HAVEN distinguishes the ordinary website, independent web frontend and signed installed Linux client.

The installed launcher pins an independently checked publisher root and verifies the complete payload: interface, workers, WASM, bootstrap, runtime and dependency lock. Its local HTTPS bridge serves authenticated assets and constrains the API to bounded data/hints from a fixed TLS identity. API HTML, executable content, redirects and security-header policy cannot replace the installed interface. Assets use release-digest paths; installed mode does not register a service worker.

Manual updates reject tampering and installed-state rollback/conflicts, prepare a separate offline hash-locked dependency environment, and switch only after preparation. The runtime inherits the update lock; parent termination cannot release it while the runtime remains alive. Browser-profile locks prevent a live page from switching worker versions. Authenticated launcher maintenance uses the existing pinned root.

Initial distribution/root trust, the publisher/build pipeline, OS and browser remain trusted. First installation needs an independent channel. An independently hosted web frontend still trusts its delivery host; same-host containers do not withstand host-root compromise. The portable Linux client is not an OS/app-store-signed mobile package.

**Review:** [delivery model](client-delivery/README.md), [verification](client-delivery/verification.md), [release verifier](../../apps/verified-client/runtime/haven_client/release.py), [bridge](../../apps/verified-client/runtime/haven_client/gateway.py), [installer](../../apps/verified-client/bootstrap.py).

## Temporary presentation cannot prevent a recipient making a copy

View-once media offers one opening session per recipient account across approved devices. Authorization, device-bound tokens/leases, limited retention and a temporary viewer cooperate to enforce that policy in honest clients. It avoids leaving a normal preview in conversation history and excludes that material from archives.

An authorized recipient, modified client, capture tool or compromised endpoint can retain plaintext. View-once is an access policy, not a guarantee against screenshots or secure-erasure proof. [Decision and limits](../adr/0005-view-once-media.md).

## How to assess the assurance

Start with [current status](../../SECURITY_STATUS.md), then trace the feature through its code, decision record and dated evidence. The [test index](../../TEST_REPORT.md) separates native protocol checks, backend/transaction behavior, browser workflows, installer/runtime checks and advisory scans. Their totals can overlap; tests of an upstream protocol are not independent certification of the whole product.

Known failure attempts and reruns remain in the engineering records. Dated ADRs may describe older blocked/default-disabled stages; use current code/status for present behavior and those records for decision history. Local tests do not establish public-host hardening, physical mobile behavior, provider failover, a throughput SLA or independent application/cryptographic review.

Security review and reproducible failure reports are welcome through [the disclosure policy](../../SECURITY.md). Do not include real credentials, messages, invitation tokens or recovery material in public issues.
