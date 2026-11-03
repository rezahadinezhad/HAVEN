> Historical design finding at `21d8cbf`. A later explicitly authorized implementation now supports a restricted two-account, single-device, text-only experiment and guarded disposable-DB retirement. See the [current implementation, protocol, tests and production limits](../conversation-closure/README.md). The broader requirements below remain relevant; the historical “not implemented” statements describe that earlier snapshot.

# Conversation closure and historical graph retirement — proposed v2

**DESIGNED_NOT_IMPLEMENTED.** There is no new runtime state flag, deletion command, background task or production migration for retirement. The synthetic graph test demonstrates retained graph copies; it is not a deletion prototype. The owner reports no real users, but this does not justify implementing a false finality protocol or weakening invariants.

## Goal and boundary

A future current-DB compromise should learn fewer relationships for genuinely finished conversations after a mutually authorized final checkpoint and removal of all graph-bearing copies. It must not affect other participants' recoverable history, replay protection or keys. It does not hide active relationships, old snapshots/WAL, provider copies, prior live observations, client copies or traffic. Deleting Membership alone fails because immutable genesis, full-roster transitions, sender headers, creator, welcomes, ACKs, attachment ledgers and quota keys repeat the graph.

## Retained reference inventory

| Copy | Required obligation before unlinking |
|---|---|
| Conversation creator/group/genesis/signature/head | Client-independent verification, trusted final head, no old signed-byte rewriting |
| Membership device/epochs/role/leave signature | Every past and present participant's authority, removed/offline recovery and consent |
| Envelope sender/client UUID/order/epoch/header/signature/digest/chain | Durable history, exact retry/idempotency, replay rejection, anti-fork checkpoint |
| CryptoControlEvent transitions/welcomes | MLS roster/epoch proof and offline joins/recovery |
| DeliveryCursor | Final persisted history on every eligible approved device, never inferred human reading |
| NotificationOutbox | All accepted sends/hints settled or explicitly recoverable; at-least-once retry preserved |
| Attachments/chunks/view-once views/tombstones | Pending upload/download/opening and account-wide consumption, expiry/accounting correctness |
| StorageUsage account/service keys | Consistent release of exact charges without deleting authorization/replay evidence |
| Audit/Invitation/recovery/session links | Independent justified retention and accidental graph copies |
| Backups/WAL/replicas/client exports | Independent historical copies; restore fences cannot assume current deletion propagates |

## State machine and signed finality

Proposed `ACTIVE → CLOSING → CRYPTOGRAPHICALLY_FINALIZED → RETIRED` is a specification only. No server boolean can constitute the cryptographic transition.

1. ACTIVE accepts existing ordered authenticated application/control events. A proposal is a new versioned signed control event, domain `haven/closure/proposal/v2`, bound to group/conversation, base head/hash/epoch, random closure nonce, complete eligible principal/device roster and advertised client capabilities. No timestamp alone determines authority.
2. CLOSING must fence new submissions under the same sorted account/conversation lock order used by normal authority checks. Every accepted pre-fence send has one sequence and remains recoverable. Concurrent application/control/revoke/recovery either linearizes before the proposal and changes the committed head/consent set, or is explicitly rejected without losing the pending ciphertext. A proposal cannot acknowledge a sender's still-unaccepted local outbox. Cancellation/reopening before finality needs a new signed, monotonic event and invalidates all prior consents.
3. Each affected participant explicitly consents to the exact final transcript commitment and scope of server retirement. Proposed safe policy requires consent from every account whose history would become irrecoverable, including removed historical members; current group-owner status is insufficient. Every eligible device must durably save a complete authenticated final checkpoint before its signed final-device acknowledgment. An offline/unreachable device or missing consent blocks finality indefinitely unless a separately reviewed preexisting device-revocation/recovery policy safely resolves that principal. Timeouts cannot manufacture consent or ACKs.
4. CRYPTOGRAPHICALLY_FINALIZED requires an all-party, authenticated finality certificate containing the exact final head/epoch/closure nonce, roster/capability agreement and durable-device attestations. It must include domain separation, protocol version and replay-safe transcript binding. New-client support/capability negotiation, application/event framing and independent implementation review are prerequisites. No certificate format/signature aggregation algorithm is invented in this change set.
5. RETIRED is permissible only after an independently checked dependency scanner proves all remaining required recovery/replay/consumption obligations have a non-graph-bearing replacement. Deletion must be transactional, resumable and idempotent, preserving permanent deny markers and exact service/accounting charges. If existing signed JSON must stay server-side for any authorized client, the relationship cannot be claimed retired. Local participant copies remain under each participant's control.

## Adversaries and incomplete transitions

A malicious participant may withhold consent forever; availability must yield to other participants' recoverability. One stolen device cannot consent for an account's unapproved/offline devices. A dishonest server can suppress proposals, reorder notifications, replay an earlier closure, restore an old DB or present forks: clients must pin monotonic final heads/nonce and reject all downgraded epochs/finality; server-only tombstones cannot defeat arbitrary server rollback. An account recovery while CLOSING changes the authority set and invalidates consent; it must not inherit an old signature. Revocation cannot silently erase the revoked user's already recoverable local history.

Crash after proposal, after one device checkpoint, after signatures, or halfway through resource release must preserve either the entire live recoverable graph or a verifiable finalized state with all proofs. Rollback cannot restore accepts for retired conversation/client IDs. Retry must be stable across process failure and backup restore. Upload/view-once lease still in flight blocks retirement until a safe final state; a cleanup timer cannot substitute for participant consent.

## Migration, rollback and proof obligations

A future migration is additive/versioned and initially disabled, with per-client capability negotiation. It must not mutate old genesis/certificate/envelope bytes, rewind MLS ratchets, drop live outboxes or infer state from current membership alone. Supported rollback before any finality can revert the feature code; rollback after finality must refuse old writers and preserve finality/replay markers. Restoring an old backup requires an external monotonic finality reference or independently verified client checkpoint reconciliation; arbitrary SQL deletion plus a DB tombstone is insufficient.

Required proofs: (P1) authorization for every affected participant; (P2) a single agreed final transcript and no send lost across the fence; (P3) persistence-before-ACK for all devices; (P4) no forged consent/role escalation; (P5) replay/downgrade/restore rejection; (P6) interrupted-state recoverability and exact quota accounting; (P7) view-once nonreopening; (P8) removal of every graph-bearing copy in a disposable post-retirement snapshot; (P9) preserved authentication and independent fingerprint checks; (P10) bounded CPU/storage/abuse costs and no unbounded retention claims.

Synthetic adversarial plan: honest/all-party and withheld/removed/offline consent; wrong signer/epoch/head/device; stale/replayed/reordered close and reopen; concurrent send/Add/revoke/recovery; pending encrypted uploads and consumed openings; dropped responses and every crash boundary; retry after partial accounting; forward migration interruption and unsafe reverse; restored old backup with/without external checkpoint; reconstruct graph from every FK and signed JSON before/after. Real MLS and real vault persistence are required, not mocks of finality.

## Finding

The current protocol has no signed all-party closure/final-checkpoint/capability negotiation and retains signed histories for offline devices. These proof obligations cannot currently be met by a safe SQL cascade or isolated status flag. An executable destructive prototype would simulate a guarantee the design has not established. Stop at this explicit design finding; independent protocol/security review and later explicit activation approval are required. No anonymous mailbox/blind-credential transport or major rewrite is proposed as a hidden dependency of this work.
