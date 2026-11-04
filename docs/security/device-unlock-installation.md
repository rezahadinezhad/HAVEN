# Device unlock on the maintained local installation

HAVEN uses the browser's passkey chooser to unlock the encrypted local vault.
Depending on the selected browser, provider and authenticator, verification may
use fingerprint, face, a provider/device PIN, or a verified security key. The
chosen authenticator must support WebAuthn PRF and user verification. HAVEN never
accepts a plain PIN or a successful-looking prompt as a decryption key.

## Addresses and first setup

The maintained hostname route is `https://localhost:8444/`. The existing
`https://127.0.0.1:8444/` route stays available. Both resolve only on this computer;
this does not establish a publicly reachable deployment.

1. Keep the existing IP tab and its vault. Open the hostname address in a browser
   with a compatible passkey provider. Chrome on Linux can offer Google Password
   Manager; support for the PRF operation is checked during the actual ceremony.
2. Sign in to the same HAVEN account. Set up a vault at this new origin and save
   its generated passphrase. A hostname is a separate browser origin and becomes
   a separate HAVEN device, even on the same laptop.
3. If the account already has an approved browser, follow the displayed approval
   instructions. In the existing browser, compare and verify the new browser's
   fingerprint under **People & trust**, then **Approve enrollment** under
   **Devices**. Return to the hostname tab and choose **Check approval**.
4. Open **Settings → Unlock with this device → Set up device unlock**. Choose a
   compatible provider/device/security key and personally confirm its prompts.
5. After refresh or idle lock, use **Unlock with this device**. The saved vault
   passphrase remains available as the fallback.

The application offers the configured hostname link from the IP unlock screen
and device-unlock settings. It opens a new tab with no opener, query, fragment or
vault-transfer payload. It never silently redirects the current vault.

## Existing conversations and history

Approval of a new browser is separate from conversation membership. An authorized
owner/moderator must add its verified device to conversations before it can
receive their new encrypted messages. Existing messages, drafts, pending sends
and device keys remain at the original IP origin. Local old history does not
move automatically. The existing encrypted recovery export/history-only import
can copy saved history explicitly; use the history-only operation, not an account
security reset. No device identity or live MLS ratchet is cloned between origins.

## Operator configuration

Set `HAVEN_OPTIONAL_HOSTNAME=localhost`, include `localhost` in `HAVEN_HOSTS`, and
add exactly `https://localhost:8444` to `HAVEN_ORIGINS` while retaining the exact
IP host/origin. The Next server receives the same hostname setting at runtime.
The ingress leaf must cover `DNS:localhost` and `IP:127.0.0.1`, chain to the
already trusted local CA, and match the existing protected private key. Updating
this leaf must preserve the IP route and CA trust; it does not require a database
migration or deletion of browser storage. No wildcard host, CORS relaxation,
certificate-warning bypass, or WebAuthn virtual authenticator is used in the
maintained service.

The signed clients at their existing IP origins retain passphrase unlock. They
receive the provider-selection improvement but are not silently moved to a new
origin. Their default independent-delivery and origin boundaries remain intact.

## Verification and limits

Chromium's virtual authenticator verifies six crypto/capability cases and the
real UI's built-in and USB enrollment/reload/removal workflows, plus the IP
hostname-link case. Eleven API environment checks retain exact Host/Origin
validation. Firefox verifies direct-IP denial; the five Chromium-CDP cases are
explicitly skipped there. These results do not certify a physical fingerprint
reader, face sensor, security key, embedded browser, or passkey-provider account.
The owner must complete actual enrollment. No operator credential or personal
vault is used for qualification.

Sources: [W3C PRF explanation](https://github.com/w3c/webauthn/blob/main/explainers/prf-extension.md),
[Google's supported Chrome environments](https://developers.google.com/identity/passkeys/supported-environments),
and [the cryptographic decision](../adr/0009-optional-device-unlock.md).
