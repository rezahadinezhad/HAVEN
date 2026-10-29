#!/usr/bin/env bash
set -euo pipefail
cat <<'PLAN'
HAVEN manual active/passive promotion; no automatic promotion.
1. Declare incident, pause invitations and application writes, preserve timelines and release hashes.
2. Fence primary at provider/power AND database/network layers. A timeout is not fencing.
3. Record standby replay LSN, last acknowledged checkpoint, asynchronous RPO and possible loss.
4. Take encrypted snapshots. Never merge divergent databases or MLS epochs automatically.
5. Write the protected fencing attestation described in docs/runbooks/operations.md.
6. Run scripts/promote-standby.sh only after independently confirming actual fencing.
7. Validate migrations, ciphertext ordering, valid standby IP TLS and signed release artifacts.
8. Use the reviewed promoted-primary Compose configuration; never reboot the writer with standby initialization.
9. Users open the independently preverified backup origin with a previously enrolled distinct device.
   A different origin has separate keys. Never resume a copied old ratchet snapshot as a live device.
10. Stop clients on any rollback/gap/conflict. Rebuild old primary from the new timeline before reuse.
Evidence: docs/evidence/failover-local.json records a fenced local database drill.
UNQUALIFIED: separate providers, private tunnel/TLS replication, public endpoint switch, production RPO/RTO.
PLAN
