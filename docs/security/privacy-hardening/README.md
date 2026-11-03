# Privacy and security hardening — 2026-11-03

Baseline: `8fb3c6c808d14277cc59e53d7363af62d9ea6c5b`. All changes are local, reviewable source changes. **Experimental; production release remains BLOCKED.** No push, merge, deployment, real-history deletion, identity reset or backup destruction occurred.

The owner confirms there are no real users. This allowed a coordinated client/API upgrade to be the supported rollout. Existing vaults, exact pending ciphertext, signed credentials/history, recovery identities and legacy attachment reads remain intact.

| Phase | Status | Evidence / decision |
|---|---|---|
| 0 baseline and exposure | IMPLEMENTED_AND_TESTED | [Baseline](00-baseline.md), [inventory](exposure-inventory.md), [threat matrix](threat-matrix.md), synthetic graph test |
| 1 identity/local profiles | IMPLEMENTED_AND_TESTED | [Identity](01-identity-privacy.md): optional pseudonyms, UUID-only offline pointer |
| 2 device/API containment | IMPLEMENTED_AND_TESTED | [Device disclosure](02-device-disclosure.md): own/peer/admin contracts; scoped lookups/claims |
| 3 contact introduction | IMPLEMENTED_AND_TESTED | [Introduction](03-contact-introduction.md): expiring revocable bearer introduction, no default name |
| 4 Redis groups | IMPLEMENTED_AND_TESTED | [Routing](04-redis-metadata.md): independent HMAC key, rotation, real Redis/subprocess evidence |
| 5 narrow credentials | IMPLEMENTED_AND_TESTED | [DB matrix](05-database-compartmentalization.md): effective login denials, worker subprocess, rendered Compose; deployment NOT_RUN |
| 6 privacy profile | IMPLEMENTED_AND_TESTED | [Privacy settings](06-high-privacy-mode.md): optional signals off, mandatory ACK unchanged, EN/FA |
| 7 attachment sizes | IMPLEMENTED_AND_TESTED | [Padding](07-attachment-padding.md): bounded format 2, legacy AEAD, real MLS/SQL/view-once |
| 8 logs/retention | IMPLEMENTED_AND_TESTED | [Retention review](08-logging-retention.md): existing retention tests plus new-secret installer redaction |
| 9 browser/release | IMPLEMENTED_AND_TESTED | [Browser](09-browser-security.md): canonical CSP host, storage/lock tests, production build; independent review open |
| 10 historical graph retirement | DESIGNED_NOT_IMPLEMENTED | [Finality design](10-graph-retirement-design.md); no safe destructive prototype justified |
| 11 authoritative-source validation | IMPLEMENTED_AND_TESTED | [Source-backed review](security-review.md); sources support primitives, not HAVEN certification |
| 12 compatibility/migrations | IMPLEMENTED_AND_TESTED | [Migration/recovery](migration-and-recovery.md); pre-upgrade synthetic schema, retry and unsafe reverse refusal |
| 13 final evidence/review | IMPLEMENTED_AND_TESTED | [Results](adversarial-test-results.md), [measurements](short-performance-results.md), [final report](final-report.md) |

IMPLEMENTED_AND_TESTED is scoped to the named local tests. It does not imply all requested infrastructure scenarios or production qualification passed. [Remaining risks and NOT_RUN items](remaining-risks.md) are part of every phase's status. Existing retention/padding protections are credited to their original work rather than presented as newly implemented.

[Before/after leakage](privacy-leakage-before-after.md) · [Implementation order](implementation-plan.md) · [Final report](final-report.md)
