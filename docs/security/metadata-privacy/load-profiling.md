# Independent native workers and load attribution — 2026-11-02

This follows the metadata continuation at source commit `8ddc3d1` and evidence commit `5446b78`. It changes synthetic benchmark instruments only. API, browser, cryptographic library, migrations, ingress, quotas and production release settings are unchanged. Production remains blocked. The objective is to distinguish generator serialization from HTTP/API/database delays, not manufacture a passing capacity result.

## Instruments and preserved guarantees

The native driver now starts a bounded pool of independent Rust processes (`--crypto-workers`, default ten, range 1–50). Each ten-device conversation is pinned to a shard; each client keeps its state in that process. Only that worker's private stdin/stdout exchange is locked. Real OpenMLS encryption/processing, outer Ed25519 verification, roster/epoch/order checks, fresh attachment nonces, encrypted atomic/fsynced checkpoints before ACK, exact request retry and restored-checkpoint inspection are preserved. No primitive or native binary changed. Private state and keys remain outside published evidence.

Fifty independent single-thread conversation lanes replace the central dispatcher's wait on a slow conversation. Each lane retains message order; unrelated conversations can be submitted on schedule. Offering stops when either dispatcher lag or the age of the oldest unfinished message exceeds ten seconds. Every generated send intent then drains, even when its queued wait/delivery takes longer than ten seconds. No maximum ten-second completion latency is claimed for a failed run. This is an explicit, stricter unfinished-work bound, not an unbounded queue or discarded work. Old stress totals cannot be treated as an otherwise identical comparison with this scheduler.

Constant-space histograms record generator crypto-lock waits, native pipe roundtrips, client HTTP-lock waits, HTTP attempts/total requests, encrypted checkpoint preparation/fsync, dispatch/ordered-lane waits and complete nine-recipient delivery. Means/totals/maxima are measured; p50/p95 are reported as bucket bounds, not exact percentiles. Concurrent/nested phase totals overlap and must not be added into wall time.

A private settings/ASGI adapter loads the selected exact baseline or current API with synthetic-only profiling middleware. It records ASGI arrival→sync middleware, sync middleware total, arrival→final response body, cursor execution split by locking/other SQL, connection creation and commit/rollback. SQL text, parameters, request bodies, paths, cookies and identifiers are never saved. SQL cursor timing is HTTP-only; connection/commit timing is process-wide and includes WebSocket work. SQL-call wall time also includes driver/scheduling effects and is not pure PostgreSQL execution time. The ASGI entry point does not measure waits before the application receives a request.

A separate PostgreSQL connection samples aggregate backend state/wait classes at approximately 100 ms, excluding its own backend and never selecting query text or user identities. Idle `ClientRead` is not evidence of blocked work; `CPU_or_runnable` is not a CPU measurement. Sampled backend observations are not exact wait durations. Owned-container cgroup v2 counters capture all PostgreSQL child CPU, throttling and memory; driver, crypto helper, API and publisher CPU are separate. API CPU excludes verifier subprocesses; driver/crypto CPU excludes the separate five-file media subprocesses. HWM/peak memory includes fixture setup. Existing WAL/I/O counters remain enabled.

All trials retain one API worker, PostgreSQL default 100 connections, fsync/synchronous commit/full-page writes/checksums, real Nginx pacing/connection/body limits, 100 accounts, 500 verified-TLS sockets, 50 ten-device groups, nine durable recipients per message and five concurrent encrypted 1 MiB files. Synthetic enrollment/login is provisioned before measurement. Instrumentation has overhead and shares the host with other work; neither this setup nor its native clients represent reference hardware or physical browsers. API/CPU profile windows include the measurement handshakes and final socket teardown; generator timings stop after generated work drains. These boundaries preclude exact cross-process phase subtraction.

## Verification and comparison

`apps/api/.venv/bin/python scripts/test-metadata-load-instruments.py` exercises actual independent native processes: the same client slot in two workers has independent keys, 64 concurrent real signatures verify against the correct worker identity, invalid commands fail, subprocesses are reaped, timing reset/bounds work, and profiler import refuses a non-disposable environment. All three tests pass.

The development smoke run completes 20 messages / 180 recipient copies with ten workers, 500 sockets and no socket errors. It precedes the independent-lane scheduler and final scope/cgroup annotations, so it is instrument validation, not final-source stress evidence.

Final trial commands and raw results are in [the new evidence index](../../evidence/metadata-load-profiling-2026-11-02/README.md). The controlled one-worker and ten-worker current trials share the new scheduler and profiler. Baseline and current use the same final native binary, worker count, workload, instrumentation and limits. Runs are sequential on a shared host, not randomized laboratory trials. Unequal drained work after a failed target cannot establish CPU/WAL efficiency ratios or a causal speedup.

## Findings

The one-worker control's crypto lock wait is about 0.50 ms mean; ten workers reduce it to about 0.044 ms. Native roundtrips remain about 2.28 / 2.15 ms. HTTP requests average about 733 / 606 ms, with nine-recipient delivery and ordered queues accumulating seconds. Both current stress trials miss 20 messages/s, with every generated message delivered and zero socket errors/429s. The global crypto lock was a genuine serialization point, but the hypothesis that it was the dominant limit is not supported by these measurements.

Observed delay is concentrated in HTTP service/wait and the ordered backlog it creates. The server profile exposes substantial middleware/ASGI time, many short-lived DB connections and SQL/transaction costs. These measurements do not uniquely attribute the remaining cost to PostgreSQL locks, database authentication, Django/GIL scheduling, TLS/ingress or host contention. SQL lock waits and DB state sampling must be assessed alongside connection, API and PostgreSQL CPU; no safety fence is removed to obtain throughput. Additional controlled server/connection-pool or separated-host trials would be needed to attribute those mechanisms individually.

All three final trials fail the offered 20/s target on the oldest-unfinished-work trigger. The dispatcher itself remains prompt: mean submission lag is 0.29 / 0.20 / 0.25 ms, so these failures are not caused by the former central dispatcher's head-of-line wait.

| Metric | Current, 1 worker | Current, 10 workers | Baseline, 10 workers |
|---|---:|---:|---:|
| Offered intents / accepted messages | 200 / 200 | 203 / 203 | 201 / 201 |
| Verified durable recipient copies | 1,800 | 1,827 | 1,809 |
| Elapsed including drain seconds | 61.59 | 52.57 | 56.40 |
| Accepted / elapsed, messages/s | 3.247 | 3.862 | 3.564 |
| Crypto lock wait mean ms | 0.504 | 0.044 | 0.077 |
| Native roundtrip mean ms | 2.277 | 2.148 | 2.524 |
| Checkpoint fsync/replace mean ms | 4.34 | 4.30 | 57.41 |
| HTTP request mean ms | 733.24 | 605.95 | 629.49 |
| ASGI arrival→final response mean ms | 445.52 | 376.65 | 400.85 |
| Sync middleware mean ms | 309.37 | 263.08 | 284.48 |
| New DB connections / mean connect ms | 6,146 / 27.34 | 5,955 / 24.29 | 6,131 / 26.33 |
| Locking SQL call mean ms | 14.31 | 11.84 | 29.76 |
| Other SQL call mean ms | 8.59 | 7.50 | 7.80 |
| Commit call mean ms | 7.31 | 6.49 | 41.86 |
| Ordered-lane queued wait mean seconds | 18.56 | 15.25 | 16.54 |
| API CPU seconds | 120.62 | 105.18 | 114.17 |
| PostgreSQL cgroup CPU seconds | 68.49 | 58.51 | 65.95 |
| Native workers combined CPU seconds | 4.11 | 3.93 | 4.25 |
| Driver CPU seconds | 10.19 | 8.49 | 9.91 |
| Socket errors / HTTP 429s / DB deadlocks | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

These are matched offered configurations, not equal completed-work efficiency experiments. Ratios include drain and are not sustainable-rate estimates or maximum server capacity. Baseline checkpoint flushes reach 985 ms and its commit calls reach 1,115 ms; these shared-disk spikes materially confound the small baseline/current difference. PostgreSQL cgroup throttling is zero in all three trials. PG samples include actual transaction/tuple lock and WAL waits, but do not isolate a single dominant server mechanism. All five files and encrypted native checkpoint restoration pass in each trial. Source and native binary fingerprints are independently rechecked in `summary.json`.

The prior claim that the shared native worker might explain the failed target must be qualified: it was a plausible hypothesis, and its serialization is now corrected, but actual measurement shows it is not the main limit here. HTTP/API and variable storage service dominate the observed delays. No authentication, authorization, fsync, quota or limit was weakened to improve these figures. A failed 20/s workload stays unqualified regardless of a lower-rate two-hour pass or improvements to the generator. Independent review, reference-production capacity, physical phones and domestic-network qualification remain open. The new worker pool is a benchmark correction, not a deployed messenger performance fix.
