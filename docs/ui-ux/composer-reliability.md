# Composer draft and keyboard reliability

Sending previously disabled the textarea through the shared busy flag. This
removed keyboard focus. A blur could also queue a draft write behind the send
that had consumed that text, making it appear again when opening the chat.

The composer now distinguishes unavailable messaging from pending operations.
Pending work keeps the textarea focused and temporarily read-only; unavailable
messaging and recording still disable it. Enter and the Send button share the
same submission path, which focuses immediately. Delivery completion never
requests focus, so switching chats cannot pull the cursor back.

An in-flight guard prevents repeated text submissions and suppresses blur saves
of the outgoing draft until the send completes. The encrypted send/outbox
transaction still determines when a text draft is consumed. Edits restore the
unrelated draft, and reactions and attachments preserve it. A count of pending
operations keeps controls busy until overlapping sends and navigation finish.

The real encrypted two-account conversation workflow checks:

- Enter sends followed by keyboard-only typing and another send.
- Switching between two chats after sending, with an unsent draft in the other.
- Switching during a deliberately held encrypted POST, preserving the other
  draft and leaving focus where navigation put it.
- Clicking Send and immediately typing again.
- Existing reload, editing, cancellation, reaction, IME, mobile newline, RTL,
  attachment, strict-CSP and encrypted-request checks.

These checks use synthetic accounts and trusted test TLS. They do not access
the operator's credentials or personal browser vault.

Chrome and Firefox passed the updated workflow on November 4, 2026. The earlier
frontend failed the added focus assertion in both browsers. TypeScript and the
regular and standalone production builds also passed.
