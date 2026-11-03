# Release and deployment checklist

Normal product activation is owner-authorized and operational. External qualification is tracked separately; see [security status](SECURITY_STATUS.md).

## Current delivery

- [x] Enable normal messaging, account-wide closure and automatic graph/media retirement.
- [x] Verify one participating device per account and unanimous group consent, including former members.
- [x] Verify encrypted local archives, media exclusions, final receipts and restore replay protection.
- [x] Pass source integrity, secret scanning, dependency checks and API/native/frontend CI for the activation source.
- [x] Upgrade the maintained local installation with tested encrypted backup, migrations through 0020, separate worker roles and the independent journal.
- [x] Verify the upgraded installation over trusted HTTPS in Chromium/Firefox, including English/Persian layouts and operational notices.
- [x] Keep current project status separate from [historical evidence](docs/history/README.md).

## External qualification still pending

- [ ] Independent cryptographic/application review and penetration testing.
- [ ] Physical Android/iOS browser, trust, memory/storage, media and accessibility qualification.
- [ ] Public-host container/clock/firewall hardening and trusted IP certificate renewal.
- [ ] Separate-provider replication/fencing and measured RPO/RTO.
- [ ] Domestic carrier/outage and fresh-host offline/disaster recovery qualification.
- [ ] Reference-host capacity qualification for the current archive/retirement implementation.

`make release-check` checks operational source activation. `python3 scripts/release-gate.py --qualification` reports the outstanding external evidence. Keep TLS, approved-device, replay and durability protections enforced. The local compatibility profile is explicitly local and does not qualify a public deployment.

[Executed installation upgrade](docs/operations/installation-upgrade-2026-11-04/README.md) · [Operator runbook](docs/runbooks/operations.md) · [Historical checklist](docs/history/2026-11-03-release_checklist.md)
