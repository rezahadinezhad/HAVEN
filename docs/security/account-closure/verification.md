# Verification — 2026-11-03

This is local engineering verification of operational product behavior, not independent certification or a remote deployment. Evidence files are retained under [evidence](evidence/).

| Check | Result and scope |
|---|---|
| Backend milestone | **166 passed in 104.01 s**, real PostgreSQL/Redis; [log](evidence/backend.txt). |
| Final focused backend | **30 passed in 27.58 s** after final media/restore hardening; account closure, legacy closure, graph retirement and view-once; [log](evidence/backend-final-focused.txt). Counts overlap the milestone suite. |
| Installer | **13 passed**; independent-key generation/redaction, scoped services, TLS and resume safeguards; [log](evidence/installer-final.txt). |
| Chromium | **3 passed in 50.2 s**; two closure workflows and the broader native MLS integration; [log](evidence/browser-final-chromium.txt). |
| Firefox | **2 passed in 1.2 min**; direct archive/offline recovery and multi-device group retirement; [log](evidence/browser-final-firefox.txt). |
| Production client build | Passed with the normal operational UI; [log](evidence/web-build.txt). |
| Typecheck / lint | Passed; [TypeScript](evidence/typecheck.txt), [Python](evidence/lint.txt). |
| Schema / inventory | No migration drift; Django checks pass; **206 current and 8 retired fields** classified; [checks](evidence/django-checks.txt), [inventory](evidence/inventory.txt). |
| Normal activation | All three source defaults enabled; [activation check](evidence/activation.txt). |
| API image | Hash-locked Python 3.14 image built using prepared matching offline wheels; network-disabled build; [log](evidence/api-image-build-offline-final.txt). Container Django check and normal API startup with the read-only journal/runtime pool passed; [check](evidence/api-image-check.txt), [startup](evidence/container-api-startup.txt). |
| Compose | Passed: bounded normal worker, read-only API journal and secret isolation; [log](evidence/compose-check.txt). |
| Independent journal container | Explicit initialization and non-root read-only authenticated read exercised on a new disposable bind directory; [log](evidence/container-journal.txt). |

## Tested behavior

Backend cases use real account/device signatures and native MLS messages. They cover account rather than device quorum; whole-account write fencing before global freeze; unanimous groups; former-member public proof access without later ciphertext; changed authority; final receipt requirements; exact accepted retries; media deletion and permanent attachment tombstones; an active view-once lease delaying retirement and its permitted settlement after finalization; invalid restore authority; replay budget refusal before journal publication; journal corruption; journal-published/SQL-rollback recovery; and restoring SQL from before the conversation existed.

The browser direct-chat workflow saves ordinary messages/files, injects local-save and lost-response failures, advances the shared head with an offline queued peer send, reprepares without discarding prior archive bytes, persists the final certificate before receipt, exports/imports the encrypted archive and rejects the wrong passphrase. It checks archive-record ciphertext reuse on unrelated draft saves, offline lock/reload/unlock, real English/Persian product UI and downloaded local files after SQL retirement. It invokes **`haven.settings` and the normal `retire_conversations` worker**, not the nonce-guarded synthetic wrapper.

The group workflow uses three accounts and four devices. The owner account's second participating device proposes/prepares/consents, while its first device stays offline with a queued message. Three account signatures/receipts suffice; the returning device preserves its unconfirmed message/wire request read-only. The broader Chromium regression exercises native group creation, delivery/retry, ordinary media, removal and reload.

## Attempt notes and limits

A first Firefox offline-worker attempt failed after Playwright interception had disabled the ordinary HTTP cache. A later fault-injection route was also still active and kept HTTP caching disabled; the fixture now removes all routes and exercises an ordinary online native vault unlock/lock before the offline worker restart, matching normal account use; it still verifies cached offline shell assets and creates a fresh worker offline. A later back-to-back attempt hit the real administrator invitation rate limit; [attempt log](evidence/browser-firefox-rate-limit-attempt.txt). No API limiter was disabled or reset to make a browser test pass. Backend pytest uses a separate Redis database to avoid its autouse cache cleanup racing browser admission checks.

The initial ordinary Docker build with network disabled could not download dependencies; the network-enabled retry failed Docker DNS resolution. A first offline fallback used old Python 3.12 wheels and correctly refused Python 3.14 binary dependencies. The successful build uses the previously prepared matching Python 3.14 wheels, the same locked hashes and the same pinned base/source/verifier. [Initial offline attempt](evidence/api-image-build.txt), [network retry](evidence/api-image-build-network.txt), [wheel mismatch](evidence/api-image-build-offline.txt). No dependency pin or integrity check was relaxed.

No new prolonged load/soak test, physical iOS/Android test, Safari qualification, independent security assessment, real provider failover or public remote deployment was run. Earlier workload results are historical measurements, not a capacity qualification of these archive/deletion changes. Existing `haven-*` containers were left untouched; only isolated test services/listeners and disposable journal directories were used. Older prototype evidence remains historical and is not relabeled as this implementation.

The [source snapshot](evidence/verified-source.sha256) identifies reviewable files outside this report directory. `SOURCE_MANIFEST.sha256` additionally covers this report and its final evidence. Both were verified before committing.
