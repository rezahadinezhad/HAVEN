# Synthetic graph retirement: what actually disappears

The native-MLS fixture has two distinct accounts/devices, a real KeyPackage claim/Add/welcome, and a signed application message. Both devices prepare, ACK, consent and sign final-certificate receipts. The server initially retains two memberships and two envelopes. This backend fixture signs synthetic archive commitments; separate real-browser tests prove actual encrypted archive persistence and offline restore. The two layers are tested separately; there is no claim of a combined browser-to-destructive-worker production run.

`test_graph_retirement.py` asserts these changes in the disposable PostgreSQL database:

| Record family | Before retirement | After successful retirement |
|---|---|---|
| Conversation including creator/genesis/group/head | One graph-bearing row | Removed |
| Membership | Two device/account edges | Removed |
| Envelopes, sender headers, signatures and control roster/welcome | Two envelopes, one Add control | Removed |
| Delivery cursors and notification outbox | Refer to this conversation/history | Removed after obligations settle |
| Closure proposal, roster, preparations, consents and receipts | Full public participant graph | Removed |
| Expired cross-participant KeyPackage claim | Device/claim association | Standard expired association minimization; digest marker retained |
| Account/device records | Two accounts/devices | Both retained |
| Account/service storage counters | Exact charged conversation and envelopes | Each charged counter exactly zero in this single-conversation fixture |
| Replay/finality markers | None | One opaque conversation marker, two keyed message markers, permanent key binding |

A pending notification, retained security audit referencing the conversation/group, live cross-participant KeyPackage claim, missing durable ACK/final receipt, attachment row or unsupported participant history blocks retirement. Retained audits are never deleted to make the scanner pass. Account/service counters are checked under locks and refunded exactly; inconsistent counters abort rather than clamp.

All deletion and marker/accounting writes share one transaction. An injected exception immediately after envelope deletion rolls back the entire graph, markers and counters. Retry succeeds; an already completed retry returns unchanged. A real second database connection tries to recreate the old MLS group under a different account while retirement is paused: advisory locks serialize the checks and the creation is rejected after retirement commits.

The scanner is scoped to this reviewed text-only schema/fixture. It does not certify arbitrary future tables or audit payloads that embed undocumented IDs. Another active conversation can independently reveal the same account relationship. Opaque IDs still correlate with an older snapshot; keyed markers permit candidate testing by an actor holding the replay key. Accounts/devices, exact aggregate accounting, backups/WAL, old observations and client copies remain. This is reduced current-database graph disclosure for the retired fixture, not anonymity or global erasure.
