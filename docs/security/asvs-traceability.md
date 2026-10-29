# ASVS planning traceability — no certification

This is a partial engineering mapping against ASVS5 themes, not a clause-by-clause conformance claim. Full verification remains blocked.

| ASVS theme | Implementation / evidence | Remaining gate |
|---|---|---|
| Encoding/input validation | Strict DRF fields, bounded bytes, React plain text, CSP nonce | Full malformed/Unicode/XSS integration suite |
| Authentication | Argon2id, invite-only API, generic login error, Redis limits | Broader adversarial recovery/enrollment qualification |
| Session management | 384-bit opaque token hash, Secure/HttpOnly/Strict cookie, expiry/revocation, CSRF/Origin | Full device/browser/session adversarial matrix |
| Access control | Role checks, member-scoped queries, chunk uploader/epoch checks, HTTP IDOR negatives | Independent review of implemented credential/roster/role policy |
| Cryptography | RFC9420 OpenMLS suite1 adapter, Argon2id/XChaCha vault/media code | Independent review; complete rollback/fork/property/fuzz matrix |
| Secure communications | TLS-only ingress, exact IP/Origin, valid/untrusted/expired test leaves | Public IP issuance and physical OS/browser trust |
| API/file/resource security | Sized envelopes/chunks, quotas, private DB blobs, no public object URLs | AEAD/resume and commit concurrency exercised; broader resource qualification |
| Logging/privacy | No free-form audit payload; body-free access config; generic errors | Sensitive-fault injection/retention review |
| Configuration/supply chain | Locks/hashes, internal networks, signed bundle, source gate | Remaining optional advisory review and qualified hardening host; DB role split tested |
| Architecture/business logic | ADRs/threat model, causal DB order, durable outbox | End-to-end conflict/rollback/failover/field qualification |
