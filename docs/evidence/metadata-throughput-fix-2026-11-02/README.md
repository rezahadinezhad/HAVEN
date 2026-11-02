# Runtime and lock investigation evidence — 2026-11-02

These are historical synthetic diagnostics and checks after source `b988879`, before the revised realistic matrix and notification batching. No output here qualifies production capacity. The final four-process heavy-stress run is **NOT_SUSTAINED**: 592 accepted application messages, 5,328 durable recipient copies, 42.28 seconds including drain. The eight-process control also fails. Their drained rates are neither sustained rates nor measured maxima.

Read the [investigation](../../security/metadata-privacy/throughput-fixes.md), [ADR 0015](../../adr/0015-bounded-api-runtime-and-storage-locks.md) and [revised workload evidence](../metadata-realistic-workload-2026-11-02/README.md). The former default means 100 accounts × five independent MLS devices, 500 sockets, all nine recipients durable before the next conversation send, and five concurrent encrypted files. Reproduce that population explicitly with `--profile legacy-stress`; the new default is different. No before/after ratio across different populations is valid.

## Interpretation of failures and controls

- `websocket-executor-before.txt`, `global-budget-before.txt` and `ack-critical-section-before.txt` are real failed concurrency reproductions; their after/regression files demonstrate each isolated correction.
- `backend-query-optimized-first.txt` is the failed projected-model field-order implementation. `auth-projection-corrected.txt` and later complete suites cover the correction. One ephemeral synthetic session value in the failed diagnostic has been redacted; no credential is needed to interpret it.
- `cpu-diagnostic-low-rate.json` contains invalid cross-thread `cProfile(time.thread_time)` values. Discard those per-request CPU values; this is not capacity qualification. `cpu-diagnostic-failed.txt` is a failed diagnostic. Later optional call profiling uses wall time and is not CPU attribution.
- `short-locks-20-asgi.json` contains the failed pool/503 diagnostic that overlapped backend testing. It is not clean capacity evidence. Temporary WSGI/Gunicorn comparisons are diagnostic; those packages are absent from final runtime dependencies.
- `pool-drill-initial-assumption.txt` preserves a failed assumption before the corrected, real database recovery drills. `instruments-host-python-missing-dependency.txt` records use of the wrong interpreter before rerunning in the locked API environment.
- The 300-second 10/s stability attempt was interrupted at the user's request, without a completed JSON result. Its pending data remains private; it is not a pass.
- Backend 130-test and browser results apply to the pre-notification-batching implementation. Later 132-test backend checks, real socket notification tests and updated offline image source proof are in the revised workload evidence.
- `offline-image-source-check.json` binds the earlier image to its earlier source hashes. It is not a claim that the image contains subsequent publisher changes. No deployed image or production container was replaced.

## Files

All JSON outcomes retain their own source fingerprints and scope. Text files contain aggregate test/build diagnostics; protected raw logs and synthetic checkpoints remain in owner-only `.local`. `SHA256SUMS` binds the final published files and excludes itself.

- [ack-critical-section-after.txt](ack-critical-section-after.txt)
- [ack-critical-section-before.txt](ack-critical-section-before.txt)
- [ack-race-regressions.txt](ack-race-regressions.txt)
- [auth-compile-probe.json](auth-compile-probe.json)
- [auth-projection-corrected.txt](auth-projection-corrected.txt)
- [backend-base-final.txt](backend-base-final.txt)
- [backend-final.txt](backend-final.txt)
- [backend-optimized-final.txt](backend-optimized-final.txt)
- [backend-pooled-first.txt](backend-pooled-first.txt)
- [backend-query-optimized-first.txt](backend-query-optimized-first.txt)
- [backend-runtime-binding.txt](backend-runtime-binding.txt)
- [backend-runtime-final.txt](backend-runtime-final.txt)
- [backend-runtime-storage.txt](backend-runtime-storage.txt)
- [browser-failover.json](browser-failover.json)
- [chromium-final.txt](chromium-final.txt)
- [cpu-diagnostic-failed.txt](cpu-diagnostic-failed.txt)
- [cpu-diagnostic-low-rate.json](cpu-diagnostic-low-rate.json)
- [final-20-asgi.json](final-20-asgi.json)
- [final-20-eight-workers.json](final-20-eight-workers.json)
- [firefox-final.txt](firefox-final.txt)
- [gil-diagnostic.json](gil-diagnostic.json)
- [gil-optimized-wsgi-diagnostic.json](gil-optimized-wsgi-diagnostic.json)
- [global-budget-after.txt](global-budget-after.txt)
- [global-budget-before.txt](global-budget-before.txt)
- [global-budget-fixed-20-asgi.json](global-budget-fixed-20-asgi.json)
- [global-budget-fixed-native-wsgi.json](global-budget-fixed-native-wsgi.json)
- [host-scope.json](host-scope.json)
- [image-pins.txt](image-pins.txt)
- [ingress-privacy.txt](ingress-privacy.txt)
- [instruments-host-python-missing-dependency.txt](instruments-host-python-missing-dependency.txt)
- [instruments-tests.txt](instruments-tests.txt)
- [inventory-check.txt](inventory-check.txt)
- [lint-final.txt](lint-final.txt)
- [local-runtime-health.json](local-runtime-health.json)
- [migration-drift.txt](migration-drift.txt)
- [native-wsgi-comparison.json](native-wsgi-comparison.json)
- [offline-api-image-metadata.json](offline-api-image-metadata.json)
- [offline-api-image.txt](offline-api-image.txt)
- [offline-image-source-check.json](offline-image-source-check.json)
- [offline-wheel-verification.json](offline-wheel-verification.json)
- [parallel-recipient-asgi-control.json](parallel-recipient-asgi-control.json)
- [parallel-recipient-wsgi-four-threads.json](parallel-recipient-wsgi-four-threads.json)
- [pool-drill-initial-assumption.txt](pool-drill-initial-assumption.txt)
- [pool-only-before-executor.json](pool-only-before-executor.json)
- [pool-recovery-binding-final.json](pool-recovery-binding-final.json)
- [pool-recovery-drill.json](pool-recovery-drill.json)
- [python-audit.txt](python-audit.txt)
- [query-optimized-four-workers.json](query-optimized-four-workers.json)
- [read-and-failure-regressions.txt](read-and-failure-regressions.txt)
- [release-gate.txt](release-gate.txt)
- [runtime-eight-workers-pool-eight.json](runtime-eight-workers-pool-eight.json)
- [runtime-pool-four-workers-first.json](runtime-pool-four-workers-first.json)
- [server-bind-wsgi-comparison.json](server-bind-wsgi-comparison.json)
- [short-locks-20-asgi.json](short-locks-20-asgi.json)
- [standby-render.json](standby-render.json)
- [standby-render.txt](standby-render.txt)
- [unprofiled-asgi-four-workers.json](unprofiled-asgi-four-workers.json)
- [websocket-cleanup-final.txt](websocket-cleanup-final.txt)
- [websocket-executor-after.txt](websocket-executor-after.txt)
- [websocket-executor-before.txt](websocket-executor-before.txt)
- [wsgi-adapter-comparison.json](wsgi-adapter-comparison.json)

## Review source and publication checks

Review source commit: `8b26eeaea5a42edcde1cc4596133261e87014267`. Final source/component binding and the full default-rule secret-scan review are recorded in [the realistic-workload validation summary](../metadata-realistic-workload-2026-11-02/validation-summary.json) and [secret-scan review](../metadata-realistic-workload-2026-11-02/secret-scan-review.json). The raw detector exits 1 for 163 individually reviewed non-secret patterns: 154 verified source hashes, five public library symbols, one Cargo dependency-name match, two public GPG fingerprints and one explicit test-fixture phrase. Zero confirmed credentials; no detector exclusion or baseline was added. Raw redacted reports and runtime fixtures remain private. `SHA256SUMS` covers every published file in this directory except itself.
