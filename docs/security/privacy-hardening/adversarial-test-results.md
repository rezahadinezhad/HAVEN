# Executed adversarial and compatibility verification

Source baseline: `8fb3c6c808d14277cc59e53d7363af62d9ea6c5b`; all current results are for this local change set. [verified-source.sha256](evidence/verified-source.sha256) records reviewed executable/config sources; [SOURCE_MANIFEST](../../../SOURCE_MANIFEST.sha256) covers the complete deliverable. No tests claim independent certification.

Commands below run from the repository root except pytest/manage.py (apps/api) and npm browser tests (apps/web), with protected `.local/test.env` exported, isolated haven-test PostgreSQL/Redis and explicitly trusted test TLS. Every run has timeout 120s (unit/Redis), 180s (DB/crypto/build), 300s (browser), or 30s (micro/CSP/config). Test tools' reported elapsed seconds are quoted; they may exclude process startup. Build wall time is explicitly measured.

| Test / command and scope | Actual reported duration | Outcome / evidence | Claim and unqualified properties |
|---|---:|---|---|
| Baseline pytest metadata/privacy/friend invitations | 8.23s | 21 PASS [baseline](evidence/baseline-tests.txt) | Pre-edit baseline only |
| Initial focused backend identity/role/Redis/metadata | 13.94s | 23 PASS [focused](evidence/backend-focused.txt) | Real SQL/Redis; selected checks |
| First broad pytest | 83.95s | 137 PASS, 1 FAIL [original](evidence/backend-regression.txt) | Old env fixture omitted new required keys; failure preserved |
| pytest optional-hostname/contracts/native privacy follow-up | 6.46s | 20 PASS [follow-up](evidence/backend-followup.txt) | Updated fixture and real native verification |
| pytest WebSocket/identity/roles/contracts milestone | 12.24s | 20 PASS [integration](evidence/backend-integration-final.txt) | Rotation, revocation, real grants; not Redis process restart |
| pytest migration/real-role | 3.65s | 2 PASS [migration](evidence/migration-permissions.txt) | Pre-0017 schema→0018, signed bytes/pending envelope/cursor preserved, retry and reverse refusal |
| pytest real notification-login subprocess | 2.59s | 1 PASS [worker process](evidence/worker-process.txt) | Uses actual Redis and no API signing key |
| Broad pytest after integration changes | 112.56s | 140 PASS [regression](evidence/backend-final.txt) | All then-current API tests; later small additions/changes have scoped evidence below, not a fictitious repeated full-suite verdict |
| pytest outbox batching/subprocess socket delivery | 5.38s | 3 PASS [cross-process](evidence/redis-multiprocess.txt) | Real worker process delivers to active socket; retries/coalescing |
| pytest final restore epoch/migration/grants/metadata | 8.74s | 16 PASS [recovery](evidence/final-scope-recovery.txt) | Invalidates old grants after restore namespace change without session/key reset |
| Final config/grant/identity tests | 5.31s | 19 PASS [final config](evidence/final-config-grants.txt) | Independent key startup rejection; minimal admin contract; column ACL scrub/regrant; no live production grant changes |
| Initial new browser spec | 6.4s | 1 PASS, 1 FAIL [original](evidence/browser-focused.txt) | Test's imported Node crypto shadowed browser crypto; corrected test import |
| New browser rerun | 4.2s | 2 PASS [rerun](evidence/browser-focused-rerun.txt) | Real sodium legacy/v2 AEAD and offline UI |
| First first-contact run | 18.1s | FAIL [original](evidence/browser-first-contact.txt) | Help text changed accessible name; explicit input aria-label fixed |
| First browser integration aggregate | 5.8s | 2 PASS, 4 FAIL [original](evidence/browser-regression-final.txt) | Native API restart was not ready; port conflict observed; services stopped/readiness checked, no weakened assertions |
| Browser aggregate: first-chat, privacy, session, MLS padding | 37.8s | 6 PASS [retry](evidence/browser-regression-retry.txt) | Real first contact, pin/tamper negatives, pagehide/idle/offline/logout, real OpenMLS reload/rekey |
| New media delivery tests | 7.0s | 3 PASS [media](evidence/browser-media-delivery.txt) | Actual two-account MLS→PostgreSQL media and view-once claim/replay denial |
| Latest browser first-chat/privacy after complete source restart | 23.7s | 5 PASS [complete](evidence/browser-complete.txt) | Latest restore-epoch links, hidden locked handle, actual media, EN/FA; single browser worker |
| Broader real browser MLS/media/view-once regression | 46.1s | 5 PASS [protocol regression](evidence/browser-protocol-regression.txt) | Real multi-device recovery, durable retries, full view-once UI; fixtures explicitly share introductions |
| Final SQL target projection | 6.86s | 15 PASS [projection](evidence/final-query-projection.txt) | First-contact claim does not SELECT target password/profile; inactive historical lookup remains valid |
| Manual introduction UI initial fixture | 21.2s | 4 PASS, 1 FAIL [original](evidence/browser-manual-introduction.txt) | Fixture reused a bare UUID before a shared relationship; correctly denied; fixture now supplies contact link |
| Manual introduction UI rerun | 1.1 min (reported) | 1 PASS [rerun](evidence/browser-manual-introduction-rerun.txt) | Advanced friend-link lookup, explicit verification, HTTP fallback, queued send |
| Native cargo test, legacy padding/replay/rekey/bounds | 4.02s build + 0.55s test | 1 PASS, 5 filtered [crypto](evidence/crypto-compatibility.txt) | Rust protocol source unchanged; selected real OpenMLS compatibility, not full vectors/fuzz |
| Latest Next production build and typecheck | 5.55s measured wall | PASS [build](evidence/frontend-build-review.txt) | Actual pinned build, regenerated offline asset revision; no dependency rebuild |
| Installer unittest after environment isolation change | 0.766s | 13 PASS [installer](evidence/installer-tests-final.txt) | Previous stale expected-integration-count failure [retained](evidence/installer-tests.txt) |
| Rendered Compose synthetic config | See JSON | PASS [isolation](evidence/compose-isolation.json) | New worker mapping contains no API signing/runtime credentials; no services deployed |
| Actual production proxy host/CSP module | 0.0453s | PASS [CSP](evidence/csp-check.json) | Seven malformed hosts denied, unique nonce, no arbitrary eval/inline permission |
| Publishable snapshot Gitleaks and path policy | 0.973s scanner | PASS [scan](evidence/secret-scan.txt) | 15.66MB scanned, no leaks found; local secret/config directories excluded |
| Release gate | <1s, exact wall not measured | Expected BLOCKED exit 1 [gate](evidence/release-gate.txt) | Source gate remains False; expected rejection is not a release pass |

Final static results are in [static-checks](evidence/static-checks.txt): Ruff, formatting, makemigrations drift, field inventory, TypeScript, generated contract and diff whitespace checks. [versions](evidence/versions.txt) bind dependency statements to actual installed/locked packages. [Short measurements](short-performance-results.md) are local arithmetic/CPU smoke only. New screenshots are synthetic and older historical screenshots are preserved at their original paths.

NOT_RUN: multi-hour/endurance/load fleets (prohibited), complete browser suite/Firefox/WebKit/physical mobile, actual Redis stop/restart/outage fleet, real rolling production key rotation, fresh hardened Compose deployment with narrow credentials, production/reference-host performance, new encrypted backup/WAL/replica restore drill, full upstream vectors/fuzz and independent security review. No timeout is labeled PASS. Test fixture ciphertext/signature markers in the SQL graph/migration tests do not count as cryptographic verification; native and real browser tests are the separate crypto evidence.

Publication preparation normalized trailing whitespace in text logs; recorded assertions, failures, outcomes and durations are unchanged.
