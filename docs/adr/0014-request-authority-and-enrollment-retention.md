# ADR 0014 — Transactional request authority and expired enrollments

Status: implemented for local verification; production release stays blocked.

## Confirmed failures and decision

Real PostgreSQL interleavings reproduced acceptance of an ACK after device revocation, consumption of view-once media after logout-all, and an MLS Add while the target's revocation was committing. Middleware authentication is an early snapshot, not a transaction fence. The Add used actual OpenMLS, outer Ed25519 signatures, one-use KeyPackage claims and the real public verifier. Before-fix outputs are retained; none is a mocked authorization verdict.

Protected HTTP requests refresh their actual cookie session, current account and device after DRF authentication. Mutations first lock the actor's User row. Cross-account administration and MLS controls lock actor and target User rows in ascending UUID order; prechecks establish authority before permitting target locks, and handlers recheck refreshed authority and membership afterward. All affected conversation rows are locked in ascending UUID order before revocation/recovery marks them for rekey. The account fences prevent a concurrently granted membership from escaping that affected-conversation set. Account locks precede object/budget locks. No new token, credential or cryptographic primitive is introduced.

The entire dispatch is transactional. DRF handles exceptions internally, so responses with status >=400 explicitly mark the transaction for rollback. Otherwise a handled ValidationError or generic 503 could commit an earlier write. Tests inject a genuine PostgreSQL divide-by-zero and controlled Redis/unexpected failures; all return generic errors and preserve prior rows. The body is read with a 1400 KiB application cap before acquiring account fences, matching the supplied ingress cap; endpoint serializers/chunk bounds remain tighter.

The mutation's account fence determines its order relative to logout, password changes, recovery, disabling and revocation. A mutation already holding the fence may finish before a waiting revocation; after revocation commits, a waiting stale request refreshes and fails. Reads revalidate before their handler but do not hold an account lock through network delivery. Already-authorized/in-flight reads cannot be recalled. WebSocket per-frame/per-hint validation remains unchanged. This is application authorization correctness, not anonymity against a live operator or compromised runtime.

Public login/redeem/recovery keep their existing proof/challenge/account protocols, within the common transaction/error rollback boundary. Login verifies the unchanged credential/generation under its existing account lock. Authenticated recovery provisioning uses the normal fence. Verified recovery also rejects existing and tombstoned device IDs before updating credentials or trust.

## Enrollment minimization

An expired, still-pending, unrevoked Device has never established trust and cannot be approved/completed after expiry. Retaining its account, label, key, identity, challenge and timestamps indefinitely is unnecessary. Cleanup now locks its account and then its device, rechecks pending/expiry and atomically inserts an ID-only DeviceEnrollmentTombstone before deleting it. A partial expiry/ID index supports bounded selection. It reads only account/device IDs for the cleanup locks.

Approved, revoked and historical devices remain. Unexpected PROTECT references preserve the whole pending row and roll back its marker; aggregate `pending_devices_protected` reports the exception. Each pass considers at most 500 candidates; backlog/failure can delay removal. Never delete reference ledgers or automatically reset a browser identity/vault to make cleanup succeed.

Enrollment and verified recovery both reject marker IDs. A marker has no account FK, key or time but is still a stable pseudonym: external knowledge or historical backups can identify it. Indefinite replay exclusion trades one UUID for the deleted account/key association. No physical erasure or A2/A4 unlinkability is claimed.

Migration 0015 adds the table/index without deleting records. Cleanup performs deletion only with matching code. Reversal refuses before any reverse DDL because dropping markers could reopen previously rejected IDs. Existing deployments must fence all writers, migrate forward with the migration role, and start matching APIs/workers together; an old API does not know the marker guard. Existing browsers receive the same expired-enrollment error as before. No MLS/vault format, ratchet, key identity, API response shape or dependency changes.

## Cost and assurance

Mutations add account locks and a fresh session query; reads add a fresh query. This can serialize same-account traffic and adds real row-lock/WAL/latency costs. Dedicated load evidence reports those costs and any missed targets; no quota, source limit or release gate is relaxed. Pending-record cleanup uses protected deletes, which can query related tables; bounded work is not a constant-time or physical-erasure claim.

Regression coverage includes both orders of mutation/logout, stale read/role rejection, cross-admin revocation, concurrent account revocation across shared groups, actual MLS Add versus target revocation, handled-error rollback, pending approval versus cleanup, replay after cleanup, protected-reference preservation, and real signed recovery refusing old IDs while succeeding with a fresh ID. Dump/restore compares selected invariant bytes before/after forward migration and cleanup. Browser/native/infrastructure results and remaining external gates are recorded separately. This ADR and tests are self-review, not an independent cryptographic audit.


## Scoped enrollment context without the global session counter

The old signing challenge exposed the monotonically increasing Session PK to ordinary authenticated callers. New requests encode a purpose-separated HMAC-SHA256 of account/session/device/fresh nonce as a decimal string in that numeric component. Existing browsers retain their exact anchored v1 grammar, own-device match and public-key check. They sign the exact string and never parse the component as a JavaScript number. No bearer credential, message/MLS format, client identity or new encryption key is introduced. Stable device IDs remain visible; this is not anonymous authentication.

The MAC uses Django's standard salted_hmac with its own purpose label and the existing server secret outside PostgreSQL. A secret rotation already invalidates cookie auth bindings; this adds no durable data decryption dependency. The one-use nonce rotates the handle on each request. A1 already sees internal session rows; the improvement removes unnecessary global ordinal disclosure through the API to ordinary clients.

A compatibility review caught two issues before finalization. A new v2 wire shape failed the browser's strict validator; the final implementation preserves the existing v1 shape rather than relaxing that validator. An unconditional legacy verifier would let a caller test guesses of its global PK using valid own-device signatures. A regression proved this (200 versus required 400). New stored nonces now explicitly use `v2:` plus 64 lower-hex characters. Only actual pre-upgrade raw 64-hex records select the old ordinal verifier. New challenges cannot choose/fall back to legacy verification; unknown stored versions fail closed and require a fresh challenge with the same identity. One-use consumption remains transactional.

Migration 0016 widens the existing nonce column to 67 characters without rewriting nonce contents or adding another identifier column. Its reverse refuses before shortening/truncating an active challenge. Existing raw nonces remain valid for their existing session/device and one use; new responses contain only the scoped decimal handle. API and workers must upgrade together. The schema/wire distinction is explicit: internal challenge encoding v2, existing client-visible v1 signing grammar. Native load preprovisions sessions and excludes enrollment; actual enrollment, legacy proof, guessed-ordinal rejection, copied-nonce cross-session rejection and strict real browser worker-signing checks are separately exercised.
