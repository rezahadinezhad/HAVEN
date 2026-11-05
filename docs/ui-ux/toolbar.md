# Application toolbar — release10 snapshot

This historical design was superseded by [the unified sidebar](sidebar.md). The authenticated application no longer has a global toolbar.

The header uses one inset rounded surface. Navigation and HAVEN’s identity form
its leading group; connection status and appearance/language controls form its
trailing group. The community label sits below the name, removing the previous
three disconnected floating islands. Spacing and color reuse the existing
Aurora design tokens.

![Dark toolbar](../evidence/toolbar-dark.png)

![Light toolbar](../evidence/toolbar-light.png)

A short icon turn confirms theme changes. The brand gently tilts on hover or
keyboard focus, and a single fading ring confirms an available connection.
These effects stop with reduced motion; the status never pulses continuously.
The existing native navigation dialog retains Escape dismissal, focus
containment and focus restoration. No animation captures conversation pixels.

On phones, secondary branding and visual status text collapse. The status
remains available to assistive technology and through the tooltip; every
header button retains a 44px target. Persian reverses the layout. The header
continues to hide in an active phone chat, preserving the conversation area.

Verification used an isolated synthetic account: Chromium and Firefox design
regressions, plus 28 layout combinations across seven widths (320–1480px),
both themes and both languages. Checks covered control overlap, overflow,
touch targets, menu dismissal/focus restoration, reduced motion and offline
status. Both production builds and TypeScript passed. Trusted-TLS live checks
confirmed all four maintained entry points and their API bridges; signed
clients run release10. Existing accounts, vaults, MLS identities, browser
origins, publisher trust and TLS identities were retained.
