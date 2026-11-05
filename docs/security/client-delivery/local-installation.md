# Maintained local client installation

The existing IP vault and account state are preserved. Device unlock uses `https://localhost:8444` in a dedicated trusted Chrome profile; that origin needs its own browser enrollment and approval. No private keys or live MLS identity are silently copied between origins.

**Signed release 11 is installed and running, after verified release1→2→3→4→5→6→7→8→9→10→11 updates.** Its reviewed source is `e24031d3b560ac93d3bbc9bdc35ca47df0400cc6`. The authenticated workspace uses one adaptive sidebar for identity, observed connection state, conversations or auxiliary navigation, and appearance/language preferences; the global toolbar has been removed. Device unlock and the protected TLS transport retain their existing behavior. No QA helper is present in the production release. Earlier evidence retains its recorded release/revision.

| Component | Maintained location |
|---|---|
| Device-unlock browser | `https://localhost:8444`; application menu **HAVEN Device Unlock**, launcher `~/.local/bin/haven-device-unlock`; isolated Chrome/NSS profile |
| Installed client | `https://127.0.0.1:9443`, loopback only; automatic user service `haven-verified-client.service` |
| User launcher | `/home/reza-hadinezhad/.local/bin/haven-verified-client`; application menu entry **HAVEN Verified Client** |
| Protected installed state | `/home/reza-hadinezhad/.local/state/haven/verified-client` |
| Independent frontend demo | `https://127.0.0.2:8447`, separate non-root/read-only container; only the existing ingress network, no DB network or backend secrets |
| Distribution archive (local) | `.local/verified-client/HAVEN-verified-client-release-11.tar.gz`, signed archive, public verifier/key and license notices; contains no private signing key |
| Frontend operator helper | `.local/manage-verified-frontend.sh` |

Publisher public-key DER SHA-256: `2cecd962301f0292caca6089a23c0a2c8fb00fb055327342d09daa6abfaaaf99`.

Manifest SHA-256: `de2f92242737e5f01360223a6ad0dff0ffe2b2ee5e081ffcbac9973c6b536ab3`.

The fingerprint printed here is a record, not an additional independent trust authority. First-install trust must be anchored through the reviewed source/publisher channel, independently of the messaging server.

Release11 passed trusted-TLS read-only checks at the installed client, independent frontend, original IP and maintained hostname. Each returned a healthy cryptographic API response and current sidebar assets. The signed endpoints advertise sequence11 and the expected manifest, contain no QA helper, and installed mode registers no service worker. Five selected browser cases passed in each of Chromium and Firefox, alongside 28 layout combinations in both themes and languages. No operator credential was read or entered. See [release11 evidence](evidence/sidebar-release11.json), [sidebar design and verification](../../ui-ux/sidebar.md), and [the device-unlock setup guide](../device-unlock-installation.md). [Release10](evidence/toolbar-release10.json), [release9](evidence/device-unlock-release9.json) and earlier snapshots remain historical.

The default IP listener retains its exact original certificate and expiry for compatibility with the existing browser. The hostname, separate API TLS transport (container444 / loopback8449) and independent frontend use a dedicated local service CA. The installed client's logical API origin, browser origin, publisher root and own browser TLS root remain unchanged. The normal user's browser profiles and OS trust store were not changed. The new Chrome launcher scopes local trust to its dedicated browser home. A daily user timer renews the 90-day hostname/frontend leaves below30 days; forced renewal and the systemd no-renewal path both passed. The old IP certificate is a legacy compatibility path, not the long-lived hostname certificate.

During release5 verification, the existing owner browser tab was separately observed running the old 22/28-second chat-panel effect. After refreshing, its DOM reports all three new animations running at 14/18/22 seconds on the new workspace canvas. Its vault had already locked due to inactivity and remains available for the owner's own local unlock. No personal passphrase was read or entered.

The earlier release2 verification passed trusted-TLS production UI sign-in/sign-out with zero foreign browser requests/page errors. No personal vault or MLS device was created. Installed mode has no registered service worker. The actual child runtime retains its update lock. Replaying authentic release1 through the installed release2 launcher was refused, with active release2 unchanged. TLS identity, origin, publisher root and browser state were preserved. The separate image refuses an altered signed worker before executing its runtime; production Python3.14.9 has only the four required packages and no pip/Django/pytest. [Public deployment checks and artifact digests](evidence/) contain no session cookies or credentials.

The dedicated interactive launcher uses the already qualified Firefox binary in the local Playwright cache and private copies of its required shared libraries. It never opens a personal browser profile. If that externally managed browser cache is removed/upgraded, update the launcher to a trusted Firefox binary; this portable distribution does not claim an OS-signed browser bundle.

The local user service uses private temporary storage and read-only home/system protection with an explicit write path for its own profile. Stop it before a signed update with `systemctl --user stop haven-verified-client.service`; close the dedicated browser, apply through the installed launcher, then start the service again. `systemctl --user disable --now haven-verified-client.service` reverses automatic startup without deleting vault state.

The local administrator credential was refreshed and prior sessions revoked after a smoke-test assertion included it in a private diagnostic. That diagnostic was removed, and subsequent assertions suppress page/error details. The current credential remains only in the protected existing operator record, outside this repository. No personal vault state was involved.

The local frontend demonstration uses a distinct loopback IP/origin, TLS leaf and container without backend database credentials or the database network. It shares the development Docker host and therefore does not establish resilience to host-root compromise. The installed client uses an independent local CA and dedicated browser profile; it makes no system trust changes.

Isolated QA retains its separate short-lived TEST CA. The maintained hostname certificate expires `2027-02-03T01:30:53+03:30` and is automatically renewable under the dedicated local CA. The legacy IP certificate retains its original expiry `2026-11-07T02:03:18+03:30`; use the hostname for regular access and complete any existing-browser approval/history export while that legacy certificate is valid. This is a loopback local deployment, not a publicly trusted public service. Public hosting still needs the independently administered delivery and TLS described in [operations](operations.md).
