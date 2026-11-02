# Metadata continuation evidence — 2026-11-02

Production remains BLOCKED. This directory contains synthetic/local aggregate evidence only. Private database dumps, cookies, keys, provider snapshots and child logs remain under owner-only `.local` paths and are not published. Historical original hardening evidence is in `../metadata-privacy-2026-11-01`.

## Reproduction and results

Export `.local/test.env` for backend/test infrastructure commands. Run from repository root unless stated. The tables distinguish final completed checks from development trials and failed targets. Source and evidence hashes bind the reviewable artifacts; no production acceptance is inferred.

| Command / check | Recorded result |
|---|---|
| `cd apps/api && .venv/bin/pytest -q` initial baseline | 84 passed in `baseline-api.txt` |
| Controlled stale ACK/view-once races before fix | Expected failures: accepted 200 versus required 403; `authorization-before-corrected.txt` |
| Controlled real MLS Add versus target revocation before fix | Expected failure: accepted 201 versus required 403; `membership-race-before-status.txt`; earlier lock-observation reproduction also retained |
| Authority + credential regressions | Passing targeted runs; `authorization-after.txt`, `authorization-regressions.txt`, `native-authority-boundaries.txt` |
| Pending enrollment first test | One test import error, two passes; corrected without weakening assertions; `pending-enrollment-first.txt` |
| `pytest` full request/account/target fence and recovery stage | 101 passed in `api-full-fences.txt`; shared-group/body additions then 103 passed in `backend-final.txt` |
| SQL projection full existing suite | 103 passed in `api-projected-auth-first.txt`; added SQL privacy tests pass eight cases in `projected-query-tests.txt`; final combined 111-test suite passes in `api-final.txt` |
| Handled/PG/Redis/unexpected failures and lock order | `fault-fences.txt`, `rekey-lock-order.txt`, fresh recovery ID rejection/success in `pending-recovery.txt` |
| `apps/api/.venv/bin/python scripts/test-metadata-migration.py` | Final `migration-final.json`: real synthetic dump/restore, invariant hashes preserved, pending account link 1→0 / marker 0→1, reverse refusal and repeat safe |
| `apps/api/.venv/bin/python scripts/check-metadata-inventory.py` | Final `inventory-final-verified.txt`: 191 current / eight retired fields, declared source-line drift check |
| Native Rust test/format/Clippy | `rust-final.txt`: five library tests pass, no warning suppression; helper builds with locked dependencies |
| `apps/api/.venv/bin/python scripts/test-privacy-infrastructure.py` | `infrastructure-final.txt`: real pinned Nginx + verified IP TLS; header scope/log markers pass |
| `npm run typecheck --prefix apps/web` | Final `typecheck-final-verified.txt` passes; `web-build-verified.txt` production build passes |
| Playwright `privacy.spec.ts` substring, Chromium/Firefox | Two tests pass in each: padded MLS plus retention and actual synthetic PG head rewind; `chromium-retention-rollback.txt`, `firefox-retention-rollback.txt` |
| Initial browser command | Incorrect duplicated path from app workdir; `browser-command-path-error.txt`; corrected command above runs successfully |

## Load instruments and honest scope

Build `cargo build --manifest-path packages/crypto-core/Cargo.toml --release --example protocol_client --locked -j 2`. Run `apps/api/.venv/bin/python scripts/benchmark-metadata-isolated.py --revision 0240706 --seconds 120 --rate 2` and the same with `--revision current`. The orchestrator creates only its own labelled loopback containers on 55434/56381/8115/8452/8454 and removes immutable owned IDs. It uses disk-backed PostgreSQL with fsync/synchronous commit/full-page writes/checksums and timing counters, real supplied Nginx pacing/connection/storage limits, separate actual loopback source per account and a byte-counting TLS-transparent relay. No existing HAVEN deployment is modified. One API process; shared host, native driver, test fixtures, cold HTTP connections after ingress keepalive expiry. This is not 500 physical/browser devices, login/enrollment load, physical battery/thermals, whole ISP/TCP/IP bandwidth or production SLA qualification.

`load-baseline-2mps.json` / `load-current-2mps.json` completed 240 sends and 2,160 durable recipient deliveries each, with 500 WebSockets and zero socket errors. These early paired trials used `max_connections=150` in both isolated PG instances; they precede final SQL projection and are labelled development measurements, not final production-limit capacity evidence. The final harness retains the PostgreSQL default 100 and records actual settings. Their native client/padding was the same for both APIs; native old/new padding costs are separately measured in original evidence. Shared-host foreground verification also ran around these development trials, so no causal speedup follows.

`load-rekey-validation.json` deliberately rekeys every two application messages per group: 175 accepted / 1,575 durable recipient deliveries / 50 real verified MLS updates, no WebSocket errors, successful encrypted checkpoint restore; **NOT_SUSTAINED** at 2 messages/second under that deliberately frequent/synchronized control workload. It stopped offering new work at ten seconds of schedule lag and drained generated messages. That is not a throughput pass. Normal endurance uses one update per 100 application messages/group, disclosed in each result.

`load-harness-development.txt`, `load-development-abort.txt` and `soak-development-interrupt.txt` retain harness errors/interrupted trials. The first overload also lost sockets and is NOT a pass. The first endurance attempt was intentionally interrupted when second-pass review led to SQL minimization; it is NOT two-hour evidence. No partial/interrupted run is relabeled as complete.

Final stress/endurance and suite outputs below were inspected after completion. Native checkpoints are AES-GCM encrypted and fsynced before ACK, with a protected local fixture key outside the DB. A persisted encrypted checkpoint is restored through the native provider. This does not establish production browser/passphrase key custody; browser IndexedDB/crypto regressions are separate. Five concurrent native 1 MiB XChaCha20-Poly1305 attachment roundtrips use the existing media format, while actual browser file-key delivery is covered by browser integration tests.

All published hashes exclude `.local`; evidence digests bind published aggregate outputs. Tests/self-review are not an independent third-party audit.


## Final source verification updates

- `api-final.txt`: **111 passed** on PostgreSQL/Redis, with Ruff/format and no migration drift. This supersedes earlier intermediate suite counts. `challenge-privacy-final.txt` passes all five scoped-context/legacy/oracle/unknown-version cases.
- `migration-final.json`: forward through 0016 preserves selected invariant hashes, including an old raw 64-hex session challenge; reverse refuses before any shortening/marker deletion and retry is safe.
- `retention-backlog.json`: actual 10,000 expired pending devices, 20 deleting batches of at most 500 plus an empty pass, 209.33 seconds total on this co-located host. The real planner selects `pending_device_expiry` without disabling sequential scans; candidate selection returns 500 in 0.434 ms on this warm fixture. Zero Device rows/10,000 ID-only markers remain. Allocated Device relation bytes increase slightly after logical deletion; no disk erasure/reclamation is inferred.
- `chromium-complete.txt`: **39 passed, two optional skips** with provider compatibility enabled. Updated browser tests observe real worker sign operations without replacing cryptographic verdicts; malformed device/domain/key challenges cause zero sign/complete operations, then a valid reconnect signs once.
- `firefox-full-v2.txt`: intermediate incompatible v2-wire attempt failed 14, passed 20, skipped six. The browser's strict signing-oracle guard correctly rejected the changed grammar. Final source retains that exact validator and uses a scoped decimal HMAC within the original v1 shape; a versioned stored nonce confines legacy verification to old challenges. `challenge-compatibility-oracle-before.txt` demonstrates why an unconditional legacy fallback was rejected (200 versus 400). These failures are retained, not passes.
- `web-build-final.txt` / `typecheck-final.txt`: initial test type inference failure in the new checkpoint closure. Explicit User/Device typing fixes it; `typecheck-verified.txt`, `typecheck-complete.txt` and `web-build-verified.txt` pass. No signing validator was loosened.
- `chromium-privacy-final.txt`: initial Node route forwarding did not trust the private test CA. Its failure diagnostic included synthetic cookie/CSRF headers; the affected synthetic session was revoked and those header values were explicitly redacted. The final helper verifies TLS with the exact test CA and emits generic transport errors, with no TLS bypass. The corrected three-test run passes in `chromium-privacy-verified.txt`.
- `api-interrupted-cache-isolation.txt`: stopped after 53 passes to avoid concurrent backend cache-reset fixtures interfering with browser verification. It is not a full pass; the final 111-test run is separate.
- Application audits: no known vulnerabilities in all Python groups, full npm audit and Cargo. Cargo's existing optional proof-tool `proc-macro-error2` maintenance warning is retained, not suppressed (`RUSTSEC-2026-0173`). The initial npm omit-optional observation is separately named; the final full npm result includes optional dependencies.

## Stress and endurance outcomes

`stress-baseline-final.json` and `stress-current-final.json` use the same native client, 100 accounts/500 sessions, real ingress limits and PostgreSQL default 100 connections. Both stop on the explicit ten-second backlog bound and drain every generated message: baseline 65/585 copies, current 52/468 copies, zero socket errors; **neither sustains the offered 20 messages/s**. Unequal completed work and cold TLS reconnects make their raw WAL/CPU/byte totals unsuitable as an efficiency ratio. No speedup is asserted. These overload trials precede final stored nonce versioning and harness diagnostics; source fingerprints record that difference. They remain failed target evidence, rather than final-source 20/s qualification. `load-startup-race.txt` precedes the corrected TCP-ready preflight and contains no measured workload.

`soak-strict-failed.json` stops after 671.07 seconds: six code-1011 socket closures, 670/6,030 durable messages/copies; zero-error endurance FAILED. The close reason was not captured in that earlier instrument and is not invented. The subsequent instrument records only bounded static reason classes and offers explicit resilience mode with authenticated verified-TLS reconnects. It never changes the separate zero-error gate.

`soak-resilience-final.json`: **7,200.25 seconds**, **7,200 accepted**, **64,800 verified/fsynced recipient copies**, **50 actual MLS updates**, **500 peak authenticated sockets**, **zero socket errors and no reconnects needed**, **zero database deadlocks**, all five 1 MiB encrypted files and encrypted native checkpoint restore pass. Source fingerprints for every exercised API/crypto/harness/config file match the final source. This passes only the tested local 1-message/s native workload; the separate 20-message/s, physical-phone and reference-production gates remain unqualified. The run's `ws_connected=0` is intentional teardown after measurement, not lost sessions.

The completed soak measured send scheduled-to-accept p95 339.29 ms and all-nine-durable-ACK p95 2,206.25 ms. TLS records total 201,957,653 upload / 443,951,233 download bytes, including 72,000 new cold HTTP connections after the supplied 30-second keepalive expires (one group turn every 50 seconds). This is native driver behavior, not a browser background-poll/battery measurement. WAL LSN grows 118,549,816 bytes; stat_wal reports 116,950,494 bytes; differences reflect distinct counter semantics/reporting. DB allocated size grows 20,602,880 bytes. API CPU 5,039.05 seconds / process lifetime peak RSS 148,692 KiB; notification worker CPU is separately recorded. Global per-instance I/O/WAL counters are isolated to this synthetic cluster, but include its catalogs/background activity; they are not exact application-row counts or SSD-media writes.


## Matched completed pair and final checks

`paired-baseline-final.json` and `paired-current-final.json`: 120 seconds at 1 message/s; both complete 120 accepted / 1,080 durable recipient copies / 500 peak WSS / zero socket errors / five encrypted files / checkpoint restore PASS. Same current native client, PostgreSQL default 100 connections and supplied ingress limits. Current exercised fingerprints match final source. `performance-summary.json` derives raw-counter deltas for pair/stress/soak; [performance.md](../../security/metadata-privacy/performance.md) reports exact latency/CPU/RSS/TLS/WAL/DB/I/O metrics and limitations. Higher current CPU in this sample (87.90→103.54 seconds) remains visible; differing shared-host timings establish no causal speedup or regression budget.

`firefox-complete.txt` retains 34 passes / six skips / one timeout waiting only 20 seconds for an offline auth probe. An in-flight success can restart the actual 30-second interval using the shifted test clock. `session-hardening.spec.ts` now permits that interval plus its 5–6-second poll (45-second bound), without changing production code or security assertions. Focused reruns pass in `firefox-session-verified.txt` and `chromium-session-verified.txt`. `firefox-interrupted-fixture-path.txt` is an interrupted retry with an incorrect provider-fixture path; it is not a pass. The final complete rerun uses the preserved `.local/rust-remediation` provider assets: `firefox-verified.txt` records **35 passed, six skips, zero failures** in 7.0 minutes.

`repository-safety.txt` is an earlier failure while an actively written benchmark JSON was empty; `repository-safety-final.txt` checks the completed artifacts. `typecheck-final-verified.txt` covers the final test timeout-only correction. `release-gate.txt` deliberately exits nonzero/BLOCKED; normal runtime crypto readiness remains false. Optional WebAuthn/hostname/showcase skips and the optional Rust maintenance advisory remain explicit. No real deployment is changed.


`secret-scan-review.json`: default-rule redacted Gitleaks scan flagged 21 patterns, all individually reviewed: 12 verified public source SHA-256 values, existing libsodium export names/Cargo dependency names, two public image-build GPG fingerprints and one explicit existing synthetic browser-test phrase. Zero confirmed credentials; no detector rules/exclusions were added. The raw detector exits 1 for these patterns; that result is disclosed rather than relabelled a raw clean scan. Protected runtime cookies, keys, DB dumps and provider checkpoints are excluded from publication. A failed early route-forwarding diagnostic was explicitly redacted after its synthetic session was revoked, as recorded above.


`exercised-source-verified.json` rehashes all 56 baseline / 61 current exercised API/crypto/config/harness files and the actual native helper binary: zero mismatches for the matched pair and completed two-hour run. Baseline API files are compared against `git show 0240706:apps/api/...`; current files against this checkout. The final whole-tree source manifest additionally covers final documentation and browser-test-only corrections; run-start whole-tree hashes are not falsely claimed identical after those edits. `source-checks-final.txt` records final Ruff/format, Python compilation, Node syntax, targeted Prettier and diff checks.


## Final result table

| Check | Final result |
|---|---|
| PostgreSQL/Redis backend | 111 passed (`api-final.txt`) |
| Rust / official upstream vectors | 5 library tests; 205 vectors pass, 3 ignored and 91 filtered; format and Clippy pass |
| Chromium | 39 passed / 2 optional skips (`chromium-complete.txt`); final timeout-only test correction separately passes |
| Firefox | 35 passed / 6 disclosed skips (`firefox-verified.txt`) |
| Production build / TypeScript / source syntax and formatting | PASS; no client validator relaxation |
| Real dump/restore / inventory / ingress | PASS in bounded synthetic scope; 191 current + 8 retired fields |
| Final matched native pair | Each 120 accepted / 1,080 durable recipient copies / 500 sockets / 0 socket errors |
| Final two-hour native soak at 1 message/s | 7,200 accepted / 64,800 durable copies / 50 actual MLS updates / 500 sockets / 0 socket errors |
| Offered 20 message/s target | NOT QUALIFIED; failed/unequal stress work retained |
| Physical phones / Iranian field hosting / independent review | BLOCKED external; local tests cannot establish these |
| Normal runtime / release script | `crypto_ready=false`, `release_status=BLOCKED`; release script intentionally refuses |
| Publication | Source manifest + evidence digests, protected-path scan and reviewed redacted secret scan; only review branch commits |

Reproduce full browsers with `HAVEN_PROVIDER_COMPAT_DIR="$PWD/.local/rust-remediation" npm test --prefix apps/web -- --reporter=list`, adding `HAVEN_BROWSER=firefox` for Firefox. Preserved compatibility assets, test CA/profile, normal/integration local stacks, `.local/test.env` and the locked native helper must exist. Backend fixtures clear the test Redis cache, so do not run pytest concurrently with browsers sharing that test service. Chromium skips optional hostname/showcase; Firefox additionally skips the four Chromium-CDP WebAuthn cases. These are not physical Safari/Android or hostname qualification results.

Source implementation commit: `8ddc3d13919c6ebaf15929ff1d0f95d0bc5a6980` on `codex/metadata-privacy-completion`. The separate evidence commit is reported in the final Git result. `SHA256SUMS` covers every file in this directory except itself; verify with `sha256sum --check SHA256SUMS` from this directory. The repository-root `SOURCE_MANIFEST.sha256` covers source/docs/tests outside volatile evidence. Captured text logs have trailing whitespace normalized; the explicitly documented synthetic cookie/CSRF diagnostic was redacted and its session revoked.
