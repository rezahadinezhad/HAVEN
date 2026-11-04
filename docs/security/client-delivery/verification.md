# Client delivery verification · November 4, 2026

These are engineering checks, not an independent penetration test or cryptographic certification.

| Check | Result and scope |
|---|---|
| Signed archive and hostile TLS API | 14 Python tests pass: wrong key, changed HTML/JS/worker/WASM/runtime/bootstrap, altered manifest, ZIP traversal/duplicates/compression, sequence replay/conflict, API HTML/JS/redirect/compression, strict Host/Origin/cookies/headers, TLS hostname checks and real TLS WebSocket bridge |
| Actual installer | First-trust fingerprint required; authenticated runtime executes; changed disk executable rejected; live private browser blocks update; runtime lock survives parent SIGKILL and normal termination reaps the child; authenticated launcher maintenance preserves the pinned root; failed/replayed update preserves active release and separate dependency environment |
| Chromium | Real TLS, two synthetic accounts, native MLS enrollment/fingerprint pins, encrypted text and file upload/download, persisted vault reload and production UI unlock; hostile API switched on while unlocked; API-supplied script blocked, signed worker unchanged, no browser traffic to upstream |
| Firefox | Same workflow and hostile-origin checks; dedicated test trust only, no TLS ignore flags |
| Exact production Python | All 14 tests also pass on the pinned Python3.14.9 image with offline hash-locked wheels; the installer test tmpfs explicitly permits executable venv files |
| Activated release | Signed release1 on both real endpoints: UI sign-in/sign-out, exact release digest, QA helper404, zero foreign browser requests/errors; container startup refuses a tampered worker |
| Client build | Complete UI/workers/WASM/fonts build in pinned Node26.13.0 image; TypeScript check passes |
| CI | New verified-client job runs boundary/installer checks, pinned standalone frontend build and tests using exact production Python3.14.9; separate client dependency graph included in advisory audit |

The first restricted Docker test attempt used a default noexec tmpfs, so copied venv interpreters could not execute. Repeating the installer qualification with an explicitly executable **test-only** tmpfs passed; the deployed gateway retains a noexec tmpfs. No verifier bypass or dependency downgrade was used.

Public logs and synthetic screenshots are in [evidence](evidence/). The browser harness uses a separately signed disposable QA release containing an explicit integration helper. That helper is refused by production packaging and is absent from the real published release. The controlled hostile proxy is a loopback-only test fixture and is never copied into a production image.

The final browser test runner used host Node24 for Playwright; production assets were built using the pinned Node26 image. Both browsers used real certificate verification. No live user's personal vault, keys or messages were opened or migrated.

The maintained signed release and deployment verification are recorded separately in [local installation](local-installation.md). CI output after pushing is authoritative for remote job completion; adding a job does not by itself mean that job has run.

Reproduce the Python boundary/installer tests with the existing locked API development environment:

```sh
PYTHONDONTWRITEBYTECODE=1 apps/api/.venv/bin/python \
  -m unittest discover -s apps/verified-client/tests -v
```

The browser test `apps/web/tests/verified-client.spec.ts` skips unless `HAVEN_VERIFIED_PROFILE` points at a configured signed QA client. It expects an isolated test backend, existing synthetic administrator credentials in `.local/ui-credentials.json`, and `/qa-client.js` in a disposable signed release. `HAVEN_TEST_ATTACK_FILE` enables the explicit loopback adversarial fixture; the fixture's TLS/API ports are independently configurable. Never use a real publisher key or a user's personal profile for that harness.
