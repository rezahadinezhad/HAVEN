# Short, bounded measurements

No load/soak/endurance/500-socket test was run. Measurements use five fixed batches of 1000 local group derivations plus nine attachment-length cases, not network traffic. Exact sample values: [JSON](evidence/short-measurements.json), script `scripts/measure-privacy-hardening.py`. The real browser independently checks the same attachment bucket boundaries and actual AEAD media delivery.

Median time per 1000 local derivations: raw UUID label **0.897 ms**, validated HMAC label **8.653 ms**. This includes UUID canonicalization/settings access. It is a tiny CPU micro-measurement, not server request latency, p95, production capacity or a long-term stability claim. A previous routing key doubles publisher derivations/sends for that transition; consumers join one group only. New pending-view query replaces ORM graph reads while preserving bounded 100-row outbox batches; query plans at production scale remain unqualified.

| Original plaintext bytes | Bucket bytes | V1 wire bytes | V2 wire bytes | Added bytes | Chunks |
|---:|---:|---:|---:|---:|---:|
| 0 | 4,096 | 16 | 4,112 | 4,096 | 1 |
| 1 | 4,096 | 17 | 4,112 | 4,095 | 1 |
| 4,095 | 4,096 | 4,111 | 4,112 | 1 | 1 |
| 4,096 | 4,096 | 4,112 | 4,112 | 0 | 1 |
| 65,536 | 65,536 | 65,552 | 65,552 | 0 | 1 |
| 65,537 | 81,920 | 65,553 | 81,936 | 16,383 | 1 |
| 1,048,576 | 1,048,576 | 1,048,608 | 1,048,608 | 0 | 2 |
| 1,048,577 | 1,114,112 | 1,048,625 | 1,114,160 | 65,535 | 3 |
| 26,214,400 | 26,214,400 | 26,215,200 | 26,215,200 | 0 | 50 |

AEAD tag overhead is 16 bytes/chunk in both formats. True length is in encrypted MLS metadata/AAD, not an additional clear server column. Size classes do not increase chunk count at the selected aligned boundaries; the authoritative count remains validated for every input. Empty/tiny files have intentionally high percentage overhead but a bounded 4KiB cost. Above 1MiB, class overhead is below 6.25%. 25MiB stays 25MiB plus tags, below existing server ciphertext cap. Exact size within a bucket is less precise, not secret against a participant or timing analysis.

Local state overhead: one Device integer, a small expiring signed contact grant (not a new per-contact DB row), one SQL view, no new service. API/Redis/WAL write throughput, host thermals/battery and physical-memory long-term behavior were NOT_MEASURED. Production build wall time 5.55s and short test durations are recorded separately; no p50/p95 SLA is inferred.
