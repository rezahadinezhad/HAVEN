# Follow-up dependency review — 2026-11-03

The owner authorized review of the six proposals opened after PR #19. This batch covers PRs #20–#25 only. New proposals opened subsequently are a separate queue. One consolidated update keeps manifests, runtime images, generated workers and qualification evidence consistent.

## Decisions

| PR | Proposal | Decision |
|---|---|---|
| #20 | Production Python 3.12.15 → 3.14.9 | Accept subject to final qualification. Django 5.2 and the project support Python 3.14. Use the bot's immutable image digest in both online/offline Dockerfiles. Development stays on pinned Python 3.12.15; CI tests that environment and both database configurations on the exact production Python image. |
| #21 | @types/react-dom 19.2.2 → 19.3.0 | Accept; matches React/React DOM 19.3.1 and current React types. |
| #22 | pytest 9.1.1 → 9.2.0 | Accept after rerunning backend suites with existing security assertions. Explicit function-scoped async fixtures preserve the suite's existing fixture lifetime and resolve the reported upcoming-default warning. |
| #23 | openapi-typescript 6.7.6 → 7.13.0 | Decline this version. Its peer dependency is TypeScript `^5.x`; the qualified application compiler is 7.0.2. A clean install fails with ERESOLVE, and the bot's frontend CI also fails. No forced/legacy peer installation or compiler downgrade is used. Retained 6.7.6 generates the checked-in contracts identically after formatting normalization. No claim about a newly audited 7.x transitive graph is made because installation failed. Revisit when the generator supports the current compiler. |
| #24 | idb 8.0.3 → 8.0.4 | Accept subject to full browser storage qualification; upstream fixes NaN reads and reduces bytes. No HAVEN IndexedDB schema change. |
| #25 | libsodium-wrappers-sumo 0.7.15 → 0.8.4 | Accept subject to full browser qualification. Engine reports libsodium 1.0.22. Use its included TypeScript definitions and remove the obsolete external @types package. Rebuild the shipped vault worker and offline shell. Preserve Argon2id-3/64 MiB, XChaCha20-Poly1305 records, AAD, nonce generation and vault version. No proprietary crypto or identity reset. |

## Compatibility and verification

A new actual-browser regression loads the exact pre-update worker preserved from the reviewed main branch. It seals checkpoints and separately bound history records with the old worker, opens them with the new worker, seals new records and opens them with the old worker. Both directions preserve payloads and reject modified ciphertext, wrong passwords, account scopes and history bindings. Fresh nonce, vault version and KDF identifiers are asserted. The served updated worker's digest must equal the just-built artifact. The initial Chromium compatibility probe passes.

The production Python proposal changes only the image. The locked application versions and development Python pin remain consistent with the existing supported range. Initial exact-image runs passed 132 tests per database configuration. Final runs after the explicit async-fixture setting pass 132 tests in each of the four Python/database combinations. Both offline production images build with networking disabled; the API image reports Python 3.14.9 and excludes pytest. Type-check/build, npm and complete Python advisory audits, 13 canonical/signature vectors, attachment plaintext digest, and eight scanner-policy probes pass. Full Chromium/Firefox suites and independent CI remain in progress and will be recorded before merge.

The pinned uv release cannot download a standalone CPython 3.14.9 build. Qualification therefore uses the exact verified Docker image with its Python interpreter, not a substituted Python patch release. Local PyPI DNS failed again; the exact pytest wheel was downloaded with normal HTTPS validation using a per-command resolved address and verified against uv.lock. Runtime wheels for 3.14 were downloaded inside the pinned image with `--require-hashes`; offline builds use networking disabled. No system DNS, TLS policy, production container or real user database is changed.

The first attachment-helper probe used insufficient stdout buffering for a 1 MiB encrypted fixture; rerunning with bounded 4 MiB buffering passes actual chunk encryption/decryption. The OpenAPI probe never installed, so subsequent missing executable/lockfile diagnostics are consequences of its peer conflict, not evidence of a successfully audited generator.

CI retains the prior five checks and adds exact-production-Python backend runs plus a minimal production-image build/import check. The existing host rejects no-new-privileges execution for baseline and candidate images alike; GitHub's independent restricted-container checks remain authoritative for that host-dependent execution restriction. No deployment flag is relaxed.

## Limits

The previous throughput/two-hour measurements remain tied to their original dependency graphs. No new capacity, battery, physical-device, independent cryptographic audit or fresh OS-container security qualification is claimed. Production `CRYPTO_READY=False` and release-gate blockers remain intact. Browser fixtures and private keys stay in protected .local diagnostics; published evidence contains aggregate results and source/artifact checksums only.

## Primary references

- [Django 5.2 Python compatibility](https://docs.djangoproject.com/en/5.2/releases/5.2/#python-compatibility).
- [libsodium.js releases](https://github.com/jedisct1/libsodium.js/releases) and npm package-provided types/lockfile integrity.
- [idb 8.0.3 to 8.0.4 source comparison](https://github.com/jakearchibald/idb/compare/v8.0.3...v8.0.4).
- [OpenAPI TypeScript migration guide](https://openapi-ts.dev/migration-guide); the actual 7.13.0 peer requirement and clean-install failure are retained in qualification diagnostics.
