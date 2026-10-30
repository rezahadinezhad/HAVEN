# Guided setup verification — 2026-10-30

Scope: new terminal installer and existing container application, on the development Linux x86_64 Docker engine. Synthetic administrator accounts and disposable isolated Compose projects only. This is not production or independent security qualification.

## Automated checks

- `make setup-test`: **13 tests passed**. Includes exact loopback/origin configuration, server compatibility refusal, dotenv injection refusal, owner-only files/symlink refusal, source-manifest tampering/coverage, namespace ownership refusal before secret creation, occupied port rejection, stale/unowned resume refusal without secret replacement, log redaction, real OpenSSL chain/IP/hostname/key checks, untrusted issuer rejection, remaining-validity rejection, CA-as-leaf refusal, and interrupted TLS generation.
- `ruff check scripts/setup.py scripts/tests/test_setup.py`: passed.
- `ruff format --check scripts/setup.py scripts/tests/test_setup.py`: passed.
- `bash -n setup.sh`: passed.
- Source/publication hygiene and Gitleaks checks passed; original input-spec SHA256 checks remain unchanged.

## Real Docker and HTTPS checks

1. Ran `./setup.sh --answers .local/setup-qa-answers.json` with an owner-only local-evaluation answer file, a unique project name, and port 8847. Explicitly chose local compatibility because this host rejects `no-new-privileges`. The wizard built both images, prepared PostgreSQL roles, applied all migrations including 0010, bootstrapped a random-password administrator through stdin, and started API/web/outbox/privacy/ingress plus the private database/cache. No host Node/Rust rebuild was required.
2. HTTPS verification passed with the generated test root, including configured IP identity, strict application CSP, local `crypto_ready=true`, `release_status=BLOCKED`, administrator login and probe logout. Container inspection showed only ingress published, on `127.0.0.1`; PostgreSQL/Redis/API/web had no published ports.
3. Ran `./setup.sh --resume wizard-qa-1030`. Completed again. SHA256 comparisons showed configuration, administrator credentials, leaf private key and test CA private key unchanged.
4. A separate attempt on the occupied port was rejected before recording ownership or saving generated secrets. Existing services were not stopped.
5. Ran a separate gated-server configuration with a matching test certificate/key and explicit public root bundle. Certificate validation passed; the real hardened-container probe failed on this host. The installer refused reduced server hardening. No server-project containers or database volume were created. **A successful hardened server installation is not claimed.**
6. On a third isolated local project, used a test-only Docker CLI shim to return a failure immediately before the migration command. The wizard stopped after role preparation and preserved state/database storage. Removed the fault injection by using the normal CLI and ran `./setup.sh --resume wizard-retry-qa`. Migrations, bootstrap, startup, verified HTTPS and administrator authentication then passed. Secret/key/configuration hashes were unchanged across the failure/retry.

The development machine's existing HAVEN and unrelated project stacks were not targeted. QA stacks were removed after verification; generated private state was not published. Formatting-only installer edits and documentation updates followed these runtime checks; the final unit/static/source checks cover those edits. The recorded source hashes in private setup state bind resume to each exact tested checkout, rather than silently accepting a changed release.

## Actual browser checks

Used Python Playwright 1.56.0 as disposable QA tooling with the installed Google Chrome executable, **Chromium sandbox enabled**, and the wizard's generated isolated NSS/browser-home trust profile. No certificate-ignore setting or sandbox bypass was used.

- Trusted `https://localhost:8847/` loaded and rendered the sign-in screen.
- Generated administrator credentials signed in through the UI.
- The welcome screen's **Set up this device** action opened **Set up this browser**. The first assertion originally expected that form without selecting the action; inspecting the actual landing screen and following its button corrected the test expectation. No application fix was needed.
- The session cookie was Secure, HttpOnly and SameSite=Strict. Strict CSP was present and observed application requests stayed on the local origin.
- A fresh browser HOME without the test root rejected the same URL with `ERR_CERT_AUTHORITY_INVALID`.

No fresh full messaging/API/Rust suite is implied by these installer smoke tests. No physical phone, public-IP certificate issuance, external reachability, certificate renewal, backup scheduling, automatic upgrade, independent review or production load was qualified. The normal release gate remains blocked.
