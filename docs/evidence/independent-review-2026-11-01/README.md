# Independent source review evidence — 2026-11-01

Revision: `61d77683d140daf26e087bd4c2f1971b7a2a97c1`.
The reviewed local revision has the same source tree as published GitHub `main` at `f539f47`; use that public commit to inspect the baseline.

All identities and contents in probes are synthetic. No deployed service was attacked. These probes exercise production implementations through controlled boundaries; they are not capacity or complete deployment acceptance tests.

Run from the repository root with its existing pinned dependencies installed:

```bash
mkdir -p .local/independent-review
cp docs/evidence/independent-review-2026-11-01/probes/* .local/independent-review/
apps/api/.venv/bin/python .local/independent-review/api_probe.py
node .local/independent-review/build-probe.mjs
node .local/independent-review/client_probe.mjs
apps/web/node_modules/.bin/esbuild apps/web/src/lib/vault-worker.ts --bundle --platform=node --format=cjs --outfile=.local/independent-review/vault-worker.cjs
node .local/independent-review/vault_probe.cjs
apps/api/.venv/bin/python .local/independent-review/run_auth_tests.py
```

- API probe: in-memory SQLite schema created from current models; local-memory rate counters; real Django middleware and CSRF/session authentication. The global-login exhaustion check seeds the actual rate helper 300 times and then sends an HTTP test-client login request. It does not perform 300 external requests. Proof rows are synthetic blobs to measure selected columns, not valid MLS messages.
- Client probe: production Messenger bundled with API/persistence adapters replaced by mocks. Real checked-in OpenMLS WASM encrypts/decrypts; real delivery signatures/hash chain are verified; checked-in native verifier accepts the offending wire structure. A retained trusted checkpoint at sequence 1 initializes the two-member group. HTTP server acceptance is inferred from its wire/signature checks, not exercised end to end in this probe. Two sync attempts encounter the same malformed application plaintext before persistence. The later message is valid and remains unprocessed.
- Vault probe: production TypeScript worker compiled for Node to retain working Node entropy/I/O adapters, then receives synthetic seal requests. It tests worker size enforcement; it does not measure browser frame rate or full-vault realistic capacity. The minimal snapshot omits actual MLS storage, so real capacity may be lower. Wall-clock durations are illustrative single samples, including the first KDF.
- Selected pytest run: 9 passed; 4 deselected (concurrency and migration cases). SQLite/local-memory cache substitute for PostgreSQL/Redis. No claim of PostgreSQL concurrency qualification.
- Rust tests: 4 native library tests passed, plus empty binary/doc-test suites. Upstream vector suites and browser integration were not rerun.
- Full npm audit exited nonzero with one underlying moderate advisory and three affected dependency entries. Production-only npm audit was clean. Python audit included development groups. Rust audit found no vulnerability and one unmaintained-crate warning.
- `npm run typecheck --prefix apps/web` passed; its short output is recorded in `typecheck.txt`.

Audit metadata reflects the databases available during this run; clean results are not evidence of absence of unknown vulnerabilities.
