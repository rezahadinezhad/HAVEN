# Performance and resource comparison

Sections before “Continuation: isolated native load” preserve the 2026-11-01 measurements. The continuation below adds measured TLS/WAL/I/O, bounded overload, retention backlog and two-hour native evidence; it does not replace physical-device or reference-production qualification.

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
| Physical mobile battery, thermal/KDF cost and reference-production resource ceilings | NOT TESTED; production qualification remains blocked; local 100-user native soak added below |

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

## Continuation: isolated native load — 2026-11-02

Reproduce with `apps/api/.venv/bin/python scripts/benchmark-metadata-isolated.py --revision 0240706 --seconds 120 --rate 1`, then `--revision current --seconds 120 --rate 1`. The driver owns and removes only immutable IDs of its labelled disposable PostgreSQL/Redis/Nginx containers. It preserves supplied ingress limits and PostgreSQL's default 100 connections, with fsync/synchronous commit/full-page writes/checksums and I/O timings enabled. Loopback source addresses are distinct per account, rather than trusting spoofed forwarding headers. Native fixture provisioning excludes login/enrollment load. Both APIs use the same current native client/MLS padding; the earlier native comparison measures padding separately.

The workload has 100 synthetic accounts, five native clients each, 50 ten-device groups, 500 authenticated verified-TLS WebSockets, real signed/encrypted application events and nine actual recipients per event. Recipients verify signatures/order/MLS roster/epoch/plaintext, atomically fsync encrypted native checkpoints, then ACK. A persisted encrypted checkpoint restores through the actual native provider. Five concurrent 1 MiB files use the application's XChaCha20-Poly1305 media format and real endpoints; their keys travel through private fixture pipes, so browser MLS file-key delivery is separately covered by browser integration. This is not 500 physical browsers, browser background polling, passphrase key custody, mobile battery/thermal or a domestic carrier test.

### Matched completed work

`paired-baseline-final.json` / `paired-current-final.json` each complete 120 accepted messages / 1,080 durable recipient copies / 2,430 HTTP requests, five files and 500 peak sockets with zero socket errors, rate-limit responses or DB deadlocks. Current exercised source fingerprints match the committed source; whole-tree fingerprints recorded at run start predate final documentation/test-only edits. One baseline-then-current pair on a shared host cannot establish causality, regression budgets or a speedup. CPU rises in this sample even though p95 latencies fall.

| Metric | Baseline API `0240706` | Current API |
|---|---:|---:|
| Elapsed seconds (120 offered at 1/s) | 120.063 | 120.957 |
| Scheduled send → accepted median / p95 ms | 133.46 / 458.51 | 139.05 / 220.55 |
| Scheduled send → all nine durable ACKs median / p95 ms | 1,125.49 / 2,686.44 | 1,217.09 / 1,717.15 |
| Five-file median / maximum roundtrip ms | 816.53 / 864.24 | 867.67 / 894.43 |
| API CPU seconds | 87.90 | 103.54 |
| Notification worker CPU seconds | 1.00 | 1.11 |
| API lifetime peak RSS KiB (includes setup) | 158,404 | 158,984 |
| TLS record upload / download bytes | 8,546,439 / 12,598,701 | 8,545,991 / 12,545,031 |
| New cold HTTP TLS connections | 1,200 | 1,200 |
| WAL LSN growth bytes | 7,013,560 | 7,160,480 |
| `pg_stat_wal.wal_bytes` delta | 6,957,352 | 7,112,274 |
| WAL records / full-page images | 16,009 / 29 | 17,430 / 44 |
| WAL sync count / time ms | 1,554 / 9,451.11 | 1,572 / 1,442.34 |
| DB allocated growth bytes | 5,873,664 | 5,865,472 |
| DB committed transactions | 25,656 | 22,390 |
| DB blocks read / buffer hits | 38 / 7,871,616 | 34 / 7,645,162 |
| `pg_stat_io` reads / writes / extensions, summed contexts | 38 / 59 / 717 | 34 / 145 / 716 |
| `pg_stat_io` read / write / extension time ms | 8.223 / 2.404 / 5.395 | 0.521 / 4.101 / 5.904 |

TLS byte counts include actual HTTP/WSS headers, TLS records and reconnect handshakes, excluding TCP/IP overhead. A group turns every 50 seconds, beyond supplied ingress's 30-second keepalive: the native driver retries exact request bytes on stale transports, without reencrypting. Its connection costs do not model the browser's polling behavior. Heartbeats were 3,000 / 2,958 respectively; neither run needed a WebSocket reconnect, so these runs supply no reconnect-latency sample. Previous browser/WSS connection measurements and actual outage/restart regressions remain separate evidence.

PostgreSQL counters come from each isolated synthetic cluster, including catalogs/autovacuum/checkpointer activity and asynchronous reporting. LSN versus statistics are different measurements. Buffer hits, tuple operations, OS/container rounded block-I/O and WAL are not exact application query/row counts or physical SSD write amplification. `performance-summary.json` derives deltas from retained before/after raw counters without asserting a causal efficiency ratio. Disk persistence stays enabled; no safety knob is relaxed to improve results.

### Overload and endurance

Bounded stress offers 20 messages/s, stops offering when schedule lag exceeds ten seconds or a socket fails, and drains every generated message. `stress-baseline-final.json` accepted 65 / delivered 585 copies in 18.09 seconds (3.59/s); `stress-current-final.json` accepted 52 / delivered 468 copies in 16.55 seconds (3.14/s). Both missed the target despite zero socket errors. Their unequal completed work cannot be compared as a CPU/WAL efficiency ratio. Those stress runs precede the final stored challenge version and harness diagnostics; their source fingerprints explicitly record that difference. They remain failed target evidence, not final-source 20/s qualification. An earlier unbounded development overload lost sockets and was interrupted; a deliberately frequent rekey trial also missed its offered rate. All are retained in the evidence index.

The initial strict 1/s soak stopped at 671.07 seconds after six code-1011 closures; all 670 generated messages / 6,030 recipient copies became durable. Its earlier instrument did not capture the close reason, so no cause is claimed. It failed zero-error endurance. The subsequent instrument records bounded static reason classes and permits authenticated verified-TLS reconnects in explicit resilience mode while preserving a separate zero-error gate.

The **final-source** `--revision current --seconds 7200 --rate 1 --resilience` run completed **7,200.25 seconds**, **7,200 accepted / 64,800 durable recipient copies**, **50 real MLS updates**, **500 peak authenticated sockets**, **zero socket errors**, **zero reconnects needed**, **zero DB deadlocks** and no 429s. Every exercised source/config/crypto/harness fingerprint matches final source. Encrypted native checkpoint restoration and all five files pass. Zero sockets after measurement is intentional teardown. Resilience mode allowed reconnects but this run never exercised that branch and gives no reconnect-latency estimate.

| Final two-hour metric | Observed value |
|---|---:|
| Send median / p95 / maximum ms | 128.93 / 339.29 / 2,803.96 |
| All-nine-durable-ACK median / p95 / maximum ms | 1,166.01 / 2,206.25 / 12,453.91 |
| Five-file median / maximum ms | 660.97 / 681.88 |
| API / notification worker CPU seconds | 5,039.05 / 59.87 |
| API lifetime peak RSS KiB | 148,692 |
| HTTP requests / stale transport retries | 145,030 / 72,000 |
| TLS record upload / download bytes | 201,957,653 / 443,951,233 |
| WAL LSN growth / stat WAL bytes | 118,549,816 / 116,950,494 |
| WAL records / full-page images | 658,518 / 7,959 |
| WAL sync count / cumulative time ms | 89,673 / 275,330.65 |
| DB allocated growth bytes | 20,602,880 |
| DB committed transactions / temp bytes | 1,335,021 / 0 |
| `pg_stat_io` reads / writes / extensions | 34 / 11,460 / 2,561 |
| `pg_stat_io` write / fsync time ms | 431.13 / 2,821.40 |

This passes only the local native 1/s two-hour workload. It does not qualify 20/s, the reference-production host, lower-end phones, Safari/Android, independent audit or Iranian connectivity. The release gate remains closed.

### Pending enrollment backlog

`benchmark-metadata-retention.py` uses its own random disposable database on the labelled local test PostgreSQL server. An actual 10,000-row expired pending-device fixture is analyzed with normal planner settings. Candidate selection chooses `pending_device_expiry` and returns 500 candidates in 0.434 ms on this warm fixture, without forcing sequential scans off. Real cleanup takes 20 deleting batches of at most 500 plus one empty pass, 209.33 seconds total: zero pending Devices and 10,000 ID-only replay markers remain. Account/protected-reference safety checks stay enabled.

Allocated Device relation bytes increase from 3,391,488 to 3,448,832 after logical deletion; the marker relation increases 8,192 → 819,200. The UUID exclusion ledger is an explicit retention cost. Cleanup does not promise physical deletion, disk shrink, erased WAL/backups or unbounded catch-up capacity; operators must monitor the bounded cleanup counts and protected references. This shared-cluster retention drill does not attribute global WAL to its own application rows.
