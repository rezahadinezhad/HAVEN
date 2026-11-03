# High-privacy settings

**IMPLEMENTED_AND_TESTED.** Existing notifications, typing, presence and optional read receipts already defaulted off; no default was weakened or reinvented. `ui.tsx` adds one action, **Use high-privacy settings**, which resets those four existing preferences and transient visible indicators. It does not create an ambiguous second flag that can disagree with individual controls. Subsequent explicit opt-in is still possible.

The preference-write effect now waits for hydration before persisting, so initial defaults cannot overwrite saved choices during startup. Browser tests start with all four opted in, apply the profile, inspect persisted values and verify English/Persian rendering. Locked account rendering hides profile information; encrypted contact labels/events are cleared by the existing lock path. Notifications remain generic, issued only by the live unlocked loop; no sender/message preview is added. No external identity lookup exists.

Mandatory durable ACKs, recipient_synced cursors, replay controls, acceptance receipts, pending sends and MLS synchronization are untouched. Human reading is distinct from durable synchronization. Disabling optional signals does not hide network connections, server requests, timing, DB writes or group membership. The existing five-minute idle/navigation lock remains; no untested shorter timer or receipt delay is introduced.

Changes: `apps/web/src/app/ui.tsx`, `src/lib/i18n.ts`. Verification: [real browser results](adversarial-test-results.md), [settings capture](evidence/privacy-settings-en.png), existing live WebSocket authorization tests. Source review and tests cover selected flows; physical-mobile notification/background behavior remains unqualified.
