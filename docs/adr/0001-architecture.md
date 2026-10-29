# ADR 0001 — architecture and gates (2026-10-23)

Accepted engineering direction; security qualification pending.

The initial directory held only the immutable supplied specification, startup instructions and checksums. No application, Git repository or AGENTS.md was found. Preserve these inputs. Implement a monorepo with Django/DRF/Channels, PostgreSQL durability, Redis fanout/rate limits, Next.js TypeScript, local OpenMLS Rust/WASM and libsodium. No external messaging server or runtime service.

A direct chat is an MLS group of device leaves. Use RFC 9420 mandatory suite 0x0001 (X25519/AES128GCM/SHA256/Ed25519) if the selected OpenMLS build passes. All state-mutating crypto operations run on a serialized worker queue. Persist encrypted provider state and pending ciphertext together before network submission. Never re-encrypt retries. Serialize server control events and messages in one per-conversation sequence. PostgreSQL commits before ACK; WS is a hint and HTTP sync authoritative. Devices and recipients must explicitly compare credentials independently; server roles grant no private keys.

Start with browser crypto/TLS proofs. A failed crypto proof locks message/device/media endpoints and UI with CRYPTO_NOT_READY; do not simulate encryption. Passing a narrow proof does not qualify integration. Gate production separately on membership authentication, durable browser state, field TLS, external review and complete functional coverage.

Development uses a short-lived test-only root/leaf for an IP SAN, explicitly supplied to a separate test browser trust store. Never use ignoreHTTPSErrors, certificate-error switches or HTTP password/crypto flows. Real public-IP trust, physical phones and Iranian routing require external qualification.

Active/passive manual promotion requires fencing the former writer. Cross-origin failover cannot magically share IndexedDB or cookies: prepare a distinct approved device at the independently trusted standby before outage, or recover into fresh identity and explicitly re-add it. History imports never resume restored ratchets. No automatic origin switch or unverified endpoint list.

Versions will be resolved from actual registries and locked. Available host: Node 24.18.0, Python 3.14.4, Rust stable, Docker engine 29.8.0; 14GiB RAM with memory pressure. Limit build parallelism; no capacity claim from this host.

Container scan remediation: application bases move to digest-pinned Debian 13 (Trixie), Python 3.12.15 and Node 24.22.1. The runtime images remove pip and global npm/Corepack/Yarn, keeping package installation in build stages. Base/library findings remain governed by the recorded scanner report and cannot be dismissed by a clean application dependency scan. Official image digests are resolved before the build; offline bundles include those exact bases.

Prepared standby origins route to the sole primary API over a separate verified private TLS bridge while the database replica remains read-only. Public backup TLS is distinct; users enroll distinct devices before outage. Only after fencing/promotion does routing move to the backup-local API. The local two-IP test covers this path without copying ratchet snapshots.
