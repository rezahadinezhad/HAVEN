# Reference review — 2026-10-23

Primary sources consulted while implementing (build-time network only; app does not fetch these):

- [RFC 9420](https://www.rfc-editor.org/rfc/rfc9420.html): normative MLS; not evidence that our integration is correct.
- [OpenMLS source](https://github.com/openmls/openmls), [WASM requirements](https://book.openmls.tech/user_manual/wasm.html), [security advisories](https://github.com/openmls/openmls/security/advisories): JS randomness/time requirements confirmed; 0.9.2 resolved from crates.io. Narrow upstream wrapper was read as an API example, not copied as a safe production wrapper. Its unwrap/TODO handling was not adopted.
- [Matrix crypto WASM](https://matrix-org.github.io/matrix-sdk-crypto-wasm/index.html): alternative library reviewed; not selected and no Matrix service deployed.
- [libsodium AEAD](https://doc.libsodium.org/secret-key_cryptography/aead/chacha20-poly1305): authenticated encryption/AAD; attachment construction still requires external review.
- [Signal Double Ratchet](https://signal.org/docs/specifications/doubleratchet/): design context only; no homemade ratchet implemented.
- [CA/Browser TLS requirements](https://cabforum.org/working-groups/server/baseline-requirements/requirements/) and [Let's Encrypt IP availability](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability): actual IP issuance uses short-lived 160h certs from Let's Encrypt. Renewals cannot be assumed available during international outage.
- [Apple manual root trust](https://support.apple.com/en-us/102390): explicit full-trust step required, actual phone testing remains blocked.
- [Secure contexts](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts), [service workers](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers): production requires trusted HTTPS; no localhost exception is used for auth/crypto testing.
- [Apple web push](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers): page requires JS; no reliable background delivery claim or external push implementation.
- [OWASP ASVS 5](https://asvs.owasp.org/): control planning; no formal ASVS certification.
- Next 16.4.3 bundled documentation for Client Components, proxy and nonce CSP was read (apps/web/node_modules/next/dist/docs/). Version-pinned code and production build, not assumed older APIs.
- [Django security archive](https://docs.djangoproject.com/en/5.2/releases/security/), package registry versions, npm audit, pip-audit and RustSec audit checked. Exact machine outputs in docs/evidence.
- [Twisted IMAP advisory](https://github.com/twisted/twisted/security/advisories/GHSA-8pqf-f4m5-798g): historical development-only dependency finding; the entire Daphne/Twisted/Autobahn dependency chain was removed on 2026-10-30. See [remediation](dependency-alert-remediation.md).
- RustSec RUSTSEC-2026-0330/0331 flag optional libcrux-kem 0.0.9 in Cargo.lock. Active native/WASM dependency trees must be compared; do not confuse disabled post-quantum backend dependencies with a clean lockfile audit. proc-macro-error2 has an unmaintained warning.

No source supplies an independent audit of HAVEN, and none is claimed.
