# Security status

**Operational · independent security review pending.** Normal messaging, account-wide closure and automatic server retirement are enabled. Local engineering tests and GitHub CI have passed. This status does not claim independent certification.

## Current protections

- RFC 9420/OpenMLS encryption, explicit device approval and fingerprint verification.
- Encrypted local vault/history/outbox, authenticated ordering and durable server acceptance.
- Scoped account/device APIs, private contact introductions, independent routing keys and a notification-only database login.
- Account-wide retirement: one approved participating device per account; unanimous consent from every affected account, including former group members.
- Encrypted available-history archives, media exclusions and explicit consent before deletion; independent permanent replay journal for SQL restores.

Closure preparation pauses the account and currently cannot be cancelled or transferred. Missing consent or changed authorization retains server history. View-once content is not archived. Older deletion-disabled prototype consent does not authorize the new policy.

## Deployment and remaining limits

The maintained local installation is described in the [November 4 upgrade record](docs/operations/installation-upgrade-2026-11-04/README.md). It uses the explicit loopback compatibility profile on this development Docker host. Public-host hardening, physical iOS/Android testing, provider failover and independent application/cryptographic review remain unqualified.

Active membership and authenticated routing remain visible to the service. Retirement does not erase old backups, WAL, exported recipient copies or prior observations. A compromised application origin or unlocked device can expose client secrets. The independent current retirement journal/key must survive SQL restoration; loss or rollback of every copy cannot be repaired by the protocol.

[Retirement behavior and limits](docs/security/account-closure/README.md) · [Operations](docs/runbooks/operations.md) · [Verification](TEST_REPORT.md) · [Historical reports](docs/history/README.md)
