# Performance and resource comparison

Baseline `0240706` and hardened binaries run on the same Linux x86_64 host (8 logical CPUs), same Rust lockfile/release profile and the same example workload. Three alternating runs per binary, each 40 real native MLS send/process roundtrips at each of nine sizes (360/run). Each operation includes serializing/loading provider state. CPU and peak process RSS use `/usr/bin/time`; neither private state nor plaintext is printed. Raw JSON and binary checksums are in the evidence directory.

The initial single runs overlap other validation; the alternating runs reduce ordering bias but remain a small shared-host experiment. Medians below are medians of three per-run medians, not pooled percentiles. Observed differences do not establish a speed improvement or a production regression budget.

| Plaintext bytes | Wire baseline → padded | Send median µs baseline → padded | Receive median µs baseline → padded |
|---|---|---|---|
| 1 | 148 → 320 | 657 → 518 | 665 → 508 |
| 16 | 163 → 320 | 569 → 519 | 557 → 502 |
| 64 | 212 → 320 | 561 → 522 | 547 → 496 |
| 128 | 276 → 320 | 549 → 513 | 537 → 505 |
| 255 | 403 → 576 | 553 → 502 | 551 → 501 |
| 256 | 404 → 576 | 569 → 521 | 555 → 499 |
| 1024 | 1172 → 1344 | 599 → 511 | 570 → 503 |
| 4096 | 4244 → 4416 | 609 → 503 | 596 → 499 |
| 131072 | 131224 → 131394 | 2279 → 2036 | 2140 → 1838 |

The 1/16/64/128-byte samples have distinct baseline sizes and the same padded size for this fixed group ID. Encrypted-content block boundaries hide some, not all, length information. Different group IDs/framing add different overhead. OpenMLS adds 0–255 authenticated padding bytes and MLS vector-length encodings can add bytes at a boundary. The example 131072-byte maximum goes from 131224 to 131394 bytes. Base64/JSON/HTTP/TLS and attachments are outside these wire measurements. No bandwidth, battery or nationwide-observer indistinguishability is inferred.

| Resource, full 360-roundtrip process | Baseline runs | Padded runs |
|---|---|---|
| cpu_user_seconds | [0.59, 0.63, 0.47] | [0.56, 0.44, 0.48] |
| cpu_system_seconds | [0.02, 0.03, 0.02] | [0.02, 0.02, 0.02] |
| peak_rss_kib | [5756, 5612, 5696] | [5700, 5744, 5576] |
| elapsed_seconds | [0.62, 0.66, 0.5] | [0.58, 0.47, 0.5] |

## Database and server operations

The outbox query assertion verifies that routing selects exclude ciphertext, header, signature, request_digest, acceptance time and sender ID. It does not infer a byte-allocation figure from column count. The durable envelope→conversation route and membership query remain. ACK writes no longer update a timestamp. Schema inspection demonstrates three time columns and an unused table removed; PostgreSQL on-disk relation bytes need not shrink immediately. Retirement/refund budgets remain unchanged.

Each incoming authenticated WebSocket frame now performs one additional Redis group_add/expiry renewal. Current frame admission is ≤60/minute/socket and ordinary heartbeats every 20 seconds; the operation is local, not a new network poll from the browser. Database session-validation queries and aggregate metrics remain. This bounds stale account-channel associations after a crash to 120 seconds instead of the channels-redis default 86400. Redis loss closes a socket for reconnect while HTTP sync remains authoritative. The actual Redis TTL/deletion/renewal/revocation test verifies these semantics. `cleanup-index-plan.txt` shows the partial expiry index is usable on the real test PostgreSQL database with sequential scans disabled for that EXPLAIN transaction; this is an index-eligibility check, not a large-dataset planner/throughput benchmark.

No new periodic cover traffic, request batching delay or activity timer was added. The browser regression suites exercise reload, reconnect, full message/media synchronization and segmented vault behavior, but their overall elapsed times are not a before/after performance benchmark.

| Required dimension | Measurement status |
|---|---|
| Native encrypt/process latency, CPU, memory, application wire size | Measured above; small shared-host sample |
| Browser/API send/receive p50/p95, database counters | Measured against isolated baseline below; physical WAL/write amplification NOT MEASURED |
| Reconnection and heartbeat, sequential sync, browser vault latency | Small same-client baseline/API comparison below; saturated/backlog throughput NOT MEASURED |
| HTTP API bodies and idle sync | Body bytes/request count and ten idle syncs measured below; whole-session TLS/headers NOT MEASURED |
| Physical mobile battery, thermal/KDF cost, 100-user soak and resource ceilings | NOT TESTED; production qualification remains blocked |

## Reproduce

Run `cargo run --manifest-path packages/crypto-core/Cargo.toml --locked --release --example metadata_benchmark`. For a baseline, export commit `0240706` to an isolated directory, copy this example into its crate, and build with its exact lockfile. Use separate target directories or force source freshness: Cargo can reuse a newer build when old archive timestamps are copied into a shared target. Assert the fixed workload has 148-byte baseline versus 320-byte padded first wire message before accepting the comparison. Alternate binaries under `/usr/bin/time -f "%U %S %M %e"`; never publish snapshots/private keys. These native numbers do not replace production workload qualification.

## Browser delivery and isolated API comparison

A second workload uses actual Chromium, trusted loopback TLS, real OpenMLS/WASM, signed authorized HTTP delivery, PostgreSQL and durable encrypted browser vaults. The API baseline is exported from `0240706`; the updated API uses this checkout. Each gets its own randomized disposable database and synthetic users, with separately owned loopback API/proxy processes. Both use the same current browser client and padded WASM: this isolates backend differences, while the native comparison above isolates padding. It does not compare the entire old versus new browser distribution.

One baseline-then-current trial on the same shared host: 30 sequential 128-character-plus-index text sends, 30 recipient durable syncs, 30 encrypted draft writes, ten idle syncs, ten fresh authenticated WSS connections plus heartbeat. All 30 messages are verified present. These are sample percentiles, not SLA or production capacity evidence; concurrent regression activity and fixed run order add noise.

| Operation | Samples per API | Baseline median / p95 ms | Updated median / p95 ms |
|---|---|---|---|
| Send incl. client encryption/persistence and durable API acceptance | 30 | 205.0 / 393.3 | 204.5 / 291.6 |
| Recipient sync incl. MLS, vault commit and ACK | 30 | 140.1 / 195.0 | 136.2 / 161.9 |
| Encrypted vault draft write | 30 | 3.5 / 5.5 | 3.2 / 5.9 |
| Change-aware idle synchronization | 10 | 29.3 / 33.0 | 29.4 / 33.3 |
| Authenticated WSS connect + validated heartbeat | 10 | 44.2 / 64.8 | 40.1 / 54.1 |

| Resource/body counter | Baseline | Updated |
|---|---|---|
| API process CPU seconds during workload | 6.75 | 6.48 |
| API process peak RSS KiB, includes setup peak | 154672 | 154688 |
| HTTP API body requests | 370 | 370 |
| HTTP API body upload_bytes | 44346 | 44346 |
| HTTP API body download_bytes | 425864 | 421904 |
| PostgreSQL xact_commit delta | 2156 | 2140 |
| PostgreSQL blks_read delta | 0 | 0 |
| PostgreSQL blks_hit delta | 488892 | 482371 |
| PostgreSQL tup_returned delta | 299577 | 293685 |
| PostgreSQL tup_fetched delta | 297288 | 292765 |
| PostgreSQL tup_inserted delta | 84 | 60 |
| PostgreSQL tup_updated delta | 323 | 210 |
| PostgreSQL tup_deleted delta | 1 | 0 |
| PostgreSQL temp_bytes delta | 0 | 0 |
| PostgreSQL deadlocks delta | 0 | 0 |

Download body bytes fall by 3960 in this workload while request count/body-upload bytes stay equal. This is consistent with omitting response acceptance-time fields; payload byte counts exclude headers, TLS, WSS and application static assets. PostgreSQL counters are asynchronous per-database observations and can include delayed setup/internal work. They are not exact per-operation query counts or physical WAL/write-amplification measures; do not interpret tuple deltas as a proven causal improvement. Both observed deadlock counters are zero.

Active receive-sync time corresponds to 6.86 versus 7.11 messages/second across these single-message sync calls, excluding sender/idle time. This is not saturated or backlog throughput. Native and browser sample results do not establish a speedup, battery budget, peak-concurrency capacity or reference-host acceptance.

Reproduce with `.local/test.env` exported and the local web/harness ready: `apps/api/.venv/bin/python scripts/benchmark-metadata-delivery.py`. The companion JS uses real browser clients; no cryptographic state is mocked. The driver refuses non-test PostgreSQL, checks unused loopback ports 8110/8111/8450/8451, creates/drops only its randomized databases, and retains credentials/logs under owner-only `.local/metadata-delivery-benchmark`. Only aggregate output belongs in published evidence. An initial runner kept stdin open after measurement; the driver now closes the input through bounded communicate, and the reported completed run exited normally.

A second execution of the formatted/preflight-guarded driver is retained in `delivery-performance-recheck.json`. It again verifies 30 delivered messages per API and equal request counts. The primary table above retains the first completed trial; the repeat is not pooled into its percentiles.
