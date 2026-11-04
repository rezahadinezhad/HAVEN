# HAVEN documentation

Start with the [project overview](../README.md). The guides below lead from everyday use to the system's architecture, operational responsibilities and security evidence.

## Use HAVEN

| Goal | Read |
|---|---|
| Set up a community or try it locally | [Guided Docker setup](runbooks/guided-setup.md) |
| Start a conversation and approve a browser | [First conversation, invitations and device trust](user-onboarding/README.md) |
| Use verified installed client delivery | [Delivery choices](security/client-delivery/README.md) · [Installation and updates](security/client-delivery/operations.md) |
| Understand closure and encrypted archives | [Account-wide closure](security/account-closure/README.md) |

## Build or operate it

| Goal | Read |
|---|---|
| Understand state, components and message flow | [Architecture](architecture/README.md) |
| Change source and run isolated checks | [Development](development.md) · [Contributing](../CONTRIBUTING.md) |
| Deploy, maintain, back up or restore | [Operator runbook](runbooks/operations.md) · [Retirement journal/restore](security/account-closure/operations.md) |
| Work with API contracts | [API documentation](api/README.md) · [Contracts](../packages/contracts) |
| Inspect the maintained local deployment | [Installation upgrade record](operations/installation-upgrade-2026-11-04/README.md) · [Installed client/gateway activation](security/client-delivery/local-installation.md) |

## Review the security

Follow **[current status](../SECURITY_STATUS.md) → [security design](security/design-guide.md) → [architecture](architecture/README.md) → [verification](../TEST_REPORT.md)**. The design guide connects problems, controls, evidence and remaining limits; the specialist records preserve exact policy and implementation details.

| Question | Evidence and detail |
|---|---|
| What is operational, and what remains unqualified? | [Implementation status](../IMPLEMENTATION_STATUS.md) · [Security status](../SECURITY_STATUS.md) |
| What does the service still see? | [Metadata threat model](security/metadata-privacy/threat-model.md) · [Privacy hardening](security/privacy-hardening/README.md) |
| What is retained or removed? | [Routine retention](security/server-data-retention.md) · [Mutual retirement](security/account-closure/README.md) |
| What changes when client delivery is verified? | [Delivery model](security/client-delivery/README.md) · [Hostile-origin/update checks](security/client-delivery/verification.md) |
| Why were these choices made? | [Architecture decisions](adr/) |
| How can a vulnerability be reported? | [Security policy](../SECURITY.md) |

Dated reports retain the state, failed attempts and qualification limits of their recorded source. Earlier results do not automatically qualify a later build. Use the current indexes for present behavior and [project history](history/README.md) for superseded release/status narratives.
