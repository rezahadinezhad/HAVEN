# Throughput investigation and implementation — 2026-11-02

This follows source `b988879` on `codex/metadata-privacy-completion`. Reproduced serialization and redundant work have implementation fixes and regression evidence. **The historical stress workload did not sustain 20 messages/s. Production remains BLOCKED and normal `CRYPTO_READY=False`.** No production/staging deployment, quota increase, durability relaxation or user-data mutation was performed.

The original master specification calls for a **20/s burst**, not perpetual all-nine-device completion at that rate. The current ordinary model, retained failures, new notification/readiness fixes and qualification boundaries are in the [workload plan](workload-plan.md) and [realistic workload evidence](../../evidence/metadata-realistic-workload-2026-11-02/README.md). The old overload table below remains historical evidence.

## What was actually wrong

1. **One API process and repeated physical connections.** The default image/local launcher used one Uvicorn process. Every short-lived Django connection could establish a new PostgreSQL connection. A pool alone shifted delay into checkout queues; it did not solve throughput. Four real API processes improved the early overload observations, while eight processes before query/lock fixes provided little additional benefit.
2. **Shared WebSocket database execution.** Session checks used one thread-sensitive executor. A real 1.2-second PostgreSQL delay blocked another account's session lookup; the bounded independent executor passes the same test. Every frame and hint still reads live authority and performs real connection cleanup.
3. **Repeated query construction and transaction work.** GIL samples implicated ORM/query compilation. A 1,000-iteration, no-record-read probe measured about 0.754 ms per authentication-query compile. The fixed parameterized query removes that repeated construction, preserving predicates, HMAC binding and field minimization. Protected reads avoid an unnecessary outer transaction, mutating handlers avoid redundant nested savepoints, membership reads use one join and ACKs project only the cursor sequence. Fresh post-fence authentication remains.
4. **A globally shared storage lock held across inserts.** Pausing one actual send's outbox insertion blocked an unrelated account/conversation. Moving budget acquisition after independent uncommitted inserts fixes the reproduction. Quota checks and both budget increments still happen before the same transaction commits; rejection rolls back the head, envelope, outbox and charge. One atomic UPDATE applies the two locked budget rows' identical deltas.
5. **Conversation locks covering entire ACK transactions.** A paused recipient cursor lookup blocked an unrelated recipient in the same conversation. ACKs now rely on the existing actor-account fence for credential/device/targeted-membership changes and take the conversation lock only through the final atomic receipt-version update. Regression tests cover concurrent recipients, same-device monotonic ACKs, removal-versus-ACK, logout races and uncommitted ACK versus retirement. Message/control writes retain lock-then-refresh membership authorization.
6. **Artificial recipient serialization in the synthetic driver.** Independent recipients fetched, verified, fsynced and acknowledged sequentially. A bounded pool now permits independent recipients to work concurrently; the group lane still waits for every durable ACK before the next event. The serial control is retained. This corrects a test limitation, not an application feature or a fabricated capacity pass.

7. **Notification loop churn and idle delay.** The publisher created a new event loop for each recipient hint, updated every outbox row separately and slept two seconds after every cycle. The revised publisher reuses its own loop/backend, coalesces account-scoped hints, marks the successful batch atomically and immediately drains further pending rows. Real Redis/socket and rollback/retry regressions cover the change.

8. **A remaining cross-author ACK barrier in the revised generator.** Native intent traces showed seconds queued ahead of relatively short POSTs. The next author was waiting for the prior author's own ACK. v6 releases the publication lane after real acceptance and durable sender checkpoint, retaining the individual author lock through ACK. Two bounded author workers permit overlap; complete-intent futures and deadlines still include every ACK. A real native held-ACK serial/pipelined control proves this change. It is a generator correction, not an API speedup or relaxed delivery requirement.

[ADR 0015](../../adr/0015-bounded-api-runtime-and-storage-locks.md) records design, lock order, budget bounds, privacy implications and alternatives. The current implementation remains Django/Channels ASGI. WSGI adapter and direct Gunicorn comparisons did not justify shipping a new HTTP architecture; those packages were removed from the restored locked environment.

## What the historical stress number means

The historical `legacy-stress` workload has 100 synthetic accounts, five native MLS clients each, 50 ten-device groups and 500 authenticated verified-TLS sockets. Each application event needs one send, one sender ACK and nine recipient fetch/ACK pairs: about **400 HTTP requests and 180 durable recipient copies per second** at an offered 20 messages/s. Outer signatures, ordering, MLS sender/roster/epoch and plaintext are verified. Each recipient fsyncs its encrypted native checkpoint before ACK. Five concurrent encrypted 1 MiB files and actual checkpoint restore are checked. Native clients are not physical browsers or mobile vault/battery tests.

Offering stops on the unchanged ten-second oldest-unfinished-work/dispatcher bound or a socket failure. Generated events drain and retain their actual latencies. `accepted / elapsed including drain` from an aborted workload is **not sustained throughput or a measured maximum**. A lower-rate completion does not qualify 20/s. There is no authentication/permission cache, relaxed quota, raised PostgreSQL connection limit, skipped fsync, shortened recipient verification or discarded generated work.

The host is a shared i7-10510U workstation: four physical cores/eight logical CPUs, with synthetic clients, PostgreSQL, Redis, TLS proxy/meter, checkpoint disk writes and desktop applications together. Readable cgroup CPU limits showed no imposed quota. This identifies the test environment; topology alone does not prove that hardware is the only remaining bottleneck or establish a hard capacity ceiling. Remaining end-to-end queuing and CPU/database scheduling need reference-host qualification. The conservative per-group all-recipient barrier also means these figures cannot be generalized to every messenger traffic pattern.

## Observations retained without relabeling failures

All rows below are bounded overloads offered at 20/s. They have unequal completed work, evolving instruments and shared-host variation; they are not randomized causal speedup measurements. The early source fingerprints distinguish intermediate implementations. Complete raw aggregates are in [the evidence index](../../evidence/metadata-throughput-fix-2026-11-02/README.md).

| Variant | Accepted / durable copies | Drain elapsed | Drained rate | Outcome |
|---|---:|---:|---:|---|
| Pre-executor source, pool only, one API process | 203 / 1,827 | 49.45 s | 4.11/s | NOT_SUSTAINED |
| Pool/executor, four API processes | 303 / 2,727 | 35.82 s | 8.46/s | NOT_SUSTAINED |
| Eight processes, eight pool slots each, before query fixes | 308 / 2,772 | 35.44 s | 8.69/s | NOT_SUSTAINED |
| Query/transaction fixes, four processes | 314 / 2,826 | 33.82 s | 9.28/s | NOT_SUSTAINED |
| WSGI adapter, eight threads, server binding, serial recipients | 369 / 3,321 | 32.70 s | 11.29/s | NOT_SUSTAINED |
| Unprofiled ASGI, serial recipients | 206 / 1,854 | 27.32 s | 7.54/s | NOT_SUSTAINED |
| Unprofiled ASGI, bounded parallel recipients | 402 / 3,618 | 36.99 s | 10.87/s | NOT_SUSTAINED |
| Shorter service-budget lock, ASGI | 559 / 5,031 | 41.51 s | 13.47/s | NOT_SUSTAINED |
| Final four-process ASGI, no validation jobs, no API phase timers | 592 / 5,328 | 42.28 s | 14.00/s | NOT_SUSTAINED |

The final four-process run delivered every offered event to all nine durable recipients, with 500 peak sockets, zero socket errors, zero 429 retries and no pool checkout errors. It still accumulated unfinished work beyond the ten-second gate. That historical stress target therefore remains unmet. It is not a capacity ceiling for the revised ordinary workload.

Two GIL sample sets, adapter/thread controls and direct synchronous HTTP controls remain diagnostic. An early per-request `cProfile(time.thread_time)` produced negative/invalid cross-thread values; **those CPU figures are discarded**. Later optional call profiling uses a wall clock and cannot attribute CPU or qualify capacity. One high-rate call-profile run failed with HTTP 500. A later short-lock overload overlapped backend validation and failed with 503/pool checkout errors; it remains a failed diagnostic, not final-source capacity evidence. The clean final run above did not overlap validation or the owned development servers. Profiling records only static function/type names and aggregate counters, never SQL parameters, cookies, locals or request content.

## Verification and compatibility

- Full backend before notification batching: **130 passed** under pooled runtime settings and **130 passed** under ordinary base settings. After batching: **132 passed** under each settings module; the focused ten-test notification/privacy run also passes without cleanup warnings. Earlier failed reproductions and the corrected projected-model field-order bug remain indexed.
- Browsers before notification batching: **Chromium 39 passed / two optional skips; Firefox 35 passed / six skips** against restarted four-process local APIs, real PostgreSQL/Redis, native/WASM crypto and trusted loopback TLS. This includes messaging, retry/reload, secret/logout handling, media, removal and real disposable failover. Engine-specific decoded-memory behavior remains outside the view-once guarantee.
- Pool drill: real SQL rollback, live revocation on reused connections, idle backend termination/replacement, two-slot exhaustion failing closed after about three seconds, recovery, autocommit and synchronous commit, and bound values absent from idle SQL text all pass in an owned disposable database.
- Four native-instrument tests, Ruff, no model/migration drift, complete 191-current/eight-retired field inventory, pinned real Nginx source-header/log tests and standby render checks pass. Release checking still exits 1 intentionally.
- A new API image builds with `--network=none --pull=false` from 29 current hash-verified wheels. Its application Python files matched that pre-notification checkout; the separately rebuilt realistic-workload image matches the notification implementation, and its launcher/default 4×16 budget and psycopg-pool 3.3.3 are verified. No web, Rust, WASM, identity, browser-vault, serializer or public API shape changed. Existing artifacts remain applicable; a fresh container OS scan or Rust suite rerun is not claimed.

## Operate and reproduce

Use `python -m haven.server` for the API. Defaults are four processes and sixteen pool slots per process. Use `HAVEN_API_WORKERS` / `HAVEN_DB_POOL_SIZE` together within the aggregate 64-connection guard; the supplied Compose defaults are 4/16. Eight processes default to eight slots when the pool is not explicitly set. Replicas and other deployments require a combined database budget; the per-deployment guard is not a cluster-wide allocator. Management commands continue using base settings. Pool size zero is an explicit diagnostic opt-out. Normal cryptography remains gated.

No new migration or client reset is required for these runtime/query changes. Existing coordinated 0013–0016 migration and backup safeguards in [upgrade.md](upgrade.md) still apply. Upgrade API workers together from a reviewed offline artifact, check aggregate errors/DB connections and verify current-session denial, exact retry and durable recipient state before operator qualification. This document does not authorize deploying to real users.

With the owned test PostgreSQL/Redis and trusted local test CA prepared:

```bash
# Export .local/test.env without printing its values before DB tests.
PYTHONPATH="$PWD/apps/api" apps/api/.venv/bin/python -m pytest apps/api/core/tests --ds=haven.runtime_settings
PYTHONPATH="$PWD/apps/api" apps/api/.venv/bin/python -m pytest apps/api/core/tests --ds=haven.settings
apps/api/.venv/bin/python scripts/test-runtime-database-pool.py
apps/api/.venv/bin/python scripts/test-metadata-load-instruments.py
apps/api/.venv/bin/python scripts/benchmark-metadata-isolated.py --profile legacy-stress --seconds 60 --rate 20 --no-phase-profile
```

The revised default profile is `realistic`; use `--profile legacy-stress` to reproduce the historical population/barrier. Both use four API processes and ten native workers by default. The legacy recipient pool defaults to 100 workers. `--recipient-workers 0` preserves serial recipients; `--api-workers 8` selects the supported eight-process/eight-slot configuration; `--revision b988879` selects the pre-fix API. Each driver invocation owns labelled disposable PostgreSQL/Redis/Nginx and refuses occupied loopback ports. Publish only completed aggregate JSON, retaining failed outcomes. Do not run validation/build/browser jobs during measured capacity windows. Keep credentials, raw stacks, checkpoints, keys, logs, dumps and protected contexts inside owner-only `.local`.
