# Maintained local client installation

The existing HAVEN service at `https://127.0.0.1:8444` and its account/vault state are preserved. No database migration or personal device enrollment is needed for this delivery change.

**Signed release 6 is installed and running, after verified release1→2→3→4→5→6 updates.** Its reviewed source is `32ec2636c78a99bbaaac0132cf34c5fcb7fe3f84`. It fixes composer focus after sending and prevents outgoing text from being saved again during a send. The rounded workspace and flowing aurora remain available. No QA helper is present in the production release. Earlier evidence retains its recorded release/revision.

| Component | Maintained location |
|---|---|
| Installed client | `https://127.0.0.1:9443`, loopback only; automatic user service `haven-verified-client.service` |
| User launcher | `/home/reza-hadinezhad/.local/bin/haven-verified-client`; application menu entry **HAVEN Verified Client** |
| Protected installed state | `/home/reza-hadinezhad/.local/state/haven/verified-client` |
| Independent frontend demo | `https://127.0.0.2:8447`, separate non-root/read-only container; only the existing ingress network, no DB network or backend secrets |
| Distribution archive (local) | `.local/verified-client/HAVEN-verified-client-release-6.tar.gz`, signed archive, public verifier/key and license notices; contains no private signing key |
| Frontend operator helper | `.local/manage-verified-frontend.sh` |

Publisher public-key DER SHA-256: `2cecd962301f0292caca6089a23c0a2c8fb00fb055327342d09daa6abfaaaf99`.

Manifest SHA-256: `a49e8f9e060ed0cf233331825a3b22203f9a7a69d75df890a8ce99e74f3ade7c`.

The fingerprint printed here is a record, not an additional independent trust authority. First-install trust must be anchored through the reviewed source/publisher channel, independently of the messaging server.

Release6 passed trusted-TLS read-only checks at all three maintained endpoints. Both signed endpoints advertise sequence6 and the expected manifest, contain no QA helper, and installed mode registers no service worker. Sign-in screens and the three-color styles loaded with zero foreign requests/page errors. No operator credentials or personal vault were used for that smoke. Chrome and Firefox also passed the encrypted composer regression workflow. See [release6 evidence](evidence/composer-release6.json) and [composer verification](../../ui-ux/composer-reliability.md). Existing tabs must reload to run the update; the operator's tab was left undisturbed. [Release5 evidence](evidence/flowing-release5.json) and earlier snapshots remain historical.

During release5 verification, the existing owner browser tab was separately observed running the old 22/28-second chat-panel effect. After refreshing, its DOM reports all three new animations running at 14/18/22 seconds on the new workspace canvas. Its vault had already locked due to inactivity and remains available for the owner's own local unlock. No personal passphrase was read or entered.

The earlier release2 verification passed trusted-TLS production UI sign-in/sign-out with zero foreign browser requests/page errors. No personal vault or MLS device was created. Installed mode has no registered service worker. The actual child runtime retains its update lock. Replaying authentic release1 through the installed release2 launcher was refused, with active release2 unchanged. TLS identity, origin, publisher root and browser state were preserved. The separate image refuses an altered signed worker before executing its runtime; production Python3.14.9 has only the four required packages and no pip/Django/pytest. [Public deployment checks and artifact digests](evidence/) contain no session cookies or credentials.

The dedicated interactive launcher uses the already qualified Firefox binary in the local Playwright cache and private copies of its required shared libraries. It never opens a personal browser profile. If that externally managed browser cache is removed/upgraded, update the launcher to a trusted Firefox binary; this portable distribution does not claim an OS-signed browser bundle.

The local user service uses private temporary storage and read-only home/system protection with an explicit write path for its own profile. Stop it before a signed update with `systemctl --user stop haven-verified-client.service`; close the dedicated browser, apply through the installed launcher, then start the service again. `systemctl --user disable --now haven-verified-client.service` reverses automatic startup without deleting vault state.

The local administrator credential was refreshed and prior sessions revoked after a smoke-test assertion included it in a private diagnostic. That diagnostic was removed, and subsequent assertions suppress page/error details. The current credential remains only in the protected existing operator record, outside this repository. No personal vault state was involved.

The local frontend demonstration uses a distinct loopback IP/origin, TLS leaf and container without backend database credentials or the database network. It shares the development Docker host and therefore does not establish resilience to host-root compromise. The installed client uses an independent local CA and dedicated browser profile; it makes no system trust changes.

The existing backend TEST CA expires November 8, 2026. The existing backend leaf expires November 6, 2026. These are local evaluation certificates; neither new client delivery mode turns them into publicly trusted production TLS. Renew backend/local demonstration leaves before expiry without replacing the trusted roots or changing browser origins. Public deployment needs the independently administered host/signer and trusted TLS described in [operations](operations.md).
