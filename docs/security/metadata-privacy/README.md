# Metadata privacy engineering — 2026-11-01–02

Implemented hardening, with central routing deliberately retained. **Production remains BLOCKED.** This initiative does not provide anonymity, remove the social graph, or constitute independent security certification. Baseline is commit `0240706`, merged [PR #18](https://github.com/rezahadinezhad/HAVEN/pull/18). Its segmented atomic vault, malformed-content quarantine, source-isolated sign-in, quotas, projected proof reads, receipt versions and signed pagination are preserved.

## Deliverables

| Deliverable | Evidence |
|---|---|
| A. Complete persisted field inventory | [inventory.csv](inventory.csv), 191 current fields across application/framework/automatic join models plus eight retired fields; [flow inventory](flows.md) |
| B. A1–A8 threat model | [threat-model.md](threat-model.md) |
| C. Architecture and routing alternatives | [ADR 0013](../../adr/0013-metadata-privacy.md), [research specification](routing-research.md) |
| D. Source changes | Migrations 0013/0014/0015/0016, transactional authority/target fences and pending enrollment cleanup, backend retention/serialization/worker changes, Rust native padding, regenerated OpenAPI/TypeScript/WASM/offline assets |
| E. Upgrade and recovery | [migration runbook](upgrade.md), isolated dump/restore drill |
| F. Regression and adversarial tests | `core/tests/test_metadata_privacy.py`, `tests/metadata-privacy.spec.ts`, native padding test, existing full suites |
| G. Exposure comparison | [leakage.md](leakage.md), machine-readable migration counts and real SQL assertions |
| H. Performance | [performance.md](performance.md), native baseline/current measurements; remaining dimensions explicitly unmeasured |
| I. Disclosures | [English/Persian user notice](privacy-notice.md), [retention policy](../server-data-retention.md) |
| J. Final status and requirement checklist | [completion report](completion-report.md), [requirements matrix](requirements.csv), [original report](report.md), [executed evidence](../../evidence/metadata-privacy-2026-11-01/README.md) |

The CSV records each field's information/type, sensitivity, purpose, authorization/API exposure, relationships, duplication, retention, classification and source. REQUIRED means needed by the current protocol; REPLACEABLE means replacement requires a new reviewed protocol, not that a random alias fixes privacy. REDUCIBLE means retain only for the documented purpose/window. REMOVABLE includes fields removed in 0013 and an unused normally-empty Device.credential placeholder that HAVEN does not populate/read; removing that empty slot would not reduce current collected information. Custom legacy contents need separate operator assessment. Source lines identify model definitions; detailed request/worker paths are in flows.md. Automatic Django tables are included even when HAVEN has no write path.

Reproduce coverage without reading records: export isolated test environment and run `apps/api/.venv/bin/python scripts/check-metadata-inventory.py`. An exact field-set and declared-source-line check prevents silently omitting new columns or retaining stale local field references. This mechanical coverage check does not prove the semantic inventory complete for every possible host extension. Operator-installed telemetry, PostgreSQL extensions, provider snapshots and browser extensions require separate review.

No schema change to browser storage, no reset of identities, no ratchet rewind, no new credential type, and no new runtime service is required. Migration 0013 removes server-only information and allows expired KeyPackage device links to become NULL. It is intentionally irreversible; use the controlled upgrade procedure.

The continuation adds [ADR 0014](../../adr/0014-request-authority-and-enrollment-retention.md), replay-safe deletion of expired pending enrollments, narrower cookie-authentication/membership/public-credential SQL reads and scoped enrollment challenge handles. The [continuation evidence](../../evidence/metadata-completion-2026-11-02/README.md) records real failed race reproductions, remediation, actual DB head rewind checks and isolated load limits.

The subsequent [runtime fixes](throughput-fixes.md), [ADR 0015](../../adr/0015-bounded-api-runtime-and-storage-locks.md), [realistic workload plan](workload-plan.md) and [case evidence](../../evidence/metadata-realistic-workload-2026-11-02/README.md) distinguish people, online devices and connections. Local ordinary 20/s bursts pass; historical heavy-stress failures remain visible, and combined/endurance/reference-host gates require their own measured outcomes.

The final [realistic results](workload-results.md) include a passing natural combined 20/s burst and a complete 7,200-second 2/s soak: 14,400 applications, 60,414 durable recipient copies, 108 MLS updates and 200 restored native checkpoints. Failed stress, latency and availability attempts remain indexed. These are local native cases, with reference-production and external release gates unqualified.
