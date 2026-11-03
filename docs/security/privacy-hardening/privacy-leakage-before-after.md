# Adversary-specific before/after leakage

| Surface / attacker | Baseline | Current behavior / evidence | Residual |
|---|---|---|---|
| Locked browser localStorage | Full six-field User, indefinitely cached | Legacy entry removed; only UUID unlock locator persists, roles/profile not restored from it; real browser restart/offline tests | UUID/indexes/preferences/ciphertext and unlocked memory remain |
| Registration / SQL reader | Required display name and chosen username | Display name optional; blank username gets 128-bit CSPRNG handle; no existing renaming | User may choose identifying values; active graph unchanged |
| Unrelated authenticated approved user | Known approved UUID grants full device lookup and package reservation | 404 without own/shared history or explicitly shared 24h introduction; peer response 10→6 fields | Bearer links forwardable; authorized peers know certificate; timing oracle not eliminated |
| Admin API | Full User response six fields; profile/security generation | Purpose-specific four-field id/username/role/active SELECT/response | Admin/SQL privileges still reveal accounts; main runtime remains broad |
| Contact sharing applications | Default account name in every friend card | Default name omitted, explicit identity-bearing warning, fragment cleared | Device UUID/fingerprint/grant remain shareable; same-origin JavaScript can read fragment |
| Redis-only dump without routing key | user.UUID group labels | route.HMAC with independent secret and bounded TTL; real Redis and subprocess delivery | Stable pseudonyms/traffic/topology, optional activity body IDs remain |
| Notification credential compromise | Shared main runtime DB/signing credentials, all graph/content SQL accessible | Separate login, outbox column grants and pending recipient view; actual denied SELECT/DDL tests; API credentials removed from Compose mapping | Pending recipient/outbox associations and routing key visible; hint suppression possible; no main-runtime secrecy |
| Attachment SQL/network size observer | Exact size = ciphertext minus chunk tags | New bucket lengths, 4/16/64KiB classes, actual browser/MLS/SQL tests | Bucket, chunk count, timing, participants, traffic totals remain; old attachments keep old precision |
| Logs / backups | Existing suppressions, bounded audits/aggregates; historical copies independent | New secrets included in installer redaction; no sensitive request logging added | Operator can add tracing; old archives/WAL/replicas are not erased |
| Current PostgreSQL graph attacker | Full User→Device→Membership→Conversation→Sender, signed duplicates and ACK/media/quota links | Still reconstructable; synthetic SQL and signed-JSON test explicitly succeeds | No graph anonymity; closure only designed |
| Malicious main origin/host | Can serve hostile JS/WASM to unlocked endpoint | CSP/storage/lock checks preserved and targeted host validation improved | Origin trust problem remains unsolved |

Current database field count increases by one revocation generation (191→192 current fields); no claim is made that this is a bulk DB-size or active-graph reduction. Existing timestamp/payload retention minimization is separately credited to [prior metadata work](../metadata-privacy/README.md).
