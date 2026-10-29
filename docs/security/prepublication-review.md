# GitHub publication review — 2026-10-29

This is a local source review and automated scan, not an independent audit or penetration test. The code may be published as experimental source. Production/emergency release remains **BLOCKED**, including the unresolved dependency advisories below.

## Corrections

- **Browser test report privacy:** 20 JSON reports contained a full inherited workstation environment. Removed those environment maps while preserving recorded test results. Chromium/Firefox launch configurations now pass only PATH, LANG, an isolated test HOME and the required library path. No current local credential was found in the historical Git blobs, but workstation identifiers and public verifying keys were present. Previous signed bundles are historical artifacts and do not attest to this revision.
- **Upload quota concurrency:** upload initialization locked only the conversation while enforcing an account-wide storage quota. Concurrent reservations in separate chats could overbook it. Initialization now locks the account before the conversation; a real PostgreSQL two-thread regression permits only one of two reservations near the limit.
- **WebSocket transport/authority:** the consumer checked a decoded Origin but did not require a secure ASGI scheme or a matching Host, and ignored non-ASCII Origin bytes. It now requires `wss`, exact approved Origin, matching Host, and strict ASCII decoding before cookie authentication. TLS terminates at the trusted ingress; only that ingress may set the forwarded protocol on the private upstream network.
- **Publication controls:** expanded private-file ignores, added an explicit file/report guard, an isolated snapshot secret scan, checksum-pinned Gitleaks and commit-pinned read-only GitHub workflow, a blocking Rust advisory job, and SECURITY.md. Forced staging of a key, an environment dump, and a synthetic token are rejected in negative tests. No GitHub repository/settings were changed.

## Recorded verification

- Full API suite: **61 passed** on PostgreSQL/Redis, including new quota and WebSocket checks; Ruff check/format passed.
- Chromium: **5 passed** for PRF enrollment/reload/removal, absent PRF, failed verification, cross-account copying and direct-IP denial after environment restriction. This is virtual-authenticator evidence, not physical biometrics.
- Firefox direct-IP denial: **1 passed** after the launch-environment restriction. A real TLS proxy/Uvicorn WebSocket connection returned authenticated hello and heartbeat with certificate validation enabled (an initial connection before the temporary upstream was ready was retried).
- Next production build and TypeScript passed. No messaging UI/crypto source, package dependency or migration changed.
- Gitleaks 8.30.1 binary checksum verified. Default rules found 35 historical matches; manual triage identified public workstation verifying keys, the public Python-image GPG fingerprint, Rust crate/library symbols, and a disposable test fixture. Only exact nonsecret symbols/fixture/fingerprint are allowlisted in the published config; workstation public-key history is deliberately not allowlisted.
- An exact-value comparison of seven currently protected local credential values against **1,191 historical Git blobs** found zero matches. This does not prove absence of unknown/obsolete secrets.
- Sanitized current-source snapshot scan: no findings with the documented narrow allowlists. The fresh GitHub export is also scanned over its complete new history before handoff.
- npm audit: zero reported vulnerabilities. Production Python requirements audit: no known vulnerabilities. These are time-bound database results, not guarantees.

Evidence: `docs/evidence/prepublication-*`.

## Dependencies at the initial review (superseded by ADR 0010)

The subsequent provider backport resolves the three vulnerability entries described in this historical section. See [ADR 0010](../adr/0010-upstream-provider-security-backport.md) and the latest TEST_REPORT.md. The Rust audit now exits successfully with zero known vulnerabilities; its maintenance warning and external qualification limits remain.

### Initial findings

Fresh Cargo audit reports **RUSTSEC-2026-0387** for `crypto-bigint 0.5.5`, a timing/constant-time advisory. The provider's `elliptic-curve 0.13.8` requires `crypto-bigint ^0.5`; the advisory's stated fixed series `>=0.7.6` cannot be substituted by a compatible lockfile update (0.7.6 was also reported yanked during the attempt). No dependency was changed or advisory suppressed. The dependency is present through the provider's P-256/P-384/K-256 support. HAVEN selects X25519/Ed25519 only, but that does not establish absence of reachable vulnerable operations or an independent security pass. A compatible upstream provider upgrade/backport and full cryptographic qualification are required.

The existing two `libcrux-kem 0.0.9` advisories **RUSTSEC-2026-0330/0331** remain in the lockfile; its optional upstream provider pins exactly 0.0.9, and it is absent from the selected native dependency tree. The `proc-macro-error2` maintenance warning remains. The new Rust CI job intentionally fails on current advisories rather than hiding them. Previous container OS findings, physical-device/TLS/infrastructure qualification, browser-origin compromise risk and independent review remain as documented in SECURITY_STATUS.md; container scans and full messaging/endurance suites were not rerun for this revision.

References: [RustSec timing advisory](https://rustsec.org/advisories/RUSTSEC-2026-0387.html), [libcrux advisory](https://rustsec.org/advisories/RUSTSEC-2026-0330.html).

## What to publish

The original local history still contains the removed workstation metadata. **Use the fresh `.local/github-ready` repository**, not the original history, for a first GitHub publication. The export preserves the reviewed files and their source manifest, starts one new `main` commit, and excludes Git history, local credentials, trust keys, dependencies and runtime data. The original checkout/history is preserved. It has no remote and has not been pushed.

To reproduce after committing changes:

```bash
GITLEAKS_BIN=/absolute/path/to/gitleaks bash scripts/scan-repository.sh
python3 scripts/prepare-github-export.py
cd .local/github-ready
gitleaks git --redact --no-banner
```

The exporter refuses an existing export or dirty source tree. Review it, choose the repository's visibility, and add your own GitHub remote to that directory. Enable GitHub secret scanning/push protection, private vulnerability reporting, dependency alerts and branch protection where available. Do not treat a successful publication or the hygiene job as a passing release gate; the Rust advisory job must remain enabled to catch future findings. No remote URL was provided, so nothing was pushed.
