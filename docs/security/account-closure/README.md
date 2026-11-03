# Account-wide conversation closure and retirement

Status: **ACTIVE_REVIEW_PENDING**, 2026-11-03. Normal application settings enable messaging, mutual closure and automatic server retirement. This replaces the restricted Phase 10 prototype. Independent security review remains pending; no external certification, remote deployment or physical-phone qualification is claimed.

## Product behavior

New direct and group conversations advertise the signed `account-wide-retirement-v2` policy. One approved device already participating in that conversation represents its entire account. Other devices do not need to come online, sign or acknowledge the final head. A direct chat needs both accounts. A group owner/moderator account may propose closure using any of its approved participating devices; every historically affected account, including former members, must prepare and consent. A majority, owner action, silence or timeout cannot substitute for consent.

An account's representative first saves its available history in the encrypted vault and signs preparation. This stops sending across that account's devices. Other accounts can still flush their pending requests until all preparations match the same signed head. Matching preparations freeze the conversation. Each account then explicitly authorizes release of history unavailable on its other devices and submits signed archive consent. Each representative must save the complete mutual final certificate before signing a separate receipt. Only then can the normal worker delete server history, after outstanding delivery notifications, media uploads/leases and applicable security retention settle.

Preparation cannot currently be cancelled or transferred to another device. Withheld consent or changed authorization preserves server history and can leave the conversation paused. This is shown before preparation; the service never deletes to resolve a stalled consent. Resolve known membership/recovery problems before starting. Groups with an unavailable former account remain undeletable through this mutual mechanism.

Former participants access public signed finality proofs through a restricted endpoint and their Recovery kit request inbox. They do not receive ciphertext or keys for epochs after removal. Nonparticipating devices cannot become representatives solely by knowing an account password. Recovery does not silently resume old MLS state.

## What is saved and removed

The encrypted local archive contains available authenticated messages, available ordinary media, drafts, unconfirmed local messages, exact queued wire requests, public proofs and the final certificate. View-once content is excluded. Unavailable files and archive-budget omissions are disclosed before explicit consent. The archive does not claim complete history from every device. Repreparation retains already archived messages/files even if they are later unavailable from the server.

Other devices keep their delivered local history. If an offline device returns after retirement with queued sends, the rejected wire requests and unconfirmed messages become an encrypted read-only local record rather than being retried or reopening the retired conversation. Private speculative MLS provider/ratchet state is never exported into these archives. Archive import is read-only and does not install live keys, trusted pins, cursors or ratchets. Export/import, local file download and explicit local archive removal are available in the Recovery kit.

Server retirement removes the conversation, memberships, ciphertext envelopes, signed control history, delivery cursors, notification rows and encrypted attachment chunks/view records. It preserves accounts/devices and minimal opaque replay exclusions, including attachment tombstones. Permanent replay markers have a separate charged service budget; no participant identifiers are retained in the independent journal. Archives are separately sealed IndexedDB records, so unrelated draft saves reuse their ciphertext rather than re-encrypting large files.

The current live server still sees authenticated routing and active membership. Retirement does not erase older backups, WAL, observations, recipient exports or physical storage traces. A compromised application origin can attack an unlocked browser. Independent journal retention is required to prevent a SQL restore from resurrecting retired history; loss or rollback of all independent copies cannot be cryptographically repaired.

## Boundaries

Per closure: at most 5,000 envelopes, 8 MiB public proofs, 100 historical device memberships, and 2–50 historically affected accounts (direct chats exactly two). Local archives: 64 MiB each, 128 MiB total, at most 256; ordinary file archive data also has a bounded encoded budget. The existing recovery kit has its own size limits. Capacity exhaustion refuses further retirement rather than dropping replay protection. No production throughput or latency SLA is inferred from local tests.

Existing signed `mutual-local-archive-v1` conversations retain their original semantics; the normal worker refuses their old deletion-disabled consent. There is no in-place rewrite of signed genesis. Create a new v2 conversation to use the normal-product policy.

[Operations and restore](operations.md) · [Verification and evidence](verification.md)
