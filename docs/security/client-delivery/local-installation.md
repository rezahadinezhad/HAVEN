# Maintained local client installation

The existing HAVEN service at `https://127.0.0.1:8444` and its account/vault state are preserved. No database migration or personal device enrollment is needed for this delivery change.

**Signed release 1 is installed and running.** Its reviewed source is `d38d934243d31199a02a8965d795a22be0414c40`; the final operational report is a later documentation commit. No QA helper is present in the production release.

| Component | Maintained location |
|---|---|
| Installed client | `https://127.0.0.1:9443`, loopback only; automatic user service `haven-verified-client.service` |
| User launcher | `/home/reza-hadinezhad/.local/bin/haven-verified-client`; application menu entry **HAVEN Verified Client** |
| Protected installed state | `/home/reza-hadinezhad/.local/state/haven/verified-client` |
| Independent frontend demo | `https://127.0.0.2:8447`, separate non-root/read-only container; only the existing ingress network, no DB network or backend secrets |
| Public distribution | `.local/verified-client/HAVEN-verified-client-release-1.tar.gz`, signed archive, public verifier/key and license notices; contains no private signing key |
| Frontend operator helper | `.local/manage-verified-frontend.sh` |

Publisher public-key DER SHA-256: `2cecd962301f0292caca6089a23c0a2c8fb00fb055327342d09daa6abfaaaf99`.

Manifest SHA-256: `77cbcc43015cc191a48c6a6d2de15bae288ce94e054400be9870f63bb0215977`.

The fingerprint printed here is a record, not an additional independent trust authority. First-install trust must be anchored through the reviewed source/publisher channel, independently of the messaging server.

Both actual endpoints passed trusted-TLS production UI sign-in/sign-out with zero foreign browser requests/page errors. No personal vault or MLS device was created. Installed mode has no registered service worker. The separate image refuses an altered signed worker before executing its runtime; production Python3.14.9 has only the four required packages and no pip/Django/pytest. [Public deployment checks and artifact digests](evidence/) contain no session cookies or credentials.

The dedicated interactive launcher uses the already qualified Firefox binary in the local Playwright cache and private copies of its required shared libraries. It never opens a personal browser profile. If that externally managed browser cache is removed/upgraded, update the launcher to a trusted Firefox binary; this portable distribution does not claim an OS-signed browser bundle.

The local user service uses private temporary storage and read-only home/system protection with an explicit write path for its own profile. Stop it before a signed update with `systemctl --user stop haven-verified-client.service`; close the dedicated browser, apply through the installed launcher, then start the service again. `systemctl --user disable --now haven-verified-client.service` reverses automatic startup without deleting vault state.

The local administrator credential was refreshed and prior sessions revoked after a smoke-test assertion included it in a private diagnostic. That diagnostic was removed, and subsequent assertions suppress page/error details. The current credential remains only in the protected existing operator record, outside this repository. No personal vault state was involved.

The local frontend demonstration uses a distinct loopback IP/origin, TLS leaf and container without backend database credentials or the database network. It shares the development Docker host and therefore does not establish resilience to host-root compromise. The installed client uses an independent local CA and dedicated browser profile; it makes no system trust changes.

The existing backend TEST CA expires November 8, 2026. The existing backend leaf expires November 6, 2026. These are local evaluation certificates; neither new client delivery mode turns them into publicly trusted production TLS. Renew backend/local demonstration leaves before expiry without replacing the trusted roots or changing browser origins. Public deployment needs the independently administered host/signer and trusted TLS described in [operations](operations.md).
