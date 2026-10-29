# Conversation experience — 2026-10-25–29

HAVEN's conversation is the primary working surface. This revision preserves the
existing Liquid Calm palette and security checks, with a denser conversation
list, quiet message bubbles and familiar chat interactions. It adds no runtime
service, package dependency, server schema or cryptographic primitive.

## Review and resulting changes

| Before | After | Why |
| --- | --- | --- |
| Paperclip immediately opened a generic file chooser | Photos & videos, Audio and File choices with appropriate native picker filters | Make choosing gallery media or music an explicit action |
| Pending attachment showed only its filename | Actual local raster image, video controls or audio player before sending; inert fallback for unsupported types | Let the sender check what they are sharing |
| Chat tips stayed below the composer | Guidance under Connection & help | Keep the message and attachment workspace focused |
| Persistent viewing-mode option beneath the chat composer | View once only inside a selected supported photo/video’s confirmation box; fresh selections default to ordinary mode | Make the choice where it applies and prevent unintended carry-over |
| Delivery enum strings beside every message | Compact check/clock/warning with accessible observed-state labels | Server acceptance must not imply delivery to, or reading by, a person |
| Reply context displayed an event ID | Author and current message preview, with a jump to locally available originals | People need to recognize the message they are answering |
| Edit always loaded the original text | Edit loads the latest authenticated edit; cancel restores the ordinary draft | Repeated editing should not silently restore outdated text |
| Reactions, receipts, files and edits consumed the text draft | Only sending a text message consumes its draft | Independent actions must not lose writing; drafts remain in the encrypted vault |
| Always-visible text actions on each bubble | Reply affordance and a native contextual popover for copy, reaction, edit and delete | Reduce noise while retaining keyboard and touch access |
| Manual textarea resizing and button-only send | Growing composer, desktop Enter/Shift+Enter, IME protection and mobile newline behavior | Match familiar messaging interactions without sending composition confirmations |
| File selection sent immediately | Filename/mode confirmation with Send attachment and Remove attachment | Give the sender a chance to catch a mistaken selection |
| Only file downloads | Explicit ordinary raster-photo/video previews with local decryption and native media controls | Inspect shared media in the conversation without downloading it to an external app |
| No scroll-position management | Follow the latest when already at the bottom; preserve reading position otherwise and offer a new-messages jump | Incoming activity should not pull the reader away from older messages |
| Conversation list showed status/count strings | Local latest-message previews, timestamps, unread counts and All chats/Unread filters | Make finding the right conversation a recognizable task |
| Global navigation occupied the phone thread | Full conversation view, back navigation and safe-area spacing | Keep room for messages and the composer on narrow screens |
| Browser approval presented raw JSON and vague instructions | Three steps, actual approved-browser labels, code explanation and missing-browser/recovery guidance | Explain the next possible action without bypassing signed approval |

## Interaction and privacy contract

- Message rendering uses only events already authenticated by Messenger. Sender-bound
  edits/deletes are resolved for previews and search; markup is rendered as text.
- The clock means pending/local state. One check means server acceptance or local
  synchronization, according to its accessible label. A double check/read label
  requires an authenticated opt-in receipt. It does not establish that every group
  participant read the message.
- A draft is distinct from an edit. Reactions, deletes, titles, receipts and file
  sends preserve the unrelated encrypted draft. Changing conversation clears the
  reply/edit context; it does not attach an old reply to a different conversation.
- On computers with a fine pointer, Enter sends and Shift+Enter adds a newline.
  IME composition confirmations never send. On touch keyboards, Return remains a
  newline; the send button sends. A small desktop emoji palette inserts at the
  selection; phones use the keyboard's emoji support.
- File messages retain the selected reply reference without consuming an unrelated
  text draft. Files are confirmed before encryption/upload. The existing 25 MiB cap remains.
  Voice recording stops to send, has an explicit discard action and is discarded
  when leaving the conversation. Voice notes remain ordinary audio even if the
  selected photo/video is being prepared for view-once sending.
- The paperclip menu uses three synchronous user-gesture native file pickers:
  gallery/photo/video, audio, or any file. Accept filters are browsing hints, not
  security checks. Client category/size checks and existing encrypted transport
  authorization remain in place. OS gallery behavior can differ.
- Sender previews use only the unsent local File. Raster image/video previews use
  the existing safe MIME allowlist; audio uses native audio controls. Documents,
  HTML and SVG are not embedded. Unsupported/undecodable content has explicit
  fallback copy. No file upload occurs until Send attachment. Replacing/removing,
  sending, locking, pagehide/unmounting releases URLs and media sources; no
  secure decoded-memory erasure guarantee is added. These previews do not consume
  any recipient's view-once authorization. Send remains available in a fixed
  preview action row while preview content scrolls on smaller viewports.
- Ordinary media is decrypted only after an explicit open action. The preview
  allowlist excludes HTML/SVG/documents. Closing, page hiding, vault locking or
  unmounting aborts pending work, clears media sources and revokes object URLs.
  These actions do not guarantee secure browser-memory erasure. Ordinary downloads
  and clipboard copies can remain outside HAVEN's control.
- View-once mode is chosen inside the pending photo/video confirmation box. It
  is not a persistent chat setting and is unavailable for documents/audio. A new
  or replacement file starts in ordinary mode, and send/remove/navigation/lock
  discards its local selection. Mode travels explicitly with the selected file.
- View-once media continues to use its separate consumed-before-load authorization
  and viewer. The new ordinary preview explicitly refuses view-once files. The
  capture and server-opening-metadata disclosures remain visible before sending.
- No browser is automatically approved. Pending-browser background synchronization
  is paused; after an actual signed approval the parent device state is refreshed.
  Passwords/admin roles cannot substitute for an approved signing key or previously
  configured recovery authority. No existing account/device/vault was reset for this
  redesign.
- Message action popovers use the browser top layer and dismiss on Escape/outside
  interaction. Pointer feedback is brief; keyboard-triggered menus and reduced
  motion omit movement. No transition snapshots of private media are introduced.

## Validation and limits

See the latest section of TEST_REPORT.md and `docs/evidence/chat-*`. The workflow
uses disposable invited QA accounts with actual browser MLS, Django/PostgreSQL,
trusted test-root HTTPS and ciphertext transfer. Screenshot conversations belong
only to those QA accounts; the product does not insert sample people or messages
into existing accounts.

Selected foreground/background pairs meet 4.5:1 normal-text contrast. Responsive
checks include 320/390/900/1280px, a short 450px viewport, light/dark themes,
Persian/mixed-direction text, keyboard focus, native popovers and reduced motion.
These are engineering checks, not a comprehensive accessibility certification.
A short viewport is not a physical iOS/Android software-keyboard test.

This is a substantial conversation UX update, not full Telegram feature parity.
There are no calls, push service, sticker ecosystem, drag/drop or multi-file batch
composer in this revision. Long history still uses the existing local event cap
and renders the selected conversation rather than a virtualized history window.
Safari/iOS device behavior, codec coverage, assistive-technology testing and
large-history performance qualification still require further testing. Existing
release/TLS/independent-security gates remain BLOCKED; prior signed archives do not
certify this revision.

The existing disposable test root was preserved when resuming on 2026-10-29. Its
renewed loopback test leaf expires **2026-10-30 09:22:11 UTC**; the test root expires
2026-10-30 18:33:30 UTC. These are temporary evaluation certificates, not a public
deployment. Certificate validation remained enabled, and trust stores outside the
private test profiles were not changed. Production certificate issuance/renewal
and independently verified trust remain external deployment requirements.
