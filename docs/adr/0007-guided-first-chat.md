# Guided first chat and bounded member invitations

Status: implemented and locally tested; independent review and security/release gates remain outstanding.

The owner reports that both members and administrators cannot discover how to
start chatting. The first useful outcome is two ordinary people exchanging an
actual encrypted message, without entering device UUIDs or navigating operator
tools. This pass implements real setup/contact/verification/chat actions, not a
tour or sample conversation.

## Product and security decisions

- One Start a chat entry leads through local browser setup/unlock, sharing or
  pasting a friend link, explicit code comparison, and creating a direct chat.
  Existing device/group/operator tools remain available for advanced workflows.
- Members with an approved proof-bound device can issue at most three single-use
  invitations per UTC day, at most three pending, expiring within 24 hours. The
  owner requested normal-member inviting; this deliberately expands the previous
  admin-only issuance policy, without public signup or administrative privileges.
  Administrators can disable member issuance or pause all invitations. Limits
  use a user-row lock and existing seven-day security audit records so redeeming
  an invite and cleanup cannot reset the daily quota. Password-only sessions and
  pending/revoked devices cannot issue member invitations.
- Friend cards contain only public device ID/fingerprint and a display name.
  Invite tokens and contact data travel in the URL fragment, not query strings or
  server lookup directories. Strict same-origin parsing, size/version validation,
  credential status and fingerprint matching are mandatory. No external link is
  automatically navigated. Fragments are read and removed from the address bar
  by the client. Browser navigation omits fragments from request URLs and
  referrer headers. Signup explicitly submits the invitation token in the
  HTTPS redemption request body; the server persists only its hash.
- A link alone is not independent identity verification. Users must explicitly
  compare the full security code through another trusted channel before pinning.
  There is no auto-pin, silent identity replacement, auto-approval or MLS bypass.
  Incoming chats provide the same verification action before encrypted content
  is accepted. Changed existing pins fail closed in the guided flow.
- Names associated with peer devices are stored only in the encrypted local vault.
  No public username discovery or new server-side contact list is introduced.
- Interrupted setup preserves its existing vault and pending enrollment. Returning
  users unlock instead of overwriting keys; another browser still needs explicit
  device approval. Pending chat creation is reused/recovered rather than silently
  claiming success after an uncertain commit.
- Local-only URLs are clearly labeled: sharing 127.0.0.1 cannot reach a friend on
  another machine. No public exposure, HTTP fallback or certificate bypass is added.

## Acceptance

Test member/admin setup, invitation capability/pause/quotas/concurrency/revocation,
strict fragment parsing, no pin or decrypt before explicit verification, peer
reply through incoming verification, native mobile/RTL/keyboard states, existing
vault/approval/reload, TLS/crypto gates and no foreign runtime requests. Independently
review the expanded invite policy and guided verification before real deployment.
