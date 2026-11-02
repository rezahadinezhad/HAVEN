# Metadata load attribution — 2026-11-02

Synthetic-only continuation of `metadata-completion-2026-11-02`. Protected artifacts remain in owner-only `.local/metadata-load-*` folders; no production/staging deployment is changed. Source changes are benchmark instruments only; normal `CRYPTO_READY=False` remains intact.

Run from repository root after building the locked native helper and preparing the existing test CA/Docker infrastructure:

```sh
apps/api/.venv/bin/python scripts/test-metadata-load-instruments.py
apps/api/.venv/bin/python scripts/benchmark-metadata-isolated.py --revision current --seconds 60 --rate 20 --crypto-workers 1
apps/api/.venv/bin/python scripts/benchmark-metadata-isolated.py --revision current --seconds 60 --rate 20 --crypto-workers 10
apps/api/.venv/bin/python scripts/benchmark-metadata-isolated.py --revision 0240706 --seconds 60 --rate 20 --crypto-workers 10
```

Run sequentially: each orchestrator owns labelled disposable containers on the same dedicated loopback ports and removes only their immutable IDs. It never clears the existing test or staging Redis/database. No real credentials, cookies, keys or provider snapshots belong in this directory.

- `instruments-tests.txt`: three passing meaningful tests, including real independent Rust worker state/signatures and lifecycle.
- `smoke-current.json`: completed 20/180 deliveries, ten workers/500 WSS, zero socket errors; development instrument check before final independent-lane scheduler/cgroup annotations.
- `control-current-one-worker.json`: final instrumented one-worker control at offered 20/s, 200 accepted / 1,800 verified durable copies, zero socket errors; NOT_SUSTAINED on the ten-second unfinished-work bound. Everything generated drains.
- `stress-current-ten-workers.json`: same source/workload/scheduler with ten native processes, 203 accepted / 1,827 durable copies, zero socket errors; NOT_SUSTAINED on the same bound.
- `stress-baseline-ten-workers.json`: identical final instruments with baseline API `0240706`, 201 accepted / 1,809 durable copies / 500 sockets / zero socket errors; NOT_SUSTAINED on the same trigger.
- `summary.json`: derived timings/CPU plus independently verified source/native fingerprints. Every offered intent drains; all three final trials pass file/checkpoint checks while failing the capacity target.

See [load-profiling.md](../../security/metadata-privacy/load-profiling.md) for method, timing windows, limitations and interpretation. Timing histograms give percentile bounds; overlapping phase totals cannot be added into wall time. PG samples count backend observations, not precise wait durations; container CPU includes PG children, API CPU excludes verifier subprocesses. Profiling overhead and shared-host variation are not a regression budget or production SLA. The failed target is retained; 500 sockets being zero after measurement is intentional teardown.

The three stress trials offer 20/s for up to 60 seconds, but stop offering after about ten seconds because completion backlog exceeds the trigger. Subsequent draining lasts longer; ordered-lane waits above ten seconds remain visible. They do not complete a sixty-second 20/s test. No equal-work CPU/WAL ratio or production speedup is inferred. Baseline disk-flush outliers are retained rather than removed. No API/browser/Rust-library/ingress code changed, so prior product regression results remain associated with `8ddc3d1`; the new native instrument tests and actual synthetic integration runs validate this benchmark change.

Source/instrumentation commit: `30109f151b8a92cdddb0c7092e69c44fd2b68d4f`. `SHA256SUMS` binds every published file here except itself; verify from this directory. Source/docs/scripts outside volatile evidence are bound by the repository-root `SOURCE_MANIFEST.sha256`. The final default-only redacted secret scan retains 29 individually reviewed non-secret patterns (21 prior, eight new public source hashes), with zero confirmed secrets. No detector exclusions were added. Text log trailing whitespace is normalized.
