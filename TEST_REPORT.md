# Verification

The product's current source and the maintained local installation have separate, inspectable verification records. Results below do not imply independent certification or public-host/physical-phone qualification.

| Scope | Evidence |
|---|---|
| Current project presentation | Real encrypted synthetic conversation capture on desktop/dark/mobile viewport, status/privacy assertions and TypeScript check; [documentation verification](docs/project-presentation/verification.md) |
| Normal product source at `8545a76` | All five [GitHub CI jobs passed](https://github.com/rezahadinezhad/HAVEN/actions/runs/41704724702): publication/secret checks, frontend, Python/Rust advisories and API regression/image checks |
| Account-wide closure and deletion | 166-test backend milestone; 30 final focused tests; 3 Chromium workflows and 2 Firefox closure workflows. Suites overlap; [full scope and attempts](docs/security/account-closure/verification.md) |
| Verified client/API-origin separation | 14 boundary/installer tests on Python3.12 and3.14, Chromium and Firefox native MLS/media/reload plus hostile API while unlocked, signed release2 installed and separate frontend activated; [scope and evidence](docs/security/client-delivery/verification.md) |
| Installer and source integrity | 13 installer tests, production client build/typecheck, migration/inventory checks, secret scan and source manifests; [evidence](docs/security/account-closure/evidence/) |
| Running installation and interface cleanup | [November 4 upgrade and verification](docs/operations/installation-upgrade-2026-11-04/README.md): backup/restore, migrations, actual container/runtime checks and trusted-TLS browser probes |

Old reports retain their original source versions, dates, failed attempts and qualification limits. They are archived under [project history](docs/history/README.md), rather than mixed into the current status. Earlier load/soak observations do not establish a throughput SLA for the current archive/retirement changes.
