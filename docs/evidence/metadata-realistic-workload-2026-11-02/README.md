# Realistic messaging workload evidence — 2026-11-02

The [workload plan](../../security/metadata-privacy/workload-plan.md) defines people, trusted devices, online identities, socket connections, new messages and recipient copies separately. The primary ordinary case has **100 accounts, two trusted devices each, 120 initially online identities, 40 direct conversations and four five-person groups**. Users are partitioned into one conversation each in this native model; multiple simultaneous conversations per user and physical browsers are outside this load result. The connection case creates 500 actual authenticated sockets sharing those identities. These are documented test assumptions, not observed user statistics or a new application device limit.

All cases use real native MLS, signatures, TLS, PostgreSQL/Redis, outer hash chains, encrypted fsynced checkpoints, cumulative ACKs and checkpoint restoration. Offline ciphertext is actually retrieved and saved before it counts as delivered. Fixture provisioning pre-enrolls devices; it does not bypass application cryptographic verification during measurement. Fixtures and private keys are synthetic and held outside the public evidence. Reference-production capacity remains **UNQUALIFIED_SHARED_WORKSTATION**; normal source cryptography and deployment gates remain unchanged.

## Initial matrix (v2, evidence root)

The root JSON files preserve the first complete matrix, including failures. Every case passed message integrity; performance did not pass every case. `matrix-summary.json` COMPLETED means execution completed, not that all targets passed.

| Case | Offered / planned application messages | Performance outcome |
|---|---:|---|
| Smoke | 24 / 24 | PASS |
| Legacy stress smoke | 5 / 5 | COMPLETED; old 500-device/nine-recipient model retained |
| Pre-fix API burst | 313 / 1,300 | FAIL, unfinished-work stop |
| Updated API burst | 1,300 / 1,300 | FAIL, recovery per-copy p95 narrowly exceeds 3 s; all 1,200 burst sends complete |
| Burst plus five files | 1,300 / 1,300 | PASS |
| Phone/laptop handoff | 226 / 600 | FAIL, unfinished-work stop |
| 30% intermittent accounts | 600 / 600 | PASS original gates; later found whole-pair outage coverage gap |
| 500 sockets, 120 identities | 240 / 240 | PASS |
| Five-person groups | 1,266 / 1,300 | FAIL |
| Ten-person groups | 535 / 1,300 | FAIL |
| 25-person groups | 177 / 1,300 | FAIL |
| Two-hour target at 2/s | 9,853 / 14,400 | FAIL; stopped after about 82 minutes, not a two-hour pass |

The initial current burst accepted all 1,200 burst messages with POST p95 in the ≤250 ms bucket, maximum 373.70 ms and no POST over 750 ms. Online burst recipient copies passed the proposed 3-second budget; recovery had 6 of 103 copies over it and fails. Acceptance alone is not complete-message delivery. Initial generic backlog stopping does not prove hardware or server acceptance was the sole cause.

## Revisions and validation

Notification batching reuses one owned Redis event loop/backend, coalesces coarse hints by account, immediately drains pending batches and retains transactional retry semantics. Driver v2.1 waits for a device's actual connection-snapshot catch-up before author selection, preserves the actual devices that were online before a planned disconnect, and records structured stop stages. It additionally counts distinct messages whose entire online recipient set has durably ACKed without disconnection; interrupted sets and messages with no online recipient are separate. Existing latency and ten-second safety thresholds are unchanged. The complete-message diagnostic is separate from the existing per-copy performance gate. v2.2 adds a combined 500-socket/burst/media/intermittent profile and captures actual oldest-recipient and rekey stages. The `v21` output directory is a run label: its first two cases use v2.1 and later cases use the backwards-compatible v2.2 additions, as each JSON version/fingerprint records. The matrix coordinator was paused between media and handoff cases for these driver-only additions; the media child ran normally, and its summary wall time includes the coordinator review pause. Driver phase/delivery timing does not include that pause.

- [Backend pooled runtime](backend-runtime.txt): 132 passed.
- [Backend base settings](backend-base.txt): 132 passed.
- [Focused real Redis/socket/privacy regressions](outbox-regressions.txt): ten passed without teardown warnings. [Initial focused run](outbox-initial-cleanup-warning.txt) retains the fixed test-helper connection-cleanup warning.
- [Workload unit tests v2.1](workload-unit-v21.txt): seven passed; [v2.2](workload-unit-v22.txt): eight passed, adding the combined-case population/connection check, including real Ed25519 negative cases. Native integration, rather than these opaque unit fixtures, verifies MLS.
- [Offline API build](offline-api-build.txt) and [source proof](offline-api-source-check.json): owner-local network-disabled image with all application Python outside tests matching the revised API. No deployment or fresh OS vulnerability scan is implied.
- [Revised smoke](v21-smoke/matrix-summary.json): PASS, including actual handoff, interruption, restoration and real control epochs.
- [Revised matrix](v21/matrix-summary.json): inspect per-case integrity/performance fields; execution and final assessment are tracked separately.

## Reproduce

With Docker, the existing trusted local test CA, locked API/native dependencies and exclusive synthetic benchmark ports prepared:

```bash
apps/api/.venv/bin/python scripts/test-metadata-workload.py
apps/api/.venv/bin/python scripts/qualify-metadata-workloads.py --label new-run
# Individual case, for example:
apps/api/.venv/bin/python scripts/qualify-metadata-workloads.py --label new-handoff --cases handoff
```

Every label refuses existing results. The serial orchestrator owns labelled disposable containers and loopback ports, retains credentials/checkpoints/raw failures in protected `.local`, and atomically publishes only completed parsed aggregates. Interruptions stay failures. Per-case JSON includes workload, exact measured source fingerprints, host scope, phase counts, waits, CPU/memory/I/O and final ledger checks. Historical source fingerprints are not relabelled to match later changes. Do not run capacity cases concurrently or overlap builds, browser tests or backend validation with measurements. Matched API comparisons use the same driver/population/native clients; they do not prove a causal speedup from one shared-host pair. The combined specification scenario and reference/mobile/domestic-network qualification require their own evidence.

## Further diagnostic correction (v3)

The revised intermittent v2.2 run stops at 226/600 messages **before** its planned disconnect, despite passing all measured p95 gates and preserving every generated message. Its oldest pending send reaches the unchanged ten-second gate in `sender_ack`; generic attribution to planned disconnection would be wrong. It records real WAL flush/lock waits and checkpoint I/O, not dominant native crypto time. These aggregate observations do not assign all elapsed time to one stage.

The v2 author cycle also visits adjacent members of each conversation together. v3 interleaves the same device slots using fixed seed 20261102 (not searched/tuned), retaining equal device opportunities, group weights, total rate, cryptographic checks and all durability/backlog limits. [Nine unit checks](workload-unit-v3.txt) verify the population/weight preservation and existing security/metric checks. New per-send stage durations improve attribution. No earlier failed target is relabelled a pass. The `v21` run label includes later v3 cases, whose individual versions/source hashes identify the exact measurement; prior burst/handoff results keep their earlier traffic definition.

[Read-only storage topology](storage-topology.json) shows the test OS, database Docker storage and all native-device checkpoints share a USB-attached TwinMOS SSD. The NVMe Windows partitions are unused; no partition, mount, cache or kernel configuration was changed. The rig therefore includes shared client/server durable I/O and is explicitly unqualified for reference-production capacity. Actual latency/wait evidence is required; the USB label alone establishes no ceiling. The group-case coordinator was also paused after its independently running child completed to add v3; summary orchestration wall time includes review pauses, while driver measurements do not.

## Final definition and case series (v5)

[Final matrix](final-v5/matrix-summary.json) uses the final person-based author cycle and real offline-backlog coverage. [Eleven unit checks](workload-unit-v5.txt) pass. A person with two connected devices receives the same author frequency as a phone-only person; eligible devices rotate within that person's turn. Offline account selection retains an online peer in every affected direct/group conversation. The native ledger records actual new copies queued for previously online devices while disconnected, and their later durable receipt. Full recovery cases must exercise every affected conversation and match queued/received totals. A 12-second smoke does not claim full recovery-window coverage.

Earlier v2/v3 device-based author cycles, v4 person-based cycles and the initial outage coverage gap remain explicitly historical. `v21` stopped intentionally after the 25-person-group case while correcting the final traffic model; its baseline/soak were not completed. `final-v4` stopped intentionally after its baseline burst while adding required offline-backlog coverage; its current burst/soak were not completed. Those interruption summaries and parsed completed cases are retained. No earlier interrupted/missing result is a pass.

Each completed `final-v5` case retains its measured source fingerprint; that series was later interrupted before its handoff/soak completed to remove a proven cross-author ACK dependency. The case JSON, rather than a directory label or orchestrator COMPLETED flag, determines integrity, performance, profile/version and scope. Distinct messages with no online recipient at acceptance remain separate from online-completed messages; their later offline receipt is real and is not presented as instant delivery. No production/reference-host qualification follows from a local case pass.

## Final author pipeline and source series (v6)

[Real native controls](v6-probes/matrix-summary.json) prove the author-ACK dependency and its removal. Both cases accept four application messages, verify/save all 76 recipient copies and restore all 20 encrypted native checkpoints. With one worker the held first ACK times out and no second publication overlaps it. With two workers a second author publishes and releases that hold before the first real ACK completes. Both probe assertions and integrity checks pass. The mixed 24-message smoke also passes, including native control events and restoration of 40 checkpoints. These controlled holds are diagnostics, not throughput qualification.

v6 releases the conversation publication lane after real acceptance and encrypted sender checkpoint, retains that author's own lock through its actual ACK, and permits another author to begin in parallel. Two workers per conversation bound this overlap. The main pending future still waits for ACK and is subject to the same ten-second deadline. All sender checkpoints and final ACK ledgers must match; no durability requirement or latency threshold was weakened. [Eleven unit checks](workload-unit-v6.txt) and [lint](lint-v6.txt) pass.

[Final capacity series](final-v6/matrix-summary.json) uses this final source, person-based author scheduling and mandatory actual offline backlog. Individual case statuses remain authoritative. Intermediate `final-v5` completed its intermittent, combined, baseline/current burst and media cases before intentional interruption during handoff; its two-hour target was never completed. In that source, the ordinary burst accepted all 1,300 planned messages but failed recovery POST/online latency; the combined case hit a ten-second sender queue despite passing observed p95 gates. Those failures are retained, rather than superseded by an invented pass.

The v6 combined case completes all 1,300 planned applications and genuinely queues/receives 317 copies across all 25 affected conversations. All 1,200 burst POSTs are below 750 ms (maximum 576.40 ms); online burst per-copy p95 is within the 1.5-second bucket. **The overall case still FAILS** because 13 of 60 recovery POSTs exceed 750 ms. Local phase success is not a full-case or reference-host pass. Controlled outages finish in-flight critical sections; they do not prove hard-power-loss or mid-checkpoint network-fault behavior.

## Natural connection target and final case coverage (v6.2)

[The natural combined case](final-v62-natural/combined-natural.json) passes every local gate: 1,300/1,300 applications, 5,352 verified durable recipient copies, all 200 native checkpoints restored, five files, 500 initial sockets and 313 genuinely queued/received offline copies across all 25 affected conversations. Device tabs retain their assignment: measured connections fall to 356 during the 30-account outage and return to 500. Burst POST p95 ≤500 ms, maximum 525.92 ms, no burst POST above 750 ms; online burst per-copy p95 ≤1.5 s. Recovery has two of 60 POSTs above 750 ms and still passes p95. It is a single local observation, not a repeated SLA.

The prior `combined` profile intentionally maintains 500 connections by reallocating tabs to remaining devices, adding churn. It remains the heavier stress variant. The new natural profile supplements it; no previous failed outcome is rewritten. All other profile policies remain unchanged. [Thirteen final unit checks](workload-unit-v62.txt) and [lint](lint-v62.txt) pass.

After v6's failed media attempt, v6.1 adds safe failure provenance without changing success policy. [Media rerun](v61-media/media-burst.json) restores integrity/all 1,300 messages but misses latency. [Remaining cases](final-v61-rest/matrix-summary.json) retain their individually recorded v6.1/v6.2 versions. The coordinator paused after its completed group-five child while adding/running the natural variant; orchestration wall time includes that pause, while driver timings do not. Later group/legacy/endurance cases use final v6.2. The [results report](../../security/metadata-privacy/workload-results.md) records actual per-case outcomes and limitations, including failed attempts before planned handoff/outage and the separate two-hour target.

## Completed final endurance and publication binding

[The final v6.2 soak](final-v61-rest/endurance.json) passes integrity and all local performance gates: 7,200.000 seconds, 14,400/14,400 applications, 60,414/60,414 durable recipient copies, 108 MLS updates, all 200 encrypted native checkpoints restored, zero socket errors/429 retries/deadlocks. Ten users hand off at 40 minutes; 30 users disconnect at one hour and return two minutes later. All 25 affected conversations accumulate real backlog, and all 185 planned-outage copies are actually received. Final deferred catch-up takes 33.431 seconds. POST p95 ≤250 ms; online copy p95 ≤750 ms. The raw maximums/tail misses remain visible; p95 does not promise every request meets its budget.

[Source binding](final-source-binding.json) verifies every measured source component/native binary of the final natural combined case and endurance against this review checkout, including four API workers ×16 pool maximum. The source working-manifest hashes were captured at case start; subsequent documentation changes are not relabelled as measured source. The [results report](../../security/metadata-privacy/workload-results.md) consolidates all final outcomes and remaining qualification limits.

## Review source and publication checks

Review source commit: `8b26eeaea5a42edcde1cc4596133261e87014267`. Final source/component binding and the full default-rule secret-scan review are recorded in [final-source-binding.json](final-source-binding.json), [validation-summary.json](validation-summary.json) and [secret-scan-review.json](secret-scan-review.json). The raw detector exits 1 for 163 individually reviewed non-secret patterns: 154 verified source hashes, five public library symbols, one Cargo dependency-name match, two public GPG fingerprints and one explicit test-fixture phrase. Zero confirmed credentials; no detector exclusion or baseline was added. Raw redacted reports and runtime fixtures remain private. `SHA256SUMS` covers every published file in this directory except itself.
