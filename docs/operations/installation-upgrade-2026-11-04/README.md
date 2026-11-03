# Maintained installation upgrade — November 4, 2026

**Completed.** The existing `haven` installation at **https://127.0.0.1:8444** now runs normal messaging, account-wide closure and the regular retirement worker. Its API reports `ACTIVE_REVIEW_PENDING`, messaging/closure enabled and no maintenance message. This supersedes the earlier “existing running installation was not upgraded” statement.

This is the maintained **local** installation. Its explicit loopback compatibility overlay remains necessary on this Docker host; it does not establish public-host hardening or independent security certification.

## What changed

The installation was still using the November 1 review images and schema through migration 0012. It had no accounts, devices or conversations. The upgrade:

- Stopped the API, client, notification/privacy workers and ingress before taking the backup and migrating.
- Created an encrypted SQL backup and restored it into a separate networkless, RAM-backed PostgreSQL instance. All 30 original table counts and SHA-256 fingerprints matched.
- Preserved existing application/database credentials; supplied missing independent routing, notification and permanent retirement secrets in the protected environment file.
- Provisioned separate migration/runtime/notification roles and applied migrations 0013–0020 with durability checks.
- Initialized retirement for the first time, after verifying no established journal or retirement exclusions existed. The role/migration one-offs created the new empty volume before explicit initialization; no existing journal was overwritten.
- Started the regular retirement worker with a writable journal mount, the API with a read-only mount, and notification/privacy workers without retirement key or journal access.
- Renewed the short-lived **TEST** leaf certificate under the unchanged TEST root, preserving the existing private browser trust. No system/personal trust-store change or TLS-verification bypass occurred.
- Started matching `haven-api:release-20261104` and `haven-web:release-20261104` images. API code is from activation commit `8545a76`; the client includes the interface cleanup in this upgrade.
- Created the first owner account, with generated credentials stored only in a mode-0600 file in the operator's protected local state. The installer does not generate a browser vault passphrase or client message keys.

The backup key is kept separately from encrypted backup storage. Protected pre/post environment files, prior image IDs and TLS material are retained locally. The newly initialized journal also has a separately encrypted, authenticated backup. These are initial upgrade recovery copies; no scheduled independent off-host backup service is claimed.

## Interface and project organization

The normal interface no longer displays a permanent warning banner or raw `UNREVIEWED`/`CRYPTO_NOT_READY` footer label. Independent review remains disclosed on sign-in and in security information. The warning banner appears when the service actually reports messaging unavailable; maintenance messages remain separate.

Root status, verification, security policy, release checklist, contributor and agent-entry documents now describe the current product. Old dated status snapshots and the previous release checklist are preserved under [project history](../../history/README.md). The original architectural specification and historical security evidence remain available. Current operator/onboarding instructions describe operational messaging, journal initialization and restore requirements.

## Verification

| Check | Observed result |
|---|---|
| SQL recovery copy | AES-256-GCM backup authenticated and restored in isolation; all 30 original table fingerprints/counts matched |
| Live schema/roles | Through `0020_closure_retirement_queue`; runtime is unprivileged and denied schema DDL/migration-history writes |
| Notification isolation | Delivery view readable; actual ciphertext read denied; no account/device table read privilege |
| Journal | Authenticated key file; API mount read-only, worker writable; no key/mount in notification or privacy services; initial encrypted backup authenticated |
| Services | API healthy; API/web/outbox/privacy/retirement/ingress/database/Redis running; [runtime inventory](evidence/installed-runtime.json) |
| Trusted-TLS Chromium | **1 passed in 3.6 s**; login, enabled setup, clean notices, dark theme, Persian RTL/mobile, no overflow or foreign requests; [log](evidence/browser-chromium.txt) |
| Trusted-TLS Firefox | **1 passed in 8.8 s**, same installed-product workflow; [log](evidence/browser-firefox.txt) |
| Source binding | Critical API source hashes match the running image; current client build inputs and TEST leaf validity recorded in [binding evidence](evidence/source-binding.json) |
| Optimized configuration validation | **11 passed in 0.65 s**, including required-key fixture and rejection cases; [log](evidence/validator-regression.txt) |
| Source/build | Pinned production web image built offline from lockfile/cache; TypeScript passed; 13 installer tests passed; rendered worker configuration passed |

Browser tests use the actual installed endpoint and native certificate verification. They confirm the unavailable-service banner through a browser-scoped simulated health response, then reload the actual healthy service. They do not create browser identities, seed conversations or send test messages into this installation. Prior native/Chromium/Firefox protocol and real deletion evidence remains in the [activation verification](../../security/account-closure/verification.md).

An initial browser attempt reached login/settings but its test-only Node `route.fetch` did not trust the private CA. The fixture now reuses the health response already fetched through the trusted browser for its simulated outage. No TLS check was weakened. The retained [initial attempt](evidence/browser-initial-attempt.txt) has authentication headers redacted. Short-lived probe sessions were revoked after verification.

The initial CI run found one missed environment-validator test fixture: it omitted the newly required retirement secret. The fixture was corrected, with added optimized-Python checks rejecting missing, short, placeholder and reused keys. The validator itself remained strict. [Initial CI result](https://github.com/rezahadinezhad/HAVEN/actions/runs/41733747447); 169 other API tests passed in that attempt.

The owner account still needs its first browser setup and a privately saved recovery kit. Existing browser tabs may need to close/reopen to activate the new offline shell; never clear vault storage as an upgrade step. Certificate renewal and public/physical-device qualification remain operator work recorded in [security status](../../../SECURITY_STATUS.md).

## Operate and recover

The active installation uses the protected root `.env` and both Compose files:

```sh
docker compose -p haven --env-file .env \
  -f infrastructure/compose/compose.yml \
  -f infrastructure/compose/local-staging.yml ps
```

Use the same files for this local installation's `start`, `stop` and `logs`. Do not omit the local overlay and accidentally expose or recreate the stack on port 443. Do not recreate credentials or initialize a replacement journal during an ordinary restart. Image/configuration changes require coordinated rebuild/recreation; old source snapshots and old image tags remain historical recovery references.

Migrations remove obsolete metadata and add permanent replay exclusions. A blind code/schema downgrade is unsafe. If recovery becomes necessary, stop/fence every writer, verify the protected encrypted backup and use an isolated restore first; retain the latest independent journal and original key. Reapply matching roles/migrations and reconcile before ingress resumes. Follow [retirement restore operations](../../security/account-closure/operations.md) and the [main runbook](../../runbooks/operations.md).
