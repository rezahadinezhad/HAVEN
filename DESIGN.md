# HAVEN interface — Liquid Calm

Private messaging for a small trusted community. People should find their next conversation or safely unlock this device without reading implementation details. Existing protocol, key approvals, explicit security warnings, and offline behavior remain authoritative.

A person uses HAVEN at a desk or on a phone under changing ambient light, possibly under stress. Default to a bright, readable surface; retain an equally deliberate dark theme and existing theme preferences. Apple iOS 27 / Liquid Glass is an aesthetic reference, implemented with browser CSS rather than an official Apple component library.

Palette: glacier `#f3f6fb`, porcelain `#ffffff`, ink `#182332`, blue `#1769f4`, muted ink `#596879`, signal amber `#8a5309`. Blue identifies actions, amber identifies unreviewed security, and green is limited to network reachability. Glass belongs to navigation and controls; message content and forms stay legible.

Use platform system typography for English, locally bundled OFL Vazirmatn for Persian. A 4/8px spacing rhythm, compact header, restrained frosted sidebar, split conversation surface, and a floating mobile navigation dock replace the previous oversized beige interface. Empty states explain the next real action. Never insert fake people/messages/activity into actual user views.

Motion: press 120ms, control 180ms, sheet 260ms; `cubic-bezier(.22,1,.36,1)` and iOS-like drawer `.32,.72,0,1`. Transform/opacity, interruptible transitions, hover only on fine pointers. No endless ornament, no interaction delays; reduced motion, reduced transparency, forced colors, touch targets, RTL and keyboard focus are required.

Frontend guidance copied from Neshino into `.agents/skills`, with provenance in `skills-lock.json`. Applied for this pass: frontend-design, emil-design-eng, motion-design, next-best-practices and vercel-react-best-practices. Other installed skills are available when relevant; installing them does not require replacing the existing application stack or invoking unrelated workflows.

References: https://developer.apple.com/design/human-interface-guidelines/materials and https://support.apple.com/en-ie/guide/iphone/iphfed2c4091/27/ios/27. All assets are served locally; no runtime request to these references is introduced.

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
