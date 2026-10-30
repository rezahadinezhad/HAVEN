# GitHub dependency alerts — remediation on 2026-10-30

GitHub reported nine open Dependabot alerts on the default branch: four high, four moderate, one low. Each pointed to `apps/api/uv.lock`. Secret scanning returned no open alerts. Code scanning returned “no analysis found”; this is absence of analysis, not evidence of zero source vulnerabilities.

## Dependency path and decision

The lockfile path was `HAVEN dev group → Daphne 4.2.3 → Twisted 26.4.0 / Autobahn 26.7.1`. GitHub labeled these lockfile entries runtime dependencies; the actual project declaration puts Daphne in the development group, and `requirements.lock`/the production Uvicorn image exclude it. Development dependencies still need remediation.

Daphne was used only because importing Channels' WebSocket test helper also imports its live-server helper. HAVEN's development and production servers already use Uvicorn; no Daphne live server is needed. Removed Daphne and the now-unused transitive stack, including both affected packages. The WebSocket tests use `asgiref.testing.ApplicationCommunicator` with explicit ASGI connect/receive/send/disconnect events. Existing assertions for hostile origin/transport, missing authentication, membership isolation, malformed/oversized messages and live credential/session revocation remain. The test helper retains Channels' test-only Django connection-lifetime handling; runtime authentication and connection management are unchanged.

This removes the affected code rather than hiding alerts or accepting prerelease transport dependencies. Twisted's current upstream fixes are prereleases and the IMAP wildcard advisory has no patched-version entry; neither is treated as a security exemption. [Twisted release information](https://github.com/twisted/twisted/releases/tag/twisted-26.10.0rc2), [Autobahn advisory](https://github.com/crossbario/autobahn-python/security/advisories/GHSA-pjh6-c8mg-3x7m).

## Every reported alert

All entries below are remediated in source by removing their dependency chain. No alert was manually dismissed, and no advisory is suppressed. GitHub closes default-branch alerts after the corrected lockfile reaches the default branch and its dependency graph is processed; that state must be verified separately.

| GitHub alert | Severity | Package | Advisory / affected behavior |
|---|---|---|---|
| 1 | Moderate | Twisted | [GHSA-8pqf-f4m5-798g](https://github.com/twisted/twisted/security/advisories/GHSA-8pqf-f4m5-798g): IMAP wildcard regular-expression denial of service |
| 2 | Moderate | Twisted | [GHSA-q7qq-6mhp-9rc4](https://github.com/twisted/twisted/security/advisories/GHSA-q7qq-6mhp-9rc4): HTTP header request smuggling |
| 3 | High | Twisted | [GHSA-3476-c5c2-fr73](https://github.com/twisted/twisted/security/advisories/GHSA-3476-c5c2-fr73): unbounded XML element tree |
| 4 | High | Twisted | [GHSA-cwm5-jh59-mwxr](https://github.com/twisted/twisted/security/advisories/GHSA-cwm5-jh59-mwxr): unbounded Telnet negotiation |
| 5 | High | Twisted | [GHSA-53xc-49m8-p798](https://github.com/twisted/twisted/security/advisories/GHSA-53xc-49m8-p798): unbounded IRC line buffer |
| 6 | Moderate | Twisted | [GHSA-2qrf-pqgx-qh9v](https://github.com/twisted/twisted/security/advisories/GHSA-2qrf-pqgx-qh9v): negative IMAP literal size |
| 7 | Low | Twisted | [GHSA-jj36-9pvh-vj5r](https://github.com/twisted/twisted/security/advisories/GHSA-jj36-9pvh-vj5r): DNS response source validation |
| 8 | Moderate | Autobahn | [GHSA-pjh6-c8mg-3x7m](https://github.com/crossbario/autobahn-python/security/advisories/GHSA-pjh6-c8mg-3x7m): Brotli decompression resource exhaustion |
| 9 | High | Twisted | [GHSA-vpp8-g58w-m8mp](https://github.com/twisted/twisted/security/advisories/GHSA-vpp8-g58w-m8mp): HTTP/2 rapid-reset denial of service |

## Verification

- `uv sync --project apps/api --frozen`: installed development environment contains no Daphne, Twisted or Autobahn. The production hash-locked requirements are unchanged.
- Full API tests: **70 passed**, including all WebSocket security cases; Ruff/format and migration-drift checks passed. See [API output](../evidence/dependency-remediation-api-tests.txt).
- `bash scripts/audit-python.sh`: all dependency groups, hash-locked export, strict `pip-audit`, no ignore list; **65 applicable packages, zero reported vulnerabilities**. See [Python audit](../evidence/dependency-remediation-full-python-audit.json).
- `npm audit --prefix apps/web --json`: **zero reported vulnerabilities**. See [npm audit](../evidence/dependency-remediation-npm-audit.json).
- `cargo audit --file packages/crypto-core/Cargo.lock --json`: **zero reported vulnerabilities**; optional proc-macro-error2 unmaintained warning remains. See [Rust audit](../evidence/dependency-remediation-rust-audit.json).
- CI now audits Python development dependencies as well as runtime dependencies, verifies the reviewed source manifest, and rejects npm findings down to low severity. Weekly update PRs are configured for uv, npm, Cargo, Actions and Dockerfiles. Updating a dependency also requires reviewing and refreshing the source manifest before installation; CI flags stale hashes.

These are dependency and regression checks, not an independent penetration test or proof of a vulnerability-free platform. Recorded container OS findings, physical-device trust, hardened production-host testing, independent cryptographic/application review and external deployment requirements remain in [SECURITY_STATUS.md](../../SECURITY_STATUS.md). The cryptographic and TLS gates are unchanged.
