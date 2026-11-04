# Composer draft and keyboard reliability

The first fix kept focus by making the textarea read-only during pending work.
Its keyboard test waited for delivery before typing again, so it missed typing
while delivery was still pending. That interval could silently ignore keystrokes.

The textarea now stays editable whenever messaging is available and recording is
inactive. Enter and the Send button share the same submission path and focus the
field synchronously. Delivery completion never requests focus. The locally accepted clear is committed
synchronously, preventing a browser key event from reading and restoring the old
DOM value before React applies the clear.

`Messenger.send` exposes a local-acceptance callback after the encrypted event
and outbox have been persisted. The composer consumes the submitted text then,
without waiting for the network. Keystrokes entered during encryption remain in
the next draft. Delivery completion updates events without clearing that draft.
The existing send promise still awaits the delivery attempt for other callers;
network failures still leave the durable encrypted outbox available for retry.
A failure before local acceptance leaves the text in the composer.

Text sends do not block the interface through the shared busy flag. Per-chat
preparation guards prevent duplicate submissions before local acceptance, and
Messenger's existing serialization and security checks still apply. Other
controls retain their operation-specific disabled states.

An in-memory draft cache binds writing to its conversation while persistence is
queued. Selecting a chat switches its composer before fetching network detail;
synchronization cannot reset writing entered during that fetch. Superseded
conversation-detail responses are ignored. The cache clears on vault lock and
does not restore retired or archived drafts. Blur saves use the current cached
draft, rather than an outgoing snapshot.

The real encrypted two-account workflow checks:

- Keyboard-only typing immediately after Enter, before waiting for delivery.
- Typing while an encrypted POST is deliberately held open.
- Switching between two chats during that held request, preserving both drafts.
- Delivery completion leaving the next draft intact and focus where the user put it.
- Clicking Send and typing again, plus existing reload, edits, cancellation,
  reactions, IME, mobile newline, RTL, attachment and strict-CSP checks.

Tests use synthetic accounts and trusted test TLS. They do not access the
operator's credentials or personal browser vault.

Chrome and Firefox passed the updated workflow on November 5, 2026 (Asia/Tehran).
The previous release failed the held-delivery check. Firefox additionally exposed
the asynchronous DOM-clear race; the final synchronous-clear implementation
passed in both browsers. TypeScript and both pinned Node production builds passed.
