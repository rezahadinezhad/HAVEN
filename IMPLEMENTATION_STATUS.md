# Implementation status

**Normal product features are operational.** Messaging and conversation retirement use the standard settings and workers. Independent security review and external deployment qualification remain pending; see [security status](SECURITY_STATUS.md).

| Area | Current implementation |
|---|---|
| Messaging | OpenMLS encryption, direct/group conversations, verified enrollment, durable retry, media and view-once policies |
| Devices and recovery | Approved multi-device access, fingerprint pins, revocation/rekey fences, fresh-device recovery and read-only history imports |
| Local storage | Encrypted segmented history/outbox, atomic checkpoints and separately sealed archive records |
| Privacy | Optional profiles, scoped peer/admin disclosure, private introductions, HMAC routing and notification-only SQL credentials |
| Conversation closure | Default signed v2 policy; one participating device represents an account; every affected group account must agree |
| Server retirement | Normal background worker, signed final archive receipts, dependency settlement, storage accounting and independent restore-deny journal |
| Interface | English/Persian, RTL, responsive layouts, light/dark themes, offline shell and contextual operational notices |
| Client delivery | Signed installed Linux client, atomic offline updates, pinned release trust and independently deployable frontend/API bridge |
| Operations | Versioned container images, coordinated migrations, protected backups, journal bootstrap and documented restoration |

The [current installation upgrade](docs/operations/installation-upgrade-2026-11-04/README.md) records the running stack and verification. Protocol/resource limits and the irreversible preparation step are documented in [account-wide closure](docs/security/account-closure/README.md).

[Latest verification](TEST_REPORT.md) · [Operator runbook](docs/runbooks/operations.md) · [Historical implementation reports](docs/history/README.md)
