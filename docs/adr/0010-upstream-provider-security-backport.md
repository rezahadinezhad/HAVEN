# ADR 0010 — Backport upstream provider migration to patched cryptography

Date: 2026-10-29. Status: implemented; local engineering qualification, independent review still required.

## Decision

Keep the published OpenMLS 0.9.2 protocol, traits 0.6.0, memory storage 0.6.0, HAVEN state format, and X25519/AES-128-GCM/SHA-256/Ed25519 suite. Backport the upstream RustCrypto provider and basic credential sources from OpenMLS commit `28369d5b48608bef4ddf8371d91503b0f3852bb3` using Cargo path patches. The sources are checked in under `packages/crypto-core/vendor` with MIT licenses, original/local hashes, archive checksum and a complete compatibility patch. No custom cryptographic primitive is introduced.

All RustCrypto provider source is unchanged upstream code. Basic credential changes only adapt three asynchronous storage wrappers back to the synchronous storage API of the published traits. Manifests resolve workspace dependencies and omit unused development dependencies. Experimental draft/PQ/targeted/virtual-client features are not enabled or qualified. getrandom 0.4's browser backend is explicitly enabled alongside the older JS backend required by unchanged OpenMLS.

The lockfile now selects `crypto-bigint 0.7.9`, hpke-rs/RustCrypto 0.8.0, P-256/P-384/K-256 0.14, Ed25519 3.0 and optional libcrux-kem 0.0.10. This resolves the three previously blocking RustSec vulnerability entries without advisory suppression. Cargo audit still reports the `proc-macro-error2` unmaintained warning in the optional lockfile graph; it is absent from the selected native tree. A maintenance warning is not a clean-all-dependencies result. Earlier container OS findings and other release gates are unchanged.

## Qualification and reproducibility

- `cargo audit --file packages/crypto-core/Cargo.lock`: successful exit, zero known vulnerabilities, one maintenance warning. The full JSON and readable output record the advisory database.
- `python3 scripts/check-crypto-vendor.py`: verifies checked-in source against the recorded original/local hashes. Reviewers should independently fetch the exact upstream archive and compare `compatibility.patch`; this is not independently verified by HAVEN's own hash checker.
- `cargo check` succeeds for native and wasm32; four native tests cover MLS roundtrip, serialization, malformed inputs and replay. New native-to-WASM fixture generation uses `HAVEN_GOLDEN_FILE`.
- `scripts/test-provider-vectors.sh` overlays the exact backported providers into a disposable copy of the pinned OpenMLS 0.9.2 test source and runs unchanged protocol known-answer tests: **205 passed, 3 ignored, 91 filtered**. Unsupported-suite vector warnings are retained. This changes only a `.local` test workspace; HAVEN's lockfile/protocol source is not replaced by upstream main.
- Browser tests cover two-way MLS, reload/reordering, membership changes, tampering/replay, vault rejection, old native snapshots, rebuilt native snapshots, and old/new browser-provider interoperability. A new member created by the backport joins an old-provider group, with messages exchanged both directions. The compatibility test asserts the served WASM hash matches the rebuilt artifact.
- Full API, real messenger/media/view-once tests, production builds and packaged artifact hash checks are recorded in TEST_REPORT.md.

Run the provider tests with `HAVEN_PROVIDER_COMPAT_DIR` pointing at the private preserved `.local/rust-remediation` directory containing `previous-crypto/{haven_crypto.js,haven_crypto_bg.wasm}` and `new-native.json`. Previous artifacts come from the pre-upgrade source (original local parent commit `6d2fede`); fixture states/private keys stay outside Git. The fresh GitHub snapshot deliberately has no previous development history or secret fixtures. Other native/browser tests remain separately reproducible with the documented local test preparation.

## Consequences

The locally maintained backport expands the integration review surface and must be replaced by a qualified published upstream release when available. Algorithm security histories and passing known-answer tests do not constitute an independent audit of this integration. The browser still trusts application code supplied by the origin. No production crypto gate, TLS requirement, device approval or recovery rule is relaxed. Public infrastructure, physical mobile testing and independent application/cryptographic review remain external requirements. Source publication can proceed; production/emergency release remains BLOCKED.

Primary references: [upstream pinned source](https://github.com/openmls/openmls/tree/28369d5b48608bef4ddf8371d91503b0f3852bb3), [upstream crypto migration](https://github.com/openmls/openmls/commit/055a2b4b06b595585783ee488e28eebd62212e2a), [RustSec timing advisory](https://rustsec.org/advisories/RUSTSEC-2026-0387.html).
