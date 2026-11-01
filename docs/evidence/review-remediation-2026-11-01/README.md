# Remediation verification — 2026-11-01

Base revision: `61d77683d140daf26e087bd4c2f1971b7a2a97c1`, plus the reviewable remediation patch and regenerated `SOURCE_MANIFEST.sha256`. The original review evidence is retained separately. All accounts, messages, certificates and databases used here are disposable test data. No production deployment or system trust-store change was performed.

| Check | Final result | Evidence |
| --- | --- | --- |
| Complete PostgreSQL/Redis API suite | 78 passed | `api-tests.txt` |
| Complete Chromium suite with preserved provider fixtures | 37 passed; 2 optional cases skipped | `chromium-full.txt`, `chromium-results.json` |
| Firefox storage, malformed-message and provider compatibility regressions | 8 passed | `firefox-regressions.txt` |
| Opt-in trusted-hostname PRF unlock UI | 1 passed separately | `hostname-ui.txt` |
| Native Rust suite | 4 library tests passed; binary/doc suites empty | `rust-tests.txt` |
| Installer and TLS tests | 13 passed | `installer-tests.txt` |
| Pinned real Nginx forwarding/privacy test | Passed | `ingress.txt` |
| Standby Compose render checks | Passed | `standby-render.txt` |
| Production Next build/typecheck | Passed | `web-build.txt`, `checks.txt` |
| npm full graph (including development tools) | Zero vulnerabilities | `npm-audit.json` |
| Python full pinned graph (including development tools) | No known vulnerabilities | `python-audit.txt` |
| Rust full lockfile | No known vulnerabilities; one maintenance notice in conditional proof tooling | `rust-audit-summary.json` |
| Reviewable worktree secret scan | Passed using checksum-verified Gitleaks 8.30.1, existing rules, redacted output | `secret-scan.txt` |
| Source and worker hashes | Passed | `checks.txt`, root source manifest and `../crypto-assets.sha256` |

The complete browser run skipped the optional hostname workflow, which passed separately, and the opt-in documentation screenshot-capture workflow, which is not needed for this remediation. The preserved `.local/rust-remediation` assets were available and both previous/new provider compatibility checks ran, rather than remaining skipped. Physical authenticator/mobile and cross-host production capacity were not tested. WebAuthn UI checks use Chromium's virtual authenticator.

The Chromium suite includes real API SIGKILL/restart, exact-ciphertext retry, Redis outage/recovery, verified distinct-origin TLS, fenced disposable database promotion, continued real MLS delivery, session revocation, encrypted media/view-once and offline reload. New focused tests cover >16 MB encrypted history, incremental record reuse, atomic failure injection, authenticated record substitution, legacy migration, history-only export, secret rotation, Web Lock/hash cancellation, malformed application quarantine followed by valid traffic, fatal bad ciphertext, and pagination traversal.

The real Nginx test verifies that all caller-provided address headers are stripped on ordinary routes, while login forwarding uses the observed transport peer. Source values are not added to persistent application data or logs. The standby drill requires explicit test-only database provenance before copying data; the source was the isolated `haven-remediation` project.

Earlier intermediate runs exposed a lost-ACK freshness bug in the new optimization and two default-project/stale-certificate fixture problems. Those were corrected before the final full run; they were not converted into skips. A documentation phrase resembling a credential was reworded after scanner inspection; no new scanner exclusion was added. Original test fixtures/certificates were preserved under protected local backup directories before disposable certificate renewal.

## Reproduction

Use the repository's pinned dependencies and prepared trusted test browser. The new backend tests require PostgreSQL and Redis, not SQLite substitutions. For an isolated stack named `haven-remediation`, the final browser invocation was:

```bash
COMPOSE_PROJECT_NAME=haven-remediation \
HAVEN_DRILL_SOURCE=haven-remediation-db-1 \
HAVEN_PROVIDER_COMPAT_DIR="$PWD/.local/rust-remediation" \
npm test --prefix apps/web
```

The database source must carry the explicit test-only label supplied by `infrastructure/compose.test.yml`. Provider compatibility assets are local engineering fixtures; environments without them must report those skips honestly. The hostname case uses `bash scripts/device-unlock-qa.sh`, which keeps certificate validation enabled and temporarily starts only a loopback test stack.

Other verification commands are the standard repository commands: pytest from `apps/api` with the protected local test environment, native Cargo tests with `--locked`, `make setup-test`, `python3 scripts/test-privacy-infrastructure.py`, `npm run typecheck --prefix apps/web`, `npm run build --prefix apps/web`, and the dependency audit commands. See the [upgrade and operational limits](../../security/review-remediation-2026-11-01.md).

## Authorized staging upgrade

After source verification, the owner requested the actual migrations and rollout. [staging-upgrade.json](staging-upgrade.json) records the completed upgrade of the existing loopback `haven` deployment: verified encrypted backup/isolated restore, original-row preservation across 29 tables, expected metadata additions, migrations 0011/0012, independently verified accounting, matched image/source hashes, least-privilege runtime access, live TLS/CSP/assets and browser rendering. All seven long-running services remain running with zero restarts. Private backup files, recovery keys, configuration snapshots, detailed fingerprints and operational logs are retained outside the checkout and are excluded from this evidence directory.
