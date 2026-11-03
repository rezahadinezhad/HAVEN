# Exposure inventory

Field-complete foundation: [existing 191-field inventory](../metadata-privacy/inventory.csv), [flow inventory](../metadata-privacy/flows.md). This supplement records current weaknesses and changes; it does not replace or omit signed copies.

| Source / fields | Class | Purpose / reader / duration | Exposure and other copies | Action / compatibility / residual |
|---|---|---|---|---|
| User UUID, username, password hash, role, security generation | REQUIRED | Authentication, sessions/admin; account lifetime | SQL, sessions, device identity and signed certificates | Pseudonyms allowed; no identity rotation; main server sees account |
| User display_name; localStorage full User | REDUCIBLE | Own UI/admin; formerly indefinite plaintext browser copy | SQL profile and browser storage | Optional name; API admin projection; browser keeps UUID-only unlock pointer; encrypted labels stay in vault |
| Device identity/public key/id/user_id | REPLACEABLE_ONLY_WITH_PROTOCOL_CHANGE | Trust, enrollment, historical signature checks; history lifetime | Signed genesis/rosters/headers and client pins | Scope lookup, preserve exact bytes |
| Device label, challenge, approval relation/signature | REDUCIBLE | Own enrollment evidence | SQL, broad device serializer | Own/enrollment retain proof; peer serializers remove label and enrollment metadata; no signature rewriting |
| Conversation/Membership/MessageEnvelope/CryptoControlEvent | REPLACEABLE_ONLY_WITH_PROTOCOL_CHANGE | Authorization, roster/epoch/order/idempotency; retained history | FKs AND signed JSON, sender refs, welcomes | Design-only closure; no graph-secrecy claim |
| DeliveryCursor, StorageUsage, view-once ledger/tombstones | REQUIRED | Durable sync, quotas, replay/consumption; lifetime or attachment TTL | Device/conversation/account and storage keys | Never remove to manufacture privacy; retirement blocked until finality |
| Invitation/recovery/session/pending enrollment/KeyPackages | REDUCIBLE | One-time signup, auth, recovery, claims | SQL, audit, backups; bounded cleanup, permanent replay digests | Existing locks/rate limits/expiry retained; contact authorization adds no persistent relationship table |
| Contact fragment/name/fingerprint | REDUCIBLE | Explicit sharing, first contact; until cleared | Clipboard/history/sharing apps/same-origin JS | Omit default real name; bounded lookup authorization; URL cleared; no confidentiality from origin |
| Redis user.UUID groups, rate/lease/cache | REDUCIBLE | Ephemeral hints, anti-abuse; 30/120/180s | Raw labels and optional hint bodies | Dedicated HMAC groups; preserve TTL, HTTP fallback; optional activity bodies still identify conversation/device |
| Attachment size/chunks | REDUCIBLE | Quota, integrity, resume; seven days | SQL, cached ciphertext, TLS lengths | Versioned bounded padding; true size inside MLS and AEAD AAD; legacy read supported |
| IndexedDB vault/history/outbox | REQUIRED | Encrypted durable client custody | Coarse account UUID/index/revision metadata remains | No key/ratchet/format reset; locked names unavailable |
| Audit/metrics/logs/backups/WAL/replicas | REDUCIBLE | Incident response, operational recovery | Independent historical and provider copies | Keep seven-day audit and aggregate health; no backup deletion; logical retirement is not physical erasure |
