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

1. Keep the existing IP tab and its vault. Open **HAVEN Device Unlock** from the
   applications menu, or run `~/.local/bin/haven-device-unlock`. This dedicated
   Chrome launcher opens the hostname with its own trusted browser profile.
   Chrome on Linux can offer Google Password Manager; support for PRF is checked
   during the actual ceremony.
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
The hostname leaf covers `DNS:localhost` and `IP:127.0.0.1`. The maintained
service now has a dedicated local CA under
`~/.local/state/haven/local-service-ca`, separate from the short-lived QA CA.
The CA key stays protected outside the repository and is never mounted into
application containers. Server private keys, browser origins, account/vault
state and the publisher key are preserved. The original IP listener retains its
exact original certificate so existing browser trust can approve the new device.
It is a legacy compatibility route with its original certificate expiry; use the
new hostname for regular access. Installed and independent API bridges trust the
new public CA through a separate TLS transport; the installed client's own
browser TLS root is unchanged.
The independent frontend leaf also uses the dedicated service CA.

The in-app browser rejected the hostname's untrusted local CA. A dedicated
Chrome launcher now uses the existing guided setup's isolated NSS/browser-home
workflow. Its profile and public CA copy live under
`~/.local/state/haven/device-unlock-browser`; normal personal profiles and the
OS trust store are unchanged. This is browser-profile isolation, not a hardened
process sandbox or protection from host compromise. No certificate bypass,
wildcard host, CORS relaxation or virtual authenticator is enabled in the
maintained browser. The owner must use a compatible real provider/authenticator.

The hostname and independent frontend leaf certificates last 90 days. `haven-local-tls-renew.timer` checks
daily and renews when less than 30 days remain, using the same server keys and CA.
Its private `renew.sh` validates both SANs/chains, reloads Nginx, updates the
independent frontend's public certificate volume and restarts that frontend.
The Docker helper uses the running reviewed image, no network, no capabilities,
and uid10001; it never receives the CA signing key. A forced renewal and the
systemd no-renewal path are qualified separately. Root rotation is an operator
trust change, not an automatic fallback. Stop the timer with
`systemctl --user disable --now haven-local-tls-renew.timer` without deleting keys.
No database migration or browser storage deletion is involved.

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
A fresh, unmodified Chrome qualification profile loaded the real hostname with
valid TLS and reported PRF client support, without certificate bypass or a virtual
authenticator. This establishes browser capability, not hardware enrollment.
The owner must complete actual enrollment. No operator credential or personal
vault is used for qualification.

Sources: [W3C PRF explanation](https://github.com/w3c/webauthn/blob/main/explainers/prf-extension.md),
[Google's supported Chrome environments](https://developers.google.com/identity/passkeys/supported-environments),
and [the cryptographic decision](../adr/0009-optional-device-unlock.md).


## Signed-client transport compatibility

The dedicated TLS listener on container port444 (host loopback8449) uses the
new service CA and serves API/WebSocket traffic only. It returns404 for web
pages. The installed client retains logical API origin
`https://127.0.0.1:8444` and its own browser origin9443, but its protected
`profile.json` selects `upstream_address=127.0.0.1`, `upstream_port=8449`.
The independent frontend retains its logical origin and reaches container
port444. TLS still verifies the logical IPv4 hostname and the independently
configured CA; transport overrides never disable certificate validation.

New installed profiles may supply `--upstream-address` and `--upstream-port`
during `configure`. An existing profile requires the operator to stop the client,
back up and edit only those protected profile fields, then restart. The browser
cannot supply endpoint overrides through a URL or the installed `serve` CLI.
This keeps cookies, origin-bound storage and live MLS identities intact while
changing only the TLS transport. The four profile regression tests and the real
TLS boundary suite verify this distinction.

The legacy IP certificate is byte-for-byte preserved and retains its original
expiry, 2026-11-07T02:03:18+03:30. Complete approval/history export there
while it is valid; the hostname and new TLS transport have their own renewable
certificate and do not depend on that legacy certificate.
