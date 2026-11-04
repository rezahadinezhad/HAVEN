# HAVEN interface — Aurora

HAVEN is a private messenger for a small trusted community. Conversations lead the interface. Device approval, identity checks, offline behavior and explicit security warnings remain authoritative.

## Structure

Desktop uses two panes: a conversation list and the selected thread. A compact menu opens a temporary native modal drawer for settings, trust, devices, recovery and operator tools. Auxiliary pages use the available width and provide a clear return to conversations. On phones, the list and thread occupy separate screens with a visible back action. There is no permanent settings rail or floating navigation dock competing with the conversation.

Telegram informs the familiar navigation pattern; the owner's Gemini references inform the atmospheric blue/teal chat canvas and rounded composer. These are visual references, not dependencies or brand assets. Existing theme preferences remain intact. Light mode uses a pale aurora; dark mode blends blue and teal into a near-black thread. Opaque bubbles preserve text contrast over the moving background.

## Visual language

Keep HAVEN's blue action color, quiet borders, platform English typography and locally bundled OFL Vazirmatn for Persian. Use logical spacing for RTL, a 4/8px rhythm, round message corners and compact circular chat actions. Read states describe observed facts; server acceptance never implies a person read a message. Empty states explain the next real action. Never fabricate people, messages or activity in the product.

## Motion and activity

The aurora uses two CSS radial gradients animated through transforms and opacity. No canvas loop, external assets, third-party requests or message content drives it. It pauses when the document is hidden and can be paused in Settings. Reduced motion removes ambient, drawer and typing-dot animation; forced colors removes the aurora. Controls respond in 160–220ms; the backdrop moves slowly over 22–28 seconds.

Local input briefly strengthens the composer border and aurora, even with remote activity disabled. A peer's typing appears as three staggered dots and an accessible status label, in a reserved space that does not move the composer. Signals expire after five seconds. Typing indicators are off by default; enabling them permits sending and displaying content-free activity through the existing authenticated WebSocket channel. This reveals activity to the service and conversation participants. It does not carry text, enter conversation history or create a read receipt.

Native dialog navigation supports keyboard focus containment, Escape, outside dismissal and focus restoration. Full-width settings, 320px layouts, English/Persian and reduced motion are checked in the browser. Native dialogs/popovers remain the containment boundary for private media; no snapshot-based transition captures message or view-once pixels.

Frontend guidance lives in `.agents/skills`, with provenance in `skills-lock.json`. The current pass applies frontend-design, impeccable, motion-design and vercel-react-best-practices to the existing React/Next.js stack. Further behavior details remain in [the conversation experience guide](docs/ui-ux/conversation-experience.md).

View-once media uses a per-attachment control inside the selected photo/video confirmation box, followed by a numbered placeholder without a thumbnail. The ordinary chat footer has no viewing-mode control. New or replacement selections default to ordinary mode; removal and sending discard the selection and its mode. A native full-screen modal keeps photo/video pixels out of conversation history, removes content immediately on dismissal, and avoids snapshot-based transitions of private pixels. Capture/interruption and server-opening metadata limits appear before opening. The sender sees the actual queue/send state; each recipient sees their own consumed state.

Conversation polish (2026-10-25–29): readable white/pale-blue bubbles on a glacier
thread canvas, grouped senders and local date separators, quiet contextual actions,
a growing composer and confirmation before attachments. Read labels describe
observed facts; server acceptance never becomes an implied human read. The phone
thread occupies the full working area with a clear back action. Native popovers
escape scroll clipping; ordinary media opens explicitly in a native dialog and
never shares the view-once authorization path. Chat guidance lives under Connection & help; the three-step browser-approval
guide explains enrollment at the point of need. Detailed
review and limits: docs/ui-ux/conversation-experience.md.

The paperclip opens a compact, keyboard-accessible native popover with Photos &
videos, Audio and File choices. Each uses the corresponding native picker filter.
The confirmation panel has a file header, a scrollable local photo/video/audio
preview and viewing-mode area, and a fixed Send action. Raster media stays contained
without cropping; audio/video never autoplay. There is no Chat tips widget below
the composer. Unsupported documents/SVG/HTML get an inert fallback. Sender previews
use temporary local object URLs and are separate from the recipient view-once
viewer; preview URLs are released on replacement, cancellation, send and lock.
