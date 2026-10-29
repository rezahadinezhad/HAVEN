# Threat model and risk register

Assets: client identity, MLS epoch/provider state, recovery kit, plaintext, session and invitation secrets, delivery order, encrypted backups and TLS signing material.

Trust boundaries: device/worker/IndexedDB; downloaded application origin; authenticated delivery API; PostgreSQL; Redis; operator filesystem; offline PKI workstation; standby origin.

| Risk | Mitigation / remaining limit | Gate |
|---|---|---|
| Malicious delivered JavaScript | CSP, local assets, hashes, reviewed releases; origin still can steal keys | Independent review; not fully mitigated |
| Endpoint compromise/coercion | Local vault, locking, warnings; cannot prevent screenshots/spyware | Residual |
| Unverified MLS adapter | Actual WASM browser tests, negative tests, state persistence; no invented fallback | BLOCKER-CRYPTO |
| Server fabricates credentials | Explicit fingerprint pinning, enrollment approval, authenticated MLS membership | BLOCKER-AUTH until integrated |
| Epoch rollback/concurrent commits | Sequencing, compare-and-swap, immutable history, client checkpoint | Must test |
| DB backup theft | Ciphertext only, encrypted operator backups; metadata remains visible | Must test |
| Session/CSRF/IDOR | Secure opaque cookie, Argon2id, Origin/CSRF, scoped access, bounded input | Must test |
| Private root compromise | Offline root, separate intermediate, replace trust anchor on every device | Operational high impact |
| Expired/untrusted TLS | Fail closed; never downgrade or bypass | BLOCKER-TLS field test |
| Browser eviction/key loss | Encrypted recovery kit, persistence warnings; DB cannot restore client keys | Must test |
| Routing/total blackout | Domestic hosts, prepared trust, offline bundle; no route means no delivery | External field gate |
| Metadata | Minimize logs, no public directory; relationships/timing/size/IP remain visible | Residual |
| Cross-origin standby | Explicit trusted endpoint and encrypted client migration; fencing | Must test |
| Host load/thermal limits | Bound queues/uploads/KDF, conservative concurrency | Capacity UNQUALIFIED |

No automated result establishes independent security verification or wartime suitability.

ADR 0006 adds ACK-safe ciphertext retirement, short-lived control-plane records,
consumption-state minimization and request/logging/spooling controls. Account,
device and signed conversation history remain visible in a database theft; live
ingress still sees IPs. A compromised origin can still steal client keys. See
docs/security/server-data-retention.md for exact categories and upgrade limits.
