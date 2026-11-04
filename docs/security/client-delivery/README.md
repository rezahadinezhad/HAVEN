# Verified client delivery

HAVEN now has a signed, installed Linux client and a separately deployable frontend gateway. Both use the existing messaging interface, native MLS/WASM, encrypted vault, device approval, history and media code. No new cryptographic protocol or database migration is introduced.

The installed client addresses this specific threat: **control of the messaging/API origin does not authorize replacement of the client program**. Its launcher, release public key, complete interface, workers, WASM and dependencies are installed independently. The browser connects only to a private local HTTPS endpoint. That endpoint serves authenticated local code and treats remote responses as constrained API data.

| Delivery | Trusted code supplier | Protection against a compromised API origin |
|---|---|---|
| Existing same-origin website | Messaging website/operator | The origin can replace code; CSP cannot establish authenticity |
| Independent web frontend | Separate frontend host/operator | API cannot supply executable assets; frontend host can still replace code |
| Installed verified client | Independently trusted launcher, publisher key and build | Signed assets checked before execution; API cannot replace those assets |

A PWA/service worker, CSP or a script hash delivered by the same compromised page does not independently establish the page's authenticity. [SRI](https://www.w3.org/TR/sri/) is useful for subresources whose expected hashes have an independently trusted source. It does not authenticate its own containing document.

## Implemented boundary

- Ed25519 signs a domain-separated manifest containing the source commit, increasing release sequence and SHA-256/size of every executable/runtime/asset payload. Archive traversal, duplicates, unsupported compression, oversized central directories and payloads are rejected.
- The trusted standalone launcher pins the public key. Initial installation requires an independently checked DER SHA-256 key fingerprint. It verifies the signed archive and disk runtime before execution.
- Publisher and installed-state version floors reject rollback and conflicting releases at the same sequence. Updates are manual, fail closed and switch the active pointer only after an offline, hash-locked, separate dependency environment is ready. Browser/runtime locks prevent updating a live session. A failed update preserves the prior active release.
- Workers, WASM and UI assets use the authenticated manifest digest in their URLs. Installed mode never registers a service worker. It serves local code even when the API is unreachable.
- The API bridge fixes the HTTPS upstream identity, validates its CA/hostname, restricts paths/methods/headers, bounds requests/responses/concurrency, refuses redirects and executable/HTML/encoded responses, and reconstructs local response policies. JSON and narrowly scoped encrypted attachment bytes are data. Upstream CSP, Location and cookie policy cannot control the local application origin.
- WebSocket hints use a separate TLS-verified, exact-origin, size-bounded bridge. No arbitrary network proxy, remote import, filesystem URL or website-driven update endpoint exists.
- The private Firefox profile trusts only its own local-client CA in addition to the browser's ordinary roots. No system or personal browser trust settings are changed. The API's optional private CA is used by the bridge, not imported into that browser profile.
- Share links retain the logical service identity. Paste/open invitations and friend links inside the installed client. A link opened in an ordinary browser still opens the ordinary website. Standby-origin navigation is explicitly stopped in verified delivery modes; changing servers requires a distinct client profile.

## Qualification and limits

[Verification](verification.md) records signed-install tests, hostile TLS API tests, Chromium/Firefox encrypted text/media/reload tests, and an API takeover while the vault is unlocked. [Operations](operations.md) covers first trust, release signing, updates, TLS and recovery. [Local deployment](local-installation.md) identifies the actual maintained installation.

The qualified portable client uses Linux, Python 3.12/3.14, OpenSSL and NSS `certutil`; the dedicated interactive launcher uses Firefox. Chromium and Firefox are exercised in browser automation with real TLS validation. Native iOS/Android, app-store signing, OS-signed desktop packages and independent security review are not claimed.

An attacker controlling the OS, browser, extension with sufficient access, trusted publisher/build pipeline, initial launcher distribution, or unlocked peer can still steal plaintext. A malicious API can deny service, lie about metadata and exercise client parsing; protocol validation and device trust remain essential. Signing proves publisher authorization, not absence of bugs. The Python interpreter, OpenSSL and hash-locked dependencies are part of the trusted local runtime.

The independent web host and signer must use separate administrative credentials and infrastructure for the production threat model. Two containers on one host demonstrate network/credential separation; they do not withstand host-root compromise. The local operator machine currently holds the publisher key outside the repository and every server mount. Move signing to a separately controlled/offline machine before using host-compromise resistance as a deployment claim. Hardware-key/offline signing and reproducible multi-party review can strengthen this further; they are not asserted as implemented guarantees.

Existing origins/vaults are preserved. Browser origin separation means a new client starts with its own storage and needs normal enrollment/approval or explicit supported recovery/history import. It cannot silently read another origin's keys, passkeys, archives or ratchet state.
