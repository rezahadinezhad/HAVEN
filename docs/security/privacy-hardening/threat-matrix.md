# Threat matrix

Use [A1–A8 model](../metadata-privacy/threat-model.md). Redis-only and narrow-worker compromise are additional subsets, not substitutes for that model.

| Adversary | Improvement | Explicit limit |
|---|---|---|
| A1 current database dump, no secrets | Less required human identity, bounded retained temporary records | Full active User→Device→Membership→Conversation→Sender graph reconstructable, including signed copies |
| A2 dump plus WAL/backups | Future retention minimization only | Cannot erase old copies or undo observation |
| A3 curious operator/admin | Purpose-scoped APIs and minimal worker SQL/grants | Privileged operator can read routing or change code |
| A4 main runtime/host secrets | Existing E2EE/trust/durable checks preserved | No routing secrecy; hostile origin can steal unlocked keys/plaintext |
| Redis-only snapshot, no routing key | HMAC group labels remove direct account UUIDs | Optional hint bodies/timing/group topology remain; known observations can correlate |
| Notification credential only | Pending hint view and outbox only, separate credential | Pending recipients remain visible; Redis key still present; API/retention credential stays broad |
| A5/A6/A7 hosting/ISP/broad observer | Size buckets reduce precision only | Timing, addresses, volume, correlations and service usage remain |
| A8 malicious endpoint/participant | Scoped lookup, validation, existing MLS/replay/view-once checks | Authorized recipient can record plaintext and roster |
| Local locked-browser observer | Remove full plaintext profile cache, hide labels | UUID unlock pointer/indexes/preferences and ciphertext remain |
