# Verification and remaining gates

Evidence is from isolated local synthetic accounts, native OpenMLS and real PostgreSQL/Redis/browser storage. [Verified source hashes](evidence/verified-source.sha256) bind the non-document source snapshot; the root source manifest also covers this report and its evidence. Test counts overlap; they are not an additive assurance score. No endurance, soak, unbounded load, production deployment or real-history deletion was performed.

| Check | Evidence |
|---|---|
| Full backend milestone and final regression: **158 passed in 110.11s** | [Backend output](evidence/backend-full.txt); includes native MLS, authorization races, retention/view-once, storage, migrations and real restricted PostgreSQL login |
| Closure/retirement focused checks: **13 passed in 25.69s** before the final extra rekey regression | [Focused output](evidence/backend-focused.txt); forged signatures/checkpoints, stale preparations, withheld ACKs/receipts, exact accepted retries, new-write freeze, restore epoch, extra device, attachment rejection and synthetic transactional rollback |
| Upgrade and unsafe reverse: **2 passed in 4.93s** | [Migration output](evidence/migration.txt); 0018→0019 preserves exact legacy ciphertext/header/signature/genesis; reverse refuses before marker tables can be lost |
| Chromium closure and existing MLS/media regression: **2 passed in 27.2s** | [Browser output](evidence/browser-closure.txt) |
| Firefox closure: **1 passed in 17.1s** | [Firefox output](evidence/browser-firefox.txt), including cold offline unlock/restore and EN/FA UI |
| Next production build | [Build output](evidence/web-build.txt); typecheck also checked separately |
| Current-schema classification | `scripts/check-metadata-inventory.py`: 206 current and eight retired fields; no row values read |
| Reviewable-source secret scan | [Redacted scan](evidence/secret-scan.txt), [machine report](evidence/secret-scan.json) |

The browser closure case uses two real accounts and their actual browser MLS/vault workers. It verifies bidirectional text, proposal, a failed archive save with no preparation sent, a lost preparation response with the identical durable retry, a genuinely offline queued peer send flushed before preparing, and renewed agreement on the new head. It then verifies that failed consent persistence submits no consent, and a failed final-certificate save withholds the final receipt even after the server finalizes. Retry recovers both receipts.

The same case decrypts both encrypted exports, confirms all text is present, reloads, unlocks offline, removes the local archive in the disposable fixture, and restores the encrypted export without changing ratchets/pins/cursors/outbox. A wrong passphrase is rejected. Locking clears local plaintext access. Actual UI checks cover closed write/media controls, finality status, restore controls, English and Persian/RTL. [English closure](evidence/closure-en.png) and [Persian archives](evidence/archives-fa.png) are real captures.

Review found and corrected a retry-related rekey-fence regression: recovering an identical accepted envelope must not permit a new application message in `rekey_required`. A dedicated test now asserts both behaviors and unchanged head on rejection. Other intermediate failures were test issues: using raw encrypted `loadVault` as plaintext state, installing no offline worker cache, an incorrect attachment test URL, and a Node-side interception lacking the test CA. Interception now stays in the browser using its trusted TLS path. An offline import comparison also incorrectly treated roster insertion order as participant-set order; verified sorted rosters are now compared and ordinary live pin checks remain mandatory. Firefox initially rejected the offline worker load while Playwright request interception was active ([diagnostic](evidence/browser-firefox-cold-initial.txt)). The final test verifies the worker is cached, removes interception to restore the normal cache/request path, and still sets the browser fully offline. Firefox then passes cold unlock and import; no application cache/CSP/TLS weakening was needed.

Remaining production gates:

- Independent review of the new application-layer signed protocol and its failure/rollback semantics.
- Explicit full participant/device capability and consent policy for groups, historical/removed principals, multiple devices, recovery and media/view-once obligations.
- Independently reviewed monotonic checkpoint/replay-key/backup restoration strategy. A server-only tombstone and manually changed namespace cannot defeat arbitrary rollback or a malicious origin.
- Qualified deployment roles, recovery drills, physical Safari/iOS/Android behavior and operational performance. No production SLA, p95/throughput or long-run stability was measured. Permanent replay-marker growth and its production quota treatment also require review; synthetic retirement does not qualify unlimited marker accumulation.
- A separately reviewed, explicitly activated production retirement integration. This change exposes no production deletion API/worker/command.

The new closure artifact table itself repeats the graph until retirement. Active conversation relationships, backups/WAL/replicas, client copies, prior observations and traffic remain observable. Source gates stay false. There is no anonymity, remote erasure or independent certification claim.
