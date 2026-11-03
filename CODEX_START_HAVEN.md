# Working on HAVEN

HAVEN is an existing operational product. Start with [README.md](README.md), [current implementation status](IMPLEMENTATION_STATUS.md), [security status](SECURITY_STATUS.md) and [verification](TEST_REPORT.md). Read the relevant architecture decision and local `AGENTS.md` before changing an area. The original [master specification](EMERGENCY_MESSENGER_CODEX_MASTER_SPEC.md) remains the architectural baseline; current owner decisions and newer implementation records supersede its old rollout status.

Normal settings enable messaging, account-wide closure and automatic server retirement. The maintained installation was upgraded on November 4, 2026; use the [installation record](docs/operations/installation-upgrade-2026-11-04/README.md) and [operations runbook](docs/runbooks/operations.md). Dated reports under `docs/history/` and `docs/security/` describe their own snapshots. Do not restore an old source gate just because a historical report says “disabled”.

Preserve standardized MLS encryption, exact TLS/Origin checks, explicit device trust, durable delivery, replay exclusions and fresh-device recovery. Never invent primitives, silently reset ratchets/identities, clear vaults to repair an upgrade, or claim unperformed review/field qualification. Independent security review remains pending.

Work on the user's current objective rather than rebuilding the original scaffold. Inspect the existing implementation, make focused changes, run meaningful bounded checks and update current-facing documentation. Keep private state, credentials, backups and keys outside Git. Regenerate the source manifest before publication, preserve historical evidence, and report what actually changed and was tested.
