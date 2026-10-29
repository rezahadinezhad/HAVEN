# HAVEN — Private Emergency Messenger
## Complete Product Requirements, Security Architecture, Delivery Plan, and Codex Execution Contract

**Status:** Build specification / engineering proposal, NOT a certification of security  
**Version:** 1.0 — 23 October 2026  
**Audience:** Codex engineering agent, owner, independent security reviewers, operators  
**Language:** English  
**Working name:** HAVEN (replaceable via deployment configuration; do not hard-code brand)  
**Document priority:** This document governs product scope, design decisions, quality gates, tests, deployment, and Codex reporting.

> **MISSION:** Deliver a usable, self-hosted, domainless, invite-only, browser-based, end-to-end encrypted messenger for a small trusted community. The system must keep working without the international internet when domestic routes and local infrastructure remain available. No native app, third-party messaging service, foreign login, purchased domain, or external runtime dependency is required. Do not substitute a polished mockup for working functionality.
>
> **SAFETY LIMIT:** No web system can transmit messages if every physical/network route fails. A server controlling downloaded browser code cannot provide the same assurance against malicious application updates as an independently verified native client. Do not claim “war-proof”, “unhackable”, or “audited” absent external evidence. Protect real users by making every limitation visible.

---

# A. CODEX OPERATING INSTRUCTIONS — READ FIRST

You are the principal architect, lead full-stack engineer, cryptographic integration engineer, QA engineer, accessibility specialist, and SRE for HAVEN. Execute the project in the current working directory. If the directory contains an existing repository, inspect it and preserve all unrelated work; do not overwrite or delete anything unexpectedly. If it is empty, scaffold a clean monorepo.

**Autonomous execution requirements**

1. Work end-to-end, rather than stopping at a plan. Create source code, migrations, container definitions, scripts, tests, design assets, documentation, and deployment runbooks. Make all reasonable implementation decisions from this specification without repeatedly requesting approval.
2. Start with repository inspection, an architecture decision record (ADR), risk register, and a proof-of-feasibility (PoF) for the E2EE Rust/WASM integration and HTTPS by IP. If a critical technical assumption fails, record reproducible evidence and choose the safest documented alternative; **never silently downgrade to plaintext, homemade cryptography, long-term static-key boxes, or disabled certificate verification.**
3. Implement in vertical slices that actually run: secure bootstrapping → client crypto PoF → accounts → encrypted direct conversations → encrypted group conversations → attachments → resilience → deployment/hardening → tests. Keep the application runnable after each slice.
4. Use tested, actively maintained cryptographic protocol implementations and audited primitives wherever feasible. Build our own client integration, delivery service, UX, and storage; **do not design a novel cipher or novel security protocol**. If a complete audited browser-compatible implementation cannot be integrated, mark the cryptography gate blocked and do not market or deploy a false E2EE release.
5. Freeze dependency versions in lockfiles. Prefer self-hosted packages, static assets, fonts, and built WASM. Do not introduce foreign-domain network calls at runtime, including telemetry, CAPTCHA, CDN, remote analytics, identity providers, push services, package-hosted WASM, or external image optimization.
6. Use strict types, explicit contracts, idempotency, access-control checks, bounded retries, structured error handling, reproducible migrations, and security-focused tests.
7. Produce real screenshots or Playwright test artifacts for mobile and desktop viewport states when UI is implemented. Do not call a screenshot a security test.
8. For environment-dependent steps that require VPS credentials, phone trust-store interaction, real Iranian networks, or a third-party audit, provide scripts and a precise runbook; never fabricate passing results. Use Docker/local test certificates for development and label them NOT production-ready.
9. Before finishing: run unit, integration, browser E2E, crypto vectors, negative security tests, migration checks, production build, linters, type checks, and outage simulations to the extent that the environment permits; publish exact commands and pass/fail/block state.
10. Deliver a fully functioning application for the capabilities whose gates pass. Provide separate `SECURITY_STATUS.md` listing remaining blockers and unverified assurances. Never claim production readiness solely because automated tests pass.

**Definition of “complete”:** Every release-1 feature below is implemented, reachable through the UI or documented API, integrated with persistent storage, covered by tests, and operable from a documented Docker deployment. Placeholders, TODO-only endpoints, demo users with fixed passwords, frontend-only encryption illustrations, unsecured test bypasses, and local-only WebSocket demos are not acceptable.

---

# 1. Context, goal, and boundaries

## 1.1 Problem

During geopolitical conflict, international connectivity may be cut while part of the domestic Iranian network still operates. Friends on different operators and in different cities want to use an independently controlled communications service from a standard browser. The system must not depend on reaching foreign certificate issuers, DNS servers, package CDNs, Apple/Google messaging APIs, external identity providers, or foreign cloud systems during normal messaging.

## 1.2 Primary target

- One trusted private community; design for **5–100 users initially**, with testable capacity for 200 accounts and 500 concurrently connected browser sessions (targets, not measured capabilities).
- Android Chrome, iOS Safari, desktop Chrome/Firefox/Safari; exact supported versions to be discovered and documented from automated/real-device testing.
- Browser-only; users type or bookmark a **publicly routable IPv4 address** (example only: `https://203.0.113.10`, RFC 5737 TEST-NET-3). No purchased domain or external DNS lookup required.
- Iranian data-center hosting, primary and backup in different operator/provider failure domains where feasible.
- All account and chat state lives on operator-owned systems. All message plaintext is encrypted/decrypted in clients, not in backend services.
- Operate during international outage **if** the domestic transport path is available; gracefully warn/retry otherwise.

## 1.3 Explicit non-goals / honesty constraints

- No promise of bypassing a nationwide total telecommunications blackout, physical network destruction, carrier blocking, widespread electrical failure, or comprehensive targeted device compromise.
- No claim of complete anonymity: server and network may observe IP addresses, connection timing, account identifiers, message envelope sizes and relationships as documented.
- No silent forced installation of PWA/home-screen apps or custom browser extensions. A bookmark is sufficient. Optional PWA install is permitted but never required.
- No Signal/Matrix/Telegram/SimpleX messaging server or externally hosted messaging backend. A self-contained cryptographic **library** does not constitute use of a third-party messaging service.
- No requirement for audio/video calls in release 1. Encrypted voice notes and general attachments ARE included. Calls may be a separate rigorously secured future release due to WebRTC/TURN and cross-browser E2EE constraints.
- No custom-designed encryption algorithm or ad-hoc cryptographic handshake.

## 1.4 Measurable high-level requirements

- Domain-free browser navigation via a valid HTTPS IP URL.
- Invite-only activation, no SMS/email/OAuth required.
- E2EE for direct/group texts, attachments, and voice notes; authenticated group/device membership and identity-key change alerts.
- No server possession of E2EE plaintext or unwrapped message keys.
- No foreign network calls during runtime and emergency rebuild from a prepared offline artifact bundle.
- Reconnection, offline drafts, resumable synchronization, at-least-once encrypted envelope delivery with deduplication.
- 2 deployable server endpoints with tested fallback and explicit anti-split-brain procedures.
- Logs cannot accidentally record message plaintext, passwords, recovery phrases, session cookies, or secret keys.

---

# 2. Threat model and adversaries

## 2.1 Defend against

- Passive network observers, packet interception, ISP collection, hostile Wi-Fi.
- Active network attackers attempting man-in-the-middle, downgrade, replay, traffic tampering, TLS interception with invalid certs.
- Stolen PostgreSQL backups, compromised object storage or backups, curious VPS operators, server administrators trying to inspect message ciphertext.
- Credential stuffing, brute-force attempts, invitation leakage, CSRF/XSS, IDOR, WebSocket cross-site hijacking, malicious attachments, resource-exhaustion attacks.
- Replay, duplication, reordering, temporarily offline users, stale group memberships, unexpected key changes.
- Accidental loss of one host, deployments without internet, database recovery, carrier route failure to one server.

## 2.2 Critical residual risks

- **Browser code delivery:** The server supplies JavaScript/WASM; a compromised origin or operator can ship malicious code to collect plaintext/keys. CSP, reproducible builds, release hashes and governance reduce risk but DO NOT eliminate this threat. A native independently pinned client would be required for a stronger guarantee.
- **Endpoint compromise:** Spyware, rooted devices, malicious browser extensions, compromised OS, physical coercion, screenshot/copying can disclose plaintext.
- **Private CA trust scope:** Installing an internal root CA on a device extends trust beyond this site. Root CA compromise can undermine TLS trust for other sites; harden the process and educate users.
- **Metadata:** IP addresses, account connections, message timing/size, recipient routing, conversation membership may be visible to server, host provider, and observers.
- **Traffic disruption:** Domestic carrier filtering and IP blocking can render the service unreachable.
- **User error:** Lost cryptographic key backups cannot be fixed by restoring only the server database. Clients must be told clearly.

## 2.3 Security invariants (automated tests where possible)

- S1: No plaintext message bodies, filenames, voice-note contents, or attachment keys leave sender browser; server storage receives ciphertext only.
- S2: Only cryptographically authorized device members can derive a conversation's current epoch secrets.
- S3: Removing a member rotates encryption epoch; removed members cannot decrypt subsequent messages, subject to completed protocol update and verified correct key state.
- S4: A newly invited member cannot read pre-join history unless another member explicitly and securely re-shares it.
- S5: Peer identity changes, new device enrollments, and verification changes cannot be silently accepted without clear user action/policy.
- S6: Server authorization independently checks every HTTP and WS request; client authorization is merely UX.
- S7: Untrusted/insecure TLS never silently falls back to HTTP or bypassed verification in production.
- S8: Message serialization is versioned, signed/authenticated where applicable, replay-resistant, and rejects unknown critical protocol versions.
- S9: Encrypted message acceptance/acknowledgment uses durable DB commit before successful server ACK.
- S10: No global internet traffic is required by the runtime app, crypto initialization, login, connection, file exchange or synchronization.
- S11: Every breaking crypto/storage migration is versioned, reversible when possible, and non-destructive unless specifically approved.
- S12: All secret logs, plaintext leakage, cross-user object reads and forged membership changes are release-blocking defects.

---

# 3. Product requirements — release 1

## 3.1 Onboarding and accounts

- Initial super-admin created via idempotent noninteractive CLI: `manage.py bootstrap_admin` with securely supplied secret through stdin/secret file; never ship a known password.
- Admin creates single-use, cryptographically random, short-lived invitation tokens. UI can display an invitation QR URL (HTTPS raw IP) and separately confirm out-of-band identity with intended recipient.
- Registration: display name, immutable internal user ID, username, strong password and a distinct **cryptographic unlock secret/recovery kit**; no email/phone required.
- Password hashing: Argon2id, tuned and documented, with rate limits and session revocation. Avoid password in localStorage.
- Sessions: opaque server-side identifiers in Secure/HttpOnly/SameSite cookies, with CSRF protection; device sessions can be revoked. Require strong Origin checks for WebSockets and CSRF-sensitive POSTs.
- Role separation: `superadmin`, `community_admin`, `member` (admin does not receive E2EE keys automatically). Permissions enforce per-resource access.
- Admin dashboard: invitations, user activation, deactivation, device list (public IDs only), rate limits, server health, storage capacity, certificate expiry, signed release manifest, backup/failover status. **No decrypted message browsing.**
- Credentials/account deletion: log out all sessions, disable account, remove member cryptographically from groups via authorized operations, document limitations of removing cached plaintext from other devices.

## 3.2 Devices and trust

- At least one trusted device per account; release 1 includes multi-device with explicit device enrollment and cryptographic approval from an existing device, with a documented recovery path if all are lost.
- Each device has its own identity/MLS credentials; keys generated client-side using secure entropy.
- Provide QR/fingerprint verification of peer identity, device list, last verified change, and conspicuous key change warning.
- A new device MUST NOT silently inherit history. Existing device may opt to send a fresh, encrypted history export after a successful verification flow; otherwise new device starts with new sessions/epochs.
- Device revocation triggers removal/rekey of relevant MLS groups. No silently trusted replacement devices.
- When no previously trusted device exists, account recovery requires pre-provisioned, high-entropy recovery material AND explicit security state reset; peer identity warnings are mandatory.

## 3.3 Conversation and messaging

- One-to-one chats, small private groups (2–50 human participants initial target), multi-device participant support.
- Group creator, member and optional moderator permissions; add/remove/leave, safe membership transitions, group icon/name metadata privacy tradeoffs documented.
- Rich interface: conversation list, encrypted text messages, timestamps, delivery states, unread counts, reply-to, reactions (encrypted event), edit/delete as new authenticated events (not physically guaranteed deletion on peers), typing indicators (ephemeral metadata, opt-out), online indicators (off by default), read receipts (opt-in and documented metadata leakage).
- Message send supports offline drafts, queue/retry and optimistic client UI. Show explicit states `local_only`, `encrypting`, `queued`, `server_accepted`, `recipient_synced`, `failed`, never falsely report actual reading.
- Reliable reconnect: WS heartbeat/backoff/jitter; HTTP delta sync cursor as fallback. Hard server shutdown during send must not create duplicate user-visible messages.
- Search: client-side only over locally available decrypted items; server cannot search encrypted message text.
- Privacy-friendly notifications only while an active tab is reachable. Do not require Apple/Google push; no promise of background wakeups on iOS.
- Accessibility: keyboard-first desktop, RTL-capable layout (Persian and English), reduced motion, sufficient contrast, appropriate labels and focus handling.
- UI language: English and Persian via bundled local translations. Full RTL support for Persian and mixed RTL/LTR chat content.

## 3.4 Attachments and voice notes

- Encrypt each file/voice note in sender browser before upload. No raw filename or preview stored on server by default.
- Content-addressable? Avoid deduplicating across users based on plaintext. Server receives opaque encrypted blob IDs and encrypted metadata.
- Chunked encryption and resumable upload/download with per-chunk integrity verification, configured maximum 25 MiB per file initially (admin adjustable only within safe operational limits), progress UI and user cancellation.
- Generate random file key per attachment with audited AEAD (e.g. XChaCha20-Poly1305 through libsodium); deliver random key and encrypted file metadata inside authenticated MLS application messages. **Design nonce uniqueness and AAD carefully; do not reuse a nonce under the same key.**
- Voice notes: record in browser with clear user permission, encrypt before upload, play after decryption client-side, graceful unsupported-browser state.
- No server-side thumbnailing, audio transcoding, antivirus decryption, or plaintext preview. Server enforces MIME/size/quota heuristics based on untrusted metadata, and browser warns about opened attachments.

## 3.5 Offline UX

- Cache static app shell, JS/WASM, fonts and translations locally via service worker ONLY after a trusted initial HTTPS load. Show cached conversation history if device is unlocked and browser storage persists.
- Keep encrypted pending outbox and message cursor in IndexedDB, with crash-safe transaction handling and bounded storage. Do not persist decrypted messages unnecessarily.
- Retry only on recovered trusted connection. Never send over HTTP when HTTPS fails.
- Warn that browser profile clearing, private browsing, storage eviction, OS reinstall and device loss may permanently remove local keys.
- PWA/home-screen support may be added as an optional convenience; zero-install is mandatory for baseline communication.

## 3.6 Operator console

- Health, queues, connection counts, message envelope rates, error budgets, storage usage, estimated backup recency, certificate status, failover state and configured endpoints.
- Warn if primary certificate validity falls below configured grace days; warn if any dependency attempts nonlocal runtime requests.
- Admin may suspend compromised devices/users, pause invitation creation, schedule service maintenance; admin cannot impersonate users or decrypt content.
- Maintenance banner controlled locally; status page independent from JS hydration as feasible.

---

# 4. System architecture and repository

## 4.1 Proposed components

- **Frontend:** Next.js (TypeScript, App Router) as client UI with localized routes and responsive design. Client-only E2EE engine executes in Worker/WASM and never server-rendered. Strict hydration isolation for secrets. Tailwind CSS and accessible UI components bundled locally.
- **Backend:** Python 3.13 or supported stable Python version verified at build, Django + DRF, ASGI, Django Channels. Use existing stable versions pinned at project creation; do not blindly trust version numbers from this document.
- **State:** PostgreSQL durable persistence; Redis for ephemeral channel layer, rate limits and coordination; never make Redis the only source of message durability.
- **Crypto:** Prefer OpenMLS (RFC 9420) compiled as a local Rust/WASM module with a narrow TypeScript facade, after PoF demonstrates required browser, persistence and interop behavior. Use a mature cryptographic provider and published test vectors. libsodium.js for attachment AEAD and local encrypted storage only when implementation choices are justified and tested.
- **Ingress:** Nginx reverse proxy, HTTPS by IP, WebSocket upgrade, strict CSP/headers and IP-based origin allowlist.
- **Deploy:** Docker Compose with isolated networks, health checks, nonroot services, reproducible local images. Optional signed images/offline registry export.
- **Ops:** self-hosted minimal metrics with no plaintext; self-contained backups and restore/failover scripts.

## 4.2 Monorepo layout

```text
haven/
  apps/
    web/                       # Next.js app / localization / UI / browser tests
    api/                       # Django project and domain apps
  packages/
    contracts/                 # OpenAPI, typed websocket envelope and version schemas
    crypto-core/               # Rust/OpenMLS adapter -> browser WASM
    crypto-client/             # TypeScript facade, IndexedDB vault, validation
    shared-ui/                 # UI components, icons and bundled fonts
  infrastructure/
    compose/                   # local, staging, production Compose
    nginx/                     # IP-hosted TLS proxy
    pki/                       # tooling, NEVER include private keys in repo
    backups/                   # encryption + tested restore scripts
    failover/                  # checked endpoint switch + fencing
    diagnostics/               # domestic-only network tests
  docs/
    adr/
    api/
    threat-model/
    security/
    operation/
    runbooks/
    user-onboarding/
  tests/
    integration/
    security/
    disaster/
    performance/
  .github/workflows/          # optional CI, offline local scripts must also work
  .env.example
  Makefile
  README.md
  SECURITY_STATUS.md
  IMPLEMENTATION_STATUS.md
  RELEASE_CHECKLIST.md
```

## 4.3 Runtime topology

```text
Mobile Safari / Chrome / Desktop browsers
     | HTTPS/WSS to primary or backup raw IP
     v
Domestic routing (availability must be tested per ISP)
     |
     +---- Primary Iranian host ------------------------+
     |       Nginx -> Next.js static UI/SSR + DRF/ASGI  |
     |                      |                           |
     |             PostgreSQL + Redis                   |
     |             Encrypted object storage             |
     +---- Standby host (different network/provider) ---+
             Nginx + preloaded images + standby DB
             Independent TLS certificate for backup IP
             Controlled promotion / split-brain fencing

Crypto keys & plaintext: inside clients only.
Server data: public key packages, ciphertext, queues, access metadata.
```

Two hosts do not guarantee independent routing; document dependencies and verify. Start with **active-passive, manual or explicitly fenced failover** rather than dangerous auto-failover without quorum.

---

# 5. Cryptographic architecture — NON-NEGOTIABLE

## 5.1 Protocol decision and mandatory proof of feasibility

Use **IETF MLS (RFC 9420)** for BOTH 1:1 and group conversations as the primary design. A 1:1 chat is an MLS group of two device members (more device members for multiple devices). OpenMLS in Rust is a credible implementation candidate and can target WASM. Its `js` feature assumes browser-provided secure randomness and time. **This does not mean its end-to-end wrapper is already proven suitable for our product.**

Before implementing the product, create a PoF demonstrating, in real browser-compatible code:

1. Initialize two independent device credentials and serialize key packages.
2. Create an MLS group, publish a key package, add a second device, transmit Welcome/Commit and successfully decrypt authenticated application data.
3. Persist protocol state in IndexedDB, reload browser and resume secure messaging.
4. Send messages in both directions, out of order, through disconnected/reconnected simulated delivery.
5. Add and remove a third device, rekey, and prove removed device cannot decrypt *future epoch* messages.
6. Tamper with ciphertext/commit/credential and prove rejection; test rollback, replay, duplicate and stale epoch behavior.
7. Test in mobile Chromium and iOS Safari (real Safari if possible; otherwise explicitly blocked).
8. Document crypto dependency versions, licenses, audit status, known issues, protocol suite, key lifetimes, cipher suites, limitations and test vector sources.

If OpenMLS browser integration is infeasible, evaluate an actively maintained, browser-ready audited MLS implementation or documented Matrix Rust WASM crypto engine **as a library only**; do not deploy a Matrix messaging server. A replacement requires an ADR and the SAME PoF. Do NOT fall back to unratcheted sealed-box encryption or simply `AES-GCM(public key)` while labeling it Signal/MLS-grade E2EE. If no candidate passes, leave service in explicitly marked `CRYPTO_NOT_READY` non-production mode, and still complete backend/UI/test scaffolding safely.

## 5.2 Authentication and device identity

- Device identity bound cryptographically to account and invitation enrollment, with a locally generated signing key and explicit user verification.
- Server publishes device credentials/key packages but is NOT itself automatically authoritative for peer key trust. Avoid relying exclusively on server-provided identity without a verification mechanism.
- Display short authentication string and QR fingerprint for comparing people/devices through an independent channel (in person where possible).
- Do not silently replace existing trusted identity keys. Show safety-number changes and prevent auto-trust for sensitive conversations.
- Key-package consumption must be unique, replay checked, and bounded; stale/reused packages rejected unless expressly permitted by protocol and documented.
- Device removal produces authenticated MLS state transitions, applies membership access controls, and sends notifications to other verified members.

## 5.3 State and key storage

- MLS state persisted client-side in IndexedDB as encrypted-at-rest serialized state; encrypt vault with a locally derived key from user-provided **strong unlock passphrase** or validated high-entropy recovery key, not with a static app constant, session cookie, or server-held secret.
- Evaluate Argon2id mobile memory/performance parameters using real-device benchmarks; prevent UI freezes by performing expensive KDF operations in Workers. Never log or transmit unlock material.
- For convenience, optionally retain unwrapped keys **only in memory** for the current unlocked tab/session; auto-lock on explicit logout/timeout, and never include secrets in Next.js server actions, SSR, telemetry, localStorage or nonencrypted Cache Storage.
- Successful server password reset MUST NOT decrypt old E2EE state by itself. A device reset without recovery kit loses old history.
- Backups of local E2EE state must be authenticated and encrypted with a high-entropy recovery key; user downloads, stores safely, and test restores. Never secretly upload plaintext key vault to server.
- Avoid accidental leakage through source maps, exceptions, browser console, and server logs.

## 5.4 MLS delivery and authentication service

- Backend is an MLS **Delivery Service**, not a decryption participant. It stores and routes opaque signed/AEAD-protected protocol messages, key packages, MLS Welcome and Commit envelopes.
- Implement application-side validation of credentials mapped to approved devices, group membership, epoch/commit sequencing, and membership authorization. Document what is guaranteed by the library vs what the app enforces.
- Use explicit, bounded strategy for concurrent commits, out-of-order commits, replayed envelopes, reordered messages, and offline members. Never overwrite cryptographic state on unresolved conflict; surface a recoverable state/error.
- Membership changes must be signed/authenticated by permitted group participants; server cannot fabricate a join without clients detecting the identity change assuming honest client code.
- Provide rekey triggers after device loss, compromised identity, membership change, periodic security intervals (set conservative values after performance tests).
- Group titles/icons may be encrypted in MLS application data; any server-visible metadata must be documented precisely.

## 5.5 Attachment crypto

- Browser generates independent random content key; uses authenticated chunk encryption. Encrypt file metadata (name, MIME, optional media dimensions) before transmission; unencrypted upload metadata minimized.
- Use XChaCha20-Poly1305 if libsodium.js integration passes supported browser tests, with cryptographically random nonces / proven unique nonce derivation for every chunk; authenticate file ID, chunk index, total chunks, protocol version, and conversation scope via AAD.
- Transfer the file key only as part of an authenticated MLS encrypted message, never URL query params or unprotected JSON.
- Bound chunks and upload limits. Verify ciphertext chunk hashes and AEAD tags before exposing downloads to user. Partial corrupted chunks are rejected.
- Scan attachment payload only on device or with user consent after decryption; never add server-side decryption as a convenience.

## 5.6 Crypto test requirements

- Official RFC 9420 and chosen library test vectors; golden cross-device compatibility vectors.
- Tamper, replay, downgrade, stale key packages, duplicate Welcome, out-of-order Commit, rollback, split group history, offline member and multi-device state cases.
- Property-based tests for serialization, key isolation, nonce reuse prevention and event ordering.
- Browser crash between `encrypt`, persistence and acknowledgment; state consistency under retries.
- Test invalid Unicode, large attachments, corrupt storage, revoked device, compromised database and unauthorized admin.
- Review key erasure limitations in JS/WASM and explicitly describe browser garbage collection constraints.
- Do not conclude audit-level security from test passing; an external specialized cryptographic review is a release condition for high-risk deployment.

---

# 6. TLS, certificates and IP-based hosting

## 6.1 Two supported trust profiles

**Profile PUBLIC_IP_TLS (frictionless browser login):**

- Obtain a certificate from a publicly trusted CA that supports `iPAddress` Subject Alternative Names for the server's real public IP; verify CA validation/contract constraints before adopting. Don't invent a provider or assume certificate lifetime equals CA/Browser Forum maximum.
- As of October 2026 the publicly trusted maximum is 200 days, reducing to 100 days on 15 March 2027; **Let's Encrypt IP certificates specifically are currently 160 hours**. Do not plan around a hypothetical long Let's Encrypt IP certificate.
- Have automated local alerts and documented pre-emergency renewal, failover certificates and tested expiry drills. This profile eventually fails if renewals need unreachable outside services.

**Profile EMERGENCY_PRIVATE_PKI (prepared trusted devices):**

- Generate offline root CA using offline workstation/HSM-like controls if available. Do not store root private key on VPS, git or CI. Issue a short-lived intermediate and server leaf certificates with `iPAddress` SANs for each actual IP, Extended Key Usage `serverAuth`, proper key usage, sensible lifecycle, and explicit validity policy.
- Document separate server/intermediate renewal, CRL/revocation limitations while isolated, revocation procedures, offline clock/time validity, key compromise consequences and protected intermediate signing material.
- Friends must **manually install AND trust** the private root certificate before an outage. iOS requires explicit full-trust action for manually installed profiles. Android/browser trust behavior must be demonstrated on supported devices. Root installation is a one-time OS configuration, not an app installation; explain that it increases trust risk beyond this website.
- Export signed/checksummed public root onboarding instructions over a safe out-of-band channel. Never have users click through an unknown certificate warning or install an unverified CA sent by a stranger.
- Never implement automatic insecure `http://` fallback, ignore-certificate-errors flags, localhost loopholes, unsigned root downloads, or javascript-level TLS validation overrides.

## 6.2 Web origin and transport security

- Origin uses literal `https://<public-IP>` (or `https://<public-IP>:<port>` when needed). Do not require DNS, reverse DNS, IP-to-host redirection, HSTS preload, public DNS-based challenge or a purchased domain.
- Keep Nginx certificate SAN aligned with each IP used. Test Safari, Chrome and Firefox with actual IP certificate validation; SNI by IP and intermediate chain behavior can differ.
- All WSS endpoints use same trusted HTTPS origin wherever possible. Strict TLS configuration; redirect HTTP only when HTTPS is independently valid; never use HTTP for password submission.
- Restrict Host/Origin, allowed hosts, CSRF trusted origins and WebSocket allowed origins to configured IP endpoints. Do not use wildcard allowances in production.
- `Content-Security-Policy` (no unsafe-eval/inline scripts unless narrowly justified with nonces/hashes), secure cookie options, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, clickjacking defenses, no external assets.
- Maintain emergency certificate runbook with exact validation commands using actual certificates, not example placeholders in prod.

## 6.3 IP address and failover

- Need routable host IP; not necessary to **purchase** a dedicated IP separately if hosting includes a suitable stable reachable address. A server reachable only behind CGNAT cannot serve unrelated domestic clients directly without a reachable relay.
- Save primary and standby URLs for users via printed QR, bookmark or pre-shared emergency card. Each IP requires a valid cert and client trust.
- Never assert one IP is accessible across Iranian carriers without tests. The operator can replace endpoints only through a verified/signed update or manually trusted printed card; do not silently trust an unauthenticated fallback origin.

---

# 7. Backend domain model and storage contracts

Implement Django models with UUIDv7 where supported and safely generated identifiers otherwise. Use PostgreSQL migrations, immutable event history where appropriate, explicit foreign-key constraints, unique indexes, pagination indexes, and retention/cleanup policies. Below is a logical schema, not permission to omit fields needed by audited library serialization.

| Entity | Minimum fields / purpose | Security/consistency rules |
|---|---|---|
| `User` | ID, unique username, display_name, password_hash, status, role, timestamps | No automatic access to conversation secrets for admin |
| `Invitation` | token_hash, intended_username?, creator, expires_at, max_uses=1, consumed_at, revoked_at | Never persist invitation token plaintext; throttle redeem |
| `Device` | ID, user, label, identity_credential_bytes, signing/public key metadata, trust_state, created_at, revoked_at | Enrollment must be verified and signed according to crypto flow |
| `DeviceKeyPackage` | ID, device, package_bytes, cipher_suite, version, expiry, consumed_at | Atomic one-time use / replenish; protocol validation |
| `Session` | opaque token hash, user, device, expires_at, last_seen, revoked_at | HttpOnly cookie, rotate on auth, revocable |
| `Conversation` | ID, kind [direct/group], creator, created_at, status, opaque group_id, protocol_version | No plaintext messages/name in this table |
| `Membership` | conversation, user, device, role, valid_from_epoch, removed_at_epoch, status | Indexed for lookup; authorization reconciled against authenticated MLS commits |
| `CryptoControlEvent` | ID, conversation, epoch, server_order, control_type, ciphertext_or_protocol_bytes, hash | Store Welcome/Commit/Proposal with ordering, verify legitimacy and avoid rollback |
| `MessageEnvelope` | ID, conversation, sender_device, protocol_version, server_seq, client_message_id, group_epoch, ciphertext_bytes, received_at, expires_at? | Unique(sender_device, client_message_id); committed before ACK; no message body |
| `DeliveryCursor` | device, conversation, last_acked_seq, updated_at | Device-level independent cursors |
| `DeliveryReceipt` | envelope, device, state, updated_at | Do not claim human read state from mere delivery |
| `EncryptedAttachment` | ID, uploader_device, conversation, encrypted_metadata_ref, ciphertext_size, status, created_at, expires_at, opaque_locator | No raw filename or decryption keys; quotas, TTL, checksums |
| `AttachmentChunk` | attachment, chunk_index, content_hash, byte_length, stored_at | Unique(attachment,chunk_index), reject inconsistent replay |
| `AuditEvent` | ID, actor, category, target_opaque_id, timestamp, redacted_payload | Security/admin actions only; never message plaintext/keys |
| `BootstrapEndpoint` | endpoint IP/port, TLS profile, priority, health status, last_validated | Treat published endpoint lists as security-sensitive |
| `SoftwareRelease` | version, manifest_hash, build_timestamp, signing_public_key_ref, status | Integrity evidence; browser-client trust limitation documented |
| `BackupManifest` | backup ID, encrypted checksum, created_at, storage location, tested_restore_at | No secret material logged |

**DB design constraints:**

- Distinguish `server_seq` (monotonic ordering per conversation) from `client_message_id` (stable idempotency identifier). Don't rely on timestamps for ordering.
- Store ciphertext in PostgreSQL for small messages; encrypted files in self-hosted object storage/filesystem with database metadata. Restrict file access through server authorization, not direct unprotected static URLs.
- Use transactional outbox when publishing WS notifications after database writes, or demonstrate equivalent durability using a documented pattern. Redis fan-out must not be the durability boundary.
- Never delete unread ciphertext before retention policy / user decision unless capacity/security settings require. Preserve replay of necessary MLS control events while clients are offline.
- Concurrent receipt updates use database constraints/upserts; no duplicates or lost acknowledgments under reconnect.
- Record expiration/deletion limitations in UI and API docs; deleting from server does not force deletion from recipient device storage.

---

# 8. HTTP and WebSocket API contracts

Provide machine-readable OpenAPI 3.1 and generated TypeScript client/types. All URLs are relative to same IP origin (e.g. `/api/v1`). Authentication required except minimal health and invitation redemption endpoints. Version all crypto envelopes.

## 8.1 Authentication, admin and devices

```http
POST   /api/v1/invitations/redeem
POST   /api/v1/auth/login
POST   /api/v1/auth/logout
POST   /api/v1/auth/logout-all
GET    /api/v1/auth/me
POST   /api/v1/auth/change-password
POST   /api/v1/devices/enrollment/request
POST   /api/v1/devices/enrollment/approve
POST   /api/v1/devices/enrollment/complete
GET    /api/v1/devices
POST   /api/v1/devices/{device_id}/revoke
GET    /api/v1/admin/invitations
POST   /api/v1/admin/invitations
POST   /api/v1/admin/invitations/{id}/revoke
GET    /api/v1/admin/users
PATCH  /api/v1/admin/users/{id}
GET    /api/v1/admin/system-status
```

## 8.2 Crypto key packages and conversations

```http
POST   /api/v1/crypto/key-packages       # Upload validated public MLS key package(s)
GET    /api/v1/crypto/key-packages/{device_id}  # Atomic claim/retrieve semantics
GET    /api/v1/crypto/devices/{user_id} # Approved device credentials and trust changes
POST   /api/v1/conversations
GET    /api/v1/conversations
GET    /api/v1/conversations/{id}
POST   /api/v1/conversations/{id}/members/propose
POST   /api/v1/conversations/{id}/crypto-events
GET    /api/v1/conversations/{id}/crypto-events?after=...
POST   /api/v1/conversations/{id}/messages
GET    /api/v1/conversations/{id}/messages?after_seq=...&limit=...
POST   /api/v1/conversations/{id}/acks
GET    /api/v1/sync?cursor=...
```

**Important:** `members/propose` is a coordination/permission endpoint, **not** authority to bypass authenticated MLS Add/Remove/Commit processing. The backend cannot force a cryptographic membership change without a valid client action. Authenticated sender/membership checks are required before accepting any control event.

## 8.3 Attachments

```http
POST   /api/v1/attachments/init
PUT    /api/v1/attachments/{id}/chunks/{chunk_index}
GET    /api/v1/attachments/{id}/chunks/{chunk_index}
POST   /api/v1/attachments/{id}/complete
DELETE /api/v1/attachments/{id}
```

- Upload/download permissions derive from conversation membership at relevant epochs and policy, documented for removed members.
- Reject oversize chunks before allocation; cap parallel uploads/downloads; use quotas per user/group. Integrity and content authenticity are checked client-side.
- Use unguessable identifiers and authenticated requests, no indefinite public pre-signed links.

## 8.4 Real-time transport

Single endpoint `wss://<ip>/ws/v1` (same origin, session-cookie auth, strict Origin check). Server sends no message plaintext. Required envelope classes:

```json
{
  "v": 1,
  "kind": "message.available",
  "conversation_id": "uuid",
  "server_seq": 125,
  "event_id": "uuid",
  "occurred_at": "2026-10-23T10:00:00Z"
}
```

Also define `hello`, `resume`, `sync.required`, `control.available`, `receipt.updated`, `ephemeral.typing`, `heartbeat`, `server.maintenance`, `error` using JSON Schema/Zod validation mirrored in Python. For high privacy, message notification need only signal that synchronization is available; fetch the ciphertext over authorized API.

**Delivery handshake**

1. Client locally prepares MLS ciphertext and stores deterministic pending message ID/outbox transaction.
2. Client posts ciphertext and idempotency ID; server validates authorization and commits envelope under `server_seq`.
3. Server replies `server_accepted` only after durable commit; transactional outbox triggers notifications.
4. Recipient resumes from last durable cursor, receives envelope/control events in causal/MLS-compatible order, decrypts locally and persists state atomically before ACK.
5. If an ACK or response is lost, retries use idempotency keys; server returns original message ID/sequence. If crypto state is stale, client pauses and synchronizes control events before decrypting.
6. A crashed client can restart without double-encrypting ratchet events or losing serialized state; build explicit transaction/recovery strategy for crypto state and pending envelopes.

**Performance and safety:** request timeouts, maximum frame sizes, per-IP and per-account rate limits, Nginx connection limits, constant upper bounds for unverified inputs, bounded WS outbound queues, slow-consumer handling, backpressure, and resilient reconnect. Do not trust client-provided sender IDs over authenticated session identity.

---

# 9. Authentication, authorization and application security

- Align application security requirements with **OWASP ASVS 5.0.0**, prioritizing authentication/session, access-control, input validation, cryptography, API, files, configuration and logging requirements (document a traceability matrix). Never falsely claim formal ASVS certification.
- Allowlist exact public IP Host/Origin combinations. Restrict WS to authenticated cookie session, strong Origin validation and per-conversation authorization. Reject cross-origin API requests unless specifically documented.
- Use Django's CSRF protections; all state-changing operations require CSRF/session checks. Cookie Secure, HttpOnly and SameSite=Strict (or documented narrow exception), rotate session at login and privilege changes; revoke sessions after device changes.
- Encrypt TLS in transit regardless of E2EE. Rate-limit invitation redemption, login, admin actions, device enrollment, message write and key-package upload.
- Explicit schema validation and untrusted-string treatment; React rendering must not allow arbitrary HTML or unsafe markdown injection. No `dangerouslySetInnerHTML` for chat messages. Sanitize any rich text using an approved policy before display; simpler release 1 may render plain text with line breaks only.
- Prevent IDOR by querying objects through user/device authorized scopes; test every endpoint with unrelated identities.
- Apply least-privilege DB roles, restricted object store paths, per-service Docker networks, minimized exposed ports, read-only file systems where feasible, nonroot containers, secrets via protected files/env injected outside git.
- Secure admin: strong passwords, optional second factor only if it does not create foreign dependencies; emergency recovery procedure must include revoke/rekey of compromised admin.
- No public contact discovery, phone number hashing, scraping endpoints, advertisement profiles, telemetry or tracking pixels.
- Audit only security control-plane events; redact addresses where operationally feasible and provide retention limits. Never include conversation content in exception traces.

---

# 10. Client UX / interaction specification

## 10.1 Visual direction

- Mobile-first, very low cognitive load, high contrast, clean typography and accessible controls. Dark and light themes; dark default optional. No excessive animation or heavyweight 3D assets.
- Locally bundled fonts and icons; system-font fallback works offline. Keep frontend payload small and cacheable for slow networks.
- Responsive layouts: 320px small phone, 375/390/430 phones, 768 tablets, 1024–1440 desktop. Confirm notches and iOS safe-area handling.
- Fully support Persian RTL, Arabic-script text, English messages, mixed direction, bidirectional timestamps and Unicode filenames. Translations provided locally.

## 10.2 Required screens

1. Connection status / server selection and TLS trust guidance (never offer click-through insecure option).
2. Invite redemption and account creation.
3. Login, session unlock and local encrypted vault unlock.
4. Conversation list + secure search of local decrypted content only.
5. 1:1 chat with composer, reaction, reply, editable authenticated event, message status, file/voice attachment.
6. Group create/rename, member list, secure member add/remove/leave and rekey status.
7. Contacts, identity fingerprint/verification QR, changed-identity warnings.
8. Device management, enrollment approval and revoke flow.
9. Encrypted key backup/download, restore, recovery help, and **irreversible key loss warning**.
10. Settings: theme, language, notification behavior, read receipts, local data/export and logout.
11. Admin console: invitations, accounts, health, cert status, backup/failover status, not plaintext chats.
12. Offline/reconnect indicator, outbox conflicts, expired/invalid certificate states, emergency help.

## 10.3 UX detail and truthfulness

- Show `Not connected`, `Reconnecting`, `Connected to primary`, `Connected to standby`, `Crypto verification needed`, `Key state locked`, `Certificate invalid`, and `Messages pending` as distinct conditions.
- Never show a green “secure” badge merely because TLS or JS loaded; security UI must represent *actual verified identity/session state* and explain residual risks.
- Prominent warnings before deleting browser data, resetting device, changing crypto identity, adding unexpected device, receiving new peer key, or bypassing enrollment recommendations.
- Message ordering uses server sequence but rendered timestamps are informational; handle timezone drift/incorrect local clocks.
- Keyboard shortcuts optional; screen reader focus management required.

---

# 11. Offline-first reliability, backup, disaster recovery

## 11.1 Expected degraded behavior

| Event | Required user/system behavior |
|---|---|
| International internet lost | Existing raw-IP trust mode, self-hosted assets/login/chat still work if domestic routes exist |
| Primary IP unreachable | Show primary failure, let client reach preconfigured independently trusted backup IP without silent identity downgrade |
| Browser disconnected | Queue encrypted outbox, backoff/retry, never mark queued as delivered |
| Server restart | Restore durable state, re-sync missed messages and control events, no duplicates |
| Redis restarted | Rebuild realtime state from PostgreSQL, resubscribe and sync missed messages |
| PostgreSQL temporarily unavailable | Fail closed on message acknowledgment, return retryable error, no false success |
| Certificate expires | Browser blocks server; show out-of-band recovery instructions; **never ignore warning** |
| User loses browser storage | Restore encrypted local backup if available; otherwise new identity/rekey and loss of inaccessible history |
| Group member is removed offline | Reject subsequent encrypted sends from unauthorized old epochs per protocol policy; sync/rekey when reconnecting |
| Network is fully absent | Locally cached UI/history may work; remote message delivery cannot happen |

## 11.2 Redundancy and failover

- First deploy can run on one host for development but do not label it redundant. Production design uses primary/standby hosts in different provider/failure domains.
- Replicate encrypted server databases/object storage using authenticated encrypted transport over reachable domestic routes. All replicas receive ciphertext/metadata only.
- Prefer active-passive database with explicit promotion and **fencing** to avoid two primaries assigning conflicting sequences or accepting mutually divergent membership changes. Document data consistency and permitted RPO under async replication.
- Suggested acceptance objectives (**targets, not promises**): recover API within 30 minutes after controlled primary failure; no acknowledged-message loss under synchronous-ack design or expose/document any async failover RPO; backup restores demonstrated from isolated host. If these cannot be met, state actual measured bounds.
- Client always preserves pending ciphertext/idempotency IDs and replays safely after endpoint switch. MLS cryptographic state and server event ordering must be tested across controlled failover.
- Backups encrypted at rest, offline copy, least-privilege access, rotation/retention, regular integrity checks and restore drills; maintain secrets separately from ciphertext backups.

## 11.3 Offline deployment supply-chain preparedness

- Pin exact Docker images and package versions; support exporting prebuilt deployment artifacts and OCI images onto encrypted removable media ahead of outage. Include `scripts/build-offline-bundle.sh` and `scripts/deploy-offline-bundle.sh`.
- Do not assume `apt`, `npm`, `pip`, `cargo`, GitHub, package registries or Docker Hub remain reachable during a shutdown. Build before emergency or host verified internal mirrors and signed artifacts.
- Provide `.env.example` and secret-creation scripts; never embed production root CA or signing keys in builds/artifacts.
- Provide a safe upgrade/rollback procedure for migrations, cryptographic protocol versions, frontend release hashes, and state schema.
- Enforce reproducible builds where feasible and cryptographic hashing/signing of offline bundles; verify manifests before install.

## 11.4 Observability and privacy

- Metrics: request latency distribution, endpoint status, ASGI websocket connections, success/retry rate, outbox delay, backlog, DB replication lag, disk, CPU/memory, queue depth, certificate expiry and backup age.
- Minimal logs with randomized correlation IDs, never message bodies or keys; remove sensitive query params and limit IP retention.
- Local operator dashboards only; no cloud telemetry.

---

# 12. Deployment and operational runbooks

Create actual deployable Compose config and scripts. Required commands and paths may differ after implementation but must be documented and tested.

**Operator lifecycle**

```bash
make doctor                 # Validate dependencies, env and host risks
make dev                    # Bring up local trusted dev stack
make test                   # Full locally executable suite
make security-test          # Negative auth/transport/crypto tests
make production-build       # Reproducible release images + frontend manifest
make offline-bundle         # Export all runtime images/assets/deployment configs
make deploy-staging         # Deploy safe staging stack
make pki-create-offline-root # Deliberate manual offline-only procedure
make pki-issue-ip-leaf      # IP SAN signing via properly controlled issuer
make certificate-check      # Cert SAN/trust/expiration validation
make backup                 # Encrypted server backup + manifest
make restore-check          # Perform isolated test restore; no production overwrite
make outage-drill           # Simulate removal of foreign egress / loss of redis / etc.
make failover-plan          # Print controlled failover checklist
```

**Never make root creation an unattended production operation.** The `pki-create-offline-root` target should demand an isolated secure environment and explicit confirmation; CI must not generate real long-term keys.

**Required documented walkthroughs**

- Prepare a VPS hosted within Iran with a genuine stable public IP, firewall policy, SSH key-only administration, uptime, encrypted disks where practical, and secure backups.
- Provision primary and standby endpoints, configure separate TLS certs, run migrations, lock down firewall, test OS clock synchronization using reachable domestic time services or a documented offline clock policy.
- Onboard iOS and Android users using publicly trusted IP TLS, plus optional private CA emergency profile with explicit root fingerprint verification. Validate actual browser trust paths and certificate chain per OS.
- Establish peer identity fingerprint verification and recovery-key download before emergency.
- Confirm foreign service egress is not required; simulate blocked external networks and log unexpected outbound attempts.
- Operator recovery from server outage, compromised account, compromised administrator, compromised private intermediate/root CA, expired certificate, database corruption, lost client key state and failed release.

**Security-sensitive operational caveat:** Private root CA compromise requires trust-anchor replacement on every participating device, not simply rotating a leaf certificate. The runbook must treat it as a high-impact incident.

---

# 13. Testing and acceptance specification

Implement actual test suites, fixtures and repeatable commands. Keep a machine-readable coverage matrix `docs/security/controls.csv` and produce `TEST_REPORT.md` with exact pass/fail/blocked evidence. A test that is not run is `BLOCKED`, not `PASS`.

## 13.1 Functional acceptance matrix

| ID | Test scenario | Must-pass criterion |
|---|---|---|
| F01 | Invite created by admin | One-use token expires/revokes; no open signup |
| F02 | Register and login | Real credentials, valid cookie session, anti-CSRF, logout invalidation |
| F03 | Wrong password/rate limit | Restricted without username enumeration; no leaked auth details |
| F04 | Device enrollment | New device is NOT trusted without verifiable approval/recovery |
| F05 | Direct E2EE | Sender/recipient can decrypt, server DB contains ciphertext only |
| F06 | Group E2EE | Three users exchange authenticated group messages |
| F07 | Remove group member | Removed device can't decrypt new-epoch messages |
| F08 | New group member | Cannot decrypt pre-join messages without explicit secure history transfer |
| F09 | Two devices / one account | Both authorized devices receive required messages, old untrusted device does not |
| F10 | Attachment upload | Binary contents encrypted client-side; file can be restored and verified by recipient |
| F11 | Voice note | Record/transfer/decrypt/play with permission fallbacks |
| F12 | Reconnection | Offline drafts and pending envelopes send eventually without duplicates |
| F13 | Server restart mid-send | No false ack; pending messages recover consistently |
| F14 | Redis loss | PostgreSQL sync recovers messages; no durable data loss |
| F15 | WS blocked | HTTP sync fallback works with clear latency/status caveat |
| F16 | Browser refresh | Unlocked after local passphrase; cryptographic state correctly resumes |
| F17 | Browser storage erased | Clear warning, recover kit workflow, no fake old-history restoration |
| F18 | RTL and mobile | iPhone/Android target dimensions, Persian/English content renders accurately |
| F19 | Search | Client local decrypted search; no server-side plaintext index |
| F20 | Admin data | Admin sees metadata/health, never decrypts private chats by role |
| F21 | Primary failover | Controlled standby promotion and endpoint-switch; no split-brain |
| F22 | Shutdown simulation | Login/crypto/messaging/file transfer work with international egress blocked |
| F23 | Certificate invalid | Browser refuses TLS; no bypass / insecure redirect |
| F24 | Private PKI | Preconfigured device trusts correct IP leaf; unconfigured device does not auto-trust |
| F25 | Offline bundle | Fresh environment can deploy with no external package fetches |
| F26 | Release update | Signed/checksummed bundle validation and rollback documented |

## 13.2 Security and cryptographic negative matrix

| ID | Attack/fault | Expected result |
|---|---|---|
| S01 | Backend administrator queries stored content | No plaintext or client private keys present |
| S02 | Unauthorized user accesses group endpoint/WS | 403/appropriate rejection and disconnect |
| S03 | CSRF and hostile WS Origin | Request rejected |
| S04 | Cross-user object ID guessing | Authorization blocks access to ciphertext/attachment |
| S05 | Corrupted authenticated ciphertext | Client decryption fails, message not rendered |
| S06 | Fake MLS credential or unapproved device | Rejected/verification warning, cannot silently join |
| S07 | MLS stale/replayed group commit | Rejected/held for safe reconciliation |
| S08 | Duplicate send + ACK loss | Exactly one user-visible logical message; idempotent server state |
| S09 | File wrong nonce/tag/chunk | Detection/rejection, no corrupted plaintext displayed |
| S10 | XSS payload in message content | Rendered inert, no code execution or key exfiltration |
| S11 | Brute-force, invite guessing | Throttled, nonenumerating responses |
| S12 | Foreign CDN/API intentionally unavailable | Core UI/auth/E2EE continues without calls outside trusted hosts |
| S13 | Expired/untrusted TLS cert | Browser blocks access; no insecure fallback |
| S14 | Device revoked during offline period | Old device cannot decrypt newer epochs after protocol rekey |
| S15 | Restore database to old state | Detect cryptographic rollback/order inconsistencies; safe resync/no silent accept |
| S16 | Browser storage persistence failure | Clear error before risky transition, no silent key loss |
| S17 | Reuse previous key package | Reject or documented protocol-safe exception |
| S18 | Large malformed payload | Bounded resources, stable service, no uncontrolled allocation |
| S19 | Sensitive exception | Redacted logs, no secret material in trace |
| S20 | Malicious frontend bundle served by compromised origin | Explicitly documented as NOT fully mitigated by browser-only design; cannot mark as cryptographically prevented |

## 13.3 Performance and endurance (proposed initial budgets)

Perform reproducible tests with representative encrypted payloads and realistic end-user actions, not just health checks:

- 100 concurrent online users, 500 simultaneous WS/browser connections (may include multiple tabs/devices), 20 delivered messages/s burst, 5 file uploads concurrently, 30% intermittently connected users. These are **qualification targets**, not implied measured capacities.
- p95 POST envelope acceptance under 750ms on the qualified reference host at expected load, excluding unavailable domestic routing; report actual measurements and resource use.
- No unexpected OOM, unbounded queue growth, dropped ACKs or permanent outbox stalls in at least 2h soak on a host that passes thermal and system preflight.
- Client E2EE group operations benchmarked on lower-end Android and iOS Safari; record memory use, WASM load time, unlock KDF latency and crash/restart behavior.
- If the available development laptop throttles or test rig cannot qualify performance, STOP the capacity claim and report `UNQUALIFIED` instead of inferring production capacity.

## 13.4 External testing gates

- Real iOS Safari and Android browsers must undergo physical-device testing (automation cannot replace OS certificate-store and browser trust testing entirely).
- Real Iranian provider reachability tests (multiple mobile and fixed carriers) require reachable test endpoints and volunteers; simulation cannot prove real-world behavior.
- Independent protocol/implementation cryptography review and application penetration test are required **before classifying release as suitable for high-risk emergency communications**. Codex cannot self-certify independence.

---

# 14. Implementation plan, milestones and release gates

Implement sequentially. Keep issues/commit history or a changelog and a live checklist in `IMPLEMENTATION_STATUS.md`. Never confuse 'started' with 'passed'.

| Stage | Engineering output | Exit criterion |
|---|---|---|
| 0. Repo discovery | ADRs, threat model, dependency choices, OS and package audit | No unreviewed overwrite; decisions documented |
| 1. Security PoFs | Raw-IP TLS dev setup, OpenMLS Rust/WASM real browser PoF, IndexedDB state | Verified encrypted messages + reload + member removal; negative tests |
| 2. Core infrastructure | Compose, Nginx, Django models, migrations, auth/invites, admin | Secure login/invitation flows, basic tests, no external calls |
| 3. Messaging core | Conversations, crypto control events, durable queues, cursor sync, WS | End-to-end 1:1 text + reconnection without plaintext leaks |
| 4. Groups & devices | Add/remove/rekey, key trust QR, multi-device approval | MLS state correct across offline/rejoin/removal, adversarial tests |
| 5. Media | Encrypted attachments, voice notes, resumable transport | Integrity tests, resource quotas, recovery |
| 6. Complete UI | Responsive, RTL, settings, local encrypted vault/backup, offline shell | Functional end-user flows on desktop/mobile simulator |
| 7. Operations | Primary/standby, controlled failover, private PKI runbooks, offline build | Isolation and restore/failover drills, certificate tests |
| 8. Final QA | Test matrix, remediation, dependency scan, secure defaults, docs | All executable release-1 tests pass; blocked external gates reported |
| 9. High-risk release review | Independent security review + physical browser/provider qualification | Explicit owner approval AFTER independent review; never self-certify |

## 14.1 Gate behavior

- **BLOCKER-CRYPTO:** No safe E2EE implementation passes browser PoF → halt production release, do not substitute fake E2EE.
- **BLOCKER-TLS:** Can't establish trusted HTTPS on target IP → halt real user onboarding, never permit plain HTTP passwords/crypto.
- **BLOCKER-CLIENT:** State fails on iOS/Android browser → report unsupported environment and prevent false compatibility claim.
- **BLOCKER-OUTAGE:** Any essential external runtime request → remove it or clearly mark affected feature unavailable during outage.
- **BLOCKER-AUTH:** Cross-user leakage, unverified device acceptance, plaintext storage → stop release and repair.
- **BLOCKER-AUDIT:** No independent cryptography review → functioning prototype may be described as **unreviewed**, not war-ready.

---

# 15. Codex completion criteria and reporting

When implementing, maintain and at the end provide:

1. **Source:** complete current repository code, committed or clearly enumerated file changes, working migrations, seed/bootstrap procedures, pinned dependencies.
2. **Deployment:** `docker compose` workflows for local dev/staging/production, production proxy config, secure sample env, manual trust/bootstrap docs, offline bundle scripts.
3. **API:** OpenAPI spec and typed clients; WebSocket JSON Schema versioning and end-to-end delivery behavior.
4. **Security:** threat model, crypto ADR, exact chosen cipher suite/protocol dependency, trust limitations, key lifecycle, certificate lifecycle, least-privilege and incident response docs.
5. **Functional UX:** complete 12 required screens, Persian/English translations and tested small-screen responsiveness.
6. **Proof:** real output from each test stage, `TEST_REPORT.md`, independent constraints and known gaps, `SECURITY_STATUS.md`.
7. **Operator runbooks:** first setup, invite onboarding, trust onboarding, new device, user recovery, backup/restore, offline install, outage drill, endpoint switch, loss of root CA, certificate expiry.
8. **Owner handoff:** exact staging URL placeholder fields and actual verified URL only after deployed; avoid inventing public IP. Document needed external resources/credentials and costs as variables, never hardcode guesses.

Final status must use one of these precise labels:

- `PROTOTYPE_COMPLETE_UNREVIEWED`: functions locally, external review outstanding.
- `STAGING_VALIDATED`: staging deploy and executable tests pass; field/operator/audit gates may remain.
- `FIELD_TESTED_UNREVIEWED`: real-device/domestic tests pass; independent security audit still pending.
- `RELEASE_REVIEWED`: reviewer evidence explicitly recorded; owner approved release based on documented remaining risks.
- `BLOCKED`: a release-critical functional/security gate failed.

**Never state that the product is safe for wartime use only because code was written, the backend starts, or Playwright is green.**

---

# 16. Deliverables and suggested priority backlog

## 16.1 Release-1 must-have

- Domainless login, invitation-only accounts, self-hosted TLS.
- Direct/group end-to-end encrypted messaging with independently implemented transport and library-backed standard MLS.
- Browser-local protected crypto state and verified device onboarding.
- Reliable persistent delivery and delta synchronization.
- Group membership management and security warnings.
- Encrypted attachments and voice notes.
- Mobile-first responsive UI, bilingual English/Persian, admin dashboard.
- No external runtime dependencies.
- Reproducible Docker deployment, backup and explicit manual failover.
- Offline shell/reconnect and secure local recovery kit.
- Extensive automated test evidence, honest security status.

## 16.2 Future releases — do NOT sacrifice must-have quality

- Browser-based voice/video calls with validated E2EE, self-hosted TURN/STUN and cross-browser support (separate design and security review).
- Optional push notifications when providers reachable (never required for core communication).
- Federation across privately hosted delivery nodes (substantial routing/identity expansion).
- Local Bluetooth/Wi-Fi direct communication via a separate native companion or alternative transport (NOT feasible as guaranteed zero-install cross-city browser-only mode).
- Key transparency independent gossip/append-only signed checkpoints and stronger independently verified client distribution.
- Optional local mesh/offline companion; explicitly breaks zero-install requirement.

---

# 17. References Codex must read and validate

These are **specification and implementation reference starting points**. Verify package APIs, licenses, security advisories and release status at build time. The runtime application must not fetch them during an outage.

1. IETF MLS RFC 9420: https://www.rfc-editor.org/rfc/rfc9420.html
2. OpenMLS repository and WASM overview: https://github.com/openmls/openmls and https://book.openmls.tech/user_manual/wasm.html
3. Alternative crypto engine documentation (evaluate only if needed): https://matrix-org.github.io/matrix-sdk-crypto-wasm/index.html
4. Libsodium authenticated encryption: https://doc.libsodium.org/secret-key_cryptography/aead/chacha20-poly1305
5. Signal's Double Ratchet security reference (design reading, not permission to build an ad-hoc protocol): https://signal.org/docs/specifications/doubleratchet/
6. CA/Browser Forum current TLS Baseline Requirements: https://cabforum.org/working-groups/server/baseline-requirements/requirements/
7. Let's Encrypt IP cert lifetime (160 hours): https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability
8. Apple manual private-root trust: https://support.apple.com/en-us/102390
9. Browser secure contexts: https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts
10. Browser service workers: https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers
11. Apple web push limitation: https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers
12. OWASP ASVS 5.0: https://asvs.owasp.org/

---

# 18. FINAL EXECUTION DIRECTIVE FOR CODEX

Implement HAVEN now in this repository. Treat this entire document as the source of truth. Do not merely write a plan or visually mock the application. First inspect the directory and publish the initial ADR/threat-model/crypto feasibility plan; then execute the work stage by stage. Perform real implementation, build, migrations, and tests. When blocked by credentials, real devices, physical-network tests or an independent external review, complete every safely executable remaining milestone, produce exact reproducible steps, and mark the appropriate gate as BLOCKED or UNREVIEWED. Do not invent successful test results, deployment outcomes, audit signoffs or security assurances.

On the last pass, run the complete available QA suite, inspect failures, repair them, repeat until passing or honestly blocked, and hand off a truthful release checklist with concise operational commands and user onboarding guidance. **Never replace a hard requirement with a less secure shortcut without an explicit ADR, visible warning, and release-gate consequence.**
