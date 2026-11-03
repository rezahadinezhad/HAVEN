# Database access and service isolation

**IMPLEMENTED_AND_TESTED**, scoped to real PostgreSQL role/grant tests and rendered deployment configuration. A rebuilt production Compose installation was **NOT_RUN / not deployed**.

Original weakness: notification query projection avoided message content, but the worker inherited the API's unrestricted runtime DB password, application signing secret and certificate mount. Projection did not protect against a compromised worker process.

Migration 0018 creates owner-backed `haven_notification_targets` with security_barrier, projecting only pending outbox_id → user_id for nonremoved memberships. `publish_outbox` locks a bounded batch of outbox rows, queries that view, coalesces recipients and marks rows only after every Redis send. Failure rolls back all rows for idempotent retry. It no longer queries graph base tables. The view itself has no recipient names, device/conversation IDs, message bytes, signatures, profiles, sessions or secrets; it can still reveal pending recipient associations.

`prepare_db_roles` provisions a distinct `haven_notify` LOGIN with independent random password and no superuser/create/replication/bypass privileges. `migrate_haven` applies explicit `database_privileges.grant_notification_worker` after schema migrations: no role inheritance or owned application objects; revoke table AND column ACLs, sequences, schema CREATE and future default grants; grant only SELECT(id,envelope_id,sent_at,attempts) and UPDATE(sent_at,attempts) on outbox plus SELECT on the pending-target view. No INSERT/DELETE/DDL/base graph grants. The main migration owner remains responsible for creating/regranting views. Do not apply a custom PUBLIC or inherited wide grant; the supported provisioner revokes PUBLIC database/schema creation privileges.

Compose's outbox environment replaces the inherited API environment entirely: separate DB login, routing key, Redis URL and `haven.notification_settings`; no main signing key/runtime DB password/TLS certificate mount. The worker supplies an ephemeral process-local Django configuration key, unused for sessions or contact grants. Its shared routing key is still sensitive. API and retention worker continue to have broad graph access because their existing authorization/cleanup queries need it. Backup/bootstrap/migration authority is not claimed to be compartmentalized.

| Table / operation | API runtime | Notification login | Retention worker | Migration/bootstrap / backup |
|---|---|---|---|---|
| User, Session, Device, recovery/audit | Existing scoped app CRUD | DENIED | Cleanup/auth-required rows | Owner/privileged recovery |
| Conversation, Membership, Envelope, ControlEvent | Existing protocol CRUD | DENIED, including ciphertext/signed JSON | Retention reads/eligible retirement | Owner; backup reads graph |
| DeliveryCursor, StorageUsage | Existing ACK/quota operations | DENIED | Required eligibility/accounting | Owner / backup |
| Attachment/chunks/views/tombstones | Existing authorized lifecycle | DENIED | Required cleanup/consumption | Owner / backup |
| NotificationOutbox | Existing creation/cleanup | Only four selected/two updated columns; no insert/delete | Cleanup sent rows | Owner / backup |
| haven_notification_targets | Runtime existing access | SELECT pending outbox/user only | Not required for cleanup | Migration owns view |
| django_migrations / DDL | Existing no mutation / no DDL | DENIED | Existing no mutation / no DDL | Migration owner; bootstrap role provisioning |

No RLS was added: shared API credentials and current cross-account transaction fences do not become separate principals by mechanically enabling policies. Admin account/device endpoints remain role-scoped and minimal. Fresh reauthentication was not added to routine disable/revoke because existing recovery/fence checks remain authoritative; existing own-disable/password changes already demand the password.

Real-login tests run actual worker queries and a subprocess, then verify denial for all graph/profile/recovery tables, migration history, outbox rebinding/delete and CREATE. Regrant handling is explicit; this is not a mock permission assertion. A worker compromise can disrupt hints and observe pending recipients but cannot authorize messages/ACKs; authenticated periodic HTTP sync remains authoritative. Main API or privileged SQL compromise still reconstructs the full graph.
