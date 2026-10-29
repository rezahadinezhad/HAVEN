# OpenMLS provider backport

Exact upstream OpenMLS revision: `28369d5b48608bef4ddf8371d91503b0f3852bb3` from https://github.com/openmls/openmls (2026-10-28 source). Archive: `https://codeload.github.com/openmls/openmls/tar.gz/28369d5b48608bef4ddf8371d91503b0f3852bb3`, SHA-256 `3b7b46a94b443ca542dc74efb522b49ad50115cbeb5ea368c109134c877e5885`.

These two MIT-licensed crates backport upstream's cryptography dependency migration to HAVEN's unchanged published OpenMLS 0.9.2 / traits 0.6.0 / memory storage 0.6.0 protocol implementation. `openmls_rust_crypto/src` is unchanged upstream source. `basic_credential/src/lib.rs` only restores the three synchronous storage methods expected by the published traits: remove `maybe_async`, `async`, and `.await`. The cryptographic methods are unchanged. Manifests resolve workspace metadata to registry dependencies, omit unused upstream dev dependencies, and omit draft-feature references to those removed dev dependencies. Draft/PQ/targeted/virtual-client features are not qualified or enabled for HAVEN.

`compatibility.patch` records every difference from upstream, including manifests; `UPSTREAM.json` records both original and local file hashes. `python3 scripts/check-crypto-vendor.py` verifies the local source. Source review should also compare with the independently fetched archive and recorded patch. This is a maintained local backport requiring independent review, not a new upstream release or an independently audited HAVEN provider.

The lockfile selects patched `crypto-bigint 0.7.9`, `hpke-rs* 0.8.0`, and optional `libcrux-kem 0.0.10`. Browser randomness enables getrandom 0.4 `wasm_js` explicitly. HAVEN still uses only MLS suite `MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519`; no fallback cipher or algorithm substitution is introduced. The older getrandom 0.2 JS feature remains for the unchanged OpenMLS crate.

When an appropriate published upstream provider release becomes available, replace this backport only after the native/browser, pre-upgrade state/message compatibility, vector, and full application regressions pass again. Keep MIT license files with the distribution.
