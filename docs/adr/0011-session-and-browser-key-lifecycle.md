# ADR 0011 — Credential-bound sessions and browser key lifecycle

Date: 2026-10-30, Asia/Tehran (test logs also use 2026-10-29 UTC). Status: implemented; local engineering qualification only.

## Findings and corrections

HAVEN uses a custom session table rather than Django's built-in session authentication. Explicit revocation in the normal password-change endpoint did not cover password updates by administrative tooling or concurrent authentication. A successful password verification could also precede a reset, with session issuance occurring afterward. Password changes checked the request's earlier user snapshot, allowing two requests to validate the same old password before serializing their writes. Enrollment completion checked a session challenge without rechecking session revocation inside its transaction.

New sessions store Django's standard `get_session_auth_hash()` HMAC of the stored password representation, keyed with the application secret. It is created once, never rebound by unrelated session updates, never returned by an API, and compared in constant time on every HTTP/WebSocket session resolution. Blank/tampered/stale bindings fail closed. A password change through any database-writing path invalidates previous bindings; the token alone does not remain sufficient. This is server authentication state, not an E2E message key or a replacement for client device proof.

Session issuance locks the account and rechecks active status, credential binding and recovery security generation against the authenticated snapshot. Password changes lock the account before verifying its current password and revoke its sessions atomically. Enrollment completion rechecks its live session, expiry and credential binding under the account/session locks before granting trust. This does not claim atomic cancellation of every possible in-flight request or protection from a compromised application server/database/browser.

At most five not-revoked, unfinished sign-ins (`device=None`) are retained per account when issuing a new session. The oldest unfinished rows are deleted before inserting the new one. Sessions bound to devices are excluded from this eviction, so password possession alone cannot use this quota to evict an established approved-browser session. This cap complements the existing login limits and expiry; it is not a general capacity/DoS qualification.

## Browser behavior

An unlocked, approved browser probes `auth/me` about every 30 seconds during synchronization. A confirmed 401/403 locks the vault, clears the cached local account and asks for a new sign-in. Network failure and server 5xx do not imply revocation; offline access remains subject to local vault protection. A suspended or disconnected browser cannot learn remote revocation immediately. Poll scheduling and the five-minute inactivity deadline use both wall and monotonic elapsed time, preventing a clock rollback or a delayed background timer from extending the deadline. The first input checks expiry before resetting the activity timestamps.

Pagehide locks the vault and terminates its workers; a persisted pageshow locks again when restoring from browser history. Existing lock cleanup releases media sources and clears references. These controls do not guarantee secure erasure of JavaScript/decoder/OS memory, screenshots, downloads, clipboard history, or malicious extensions. No passphrase is persistently unwrapped, no insecure PIN/pattern substitute is added, and the optional device PRF unlock remains available on its qualified hostname path.

## Migration and operations

Migration `0010_credential_bound_sessions` adds the binding and revokes previous sessions with no binding. They are never silently trusted under today's password. Users must sign in once after upgrade; encrypted vaults, existing device IDs/approval, and recovery material are preserved. A migration rollback cannot restore the old sign-ins. Stop old API/outbox/privacy processes, apply with the migration role, then start the new API/workers/web together. The local packaged upgrade exercised the actual migration role and durability checks; runtime-role access to the new column was verified. A disposable ordinary account also completed trusted-TLS login/me against the packaged runtime, then its existing token failed after a direct password update; the account was removed. Application SECRET_KEY rotation also invalidates bindings and requires sign-in; protect the secret as before.

## Evidence and limits

Full PostgreSQL/Redis API suite: **70 passed**, including genuine credential updates without explicit revocation, stale verified login, account disable, concurrent password changes, incomplete sign-in eviction, invalid bindings, migration behavior, live WebSocket invalidation, and in-flight revoked enrollment completion. Chromium **4 passed**: guided approval, full messaging/offline/voice UI, new session/lifecycle/clock tests, and multi-device view-once media. Firefox **3 passed** for approval, new security behavior and view-once media. The browser test preserves the device identity across lock/unlock, simulates both wall-clock advance and rollback with monotonic elapsed time, confirms offline failure retains an unlocked local vault, confirms actual server logout locks it, and observes no vault passphrase in network requests.

Fresh npm/Python/Rust audits report zero known vulnerabilities; the optional Rust maintenance warning remains. TLS/CSP/gates, offline shell lifecycle, production build, TypeScript, lint, schema drift, source hashes and publication guards passed. These tests are local desktop/browser engineering evidence; no physical-mobile, independent security review, fresh container OS scan or infrastructure/capacity certification occurred. Production cryptography remains gated. See TEST_REPORT.md and `docs/evidence/security-pass2-*`.

References: [Django session invalidation](https://docs.djangoproject.com/en/5.2/topics/auth/default/#session-invalidation-on-password-change), [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html). These inform the design; they do not independently verify HAVEN.
