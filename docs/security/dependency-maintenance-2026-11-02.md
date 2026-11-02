# Dependency maintenance — 2026-11-02

This review covers the 15 Dependabot proposals open when the owner authorized qualification. Changes are combined on one review branch so the tested dependency graph, generated cryptographic artifacts and source manifest agree. Individual bot branches have stale manifests and several different base commits; they are superseded only after the consolidated change passes review and CI.

## Decisions

| Original PR | Proposal | Decision |
|---|---|---|
| #3 | Python 3.12.15 → 3.15.0 | Decline this runtime-only upgrade. `requires-python` is `>=3.12,<3.15`; Django 5.2 documents support through Python 3.14. Keep the qualified Python 3.12.15 base and its digest. Revisit with framework/runtime qualification; Dependabot excludes Python 3.15+ until then. |
| #4 | actions/checkout 4.4.0 → 7.0.1 | Adopt the bot's immutable commit pin for hosted Ubuntu runners; retain disabled credential persistence. |
| #5 | Node 24.22.1 → 26.13.0 | Adopt the rebased proposal's 26.13.0 image and digest, align both Dockerfiles, `.nvmrc` and npm engines. |
| #6 | base64 0.22.1 → 0.23.1 | Adopt; qualify native and browser decoding, snapshots and MLS interoperability. |
| #7 | canonicalize 2.1.0 → 5.1.0 | Adopt; verify signed JSON bytes against the old library and Python RFC 8785. Invalid non-finite numbers and lone surrogates remain rejected. |
| #8 | sha2 0.10.9 → 0.11.1 | Adopt with a source repair: the new digest array has no `LowerHex` implementation. Encode each digest byte as two lowercase hex digits. Published SHA-256 vectors fix the exact state-fingerprint representation. The vendored provider already uses sha2 0.11; its source is unchanged. |
| #9 | TypeScript 5.9.3 → 7.0.2 | Adopt after native compiler type-check and Next production-build qualification on Node 26.13.0. |
| #10 | Node types 24.10.0 → 26.6.6 | Adopt alongside the Node 26 runtime. The branch name still ends in 26.6.5; its actual proposal contains 26.6.6. |
| #11 | redis-py 7.4.1 → 8.1.0 | Adopt; test actual PostgreSQL/Redis backend, cache, WebSockets, outbox and browser delivery. Redis server remains 7.4.6. |
| #12 | Prettier 3.6.2 → 3.9.10 | Adopt as development tooling. |
| #13 | Uvicorn minimum 0.38 → 0.54.0 | Adopt the declaration update; the locked/runtime version was already 0.54.0. |
| #14 | React types 19.2.2 → 19.3.0 | Adopt; type-check against installed React 19.3.1. |
| #15 | Ruff 0.15.22 → 0.17.3 | Adopt; existing API lint/format checks pass without source reformatting. |
| #16 | pytest-asyncio 1.4.0 → 1.4.1 | Adopt and rerun both API configurations. |
| #17 | jsonschema 4.25.1 → 4.26.0 | Adopt and rerun backend/contract tests. |

The initial unconstrained Cargo resolution updated unrelated packages; it was discarded. Final resolution updates only base64 and the direct sha2 requirement and removes the superseded sha2 0.10 dependency chain. Python package blocks/hashes are the exact bot-proposed releases, combined without unrelated upgrades. `uv lock --check --offline` and `uv sync --frozen --offline` validate the graph. The first online Python installation failed because this machine could not resolve files.pythonhosted.org. The four exact wheels were downloaded with HTTPS certificate verification intact, using a public DNS response for a per-command address, verified against `uv.lock`, installed locally, and validated by frozen offline sync. No system DNS configuration or TLS policy changed.

## Publication-safety repair

The existing `main` publication check failed on 154 matches, all the exact SHA-256 digests of two publicly reachable source files. Each value was recomputed from the referenced Git source blob before adding an exception. Only these two exact values, the four dated metadata evidence directories, and the generic-api-key rule qualify. Existing exceptions are also explicitly attached to that rule. A global path allowlist can otherwise skip a file before checking its matched value; rule-specific exceptions preserve the intended path-and-value intersection. Regression probes require that a new random value, a modified public value and the same public value outside the evidence paths are still rejected. The final evidence scan also identified four occurrences of the owner-local Docker image tag as API-key patterns. Verify the exact label against the actual image ID, and constrain that separate exception to its exact value and two build-provenance files. Eight scanner probes cover public checksums and the build label, changed values and unrelated paths. No scanner rule is disabled, directory excluded or unknown match accepted.

CI now additionally runs the complete API suites under both database configurations and builds the web Docker image using the pinned Node runtime. The three existing required security checks remain in place. No direct-push rules bypass is part of this update workflow.

## Verification

Completed results so far: 132 backend tests pass under `haven.runtime_settings` and 132 under `haven.settings`; six native Rust tests pass; 205 upstream OpenMLS provider/vector tests pass (three upstream tests ignored, 91 filtered); native/WASM builds and vendor-source verification pass. TypeScript 7 type-check and Next build pass on verified official Node 26.13.0. Thirteen canonical JSON vectors match old JavaScript and Python encodings, signatures verify, and five malformed primitive inputs are rejected. Database pool rollback/revocation/reconnect/exhaustion/recovery, 13 workload checks, 13 setup tests and offline-shell lifecycle checks pass. Python and npm vulnerability audits report no known vulnerabilities; Cargo audit retains its previously documented optional proc-macro-error2 maintenance warning.

The first full Chromium run passed 37 tests, skipped two browser-conditional cases, and failed two setup-dependent cases: provider-upgrade expected the fixture filename `new-native.json`, and the private bridge-test leaf certificates had expired. Preserve the original failed run. The already generated fixture was supplied under its expected filename, and expired TEST-only certificates were preserved before generating new verified private leaves. Both affected cases and the old/new-provider exchange pass on the focused three-test rerun. Firefox completed with 35 passes, six expected skips and zero failures. Chromium finishes with 39 unique passing cases and two expected skips across the full run and focused rerun. Skips cover opt-in hostname/documentation capture and Firefox-inapplicable Chromium virtual-authenticator tests. Local source/manifest/scanner verification is complete; remote CI results are recorded with the final pull request. [Machine-readable evidence and retained failure scope](../evidence/dependency-maintenance-2026-11-02/README.md). A network-disabled read-only/capability-free web image returns HTTP 200 for the app and 404 for its removed engineering harness. This host rejects `no-new-privileges` execution with EPERM for the old Node image, new Node image and Python image alike. No host or deployment security setting was weakened; the independent GitHub frontend check passes with the production restrictions, including `no-new-privileges`. The default vulnerability database mirror returned HTTP 403; an explicit GHCR refresh timed out. Cached image scans are dated 2026-10-24, and are diagnostic only: API 44 HIGH/58 MEDIUM/61 LOW/1 UNKNOWN, web 43 HIGH/60 MEDIUM/60 LOW/1 UNKNOWN, no critical or listed fixes. This is not a fresh OS vulnerability qualification; external image triage remains open. The online Docker build's npm download failed with ECONNRESET; network-disabled offline API and web builds are retained as separate evidence, without relabeling the online failure.

This dependency work does not repeat the prior two-hour load test or transfer its performance measurements to this dependency graph. Existing performance evidence remains bound to its original source/dependencies. No deployed staging container, identity, browser vault or database schema is changed. Normal `CRYPTO_READY=False` and the release gate remain closed; local regression success is not production qualification.

## Primary references

- [Django 5.2 supported Python versions](https://docs.djangoproject.com/en/5.2/releases/5.2/#python-compatibility).
- [Node release schedule](https://github.com/nodejs/Release) and [Node 26.13.0 release](https://nodejs.org/en/blog/release/v26.13.0).
- [Checkout 7.0.1 runner requirements](https://github.com/actions/checkout/blob/v7.0.1/README.md).
- [TypeScript 7 release and native compiler](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/).
- [Canonicalize 5.1.0 source](https://github.com/erdtman/canonicalize/tree/v5.1.0).
- [Gitleaks 8.30.1 configuration and rule-specific allowlists](https://github.com/gitleaks/gitleaks/tree/v8.30.1).
