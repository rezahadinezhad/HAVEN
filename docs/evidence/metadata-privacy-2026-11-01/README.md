# Metadata privacy validation — 2026-11-01–02

Baseline `0240706`, branch `codex/metadata-privacy-hardening`. All accounts, messages, media and databases in these checks are synthetic local QA. No production/staging deployment or deletion of existing backups. Raw keys, account credentials, browser snapshots, original fixture dumps and detailed child logs stay under `.local`, not here. The evidence folder uses the initiative's start date; final report is dated November 2 in Asia/Tehran.

Log line endings/trailing whitespace are normalized for repository review; test results, failed assertions and diagnostic content are preserved.

## Authoritative checks

| Check / actual command | Result and evidence |
|---|---|
| `cd apps/api && .venv/bin/pytest -q` with exported `.local/test.env` | Baseline 78 passed (`baseline-api.txt`); final 84 passed (`api-verification.txt`, also `api-final-index.txt`). Actual PostgreSQL/Redis, including concurrent cleanup/complete and group TTL/revocation |
| Ruff / format / `manage.py makemigrations --check --dry-run` | Passed; migration drift `migration-drift-final.txt`; script checks `script-checks.txt` |
| `cargo test --manifest-path packages/crypto-core/Cargo.toml --locked -j 2` | Five library tests pass (`rust-final.txt`), including generated Unicode/replay/frame cases and legacy padding/tamper/max-size/rekey. Native fixture generated locally for browser interoperability |
| `cargo clippy --manifest-path packages/crypto-core/Cargo.toml --locked --all-targets -- -D warnings`; `cargo fmt ... --check` | Passed (`clippy-final.txt`); formatting checked |
| `bash scripts/test-upstream-vectors.sh` | 205 passed, three ignored, 91 filtered (`upstream-vectors.txt`). Ignored cases are not passes |
| `bash scripts/build-crypto.sh`; `NEXT_TELEMETRY_DISABLED=1 npm run build --prefix apps/web` | WASM and final production web build pass (`wasm-build.txt`, `web-build-final.txt`); regenerated contracts and TypeScript pass (`typecheck-final.txt`) |
| `HAVEN_PROVIDER_COMPAT_DIR="$PWD/.local/rust-remediation" npm test --prefix apps/web -- --reporter=list` | 38 passed, two skipped (`chromium-complete.txt`): hostname PRF and opt-in documentation capture; old/new provider tests enabled |
| `HAVEN_BROWSER=firefox HAVEN_PROVIDER_COMPAT_DIR="$PWD/.local/rust-remediation" npm test --prefix apps/web -- --reporter=list` | 34 passed, six skipped (`firefox-verified.txt`); four Chromium-CDP PRF tests, hostname PRF and documentation capture are explicitly unsupported/optional, not silently passed |
| `bash scripts/device-unlock-qa.sh` | One passed (`hostname-prf.txt`), including trusted hostname, exact Host/Origin negatives and virtual PRF; no physical biometric qualification |
| `python3 -m unittest discover -s scripts/tests -v` | 13 installer/TLS tests pass (`installer-tests.txt`) |
| `python3 scripts/test-privacy-infrastructure.py` | Real pinned Nginx, verified IP TLS, address-header stripping/login overwrite, no synthetic markers in logs (`ingress.txt`) |
| `bash scripts/test-webkit-container.sh` | Real trusted-IP TLS + OpenMLS WASM pass in isolated Linux WebKit (`webkit-smoke.txt`), not physical iOS Safari |
| `cd apps/web && node scripts/test-offline-shell.mjs` | Existing shipped-worker lifecycle harness passes (`offline-shell-final.txt`), cache isolation and mismatched-manifest rejection retained |
| `apps/api/.venv/bin/python scripts/check-metadata-inventory.py` | 190 current plus eight retired fields covered, no record values read (`inventory-check.txt`) |
| `apps/api/.venv/bin/python scripts/test-metadata-migration.py` | Actual synthetic pg_dump/restore, 0012→latest, cleanup, invariant-field hash, reverse refusal and restart idempotence pass (`migration-comparison.json`) |
| `apps/api/.venv/bin/python scripts/test-privacy-migration.py` | Existing 0007→latest view-once consumption/TTL migration and unsafe rollback refusal pass (`legacy-migration.txt`) |
| Actual PostgreSQL `EXPLAIN` in scoped transaction with sequential scans disabled | Partial expiry index is eligible (`cleanup-index-plan.txt`); not production query-plan/capacity evidence |
| Native baseline/current benchmark example | Nine sizes × 40 roundtrips × three alternating runs (`paired-*.json`, `performance-summary.json`); actual wire/CPU/RSS/latency, no state/keys emitted |
| `apps/api/.venv/bin/python scripts/benchmark-metadata-delivery.py` | Actual browser TLS/MLS/durable send/sync, encrypted vault writes, WSS connect/heartbeat, API CPU/RSS, PG counters and HTTP body comparison (`delivery-performance.json`, repeated in `delivery-performance-recheck.json`); 30 verified messages per isolated API |
| Python/npm/Cargo advisory audits | No known vulnerabilities reported (`python-audit.txt`, `npm-audit.txt`, `cargo-audit.txt`); existing proc-macro-error2 unmaintained warning remains, not suppressed |
| `python3 scripts/check-crypto-vendor.py` | Provider source integrity passes (`provider-integrity.txt`); vendored code not changed |
| `python3 scripts/repository-safety.py`; public-source Gitleaks; source manifest | Final outputs `repository-safety.txt`, `secret-scan.txt`, `source-manifest.txt`; raw private environment is excluded from export |
| Normal settings and release command | Normal `CRYPTO_READY=False` rejects crypto operations (`normal-gates.txt`); `python3 scripts/release-gate.py` exits one/BLOCKED (`release-gate.txt`). This is expected gating, not release acceptance |

The browser matrix includes real MLS/epochs/rosters/signatures, pinned identities, encrypted segmented persistence, sync/ACK after durable storage, malformed-content quarantine, exact outbox retry, process-kill and Redis-outage recovery, media/view-once and fenced disposable promotion. The rollback test remains an explicit characterization of a known release-blocking limitation. Passing it is not proof of rollback prevention.

## Failures and remediation retained

- `final-api.txt`: 80 passed/two failed because old migration tests reversed across intentionally irreversible 0013. Tests now use separate forward-only real PostgreSQL databases. Original revocation/backfill assertions and the reverse gate remain; later 84 pass.
- `firefox.txt`: initial 26 passed/six failed/eight skipped. Some old tests bypassed the private trust fixture; Chromium-only microphone permission was unsupported. Corrected fixture imports and Firefox synthetic capture, retaining actual TLS validation.
- `firefox-rerun.txt`, `firefox-messenger-final.txt`, `firefox-messenger-permission.txt`: UI timeout at disabled controls. Direct probes found `navigator.storage.persist()` awaiting an unattended browser permission prompt, including after Playwright permission grants. Mozilla's own storage-prompt test preferences answer it in disposable test profiles; no IndexedDB/crypto or TLS bypass.
- `firefox-messenger-mime-failure.txt`: the next focused run failed to find a playable voice note. Real MediaRecorder probe showed `mimeType=''` after stop while output Blob.type was `audio/ogg; codecs=opus`. The client now retains the Blob MIME/extension; final full UI/playback checks use the rebuilt application.
- `chromium-final.txt`: 35 passed/one failed/four skipped. Existing negative AEAD test replaced a Base64 character with A, sometimes leaving the ciphertext unchanged. It now flips an actual decoded byte, preserving the rejection assertion. Final Chromium crypto rerun passes. An initial version of the new decoder used standard Base64 and failed on URL-safe characters in Firefox (`firefox-complete.txt`: 33 passed/one failed/six skipped). The decoder now preserves the vault’s URL-safe encoding; final full Firefox verification is `firefox-verified.txt`.
- `offline-shell-initial-command.txt`, `offline-shell-initial-cwd.txt`: wrong executable/path and then wrong working directory, corrected with the existing Node harness; final lifecycle check passes.
- Newly generated 0014 initially failed format check; Ruff formatting was applied before successful full checks. Script formatting/import placement was corrected and the actual migration drill rerun; no check was disabled.
- An initial delivery benchmark runner left stdin open after measurement, keeping its child alive. That run was terminated, cleaned its own disposable DB, and is not measurement evidence. Bounded communicate now closes input and the recorded completed comparison exits normally. Initial native baseline rebuild also reused a stale shared Cargo target; accepted paired runs assert distinct expected wire lengths and binary hashes. No invalid run contributes figures.

## Reproduction and limits

Use only the test environment and test-only database container. Run `bash scripts/dev.sh`, prepare private test trust/accounts, and `bash scripts/integration-dev.sh`. Rebuild/restart standalone web snapshots after client changes. See the [controlled upgrade](../../security/metadata-privacy/upgrade.md), [performance methodology](../../security/metadata-privacy/performance.md) and [complete report/checklist](../../security/metadata-privacy/report.md).

A dump still reconstructs all membership edges in the synthetic comparison. Application content confidentiality is conditional on endpoint/key/origin integrity. No complete anonymity, ISP/nationwide correlation defense, physical erasure, production load/soak/battery guarantee, formal cryptographic proof or independent audit follows from these local checks. Logical schema/row retirement does not erase historical backup/WAL/provider copies. Production remains blocked.
