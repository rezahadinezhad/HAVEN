# Research-only routing specification and open proof obligations

**No anonymous mailbox endpoint, routing credential or prototype is enabled.** This is a reviewable architecture specification, not a proven protocol or a completed unlinkability feature. It intentionally leaves unresolved designs outside production code. The current API keeps approved-device authentication and membership authorization.

## Why an opaque queue alone is insufficient

HAVEN's current header signatures expose stable sender/conversation/sequence, genesis and transitions expose full public rosters, and MLS BasicCredential binds user:device. A queue alias still correlates with cookie sessions, issuance/account quota reservations, discovery, IP/time, WebSocket group and ACKs. Moving Membership behind an encrypted column does not hide signed copies. A server-side attacker with keys can decrypt server-encrypted routing fields. An honest operator also sees requests while processing them.

SimpleX's [chat architecture](https://github.com/simplex-chat/simplex-chat) and [SMP specification](https://github.com/simplex-chat/simplexmq/blob/master/protocol/simplex-messaging.md) motivate independently authorized unidirectional queues, sender/recipient key separation and recipient-chosen queue addresses. HAVEN must retain its own MLS/device trust and durable delivery guarantees; SMP retention/ACK and pairwise identity semantics cannot simply replace them. Reused queues and transport observations still correlate traffic.

Signal's [sealed-sender design](https://signal.org/blog/sealed-sender/) separates sender authentication inside encrypted envelopes from outer delivery authorization. Its sender certificates and delivery tokens show that concealing an outer sender requires replacing spoofing and abuse defenses as well as hiding a label. HAVEN's signed total-order headers and account-charged quotas prevent treating that design as a direct patch. Same-server traffic correlation persists.

## Candidate R2: versioned group sequencer plus per-device capabilities

This candidate is unimplemented. A formal specification would need at least the following state and invariants before code approval:

1. Each group has a versioned opaque sequencing scope. Each device has separate retrieval and submission keys scoped to an epoch, purpose and audience. A random address is not a bearer grant. Proof of key possession binds every method, body hash, nonce and scope, with bounded replay windows and durable replay protection. No cross-purpose or cross-mailbox use.
2. An authenticated MLS transition authorizes capability issuance/revocation without revealing an unnecessary global account identifier. The recipient verifies signed identity/roster/order data *inside* authenticated encryption; a replacement outer order proof must still detect equivocation, omission, epoch substitution and identifier swapping. Do not remove current signatures before an equivalent protocol is reviewed.
3. Delivery to offline devices commits ciphertext and checkpoint proof atomically before acceptance. Duplicate logical sends have exactly one effect across expired credentials, credential rotation and failover. Queue token rotation does not orphan old outbox retries. Retrieval and ACK credentials are separate; ACK only after durable atomic vault save. No TTL may discard unacknowledged ciphertext.
4. Revocation fences writes before authorized MLS Remove/rekey, including in-flight writes. Multi-device issuance requires existing-device approval and explicit fingerprint checking. A stolen retrieval key must not grant submit, history import, view-once reopening or identity recovery. Global and per-group revocation/fork suppression require explicit retained state.
5. Resource accounting has a linearizable reservation/commit/refund model. A design must bound messages, bytes, tombstones, empty queues and verification work without mapping all token spends straight back to accounts. Quotas must survive retries, cleanup, double spend and service crashes. Removing StorageUsage requires a consistent replacement first.
6. Recovery has an authenticated, rollback-resistant encrypted mailbox directory with atomic cross-tab updates and versioned migration. Offline devices must discover rotations without a plaintext central identity map. A restored backup must not reset token spend, consumption, signed head or approved-device generation. No legacy vault clear/reset is allowed.
7. Transition v1→v2 needs authenticated negotiation and a downgrade fence, dual-reading without double delivery, a complete pending-outbox/old-client policy, staged synthetic migration with interrupted-write/restore tests, and a proof that historical v1 graph remains disclosed. New versions cannot retroactively hide old signed rosters or backups.

The submission and retrieval surfaces must reject forged/expired/replayed/cross-audience tokens, wrong group/epoch, stale revocation generations, swapped bodies and duplicate spend. Discovery must resist mailbox enumeration. Limits on token parsing, response sizes, directory entries and expensive verification must be explicit. This is a requirements skeleton, not a cryptographic construction; no custom primitive is specified.

## Blind quota credentials and PIR are separate research

[RFC 9474](https://www.rfc-editor.org/rfc/rfc9474.html) offers a documented RSA blind-signature primitive. Issuance privacy does not define online account quota refunds, scope binding, colluding issuer/router behavior, revocation or one-time token spend. An independently reviewed library and application protocol would be required. A single server may correlate issuance time/volume/IP and subsequent spending even when cryptographic transcripts are unlinkable. No custom blind-signature implementation is added.

[PIR communication/computation research](https://eprint.iacr.org/2019/1483) supports investigating hidden mailbox lookup. It does not hide submission, login, traffic shape or malicious response substitution. Database size/update frequency, mobile CPU/bandwidth, membership checking and admission control need measured bounds before implementation. No performance numbers from other systems are attributed to HAVEN.

Independent mix systems such as [Katzenpost](https://katzenpost.network/docs/) illustrate the need for an explicit network threat model, directory/trust and traffic scheduling. They are not optional HTTP proxies that magically anonymize a single server. Mandatory foreign connectivity or user-run relays violate this deployment's requirements. No cover-traffic loops or compulsory anonymity transport are introduced.

## Promotion gates

Keep this design research-only until independent protocol/security review establishes authentication/order/revocation/epoch/ACK/recovery invariants; audited libraries and a key lifecycle exist; synthetic migration/concurrency/adversarial and real MLS browser tests pass; and same-environment latency, bandwidth, mobile battery, storage and abuse costs are acceptable. Any A6/A7 anonymity claim additionally needs an independently justified anonymity architecture, realistic observer analysis and field evidence. An account-issued alias or a passing unit test is insufficient.
