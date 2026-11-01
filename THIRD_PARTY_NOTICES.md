# Dependency / licensing notes

This is an inventory starting point, not a completed legal or independent security review. Exact dependency versions/checksums are in apps/api/uv.lock, apps/api/requirements.lock, apps/web/package-lock.json and packages/crypto-core/Cargo.lock.

Primary components: Django (BSD-3-Clause), DRF (BSD), Channels/channels-redis (BSD), Uvicorn (BSD-3-Clause), PostgreSQL (PostgreSQL license), Redis7.4 (RSALv2/SSPLv1 licensing must be reviewed for the deployment), Next.js/React (MIT), OpenMLS/RustCrypto/basic credential/memory storage (MIT), tls_codec (Apache-2.0/MIT), wasm-bindgen (Apache-2.0/MIT), libsodium/libsodium.js wrappers (ISC), idb/qrcode/zod (MIT), Nginx (BSD-2-Clause). Verify transitive notices and Docker base OS packages before distribution. License text from bundled libsodium worker is retained by esbuild's legal-comment behavior where present; retain upstream notices in release packaging.

No claim that HAVEN or the selected complete integration is audited. Library tests/security history do not transfer independent assurance to this application. Audit results and unresolved optional/development findings are in SECURITY_STATUS.md and docs/evidence.

## Continuation, 2026-10-24

Added RFC8785 Python 0.1.4 and canonicalize JavaScript 2.1.0 for consistent signed public metadata; their own package licenses remain in installed/distributed package notices. Zod updated to 4.6.7; Playwright 1.64.1 and openapi-typescript 7.13.0 are development tooling. Exact lockfiles and audit outputs are the dependency record.

Upstream OpenMLS known-answer tests were run at the VCS revision embedded in the locked crate, 8a8f83b4b61fc45f28facec25e914992b3465de6. This is upstream test evidence, not an independent HAVEN audit. [RUSTSEC-2026-0330](https://rustsec.org/advisories/RUSTSEC-2026-0330.html) and [RUSTSEC-2026-0331](https://rustsec.org/advisories/RUSTSEC-2026-0331.html) remain in the lockfile for optional libcrux-kem 0.0.9. The selected RustCrypto native/WASM graphs exclude it. No alternate vulnerable hybrid backend is selected and no all-lockfile-clean claim is made.

The optional Linux WebKit test image uses the official pinned Microsoft Playwright image; it is test infrastructure and not included in the deployed application images. Browser/test/compiler dependencies are distinct from runtime packages. Offline source rebuilding currently uses the bundled prebuilt Rust/WASM artifacts; compiler/toolchain redistribution and bit-for-bit reproducibility are not implied.

Proptest 1.12.0 is a pinned development-only test dependency for generated malformed public inputs and Unicode MLS serialization/replay properties. It is not part of the browser or public-verifier runtime dependency graph.

Container runtime scan: `scripts/scan-images.sh` pins Trivy 0.76.1 by image digest and uses tar inputs without Docker socket access. Application images use digest-pinned Debian 13, Python 3.12.15 and Node 24.22.1, with unused runtime package managers removed. The recorded scan has no critical issues or listed fixed versions, but still reports HIGH/MEDIUM/LOW/UNKNOWN OS findings. They are retained in full JSON and require applicability/maintainer triage; no clean-image or independent-audit claim. Debian tracks source-package findings and available fixes at https://security-tracker.debian.org/; scanner severity and practical reachability are different questions.

UI redesign: Phosphor React 2.1.10 (MIT) is imported by individual icon modules. Persian uses the locally bundled Vazirmatn variable font (SIL OFL 1.1); its OFL and the icon MIT license are retained in apps/web/public/licenses. English uses platform system fonts. Neshino's project-local frontend skills were copied with their licenses/references preserved; skills-lock.json records original source metadata and local SKILL.md hashes. These are authoring tools, not browser/runtime dependencies.

Next 16.4.3 includes a local, version/source-checked build patch moving the accessibility route announcer's two static style assignments into external CSS. Its MIT notices remain in the dependency. See docs/adr/0004-browser-csp-compatibility.md; this modification requires review when updating Next. Zod uses its supported jitless configuration; no validation or CSP exception is substituted.

## Provider security backport, 2026-10-29

The latest provider backport supersedes the previous unresolved Rust vulnerability statements above: `crypto-bigint 0.7.9` and optional `libcrux-kem 0.0.10` resolve the three vulnerability entries in the fresh audit. The optional `proc-macro-error2` maintenance warning remains. Two MIT-licensed upstream OpenMLS provider/credential crates are vendored at commit `28369d5b48608bef4ddf8371d91503b0f3852bb3`; retain their LICENSE files, UPSTREAM.json and compatibility.patch. See vendor/README.md and ADR 0010 for the minimal storage/manifests adaptation, exact dependency versions and remaining independent-review requirement. This is a local backport, not an upstream package release or security certification.

## Public project license

Original HAVEN code and project-authored documentation are distributed under the root MIT LICENSE. Vendored libraries, fonts, icons and authoring skills retain their own license terms and notices; the root license does not relicense third-party material.

## Review remediation, 2026-11-01

Contract generation now uses development-only openapi-typescript 6.7.6 (MIT), with its compatible undici fetch dependency pinned to 6.29.1 (MIT). The regenerated OpenAPI types and API client pass TypeScript checks; full npm audits include this tooling. This replaces the previously recorded Redocly/minimatch dependency path. Exact graph, notices and hashes remain in the npm lockfile/distributed dependencies. Cryptographic providers and their licenses are unchanged.
