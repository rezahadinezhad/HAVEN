# Source development and verification

For service installation without a host compiler toolchain, use the [guided Docker installer](runbooks/guided-setup.md). This guide is for changing the source and running isolated development checks.

## Prepare the checkout

Prepared native server artifacts target Linux x86_64. Install Docker/Compose, Python with uv, Node.js, Rust and OpenSSL. Use the exact versions in [`.nvmrc`](../.nvmrc), [`.python-version`](../.python-version), [`rust-toolchain.toml`](../rust-toolchain.toml), and the dependency lockfiles; runtime images also pin their own versions/digests. [Operations](runbooks/operations.md) covers browser trust tools and TLS.

```bash
git clone https://github.com/rezahadinezhad/HAVEN.git
cd HAVEN
cargo install wasm-bindgen-cli --version 0.2.105 --locked -j 2
make prepare
make dev
```

The development endpoint is `https://127.0.0.1:8443`. Keep that terminal running. The server uses an immutable copy of its completed web build; restart it after rebuilding to evaluate changed assets.

In another terminal, start the isolated evaluation messenger:

```bash
make integration-dev
```

That endpoint is `https://127.0.0.1:8445`. Its settings refuse non-loopback hosts and keep encryption, authentication, CSRF, device approval and TLS checks active. The evaluation environment is not a deployment qualification switch.

Prepare its disposable browser trust and credentials before running browser workflows:

```bash
make browser-test-prepare
make test
```

Generated credentials are stored in a mode-0600 file under `.local`; no shared passwords are shipped. The test CA belongs only in the prepared isolated browser profiles. Never bypass a certificate error or mount a test CA signing key on a server. See [first conversation](user-onboarding/README.md) for the actual user flow.

## Check the layer you change

```bash
# Native adapter and pinned provider provenance
cargo test --manifest-path packages/crypto-core/Cargo.toml --locked -j 2
python3 scripts/check-crypto-vendor.py
bash scripts/test-provider-vectors.sh

# TypeScript and prepared browser integration
npm run typecheck --prefix apps/web
HAVEN_BROWSER=firefox npm test --prefix apps/web -- crypto.spec.ts integration.spec.ts

# Verified-client boundary and installer checks, using the prepared API environment
PYTHONDONTWRITEBYTECODE=1 apps/api/.venv/bin/python \
  -m unittest discover -s apps/verified-client/tests -v

# Dependency and publication checks
bash scripts/audit-python.sh
GITLEAKS_BIN=/absolute/path/to/gitleaks bash scripts/scan-repository.sh
make dependency-audit
```

The [CI workflow](../.github/workflows/repository-security.yml) records the complete backend/runtime-image, frontend, native/browser-crypto, advisory and installed-client checks. Browser scenarios that require explicit profiles or documentation capture remain opt-in; a successful build does not mean every physical device was tested.

For prose/assets, check local links, anchors, GitHub rendering, publication hygiene and the source manifest. Do not report unchanged cryptographic suites as freshly rerun. New fixture behavior should receive an appropriate focused check.

`make production-build` builds normal application images. `make release-check` verifies product activation. `python3 scripts/release-gate.py --qualification` separately reports outstanding external assurance. A loopback compatibility overlay is not a public-host hardening profile.

## Work with the existing boundaries

Account login, device approval and local unlock are separate. Optional WebAuthn PRF unlock needs a compatible authenticator and trusted hostname; a raw-IP origin retains the passphrase path. Changing origins does not move IndexedDB keys. [Unlock design](adr/0009-optional-device-unlock.md).

Recovery/history import must not resume stale private ratchet state. Retry already prepared ciphertext rather than encrypting again after uncertain acceptance. Database changes need coordinated migrations and restore checks, including the independent retirement journal. [Architecture](architecture/README.md) and [security design](security/design-guide.md) provide the relevant implementation paths.
