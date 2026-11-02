# Realistic workload results — 2026-11-02

**A realistic 20-message/s burst has a fully passing local run. Consistent latency and reference-production capacity remain unqualified.** Normal source cryptography and release gates remain blocked. No real deployment, quota increase, weakened durability or device reset was performed.

## What is now tested

The ordinary population is 100 people with two trusted identities each: 100 primary and 20 secondary devices initially online. Keeping a second device connected does not double a person's sending rate. Forty direct conversations and four five-person groups partition the users; multiple simultaneous conversations per user are outside this native load model. The 20/s rate means service-wide new application messages in a 60-second busy burst, about one per person every five seconds. It does not mean 20 per person or a new cryptographic copy for every socket.

The natural combined case starts with 500 authenticated sockets sharing 120 online identities, adds five actual encrypted 1 MiB transfers, then disconnects 30 accounts while their peers continue sending. Each device retains its own assigned tabs. Connections fall to 356 during the outage and return to 500. The separate constant-500 case deliberately redistributes tabs among the remaining devices and is a heavier connection-churn stress. Neither case represents 500 physical browsers.

## Passing natural combined case

[Exact aggregate](../../evidence/metadata-realistic-workload-2026-11-02/final-v62-natural/combined-natural.json): **1,300/1,300 applications**, including all 1,200 burst messages; **5,352 actual durable recipient copies**; 200 restored encrypted native checkpoints; all five files verified. All 25 affected conversations accumulate real new offline backlog, and all 313 queued copies for previously online devices are verified, saved and ACKed later. The planned outage starts at 55 s; the controlled close waits for scheduled outbound work and actually finishes at 57.681 s. Return occurs at 77.000 s. These are measured lifecycle times, not a claim that the full planned interval elapsed.

Burst POST p95 is in the ≤500 ms bucket, maximum 525.92 ms, with zero burst POSTs above 750 ms. Online burst per-copy p95 is in the ≤1.5 s bucket; two of 2,161 copies exceed the proposed 3 s budget. Recovery POST has two of 60 samples above 750 ms and passes its p95 gate. All existing thresholds apply. Offline wait is reported separately; queued messages are never described as instant delivery to an offline peer.

This is one shared-workstation observation. Other runs miss recovery latency or stop before their planned lifecycle action. There is no repeated SLA or causal speedup claim from the passing sample.

## Completed two-hour soak

[Exact aggregate](../../evidence/metadata-realistic-workload-2026-11-02/final-v61-rest/endurance.json): **PASS integrity and all local performance gates**. It offers 14,400/14,400 application messages across 7,200.000 seconds at 2/s, saves and verifies all 60,414 expected recipient copies, processes 108 real MLS updates and restores all 200 encrypted native checkpoints. There are zero unexpected socket errors, zero 429 retries and zero database deadlocks. Final deferred catch-up finishes in 33.431 seconds.

Ten people switch phone/laptop at 40 minutes; 30 accounts disconnect at one hour and return two minutes later. Every affected conversation receives new offline backlog, and all 185 queued copies for previously online devices are actually saved/ACKed after return. POST p95 is in the ≤250 ms bucket (21/14,400 above 750 ms); online per-copy p95 is in the ≤750 ms bucket (four/30,303 above 3 s). These are p95 passes, not claims that every sample meets the threshold. Device readiness p95 is ≤1.5 s for handoff and ≤1 s for return. This is a full local two-hour result; the earlier 82-minute failure remains a failure.

[Final source binding](../../evidence/metadata-realistic-workload-2026-11-02/final-source-binding.json) matches every measured executable/source component and native binary of this soak and natural combined case to the review checkout. Both use four API workers and a maximum of 16 DB connections each, preserving the aggregate 64/default PostgreSQL 100 limits.

## Case outcomes

These independently isolated runs span documented harness revisions. v6.1 adds failure provenance only; v6.2 adds the fixed-tab natural case without changing existing profile policies. Per-case versions and component fingerprints identify the measured source. There is no claim that every case ran in one uninterrupted, clean all-pass suite.

| Case | Accepted applications / planned | Integrity | Performance | Evidence |
|---|---:|---|---|---|
| Natural combined target | 1300 / 1300 | PASS | PASS | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/final-v62-natural/combined-natural.json) |
| Constant-500 combined stress | 1300 / 1300 | PASS | FAIL | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/final-v6/combined.json) |
| Pre-fix API burst | 396 / 1300 | PASS | FAIL | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/final-v6/baseline-burst.json) |
| Updated API burst | 1300 / 1300 | PASS | FAIL | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/final-v6/current-burst.json) |
| Five-file burst, rerun | 1300 / 1300 | PASS | FAIL | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/v61-media/media-burst.json) |
| 30% intermittent accounts | 64 / 600 | PASS | FAIL | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/final-v61-rest/intermittent.json) |
| Phone/laptop handoff | 91 / 600 | PASS | FAIL | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/final-v61-rest/handoff.json) |
| 500 live sockets | 240 / 240 | PASS | PASS | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/final-v61-rest/connections.json) |
| Groups of five people | 1300 / 1300 | PASS | FAIL | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/final-v61-rest/group-5.json) |
| Groups of ten people | 701 / 1300 | PASS | FAIL | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/final-v61-rest/group-10.json) |
| Groups of 25 people | 312 / 1300 | PASS | FAIL | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/final-v61-rest/group-25.json) |
| Historical 500-device smoke | 5 / legacy smoke | legacy compatibility checks | COMPLETED | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/final-v61-rest/legacy-smoke.json) |
| Two-hour 2/s endurance | 14400 / 14400 | PASS | PASS | [JSON](../../evidence/metadata-realistic-workload-2026-11-02/final-v61-rest/endurance.json) |

An earlier v6 media attempt aborted at the final catch-up failure gate and is retained as [failed evidence](../../evidence/metadata-realistic-workload-2026-11-02/final-v6/media-burst.json). One API process recorded two pool checkout errors and about 147 seconds of accumulated checkout wait. The original client exception was not retained, so its exact first cause is not proven. Failure provenance now persists finite redacted cause codes before teardown. The subsequent media run completes all 1,300 messages and restores all checkpoints but still fails latency; it is not a full qualification pass.

The latest long handoff and intermittent attempts stop **before** their planned switch/outage. Their failures are not evidence that reconnect itself failed. An individual sender spends about 6.2 seconds in its checkpoint-persistence stage in the intermittent run, and another spends about 8.8 seconds in POST in the handoff run, reaching the unchanged ten-second total intent bound. The earlier corrected intermittent case does finish 600 messages and genuinely queues/receives 82 copies across all 25 affected conversations; the latest natural combined case provides current-source recovery evidence at burst load. Short handoff/control smokes pass; a failed longer qualification remains a failure.

## Fixes and preserved guarantees

The API uses bounded processes/database reuse, independent WebSocket DB execution, fresh parameterized minimal authentication reads, fewer redundant transactions/savepoints and shorter storage/ACK lock sections. The outbox reuses one owned Redis loop/backend, coalesces coarse account hints and atomically preserves whole-batch retries. No cached authentication verdict or relaxed quota was added.

The native generator separates people/devices/connections and burst/steady/fan-out cases. Receivers independently verify signatures, ordered hash chains, MLS sender/roster/epoch and plaintext; save encrypted native state before cumulative ACK; and retrieve paged offline history. Every device's final native checkpoint and authoritative DB cursor are inspected. A returning device catches up before authoring. The sender's full future still includes its real ACK, even though another author may start after publication/checkpoint. Actual held-ACK serial/pipelined controls prove this dependency removal with all 76 recipient copies and 20 restored checkpoints in each case; these diagnostics are not capacity evidence.

API validation: 132 tests pass under both base and pooled settings; ten focused real Redis/socket/privacy regressions pass without teardown warnings. Thirteen workload unit checks and lint pass. Chromium 39/two skips and Firefox 35/six skips were run before notification batching; new browser, Rust or Next builds are not claimed. The rebuilt owner-local offline API image matches every application Python file outside tests. No deployed image was replaced.

## Qualification limits and next environment

[Read-only topology](../../evidence/metadata-realistic-workload-2026-11-02/storage-topology.json) places both all simulated client checkpoint writes and PostgreSQL Docker storage on the root USB-attached TwinMOS SSD. The NVMe Windows partitions are unused and were not mounted or changed. Real checkpoint/WAL/lock waits are measured; the USB label alone is not proof of a hard ceiling or sole cause. The rig remains `UNQUALIFIED_SHARED_WORKSTATION` under master specification §13.3. A proper reference host and separate durable client storage/load generation are needed to qualify a repeatable production latency/capacity claim. Do not replace durable state with tmpfs or disable synchronous commit/fsync.

Large-group fan-out and the old five-device/all-nine-recipient barrier remain explicit stress cases, not the ordinary two-device model or a universal API maximum. Physical phone memory/KDF/battery/thermals, domestic carrier behavior, real provider/TLS/failover and independent cryptographic review remain external gates. Controlled disconnects finish in-flight critical sections and do not claim hard-power-loss or mid-checkpoint packet-loss qualification.

See the [plan and primary research](workload-plan.md), [runtime investigation](throughput-fixes.md), [ADR 0015](../../adr/0015-bounded-api-runtime-and-storage-locks.md) and [complete evidence index](../../evidence/metadata-realistic-workload-2026-11-02/README.md). Signal/SimpleX inform asynchronous mailbox, batching and saved-before-ACK principles; they do not provide a directly comparable HAVEN benchmark or interchangeable cryptographic protocol.
