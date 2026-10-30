# Guided Docker setup

Run `./setup.sh` (or `make setup`) from the checked-out HAVEN directory. The wizard configures a separate Compose project; it does not overwrite the root `.env` or stop another installation. Use a regular Linux user with Docker access. Docker access is effectively privileged access to the host.

## Prerequisites

- Python 3.10 or newer, OpenSSL, and Docker with Compose 2.24.4 or newer.
- A Linux x86_64/amd64 Docker engine: the committed public-only native verifier targets this architecture.
- Internet access for the first Docker build and missing pinned infrastructure images. This wizard is not an offline artifact deployment tool.
- An unused HTTPS port and sufficient resources for Docker image builds and PostgreSQL. Host capacity is not qualified by installation checks.
- For the optional isolated local browser launcher: Chrome/Chromium and NSS `certutil` (commonly supplied by `libnss3-tools` on Debian/Ubuntu). The installer diagnoses prerequisites; it does not install system packages or run a remote shell script.

The application runtimes run in Docker. The host does not need Node.js, Rust, uv, or a PostgreSQL installation.

## Questions and modes

The wizard asks for mode, a unique installation name, a community name, an administrator username, and an HTTPS port. It generates a random administrator password and separate high-entropy application, bootstrap-database, migration-role, and runtime-role secrets. There are no shared default passwords.

**Local evaluation** binds the listener only to `127.0.0.1`, defaults to port 8447, and permits the exact `localhost` hostname. Real browser encryption, authentication, device approval, CSRF, and TLS remain enabled. Its integration settings refuse remote hosts. This mode is for this computer, not invitations to remote users.

The wizard generates a disposable seven-day test CA and a three-day leaf certificate with an IP SAN and localhost DNS SAN. The CA signing key stays outside the mounted TLS directory. Trust is imported only into the wizard's separate browser profile, never the system trust store. Run the printed `open-browser.sh` launcher. It uses the browser sandbox without certificate-bypass flags. Without the browser tools, setup can pass its verified HTTPS checks, but browser trust still needs preparation. Do not click through a certificate warning.

On hosts that cannot launch a container with `no-new-privileges`, the wizard stops or explicitly offers a reduced-hardening **local-only** profile. It never selects that profile silently. Server mode rejects it. Other existing container/network controls remain applied. This local exception is not a production profile.

**Gated server** asks for the real server IPv4 address, optional exact hostname, an existing full-chain PEM certificate, matching unencrypted private-key file with mode 0600, and optionally an independently verified public root bundle. The certificate must cover the IP and any configured hostname, be a server leaf rather than a CA, match the key, have a valid trust chain, and have at least 48 hours remaining. Private-root certificate acquisition, offline CA custody, client trust installation, public IP reachability, firewall rules, NAT, renewal and standby infrastructure remain operator responsibilities. Do not put an offline CA signing key on the server.

Server mode binds the chosen port on IPv4 interfaces and retains the ordinary blocked cryptographic release gate. It can prepare the stack and administrator login; it cannot enable production messaging. No environment variable supplied by this wizard overrides independent review or release acceptance.

## What happens automatically

1. Verify the source manifest and prerequisites; reject another Docker project, database volume, network, or occupied listener using the chosen name/port.
2. Save protected configuration and credentials; validate and atomically publish TLS material.
3. Build API and web images from the checkout, using the locked dependencies and committed browser/native artifacts. Pull missing digest-pinned infrastructure images.
4. Start the private PostgreSQL and Redis services, create least-privilege database roles, and apply durability-checked migrations.
5. Bootstrap the initial administrator through stdin and start the application, workers and ingress.
6. Verify the configured TLS identity and trust chain, strict browser CSP, expected release/crypto gate, and saved administrator login. Log out the probe session.

The server check connects locally while validating the configured server identity; it does not prove that a remote client can reach or trust the endpoint. Browser message keys are generated on the user's device during first setup. The installer does not create or retain client message keys, recovery kits or unlock passphrases. After sign-in, follow the in-app browser setup and [first conversation guide](../user-onboarding/README.md).

## Credentials, logs and management

The wizard prints exact paths after installation. For an installation named `my-haven`, state is under `.local/setup/my-haven/`:

| File | Purpose |
|---|---|
| `admin-credentials.json` | Generated initial administrator username/password; mode 0600. Transfer the password into a password manager and treat this file as a secret. |
| `config.env`, `state.json` | Secrets and resumable configuration; mode 0600. |
| `setup.log` | Protected build/command diagnostics with generated secret values redacted. Never publish real installation logs without review. |
| `tls-bundle/tls/` | Leaf certificate and leaf private key mounted into ingress; only the public leaf is mounted into the API. |
| `tls-bundle/issuer/` | Local evaluation CA only; not mounted into containers. |
| `open-browser.sh` | Optional isolated local browser launcher. Browser state and keys remain in that separate profile. |
| `manage.sh` | Compose wrapper with the exact project/configuration arguments. |

For example, run the printed credential-file path through a local JSON viewer to retrieve the generated password. Do not paste credentials or the installation directory into an issue or commit. The directory is Git-ignored and owner-only, but host root/Docker administrators can still read its secrets. Installation is not a defense against host compromise.

```bash
.local/setup/my-haven/manage.sh ps
.local/setup/my-haven/manage.sh logs --tail 50 api
.local/setup/my-haven/manage.sh stop
.local/setup/my-haven/manage.sh start
./setup.sh --resume my-haven
```

Stopping preserves the database. Do not use `down --volumes` unless you intend to destroy this installation's data. Keep configuration and database backups separately protected. Existing backup scripts use the original deployment configuration; do not assume they automatically select a wizard project. Automated encrypted backups, restore qualification, certificate renewal, monitoring, and a second endpoint must be configured and tested before any production qualification.

## Interrupted setup and upgrades

Fix the reported prerequisite or Docker/TLS issue, then resume with `./setup.sh --resume <name>`. A per-installation lock prevents concurrent installers. Resume retains credentials and existing database data, repeats idempotent role/migration/bootstrap steps, and verifies login again. It will not reset an existing administrator password. If the password has since been changed, the initial-credential probe fails rather than overwriting the account; update the protected credential file with the current password before retrying.

An interruption during certificate preparation does not publish an incomplete TLS bundle. A completed bundle is reused on resume and validated again. Expired or nearly expired certificates fail closed: resume does not silently replace trust roots or issue new credentials. Test certificate renewal is not automatic.

Resume requires the identical source manifest. This first installer does **not** implement in-place application upgrades, account recovery, or certificate rotation. For a changed release, retain the old checkout and protected state, take and test backups, and follow a separately reviewed migration/rotation procedure. Do not regenerate the manifest or edit the saved source hash to evade this check. For a separate clean evaluation, use a new name and port; it has a separate database and does not migrate old conversations.

The source manifest detects accidental changes relative to the supplied checkout; it is not an independent signature or security audit. Establish the source/release provenance separately.

## Automation and tests

For controlled automation, `./setup.sh --answers /absolute/path/answers.json` accepts an owner-only mode-0600 JSON object with `mode`, `slug`, `name`, `admin`, `ip`, `port`, and `hostname`. Local values must use `127.0.0.1` and an empty hostname or `localhost`. `local_compatibility: true` is an explicit test-only choice. Server answers additionally require `certificate`, `private_key`, and optional `roots`. Passwords are generated, never supplied as command-line arguments. Do not commit real answers or credentials. `--answers` and `--resume` are mutually exclusive.

Run `make setup-test` for stdlib tests, including actual OpenSSL chain/identity rejection checks. Recorded real Docker setup results are retained under `docs/evidence/` and indexed in the test report. Successful setup is engineering evidence only. Independent application/cryptographic review, physical-device trust tests, capacity and infrastructure acceptance, and remaining documented release blockers still apply; see [SECURITY_STATUS.md](../../SECURITY_STATUS.md).
