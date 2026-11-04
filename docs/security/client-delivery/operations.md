# Operating the verified client

## First trust

Obtain the initial `bootstrap.py`, publisher public key and this procedure from an independently authenticated, reviewed source checkout/distribution. Never trust a bootstrap or replacement key solely because the messaging website serves it. Independently compare the public-key DER fingerprint:

```sh
openssl pkey -pubin -in release.pub -outform DER | sha256sum
```

The maintained publisher root is `apps/verified-client/trust/release.pub`. Its private key is never committed or copied into an image. Back up the signing key and its adjacent monotonic `.releases.json` ledger together, encrypted and independently protected. A lost key has no website-based recovery. A compromised key requires a new independently authenticated trust ceremony/launcher distribution; an ordinary signed update cannot replace the installed root.

Prerequisites on Linux: trusted Python 3.12 or 3.14 with `venv`/`ensurepip`, OpenSSL with Ed25519 support, NSS `certutil`, and Firefox. Supply platform-compatible wheels for all four hash-locked runtime dependencies. Download them on a trusted connected build machine with:

```sh
python3 -m pip download --require-hashes --only-binary=:all: \
  -r apps/verified-client/requirements.lock -d /protected/client-wheels
```

Installation is offline. Use an absolute, private state directory; replace the example fingerprint with the independently verified value:

```sh
python3 apps/verified-client/bootstrap.py --state /private/haven-client apply \
  --bundle /verified/release.haven --trusted-key apps/verified-client/trust/release.pub \
  --key-fingerprint VERIFIED_DER_SHA256 --wheelhouse /protected/client-wheels
/private/haven-client/haven-client run -- configure \
  --api-origin https://API_IP:PORT --port 9443
/private/haven-client/haven-client run -- serve --open
```

For an API using an independently supplied private CA, add `--api-ca /verified/api-ca.crt` during configuration. Use exact HTTPS IPv4 origins, consistent with HAVEN's current IP-origin deployment model. Never bypass TLS warnings or import the messaging server's private CA into the dedicated client browser. `--browser-binary /trusted/firefox` selects a trusted Firefox installation if the default binary cannot access a private profile (for example a sandboxed distribution).

The launcher generates its own local CA/leaf and imports that root only into `/private/haven-client/browser`. Keep the entire state directory private (0700), including local TLS keys and browser storage. The leaf lasts one year; the local root lasts ten. Before leaf expiry, stop the client/browser and issue a replacement loopback leaf using the existing private root, same SAN `IP:127.0.0.1`, serverAuth and private permissions. Do not replace the root, port or profile during routine updates. Certificate renewal does not require moving vault state. Keep the host/browser clock correct.

## Publishing and updates

Build from reviewed, committed, clean source with the pinned Node image. The build marker ties the output to the current client source inputs; stale output and test harnesses are refused for production signing.

```sh
docker build -f apps/verified-client/Dockerfile.web-build \
  --output type=local,dest=/fresh/client-build .
python3 scripts/package-verified-client.py --web /fresh/client-build/web \
  --signing-key /offline/publisher/signing.key --sequence NEXT_INTEGER \
  --output /public-distribution/release.haven
```

Use a fresh export directory. The signing key must be Ed25519, mode0600. Preserve the publisher ledger; never reset it to work around refusal. `--development` permits dirty-source QA builds and must use a separate disposable key. Production signing rejects QA helpers, proof-of-function files and source maps. Do not share the private key with CI.

Close the dedicated browser and stop the client. Use the **already installed** launcher to apply a manually obtained package:

```sh
/private/haven-client/haven-client apply --bundle /verified/new-release.haven \
  --wheelhouse /protected/client-wheels
/private/haven-client/haven-client run -- serve --open
```

The root key is pinned; no replacement key argument is necessary. The existing verifier authenticates maintenance updates to the launcher itself under that same pinned key. No website supplies or replaces the root. Do not delete `active.json` or reinstall a new profile to bypass a rollback rejection. Recover a defective release by signing the reviewed repair with a higher sequence, even when it restores older source behavior. Keep the old release directory for diagnostics; it is not an authorized downgrade path. Full deletion/rollback of all local state is outside the monotonic-state guarantee, as is an attacker with local filesystem control.

## Independent frontend deployment

Build the server image from reviewed source and a public release directory containing only `release.haven`:

```sh
docker build -f apps/verified-client/Dockerfile \
  --build-context client_release=/public-distribution \
  --build-arg CLIENT_MINIMUM_SEQUENCE=REVIEWED_SEQUENCE \
  -t registry.example/haven-client:REVIEWED_VERSION .
```

The image bakes the reviewed public root, verifies the package during build and startup, and runs non-root without pip. It cannot be built with a release signed by a different key. Pin the resulting image digest in `HAVEN_CLIENT_IMAGE`.

Use `infrastructure/compose.client.yml` on a separately administered host. Supply an independently issued frontend TLS leaf/key and the API's public CA in a dedicated directory readable by uid10001. Never mount a CA signing key, publisher private key, backend credentials, DB network or Docker socket. Set the image, dedicated bind IP/HTTPS origin, logical API origin and TLS directory as required by the compose file. The API continues to see its own fixed Origin; the browser uses same-origin cookies on the frontend bridge. The frontend host can observe session cookies and API metadata but receives encrypted message content; it remains trusted to deliver web code.

Keep standard cap-drop, read-only filesystem, no-new-privileges and resource restrictions. An explicit loopback-only host compatibility override may omit no-new-privileges when the local Docker host cannot support it. That exception does not qualify public deployment. Transport-address overrides are for operator-configured networking only and retain logical upstream TLS hostname verification.

For frontend updates, stop/switch the gateway image, retain the same frontend origin/TLS identity and let clients reload. The web edition uses release-versioned assets and a service worker; existing open pages may need a reload after a server upgrade. Installed clients update independently and are unaffected by a web-host image switch.

### Initial release1 launcher maintenance

Local release1 was installed before the runtime-lifetime fix. Its initial launcher did not replace itself during updates. The maintained operator installation is upgraded using the reviewed source bootstrap and the already pinned root to apply release2; the TLS/browser/vault profile stays in place. Release2 and later authenticate launcher maintenance updates as part of normal signed installation. The runtime inherits the kernel update lock, even if a parent is killed abruptly, and ordinary launcher termination forwards the signal and reaps the runtime.


### Installed transport override

An operator may set `--upstream-address` and `--upstream-port` during `configure`,
or preserve an existing protected profile's `api_origin` while explicitly setting
those two optional fields with the client stopped. The transport port is an
integer in1..65535. Certificate and request identity remain the logical API origin;
the separate address/port only select the socket destination. Installed `serve`
still refuses endpoint overrides on its command line. See the maintained
[device-unlock installation](../device-unlock-installation.md) for the local
compatibility listener. No website or API response can reconfigure these fields.
