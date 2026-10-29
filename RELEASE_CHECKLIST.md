# Release checklist — BLOCKED

- [x] Preserve original specification; establish source history and architecture/security records.
- [x] Integrate actual MLS native/WASM and authenticated Django/PostgreSQL/browser workflows.
- [x] Test local persistence, offline queue, idempotence, device approval, media integrity and fresh-device recovery.
- [x] Provide migrations, container builds, separate DB roles, signed bundle/source build, encrypted backup and fenced local database promotion with prepared two-IP browser continuity tooling.
- [ ] Execute every remaining functional/security acceptance item in controls.csv; resolve failures and gaps.
- [ ] Independently review cryptography, credentials/rosters, concurrent state, recovery, files and browser integration; complete penetration test.
- [ ] Qualify actual Android/iOS browsers, CA trust, low-memory KDF/storage/media behavior and accessibility.
- [ ] Deploy two independently reachable domestic public IP hosts with valid IP TLS and tested certificate renewal/expiry procedures.
- [ ] Qualify hardened containers, clock/firewall policy, private-tunnel/TLS replication and real provider fencing; measure RPO/RTO.
- [ ] Verify login/chat/files with foreign egress unavailable and multiple Iranian mobile/fixed carriers.
- [ ] Perform fresh-host offline deployment and disaster recovery using independently verified signed artifacts.
- [ ] Complete representative 500-session workload, 20-message/s burst and two-hour soak on the reference host.
- [x] Run local API/Rust/Chrome/Firefox/WebKit checks and scan/remediate application container bases; retain remaining OS findings.
- [ ] Review all dependency advisories, licenses and reproducibility; record exact reviewed source/image hashes.
- [ ] Obtain owner release approval based on independent review and explicit remaining risks.

No owner approval or independent review has occurred. Do not change CRYPTO_READY simply to remove the warning. `make release-check` must continue failing until a reviewed change records the required evidence. Use only the isolated loopback evaluation profile for current functional testing.
# Minimal-retention upgrade checks (release gate remains BLOCKED)

- Verify a protected encrypted recovery backup; decryption keys stay off the VPS.
- Stop old API/outbox/privacy before migration 0008; preserve consumed-media state.
- Acknowledge shorter seven-day media expiry, including existing files, and the
  irreversible migration. Never attempt a blind downgrade/reopen old consumption.
- Deploy matching images; start privacy maintenance only on the sole writer.
- Verify cleanup health, API policy, real TLS, current-vault sync and restored-vault
  HTTP 410. Retain signed MLS history; never skip missing ratchet events.
- Review backup rotation separately, keeping tested recovery copies. Old archives,
  WAL, snapshots and recipient copies are outside live-row deletion.
- Rebuild/review/sign artifacts for this source; old signed QA bundles are stale.
- Independent review, target phones/providers and all original external gates
  remain required. Direct-browser service does not hide live IPs from ingress or
  prevent malicious server-delivered JS/WASM.
