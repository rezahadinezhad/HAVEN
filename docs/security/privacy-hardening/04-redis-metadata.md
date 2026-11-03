# Redis routing metadata

**IMPLEMENTED_AND_TESTED.** Original Channels groups were `user.<account UUID>` in `SyncConsumer`, typing/presence publishers and `publish_outbox`. Redis-only snapshots exposed direct account identifiers.

All producers and consumers now call `core.privacy.routing_groups`: HMAC-SHA256 with a separate required `HAVEN_ROUTING_SECRET`, input `haven/channels/account/v1\0 || UUID.bytes`, and Channels-compatible `route.<64 hex>`. UUID parsing provides one canonical byte representation. No plain hash or global signing-key fallback exists. Startup rejects missing/short secrets or reuse of the application signing key. Secrets are generated independently by setup/create-secrets; test prepare only appends a missing disposable test secret. Existing real deployment configuration is not edited.

Consumers join exactly the current group, so hints are not duplicated. Publishers send to the current and optional previous key. The 120-second group TTL, authenticated heartbeat repair, live session revocation, 30-second message expiry and HTTP sync authority are unchanged. Existing rate keys already use time/category-scoped HMACs; metrics/leases already avoid account labels.

## Rotation and first upgrade

First upgrade from raw UUID groups requires a coordinated drain/restart of old socket and notification processes with the new configuration. Do not run old raw-group consumers alongside the new publisher and pretend they receive hints. HTTP remains authoritative throughout, but drain/reconnect is the supported transition; no legacy raw label is retained by new code.

For later HMAC-key rotation: (1) distribute old current key plus the new key in PREVIOUS to every producer; keep consumers on old current; (2) after all publishers know both, switch CURRENT=new/PREVIOUS=old across processes; (3) drain/reconnect remaining old-key consumers, stop all old-config processes and wait at least group/message expiry; (4) remove PREVIOUS everywhere. Simply waiting 120 seconds while an old socket heartbeats is insufficient: it refreshes its old group. Keep old key material protected through the transition. Do not mix different current-only publishers during rollout.

Actual Redis tests verify scoped delivery, reconnect/state-loss repair, TTL, key rotation to old/new sockets and absence of raw UUIDs in affected group keys. An independent publisher process reaches an active socket through real Redis. A separate real narrow-login worker subprocess executes without the API signing key. Full Redis restart/stop and extended outage qualification were NOT_RUN; state-loss repair deletes only synthetic group keys, not production Redis. See [results](adversarial-test-results.md).

Threat boundary: a Redis-only observer lacking routing secrets cannot read account UUIDs directly from these labels. Group membership/traffic remains linkable. Optional typing/presence event bodies still identify conversation/sender devices; they are off by default. Redis operators can observe timing; Django/hosting/runtime operators or a worker holding the routing key can derive labels. PostgreSQL and signed histories retain the active graph.
