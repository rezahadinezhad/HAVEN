# Test report — local engineering qualification

Date: 2026-10-30 (Asia/Tehran; test logs use UTC; earlier sections retain their original evidence dates). **Release status: BLOCKED.** Results concern the recorded source/workspace and isolated test infrastructure. No independent security review, physical-phone test, public IP deployment or Iranian carrier qualification is claimed. See controls.csv for incomplete full criteria; a local subcheck does not make an entire external criterion PASS.

## Latest: guided terminal setup

2026-10-30: added `./setup.sh` / `make setup`, an interactive installer with generated secrets, separate Docker projects, TLS validation, least-privilege role/migration/bootstrap steps, verified HTTPS/login probes and resumable state. **13 stdlib/OpenSSL tests passed**, both application images built, a real local installation and repeat run passed, and a deliberately failed pre-migration step recovered through resume without replacing credentials or keys. Sandboxed Chromium accepted the isolated profile's test root, signed in through the UI and reached browser setup; an untrusted profile rejected TLS. Port collision refused. Gated server mode correctly stopped at this host's failing `no-new-privileges` probe rather than weakening server hardening. Local integration checks explicitly used the local compatibility choice. See [exact scope, commands and limitations](docs/evidence/setup-wizard-2026-10-30.md) and the [setup runbook](docs/runbooks/guided-setup.md). No fresh full application suite or qualified server deployment is claimed.

## Prior: public project presentation

2026-10-30: prepared an MIT-licensed public-source presentation of HAVEN as a practical security engineering experiment. Updated README, architecture/features/security explanation, contribution guidance, original SVG/PNG artwork and real synthetic-data interface captures. Generalized the visible review/connection guidance while preserving the unreviewed/production prohibition, TLS rules and all cryptographic gates. Original input-spec checks remain unchanged. The opt-in `tests/showcase.spec.ts` workflow **passed** with a real encrypted two-account conversation, local fingerprint pins, desktop/dark/mobile views, visible review notice and no synthetic message plaintext in observed messaging request bodies. Production build/TypeScript and publication checks passed. No fresh full API/Rust/physical-device suite is claimed for these copy/documentation changes; the recorded security suites below remain the evidence for that source behavior. Artwork is project-authored SVG plus browser raster export; screenshots are actual application output, not AI-generated product mockups. See `.github/assets/README.md`.

## Prior: credential-bound sessions and browser key lifecycle

2026-10-30 Asia/Tehran (logs may use 2026-10-29 UTC). The second security pass corrected stale session/credential races, bounds unfinished browser sign-ins, and improves lock behavior around navigation, suspended timers, clock rollback and confirmed session loss. See [ADR 0011](docs/adr/0011-session-and-browser-key-lifecycle.md). No message-cryptography primitive or trust/TLS gate changed.

| Check | Observed result | Evidence prefix `docs/evidence/security-pass2-` |
|---|---|---|
| Full API | **70 passed** including credential updates without explicit revocation, stale verified login, account disable, serialized password changes, pending-sign-in eviction, blank/tampered bindings, actual old-session migration, live WSS invalidation and revoked in-flight enrollment | api-final-tests.txt |
| Chromium | **4 passed**: existing-device approval, full chat/offline/voice UI, new real-vault pagehide/pageshow/suspended/clock/offline/remote-logout workflow, multi-device view-once | chromium-final-tests.txt |
| Firefox | **3 passed**: approval, the new security workflow and multi-device view-once; synthetic microphone workflow is Chromium-only | firefox-final-tests.txt |
| Dependency audits | npm/Python/Rust: **zero known vulnerabilities**; existing optional Rust proc-macro-error2 maintenance warning retained | npm-audit.json; python-audit.json; cargo-audit.json |
| Build/static | Production build, TypeScript, scoped formatting, Ruff, schema drift, offline-shell lifecycle, source/vendor integrity and publication checks passed | web-build.txt; offline-shell.txt; source-scan.txt |
| Upgrade/staging | Migration 0010 exercised with the actual local migration role and durability checks; new column readable by runtime role. Actual packaged TLS login/me succeeds and the same token is rejected after a direct password update. Matching API/web images deployed locally; trusted TLS, strict CSP, static resources, worker manifests and correct 8443/8444/8445 crypto gates verified | staging-upgrade.txt; runtime-schema.txt; packaged-auth-smoke.txt; staging-status.json; images.json; api-image.txt; web-image-final.txt |

The browser workflow checks preserved device identity and absence of the vault passphrase in observed requests. Clock behavior is tested with controlled browser clock functions and lifecycle events, not physical device suspension. The migration intentionally signs existing sessions out once; rollback cannot restore them. The full chat test now expects automatic logout detection rather than racing it with manual logout. Earlier initial tests (69 API / 2 Chromium) preceded the extra enrollment-race and clock cases; final counts above supersede those. Independent review, physical phones, fresh container OS scanning and external infrastructure/capacity qualification remain outstanding. Server-side credential binding does not protect against a fully compromised origin, server, database writer or endpoint. Production release remains **BLOCKED**.

## Prior: Rust dependency vulnerability remediation

2026-10-29: Backported the pinned upstream OpenMLS provider/credential migration, retaining published OpenMLS 0.9.2, traits/storage 0.6.0, the state format and the mandatory X25519/Ed25519 suite. Source provenance and the minimal sync-storage/manifest compatibility patch are in `packages/crypto-core/vendor` and [ADR 0010](docs/adr/0010-upstream-provider-security-backport.md).

| Check | Observed result | Evidence prefix `docs/evidence/rust-remediation-` |
|---|---|---|
| Cargo audit | **Zero known vulnerabilities**, successful exit; crypto-bigint 0.7.9 and optional libcrux-kem 0.0.10 resolve all three previous entries, with no ignored advisory. One optional proc-macro-error2 maintenance warning remains | audit-final.json; audit-readable.txt |
| Native/build | **4 passed**, native and wasm32 check, release WASM and static Linux verifier rebuilt; original native snapshot retained privately for compatibility testing | native-tests.txt; check-native.txt; check-wasm.txt; build-crypto.txt; build-verifier.txt |
| Upstream protocol KATs with backported providers | **205 passed, 3 ignored, 91 filtered**; unsupported-suite warnings retained | provider-vectors.txt |
| Final Chromium | **7 passed**: real MLS/vault, previous native snapshot, old/new provider bidirectional messaging and membership, new native/WASM snapshot, full messenger/media/retry/removal and view-once multi-device flows | chromium-final-tests.txt |
| Final Firefox | Same **7 passed** against the rebuilt artifact; physical iOS/Android not tested | firefox-final-tests.txt |
| Build/runtime | TypeScript and production web build, offline-shell lifecycle checks, package artifact hashes, trusted TLS/CSP/static assets and offline revision checks on 8443/8444/8445 passed. Production 8443/8444 remain crypto_ready=false; only isolated 8445 is enabled | web-build.txt; offline-shell.txt; image-artifacts.json; staging-status.json |

The first browser run overlapped API tests that clear shared Redis state and had two application failures. It is retained as preliminary evidence, with the isolated application rerun. An older immutable preview was then discovered; it was restarted with the rebuilt WASM, its SHA-256 was verified against source, and the final Chromium/Firefox runs above assert the served hash inside the compatibility tests. Preliminary runs are not counted as final rebuilt-browser qualification. Full API suite: **61 passed** against the rebuilt verifier. Vendor hash checks, rustfmt, YAML parsing and source publication guards passed. Container images were rebuilt and local staging updated; fresh container OS scans and independent review were not performed. Prior signed bundles remain historical and must be regenerated for this revision. Overall production release remains **BLOCKED** for the external requirements documented in SECURITY_STATUS.md; the three Rust vulnerability entries no longer block it.

## Prior: prepublication security review

2026-10-29: full API **61 passed**, focused Chromium device-unlock **5 passed**, Firefox direct-IP **1 passed**, real trusted-TLS proxy/Uvicorn WebSocket hello/heartbeat passed, production web build/TypeScript and Ruff passed. Fixed concurrent account quota reservations and WebSocket secure-scheme/authority validation. Removed inherited workstation environment maps from 20 historical browser reports and restricted future browser environments. Added negative-tested publication guards, secret scanning, a fresh-history GitHub export and GitHub security workflow. npm/Python audits report zero findings. Fresh Cargo audit reports three advisories (including newly surfaced RUSTSEC-2026-0387) plus a maintenance warning; incompatible upstream constraints prevent a safe lockfile-only fix. The Rust CI job intentionally remains blocking. Original history retains workstation metadata; publish the scanned fresh export. See [review](docs/security/prepublication-review.md) and `docs/evidence/prepublication-*`. No independent review, container re-scan, physical-device test or deployment is claimed. Release remains **BLOCKED**.

## Prior: optional device-verified vault unlock

The default direct-IP app continues to require the vault passphrase on refresh/reopen and now explains password-manager autofill. The opt-in exact-hostname path uses a fresh WebAuthn assertion with required user verification and a required 32-byte PRF result to decrypt a browser-local AES-GCM-wrapped copy of the existing vault passphrase. It is offered only after the user has unlocked and enrolled it. No passphrase, PRF output or credential is uploaded. API, Next proxy, Compose and env validation accept at most one explicitly configured hostname while retaining an exact IPv4 route and rejecting wildcard/HTTP/foreign Host/Origin traffic. The account session, Argon2id vault, device approval, TLS and release gate are unchanged. See ADR 0009 and the runbook.

| Check | Observed result | Evidence |
|---|---|---|
| Chromium relevant browser selection | **8 passed**: 5 PRF/direct-IP tests and 3 existing vault setup/reload/fallback UI tests | docs/evidence/device-unlock-chromium-tests.txt |
| Firefox relevant browser selection | **4 passed, 4 skipped**: IP denial and 3 vault UI tests passed; CDP virtual-authenticator PRF cases are Chromium-only | docs/evidence/device-unlock-firefox-tests.txt |
| Full hostname UI | **1 passed**: real invited account, encrypted vault, PRF enrollment, reload unlock without typing, same device identity, local ciphertext-only wrapper, removal and passphrase fallback. Test-root-signed `https://localhost:8446`, certificate validation enabled; both hostname and IP root routes work, wrong API/web Host returns 400 and wrong Origin returns 403 | docs/evidence/device-unlock-hostname-qa.txt; device-unlock-hostname-settings.png; device-unlock-hostname-unlock.png |
| API/config | **57 passed** for full API suite, including 9 exact-hostname/IPv4 accept/reject cases and an optimized-Python env-validator failure test; Ruff check/format passed | docs/evidence/device-unlock-api-tests.txt |
| Build/static | Next production build, TypeScript, scoped Prettier, Ruff, Python/shell syntax, unchanged original-spec checks and source manifest verification passed; no new package dependency or database migration | docs/evidence/device-unlock-hostname-qa.txt; device-unlock-checks.txt; SOURCE_MANIFEST.sha256 |
| Packaged preview | API image `sha256:3c16ba30b2f41bdade40f32ea052487c5415b98d44c86332591e766444a94087` and web image `sha256:f1da223bf137590dd28af08d21c5642acded5f3088db51244ec9f8683faaa1d9` built. Loopback Compose API/web/workers recreated. A transient 502 during ingress/upstream transition resolved; final trusted TLS, strict CSP, 8 loaded static assets, matching offline worker and correct crypto gates passed on 8443/8444/8445 | docs/evidence/device-unlock-api-image.txt; device-unlock-web-image.txt; device-unlock-staging-deploy.txt; device-unlock-staging-status.json |

Chrome tests explicitly reject missing PRF, failed user verification and a copied wrapper under another account. The trust test uses a disposable root already installed in isolated test browser profiles; no TLS-error bypass or HTTP app origin is used. These checks do not establish hardware-bound biometrics, physical iOS/Android behavior, passkey-provider sync behavior, independent security review or emergency release suitability. A platform passkey may sync and its OS may use a PIN. The current `https://127.0.0.1:8445/` origin cannot use WebAuthn and does not inherit the hostname-origin vault. The short-lived local hostname leaf and the existing IP leaf expire on 2026-10-30; neither is a deployment certificate. Release remains **BLOCKED**.

## Latest: visible sender previews and attachment-type picker

The paperclip opens Photos & videos, Audio and File choices with separate native file inputs and accept hints. The confirmation panel renders the actual unsent local raster photo, video player or audio player before upload. Its content scrolls while Send stays visible. Unsupported types and decoder failures have explicit fallback copy; documents/HTML/SVG are not embedded. Local preview resources are released on replacement/removal/send/lock/pagehide/unmount. Chat tips was removed from the composer and guidance moved to Connection & help. Uploaded music/audio has its own playback label. File-scoped view-once mode, existing encrypted transport and consumption/approval/TLS gates remain unchanged.

| Check | Observed result | Evidence |
|---|---|---|
| Chromium final-source flows | 3 unique workflows passed across suite and targeted rerun: new picker/preview/chat workflow, real voice/offline UI, and account-wide view-once media. The first chat navigation was interrupted by host ERR_NETWORK_CHANGED during container restart before the app loaded; after the environment settled its targeted rerun passed with validation still enabled | docs/evidence/media-picker-chromium-tests.txt; media-picker-chromium-startup-results.json; media-picker-chromium-final-flow.txt; media-picker-chromium-final-flow.json |
| Firefox final-source flows | 2 passed: the picker/preview/chat workflow and full view-once photo/video scenario | docs/evidence/media-picker-firefox-tests.txt; media-picker-firefox-results.json |
| Build/typecheck/format | Passed; no package dependency or server schema changes | docs/evidence/media-picker-build.txt; media-picker-typecheck.txt; media-picker-format.txt |
| Offline shell | Worker/cache lifecycle and private/foreign bypass checks passed | docs/evidence/media-picker-offline-shell.txt |
| Packaged preview | Web image rebuilt and local web updated. Verified trusted test-root TLS, nonce CSP, assets and worker/manifest consistency at 8443/8444/8445. Normal 8443/8444 remain crypto_ready=false; isolated 8445 alone permits engineering evaluation | docs/evidence/media-picker-web-image.txt; media-picker-staging-status.json |

The tests use the actual paperclip menu and intercepted native file chooser, asserting all three accept filters and menu bounds. They verify local photo pixel dimensions before sending, no attachment initialization before confirmation, stable preview across viewing-mode toggles, decoded video dimensions, selected WAV playback and encrypted recipient playback, reset/revocation after replacement/removal/send, source clearing and pause on send, actual vault-lock cleanup, document/SVG inert fallback, invalid image and wrong-category feedback, absence of Chat tips, EN/FA/RTL, reduced motion, CSP and no foreign application requests. The existing pending-file view-once reset and account-wide single-opening/export/cache limitations still pass. Screenshots are chat-attachment-menu*, chat-attachment-mode*, chat-selected-video* and chat-selected-audio*; all are disposable QA content.

These are Linux desktop browser/native-chooser automation checks and resized mobile viewports. Actual OS gallery integrations, physical Safari/iOS/Android, codec breadth and independent application/security review remain unqualified. Accept hints do not validate decrypted file content on the server; authorization and encrypted transport validation remain separate. Browser decoded-memory erasure is not guaranteed by removing sources/revoking URLs. No automatic upload, recipient view-once preview, remote thumbnail service, active document embedding, new cryptographic primitive or security gate bypass was added. Earlier broad-suite counts below are not fresh reruns for this change. Release remains BLOCKED; temporary test-certificate expiry is unchanged.

## Prior: view-once mode belongs to the selected attachment

Removed the persistent chat-footer checkbox and its chat-level state. A supported selected photo/video now offers **View once** inside its confirmation box, with capture/opening disclosures before Send attachment. Documents/audio do not offer the control. The file and its mode share one local selection object; selecting/replacing a file defaults to ordinary mode, and send/remove/navigation/lock discards that selection. Attachment preparation receives the mode explicitly. Server authorization, consumption, encryption, approval and TLS gates are unchanged.

| Check | Observed result | Evidence |
|---|---|---|
| Chromium focused workflows | 2 passed: ordinary chat/media workflow plus the real three-account/four-device view-once photo/video flow | docs/evidence/attachment-mode-chromium-tests.txt; attachment-mode-chromium-results.json |
| Firefox focused workflows | The same 2 workflows passed | docs/evidence/attachment-mode-firefox-tests.txt; attachment-mode-firefox-results.json |
| Types/format/build/offline shell | Passed | docs/evidence/attachment-mode-typecheck.txt; attachment-mode-format.txt; attachment-mode-build.txt; attachment-mode-offline-shell.txt |
| Local packaged preview | Web image rebuilt/updated; trusted TLS, strict CSP, static assets and matching worker manifests verified on 8443/8444/8445. Normal 8443/8444 remain gated; only isolated 8445 permits evaluation messaging | docs/evidence/attachment-mode-web-image.txt; attachment-mode-staging-status.json |

New assertions verify no option without a file, an unchecked contextual control for new photos/videos, notices inside the confirmation box, true initialization flags only for explicitly enabled media, false flags for ordinary photo/video sends, reset after replacing with a document and after removal, absence for documents, and EN/Persian/RTL/mobile layouts including a short 450px viewport. Existing account-wide one-opening, other-recipient independence, cache/export exclusion and consume/reload denial checks passed. See chat-attachment-mode*.png. These are local engineering checks; physical-device testing and independent review remain outstanding. The 16/15 browser counts below belong to the previous broader UX revision, not a fresh rerun of that selection. Release remains BLOCKED; existing temporary test-certificate expiry is unchanged.

## Prior: conversation UX and contextual guidance

The conversation surface now has local previews/unread filters, grouped bubbles/date separators, observed-state delivery indicators, native message-action popovers, current-text reply/edit previews, a growing IME-aware composer, attachment confirmation, ordinary raster-photo/video preview, recording cancellation, full mobile chat layout and EN/FA contextual guidance. Additional-browser approval remains signature-gated and now explains the actual steps and recovery limits. Only sending a text message consumes its unrelated encrypted draft. File/voice replies carry their selected reply context. No server schema, package dependency or cryptographic primitive changes.

| Check | Observed result | Evidence |
|---|---|---|
| Chromium focused selection, final build | **16 passed**, zero failed/skipped/flaky: new conversation workflow plus messaging UI/offline/voice, MLS/native-WASM, design/CSP, guided first chat/approval/retry, passphrase and full media/member integration/view-once cases | docs/evidence/chat-chromium-tests.txt; chat-chromium-results.json |
| Firefox focused selection, final build | **15 passed**, zero failed/skipped/flaky: the same selection except the Chromium synthetic-microphone/offline-UI case; the new thread/photo/video workflow, native/WASM, full integration and view-once flows pass | docs/evidence/chat-firefox-tests.txt; chat-firefox-results.json |
| Types/format/production build | Passed; scoped source/test Prettier and TypeScript; Next production build prepares 19 local shell assets | docs/evidence/chat-format.txt; chat-typecheck.txt; chat-build.txt |
| Offline worker lifecycle | Current shell after restart, previous-cache cleanup, unrelated cache preservation, private/foreign bypass and mismatched-manifest rejection passed | docs/evidence/chat-offline-shell.txt |
| Selected token contrast | Nine solid normal-text pairs pass 4.5:1; darker action text is used on pale outgoing bubbles. This is a selected-pair check, not a complete accessibility audit | docs/evidence/chat-contrast.json |
| Packaged local web | Rebuilt web image and updated loopback Compose web. Trusted test-root TLS, strict CSP, new static assets and worker/manifest consistency passed on 8443/8444/8445. Normal 8443/8444 remain crypto_ready=false; isolated 8445 alone permits evaluation messaging | docs/evidence/chat-web-image.txt; chat-staging.txt; chat-staging-status.json |
| Source/security gates | Original master/start documents verified; release gate retains its expected nonzero BLOCKED result | docs/evidence/chat-original-spec-checks.txt; chat-release-gate.txt; SOURCE_MANIFEST.sha256 |

Exact tested desktop browser/Playwright/Node versions are recorded in docs/evidence/chat-test-versions.json.

The new workflow uses two disposable invited accounts with actual MLS and backend ciphertext transport. It verifies desktop Enter/Shift+Enter, IME confirmation safety, current edited text, cancellation/draft preservation across reactions/edits/reload, real reply previews, attachment reply/draft preservation, edited-text local search, emoji insertion, reader scroll-position preservation, incoming-message jump, confirmation/removal before file send, explicit ordinary PNG preview and real recorded WebM decode/play, dismissal/lock cleanup, light/dark themes, 320/390/900/1280px widths, a short 450px viewport, Persian RTL and reduced motion. Tested requests make no foreign application requests; plaintext text and filenames are absent from captured message-envelope bodies. Existing browser tests cover inert HTML rendering, encrypted media, membership changes, offline queue ordering, and view-once consumption/key/export limits. Chromium microphone input is synthetic; this is not physical microphone/device qualification.

Initial runs exposed duplicate React sibling keys and an overridden native-popover hidden state; both were corrected before the final pass. The view-once test now uses the explicit attachment confirmation and returns from the full mobile thread before opening Settings. An excessively short synthetic ordinary video reached end-of-playback during the play assertion; the fixture now records a longer clip and starts from time zero. The Firefox newline test no longer presses End after inserting a newline, since caret behavior differs by engine. Final results are distinguished from the retained initial diagnostic reports. Firefox still permits a decoded image to load from its internal cache after an object URL is revoked in the existing view-once probe; HAVEN consumes the viewing authorization and removes sources, but secure decoded-memory erasure is explicitly outside the guarantee.

The root/leaf trust chain was preserved when local testing resumed after interruption on 2026-10-29. The expired disposable leaf was renewed and verified without a TLS bypass. This loopback test leaf expires **2026-10-30 09:22:11 UTC**, and its test root expires 2026-10-30 18:33:30 UTC; see chat-test-tls-renewal.txt and docs/ui-ux/conversation-experience.md. The first offline-Dockerfile invocation lacked the separately packaged offline-deps directory; the normal pinned web Dockerfile subsequently built successfully. No new dependency was added and no fresh air-gap installation is claimed.

Backend/native full-suite counts in earlier sections remain evidence for prior unchanged server/Rust code; they are not newly rerun or reclassified here. Physical Safari/iOS/Android, assistive technology, codec breadth, large-history virtualization/performance, public infrastructure and independent review remain unqualified. The UI revision does not establish full Telegram feature parity or independent security assurance. Earlier signed QA bundles predate this revision. Release remains **BLOCKED**.

## Prior: optional local unlock-passphrase generation

The new-browser guide offers a 43-character secret from 32 browser-CSPRNG bytes, optional reveal/copy, a saved confirmation after access, and manual entry. Existing vault unlock never offers regeneration. No server code, schema, dependency or messaging cryptographic protocol changes in this revision.

| Check | Observed result | Evidence |
|---|---|---|
| Chromium focused regression | 12 passed: three new generator checks plus existing browser crypto/native-WASM, design/CSP and all four guided-first-chat checks | docs/evidence/passphrase-chromium-tests.txt; passphrase-chromium-results.json |
| Firefox focused regression | 12 passed, covering the same generator, crypto, design and guided-chat cases | docs/evidence/passphrase-firefox-tests.txt; passphrase-firefox-results.json |
| Types/format/build | TypeScript, scoped Prettier and Next production build passed | docs/evidence/passphrase-checks.txt; passphrase-build.txt |
| Offline shell | Cache selection/restart, old-cache cleanup, API/WS/foreign bypass and manifest rejection passed | docs/evidence/passphrase-offline-shell.txt |
| Packaged web | Web image rebuilt and loopback Compose web/ingress updated. Trusted test-IP TLS, CSP, assets and worker/manifest consistency checked on 8443/8444/8445. Normal 8443/8444 remain crypto_ready=false; isolated 8445 remains the sole enabled evaluation origin | docs/evidence/passphrase-web-image.txt; passphrase-staging.txt; passphrase-staging-status.json |

The generator tests check a deterministic encoding vector, a 32-byte draw, cleared temporary byte buffer, independent real sample formatting, and failure when secure randomness is missing/throws while Math.random is forbidden. Sample uniqueness is a smoke check, not entropy certification. The UI tests check masking, explicit reveal/copy, actual Chromium clipboard round-trip, regeneration/manual reset, disabled confirmation before access, handler-level saved-confirmation enforcement, no enrollment before confirmation, real vault creation and original-identity unlock after reload. Clipboard denial keeps the value masked and offers explicit manual reveal; cancellation leaves no saved device. Tested request URLs/bodies, local/session storage and encrypted IndexedDB records do not contain generated passphrases. Screenshots mask private values. EN/FA, 320/390/1440px and the closed normal source gate are covered.

The browser/OS random source, compromised-origin/extension risks, clipboard history/sync and lack of secure browser-memory erasure remain explicit in ADR 0008 and SECURITY_STATUS.md. No physical-phone or independent-security qualification is added. Backend/native full-suite results below describe prior unchanged code; they are not newly rerun or reclassified here. Existing signed QA archives predate this revision. Release remains BLOCKED.

## Prior: guided first chat and bounded member invitations

| Check | Observed result | Evidence |
|---|---|---|
| Backend full suite | 47 passed; includes real PostgreSQL concurrent quota checks, single-use redemption, token hashes, idempotent own-invite revocation/IDOR, UTC reset/pending limits, CSRF/Origin, password-only/pending-device denial, member/admin policy and crypto gates | docs/evidence/first-chat-api-tests.txt |
| Chromium full suite | 19 passed, including four new first-chat checks and the existing crypto/group/media/offline/restart/standby/TLS regressions | docs/evidence/first-chat-chromium-full-tests.txt; first-chat-chromium-full-results.json |
| Final Chromium focus | 6 passed after the final incoming-error wording correction; design/CSP and all four first-chat cases | docs/evidence/first-chat-final-chromium-tests.txt; first-chat-final-chromium-results.json |
| Firefox selected suite | 12 passed, including every new first-chat case and existing crypto/design/integration/retirement/view-once checks; shared QA login waits respected the real rate limit | docs/evidence/first-chat-firefox-tests.txt; first-chat-firefox-results.json |
| Final revocation UI | The ordinary-member two-way/reload flow passed again in Chromium and Firefox against the final API, including actual invitation revocation, removal of the signup capability from the share link, empty pending list and preserved quota usage | docs/evidence/first-chat-revocation-chromium-tests.txt; first-chat-revocation-firefox-tests.txt; matching results.json files |
| Rust and static checks | 4 native tests passed; Ruff check/format, migration drift, TypeScript, relevant Prettier checks and production Next build passed | docs/evidence/first-chat-rust-tests.txt; first-chat-checks.txt; first-chat-web-build.txt |
| Migration and packages | Migration 0009 applied locally and to gated Compose staging. API/web Docker builds passed; runtime-role policy read/update tested in a rolled-back transaction. Trusted test-IP TLS, static assets, strict CSP and matching offline worker/manifest passed on 8443/8444/8445. Only isolated 8445 has crypto_ready=true | docs/evidence/first-chat-migration.txt; first-chat-api-image.txt; first-chat-web-image.txt; first-chat-staging-deploy.txt; first-chat-staging-policy.txt; first-chat-staging-status.json |
| Backup/restore | Pre-upgrade encrypted staging backup restored using a disposable QA key into a networkless RAM-backed PostgreSQL instance. This staging dataset had zero retained message envelopes: this is schema/data restoration, not a new ciphertext/epoch-continuity qualification. Final TCP readiness fixes a reproduced initialization-server race | docs/evidence/first-chat-preupgrade-backup.txt; first-chat-preupgrade-restore.txt |
| Offline shell | Worker restart/cache selection, API/WS/foreign bypass, old-cache cleanup and mismatched-manifest rejection passed | docs/evidence/first-chat-offline-shell.txt |
| Release gate | Expected nonzero BLOCKED result; no release authorization | docs/evidence/first-chat-release-gate.txt |

The ordinary-member UI test sets up two real browsers, creates/consumes a member-issued signup link, removes its fragment from the address bar, compares the complete public-key codes, verifies no chat/decryption before explicit confirmation, exchanges actual encrypted messages in both directions, and reloads/unlocks without replacing the device identity. Link tests reject foreign origins, insecure protocols, malformed/duplicate/versioned/oversized cards, fingerprint mismatch and changed saved pins. The guide is checked at 320/390px and in Persian RTL; existing design checks cover desktop/mobile/theme/reduced motion and CSP. The additional-browser test preserves pending keys across reload, explicitly pins/approves them from the trusted device, checks administrator controls, and confirms the normal source gate remains effective. The retry test loses an actual accepted creation response, reloads the encrypted vault, and runs concurrent retries with one resulting two-member chat. No new cryptographic algorithm is introduced.

Initial testing found and fixed formatted-fingerprint serialization and textarea-label ambiguity. The first Firefox selection also hit the real five-logins-per-minute limit on its shared QA administrator; the test bootstrap now respects the 60-second retry window instead of weakening controls or clearing Redis. The initial results are retained as failure evidence. The full Chromium run preceded a final friendly-error wording correction and test-bootstrap improvements; the focused final checks cover that UI correction. Final backend tests also cover idempotent revocation (one audit record across retries), with the ordinary-member UI flow rerun against the updated API in Chromium and Firefox. Latest first-chat screenshots are from the selected desktop-browser run, not physical phones. No physical Safari/Android, public endpoint, carrier, complete accessibility/capacity or independent-security qualification follows from these results. Prior signed QA archives predate this revision and do not authorize its distribution.

## Prior: minimal server retention hardening

| Check | Observed result | Evidence |
|---|---|---|
| Backend full suite | 42 passed; includes per-device ACK/grace/epoch/revocation retirement, preserved proof/control history, stale-history HTTP 410, ephemeral-record cleanup, keyed rate labels, authenticated policy, JSON-only cache decoding/counters, safe worker errors and backup rotation dry-run/apply/corruption/symlink cases | docs/evidence/privacy-backend-tests.txt |
| Chromium full suite | 15 passed; existing direct/group/media/offline/restart/failover/TLS/UI checks plus actual browser MLS reload and new-epoch messaging after server ciphertext retirement | docs/evidence/privacy-chromium-results.json; privacy-chromium-tests.txt |
| Firefox selected suite | 8 passed; crypto, full integration, retirement/reload/rekey, EN/FA design/CSP and view-once media | docs/evidence/privacy-firefox-results.json; privacy-firefox-tests.txt |
| Final policy/UI checks | 3 passed after the final policy naming/copy update; settings, actual policy, disclosure, RTL/CSP and browser MLS retirement/rekey | docs/evidence/privacy-final-policy-ui-tests.txt; privacy-settings-browser-results.json; redesign-privacy-retention.png |
| Rust | 4 native tests passed; formatting unchanged | docs/evidence/privacy-rust-tests.txt |
| Schema/type/format | No pending migrations; Ruff check/format and TypeScript passed | Commands recorded in docs/security/server-data-retention.md; executable local outputs |
| Real migration | Disposable PostgreSQL 0007-to-0008 preserved consumed/unopened states and live capability, capped existing file TTL, refused unsafe rollback | docs/evidence/privacy-migration-test.txt |
| Real proxy | Pinned Nginx, trusted test-IP TLS; API/WS/web strip address headers and preserve auth/CSRF/media capability; synthetic markers absent from logs | docs/evidence/privacy-ingress-test.txt |
| Build | Next.js production build and API/web Docker builds passed | docs/evidence/privacy-api-image-build.txt; privacy-web-build.txt; privacy-web-image-build.txt; privacy-image-ids.txt |
| Gated local deployment | Compose upgrade healthy, migration 0008 applied, JSON cache and privacy maintenance verified; trusted TLS health remains crypto_ready=false/BLOCKED; PostgreSQL logging settings verified | docs/evidence/privacy-staging-deploy.txt; privacy-staging-status.json; privacy-staging-health.json; privacy-postgres-settings.txt |
| Pre-upgrade recovery | Encrypted backup restored into isolated networkless RAM-backed PostgreSQL using disposable local QA keys; no production qualification | docs/evidence/privacy-preupgrade-restore.txt |

The new migration and shorter retention are irreversible data changes; stop old
API/outbox/privacy before upgrade. Exact retained categories and backup/restore
limits are in docs/security/server-data-retention.md. Account/membership/signed
proof metadata and malicious-origin trust are not eliminated. A corrupted test
harness invocation was repaired before the successful complete browser run; it
was not a product cryptography failure. No physical Safari/Android, global
anonymity, physical erasure, external audit, OS-advisory clearance or production
capacity claim follows from these local results. Older evidence below describes
earlier source states; prior signed QA bundles do not represent this revision.

## View-once feature verification — 2026-10-24

These results supersede the older backend/browser counts below for this feature. No new independent security review, physical Safari/Android test or secure-erasure guarantee follows from them.

| Check | Result and scope | Evidence |
|---|---|---|
| Backend full suite | 31 passed; five view-once tests cover account-wide claim/retry/close, separate group recipients, wrong token/device/account, mode/scope/late join/revocation/crypto gates, CSRF, lease expiry/cleanup and identifier replay denial after TTL deletion. The concurrency test uses real PostgreSQL and distinct connections | docs/evidence/view-once-api-tests.txt |
| Backend checks | Ruff/format passed; no migration drift; migrations 0006/0007 applied locally | docs/evidence/view-once-api-checks.txt |
| Full Chrome regression suite | 14 passed on the finished code, including view-once cleanup assertions and the existing MLS/media/offline/restart/failover/TLS flows | docs/evidence/view-once-full-browser-tests.txt |
| Firefox subset | 7 passed: crypto/design/full integration and the real view-once photo/video flow | docs/evidence/view-once-firefox-tests.txt |
| Real view-once flow | Four approved MLS devices / three accounts; PNG render, real recorded WebM decrypt/play/automatic close, storage-failure stop before claim, second-device rejection, independent group view, no recipient chunk-cache entry, reload denial, local key redaction, plaintext/recovery export exclusion and old-history import rejection | apps/web/tests/view-once.spec.ts; view-once-photo*.png |
| Browser cleanup limit | Original Firefox cache probe exposed decoded-image retention after URL revocation. Final code clears the image source and final tests verify actual revocation/DOM cleanup, recording cache behavior without asserting secure memory erasure | docs/evidence/view-once-initial-firefox-cache-observation.txt; final browser logs |
| Build/TypeScript/format | Production build and checks passed | docs/evidence/view-once-build.txt; view-once-typecheck.txt; view-once-format.txt |
| Offline shell | Existing worker lifecycle harness passed; view-once API/media do not enter the shell cache | docs/evidence/view-once-offline-shell.txt |
| Container staging | API/web images built, migrations 0006/0007 applied with migration role; runtime new-table CRUD/sequence privileges verified; trusted TLS/new assets and original closed normal gates checked | docs/evidence/view-once-api-image.txt; view-once-web-image.txt; view-once-staging.txt |
| Release gate | Expected nonzero BLOCKED result; not an acceptance pass | docs/evidence/view-once-release-gate.txt |

View-once means one cooperating-client viewing session with durable server authorization, not guaranteed physical destruction. Opening is consumed before loading; failover/restore must preserve consumption state. The server learns opening access despite optional read receipts being off. New export exclusions cannot retract older/manual snapshots or captures. Linux WebKit's earlier general UI/MLS results do not qualify this new viewer or its codecs; physical device coverage and independent review remain outstanding. See docs/adr/0005-view-once-media.md. Existing signed QA archives predate this feature.

## UI redesign verification — 2026-10-24

The newer interface evidence below supersedes the older UI/browser counts for this source. Backend/native/upstream results below remain earlier evidence; they were not reclassified as freshly rerun UI tests.

| Check | Result | Evidence |
|---|---|---|
| Full Chrome regression suite | 13 passed, including real encrypted messaging/media/offline/restart/standby flows and two new design/CSP checks | docs/evidence/ui-redesign-browser-tests.txt |
| Firefox crypto/design/full integration subset | 6 passed | docs/evidence/ui-redesign-firefox-tests.txt |
| Linux WebKit | Genuine MLS/trusted-IP smoke passed; actual login/mobile navigation/dark/Persian RTL passed **with 3 reproduced native-select CSP engine warnings**. Other CSP violations fail. Physical Safari unqualified | docs/evidence/ui-redesign-webkit-tests.txt; docs/adr/0004-browser-csp-compatibility.md |
| Responsive/design checks | Widths 320–1440px; mobile popover/Escape, setup navigation, theme/RTL/local Persian font, reduced motion, no horizontal overflow or foreign network requests in tested flows | apps/web/tests/design.spec.ts; redesign-*.png |
| TypeScript / production build / format | Passed | docs/evidence/ui-redesign-typecheck.txt; ui-redesign-build.txt; ui-redesign-format.txt |
| Runtime npm audit | Zero reported vulnerabilities in the recorded scan; no independent security review implied | docs/evidence/ui-redesign-npm-audit.json |
| Token contrast | Seven selected foreground/background pairs passed WCAG AA normal-text ratio. This is not a complete accessibility audit | docs/evidence/ui-redesign-token-contrast.json |
| Offline dependency cache | Fresh disposable install followed by `npm ci --offline` from the refreshed cache | docs/evidence/ui-redesign-offline-npm.txt |
| Offline worker lifecycle | VM harness exercises shipped worker after restart with two existing build caches; current shell selected, old cache removed, unrelated cache retained, private/foreign requests bypassed, mismatched manifest rejected. Separate real Chrome test covers actual offline messaging | docs/evidence/ui-redesign-offline-shell.txt; ui-redesign-browser-tests.txt |
| Web container rebuild | Updated image built; exact resulting image and staging checks recorded separately | docs/evidence/ui-redesign-web-image.txt; ui-redesign-staging.txt |

CSP remains strict, arbitrary inline scripts/styles are tested as blocked, and the normal cryptography release gate remains closed. The previously signed 0.2.0 QA archive predates the redesign; it is not an artifact of this updated source. See docs/UI_REDESIGN.md.

## Executed evidence

| Command/check | Result and scope | Evidence |
|---|---|---|
| `bash scripts/test-local.sh` | Backend, Rust, TypeScript and complete Chrome suite executed; latest aggregate output is authoritative | docs/evidence/final-qa-v2.txt |
| API Ruff / migration drift / pytest | 26 backend tests passed; no migration drift. Some older transport fixtures mock public structure validation explicitly; real browser integration uses the native verifier without mocks | docs/evidence/backend-tests-v2.txt; final-qa-v2.txt |
| `cargo test --manifest-path packages/crypto-core/Cargo.toml --locked -j 2` | Four native tests: roundtrip/replay, native/browser golden fixture, 64 generated Unicode/serialization/replay cases and 64 generated public-parser frame cases | docs/evidence/rust-tests-v2.txt |
| `cargo fmt --check`; `cargo clippy --all-targets --locked -- -D warnings` | Passed recorded adapter checks | docs/evidence/rust-clippy-v2.txt; final-qa-v2.txt |
| `scripts/test-upstream-vectors.sh` | 205 passed, 3 ignored, 91 filtered at exact upstream VCS revision embedded in OpenMLS 0.9.2; ignored tests are not passed | docs/evidence/upstream-kats.txt |
| Chrome browser suite | 11 tests passed, including the raw-snapshot rollback characterization. That characterization is an observed limitation, not a passing rollback-prevention assertion | docs/evidence/final-qa-v2.txt |
| Extended actual integration | Direct/group MLS through Django/PostgreSQL; bidirectional text, signed-history tamper rejection, approved multiple devices, no automatic old history, revoke/remove/rekey, vault reload, fresh-identity recovery, lost ACK, concurrent commit reconciliation, fixed-snapshot/delta synchronization and historical certificate verification after revocation | docs/evidence/integration-final-v2.txt; extended-browser-v2.txt |
| Storage/media negatives | Forced IndexedDB failure leaves active crypto/revision unchanged; upload reload/resume; interrupted verified download resume; wrong key/nonce/altered chunk rejected before Blob | docs/evidence/integration-final-v2.txt |
| Real UI | Actual enrollment/fingerprint/group/text, WS-blocked HTTP fallback, reply/edit/delete, inert HTML payload, client-local search, synthetic microphone encrypted voice capture/transfer/decrypt/play, trusted offline shell/reload/queued send | docs/evidence/extended-browser-v2.txt; final-qa-v2.txt |
| Actual Redis stop | Real approved-session MLS reads from PostgreSQL while test Redis is stopped; write remains queued and delivers after restart | docs/evidence/process-redis-outage-v2.txt |
| Actual API process kill | Owned API SIGKILL after acceptance and lost response; browser reload retries exact ciphertext and recipient sees one logical message | docs/evidence/extended-browser-v2.txt; process-redis-outage-v2.txt |
| Firefox | Four crypto/golden/vault/full integration tests passed with explicitly trusted private NSS profiles; latest rerun file records current outcome | docs/evidence/firefox-integration.txt |
| Linux WebKit | Trusted raw-IP TLS and actual browser OpenMLS roundtrip passed in pinned isolated container; not physical iOS Safari | docs/evidence/webkit-mls-smoke.txt |
| TLS negatives | Fresh untrusted profile rejects CA; correct-root/expired-IP leaf rejects dates. No certificate bypass used | final-qa-v2.txt; browser test sources |
| UI/production builds | TypeScript and Next production build passed; container images built from pinned bases | docs/evidence/frontend-build-v2.txt; api-image-v2.txt; web-image-v2.txt |
| Runtime DB privilege/durability | Runtime cannot create tables, mutate migration history or SET ROLE migration owner; fsync/synchronous_commit/full_page_writes/data_checksums on in local container staging | docs/evidence/database-role-v2.txt |
| Stored ciphertext inspection | Real browser-test envelope/chunk data checked for known plaintext/name/file-pattern markers; observed dataset only | docs/evidence/ciphertext-storage-v2.txt |
| Encrypted backup/restore | GPG-encrypted server backup metadata path tested; separate isolated networkless restore recovered 449 actual browser-test ciphertext envelopes and 20 migrations; the gated staging DB backup was empty | docs/evidence/backup-v2.txt; restore-ciphertext-v2.txt; restore-browser-ciphertext-v2.txt |
| Prepared backup origin | Four distinct approved devices at two IP origins; real TLS bridge/WSS, wrong-name rejection, primary API/route stop, database-stop fencing/promotion, new messages and MLS epoch update | docs/evidence/standby-origin-result.json; failover-origin-db.json; standby-origin-test-v2.txt |
| Streaming failover | Real local PostgreSQL streaming standby caught up; primary explicitly stopped before promotion; ciphertext envelope/order hashes identical; actual count, controlled stop/promote/write duration and row-loss measurement are recorded in JSON | docs/evidence/failover-local.json |
| Offline application source build | Signed source/cache bundle verified; Python hash-locked wheels and npm offline cache rebuilt with network-disabled RUN steps using preloaded pinned base images and bundled prebuilt Rust/WASM artifacts | docs/evidence/offline-source-build-v2.txt |
| Container vulnerability scan | Pinned Trivy 0.76.1 scans tar inputs without Docker socket; app images moved to Debian 13, unused pip/npm removed. API 44 HIGH/58 MEDIUM/61 LOW/1 UNKNOWN; web 43 HIGH/58 MEDIUM/60 LOW/1 UNKNOWN; no critical/fixed versions listed; further OS triage required | docs/evidence/container-scan-v2.txt; *-container-audit-v2.json; container-before-remediation-v2.json |
| Dependency scans | Recorded runtime npm/Python scans have zero findings; Cargo.lock has two optional inactive libcrux-kem advisories plus maintenance warning | docs/evidence/npm-audit-v2.json; python-audit-v2.json; cargo-audit-v2.json; active-*-dependencies-v2.txt |

Exact browser versions are supplied by the installed binaries/Playwright 1.64.1, not inferred Safari compatibility. Test profiles contain synthetic users/content, generated secrets and local TEST CA material only. Screenshots under docs/evidence are UI evidence, not security assurance. Older failed/intermediate logs document development history and must not override the latest named aggregate result.

## Reproduce

Follow README.md and operations.md. Keep `make dev` and `make integration-dev` running, prepare isolated trust/QA accounts, then run `make test`. Build first and restart the local standalone snapshot before testing so the tested version is current. The server copy protects running files from later builds. Upstream vectors, optional Firefox/WebKit, encrypted restore, offline builds and failover are separate commands; they are not silently implied by a single npm test.

The process/Redis outage test affects only the owned additional test API and haven-test Redis; production/other projects are not targeted. Existing transport-only Redis fixture evidence is historical and does not by itself prove E2EE outage operation.

## Not passed / external or incomplete

Django deployment warnings W005/W021 concern domain/subdomain HSTS/preload and are inapplicable to raw-IP hosting; W008 is covered by TLS-only ingress and API HTTP rejection rather than a password-bearing HTTP redirect. These warnings are retained, not suppressed.

- Physical iOS Safari/Android trust, memory/KDF/media/storage/background behavior; complete screen-reader/keyboard/RTL device matrix.
- Complete official interoperability/property/fuzz/malformed/resource, malicious/censored fork, database rollback and sensitive-exception matrices. Checkpoint tamper checks are narrower than full global fork detection.
- Actual public-IP certificates, private CA phone trust, issuer renewal during international isolation, two independent domestic providers and Iranian carrier routes.
- Hardened production container execution on this host, verified private-tunnel/TLS replication, provider fencing and physical-user standby continuity. The two-IP prepared-origin path is locally tested.
- Fresh separate host/air-gapped installation, complete compiler toolchain rebuild and bit-for-bit artifact reproducibility; signed hash/source build is narrower.
- 100-user/500-session/20-message-per-second/five-file workload, p95 budgets, two-hour soak, reference-host thermals and production RPO/RTO.
- Independent cryptographic integration review, penetration test and owner release approval.

These omissions keep release qualification BLOCKED. No false all-tests-complete, wartime safety, independent audit or production capacity claim follows from local passes.
