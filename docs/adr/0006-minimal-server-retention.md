# Minimize retained server data without changing the browser deployment model

Status: implemented and locally tested; independent security review remains required.

The owner requests less information on a stolen server without another device,
user-operated relay, foreign service, or a new installation requirement. Preserve
the existing OpenMLS protocol, durable offline delivery, authenticated history,
device approvals and IP HTTPS gates. This changes retention, not the anonymity
model. No custom cryptographic protocol is introduced.

## Decisions

- After a 24-hour retry window, retire application ciphertext only when every
  eligible, active approved device has durably acknowledged it. Keep unread
  ciphertext and all MLS control/Welcome material. Preserve signed headers,
  signatures, digest/idempotency markers and sequence numbers for verification.
  Remove the retired envelope's precise receipt timestamp. Old/cloned vaults
  requesting retired history fail closed; they must use a verified fresh device.
- Encrypted attachments expire after seven days; abandoned uploads after one
  hour. View-once state stores a consumed boolean instead of a permanent opening
  timestamp. Drop temporary capabilities/device bindings when leases end and
  recipient consumption rows when every opening is finished. Keep ID-only replay
  tombstones. Server deletion is not physical erasure from pages/WAL/backups.
- Delete expired/revoked sessions and expired/consumed recovery challenges,
  obsolete invitations, delivered notification rows and expired key-package
  payloads. Preserve used-package digests to prevent reuse. Security audit records
  expire after seven days; ordinary successful logins create no durable audit row.
- A separate maintenance worker performs bounded cleanup every five minutes;
  Redis notification failures do not stop retention. Record aggregate cleanup
  health only, with no account/conversation labels. Do not silently expire unread
  messages or remove required signed membership history.
- Do not pass client IP headers to Django/Next. Nginx still necessarily observes
  network IPs and applies per-IP limits in volatile memory. Authenticated limits
  use accounts; login uses keyed, minute-scoped account identifiers plus a global
  budget. Redis keys do not contain raw or unkeyed hashes of IP/account identifiers.
- Disable request body/response disk spooling at ingress, SQL/parameter/connection
  logging and query process titles in the supplied PostgreSQL configuration.
  Redis remains nonpersistent. Suppress raw exception/request logs, retain bounded
  operational counters. These settings cannot constrain a hostile root operator.
- Replace Django Redis pickle serialization with bounded JSON-only decoding,
  retain atomic integer counters, namespace the cache format and bound Redis
  connection/read timeouts. Coordination data is never an executable object.
- Expose the actual retention policy and remaining metadata in EN/FA settings.
  Keep browser trust, endpoint compromise, backups, account graph and traffic
  correlation limits explicit. Do not claim database theft reveals no metadata.

## Scope limits

Accounts, password hashes, public device credentials, routing/membership and
signed proof history remain in PostgreSQL. Removing these safely needs a new
identity/delivery design and separate review; deleting them is not hardening.
Disk/database encryption with a key on the same live host does not defeat root.
No extra relay or Tor requirement is introduced. Direct connections expose IPs
to ingress/provider/kernel, and malicious origin code can still steal keys.
Deleted data may persist in older backups and replicas. Operators must rotate
encrypted backups under the documented policy; never delete the only recovery
copy automatically. Existing external release gates stay blocked.

## Deployment

Deploy migration/API before the maintenance worker and updated UI. Retention is
enabled by default; old unsynchronized messages and protocol proofs remain intact. The
payload change is irreversible without an older backup and never repairs an old
client ratchet. Back up and verify before migration. Stop maintenance before a
rollback. Run cleanup after restoring old backups and fence obsolete primaries.
