# Before/after privacy leakage comparison

Baseline: actual merged source `0240706`, including original retention and PR #18. Measurements use synthetic data and current source, not real user dumps. No privacy score or percentage of anonymity is assigned.

| Observation | Before | After | Scope and limit |
|---|---|---|---|
| Exact durable ACK time | DeliveryCursor.updated_at | Column absent | Sequence and live receipt-version changes still reveal syncing; other logs/backups may preserve time |
| Per-chunk upload time | AttachmentChunk.stored_at | Column absent | Attachment creation/expiry, byte lengths and live transfer remain visible |
| Convenience session activity time | Session.last_seen, auto_now during selected saves | Column absent | Already not a per-poll presence log. Session.created_at/expiry/binding remain |
| Unused per-message receipt graph | DeliveryReceipt schema, available to store device/envelope/state/time | Table absent | Baseline production code had no writer. Removing the schema prevents future incidental collection; it is not evidence that real deployments accumulated those rows |
| Expired KeyPackage owner | Permanent device FK even after payload/claim scrub | NULL after bounded cleanup | No owner linkage left in that current row; known public digest/ID/expiry and backups can still correlate. Active claims retain owner and claimant until expiry |
| Previously scrubbed KeyPackage rows | Blank payload could exclude row from later cleanup | Candidate predicate includes any remaining device/claim/time | Regression seeds both old blank payload and ordinary expired payload. Permanent digest still rejects reuse |
| Message response timing | Exact received_at on delivery/accepted response | Not serialized; removed from generated contract | Server still needs acceptance time for retirement and aggregate health; API removal does not hide live arrival or network timing |
| Notification worker visibility | select_related fetched full envelope ciphertext, header, signature and sender | Only ID/conversation route plus worker fields | Same routing graph and PostgreSQL permissions remain; this reduces unnecessary process exposure, not A4 access |
| Redis account→channel after crashed socket | channels-redis default group_expiry 86400s | Configured 120s, renewed after session validation | Valid heartbeats keep live links; group name still contains account UUID. Actual Redis lost-key/renewal/revocation tested; host memory copies not erased |
| New MLS application lengths | Nearly exact framing-dependent content length | Authenticated 256-byte content blocks | Fixed-group benchmark 1/16/64/128 plaintext bytes change from four distinct wire lengths to 320 each. Larger buckets, group ID length, traffic, attachment size and timing remain distinguishable; old clients remain unpadded |
| Current DB social graph | Fully reconstructable | Fully reconstructable | Deliberately reported unchanged; signed JSON, credentials and accounting are independent graph sources |
| Host/network observation | IP, timing, volume at service/ISP/provider | Same fundamental visibility | No A6/A7 anonymity claim; existing no-log/no-spool source controls preserved |

## Reproducible database experiment

`apps/api/.venv/bin/python scripts/test-metadata-migration.py` seeds a fresh 0012 database with three synthetic active accounts/devices, membership and signed-structure records, old pending application ciphertext, an ACK from only one device, live and expired KeyPackages, a session and active view-once lease/unopened recipient. A real custom pg_dump is restored to a second disposable database. Forward migrations and cleanup run there.

Recorded [machine-readable evidence](../../evidence/metadata-privacy-2026-11-01/migration-comparison.json): three recoverable time columns become zero; receipt table disappears; package owner links 2→1 and claim links 2→1, leaving the live claim. Membership edges remain 3→3. A SHA256 over selected identity/trust, signed genesis/header/transition, ciphertext/acceptance time, sequence/head/epoch, cursor, session binding, media consumption/lease, chunk content, outbox and quota fields is identical before migration, after migration and after cleanup. This hash is selected-field consistency evidence, not a semantic cryptographic proof or a privacy score.

The old pending envelope remains despite its age because two active eligible devices have not acknowledged. The dump checksum/size is recorded; raw synthetic dumps remain owner-only in `.local/metadata-dumps`. Full restore succeeds, unsafe reverse fails before changing the observed state, and retrying forward migration/cleanup is idempotent. The fixture is not MLS-valid ciphertext; real native/browser integration is separate evidence.

## Responses, SQL, Redis and logs

PostgreSQL-backed API tests inspect actual message responses and captured SELECT statements: acceptance time/request digest are neither returned nor selected for message reads, signed fields survive, and worker routing does not load content/proof columns. Existing proof projection stays intact. A real Redis test reads group TTL, deletes the actual group key, observes heartbeat recovery, revokes the session, deletes the key again and verifies it cannot be recreated. No mocked channel layer is used for this property.

Real pinned Nginx with verified loopback-IP TLS rejects forwarded-origin spoofing by overwriting the exact login source and removing other address headers for API/WS/web. Synthetic sensitive markers are absent from its logs. That test pre-existed and was rerun, not newly invented protection. Existing Django/worker static-error and JSON-cache tests remain. Arbitrary host logs, provider telemetry, PostgreSQL extensions, Redis memory snapshots and physical media remnants are not covered by those tests.
