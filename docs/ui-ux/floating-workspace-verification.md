# Floating workspace verification · November 4, 2026

The supplied Telegram screenshots guide spacing and surface separation. No
reference account names, phone numbers, messages or branding enter HAVEN assets.
The implementation keeps the existing Phosphor icon family, local fonts, aurora
and privacy controls; it adds no dependency or server behavior.

## Scope

- A continuous authenticated aurora canvas behind an inset conversation list,
  rounded thread-width header and separate pill composer.
- A compact rounded native navigation panel with a light backdrop, inset RTL
  positioning, keyboard containment, Escape/outside dismissal and restored focus.
- Consistent settings groups, category glyphs, circular 44px actions, a compose
  pencil and send paper plane. Existing labels remain accessible.
- Short transform/opacity surface and menu entrances, control feedback and row
  selection transitions. Reduced motion removes animation; forced colors uses
  system surfaces. Private media dialogs and cryptographic flows are unchanged.

## Validation

The signed QA workflow uses disposable synthetic accounts and actual OpenMLS
messages. It checks detached surface geometry, rounded/divider-free chat headers,
consistent settings widths, compact menu bounds, keyboard/outside dismissal,
320–1024px layouts, Persian RTL, motion controls, real optional typing and expiry,
absence of plaintext/vault secrets from observed message requests, and no foreign
browser requests or page errors. Chrome and Firefox are exercised separately.

The regular pinned Next.js image is checked with the responsive design and CSP
workflows. The existing conversation workflow covers keyboard/IME, drafts,
replies, media previews, mobile/RTL and immediate preview cleanup on vault lock.
TypeScript and both pinned production builds passed. The regular-web design/CSP checks and conversation workflow passed; the signed workspace workflow passed separately in Chrome and Firefox. The final reduced-motion press behavior was also checked in Chrome.

The refreshed README captures show real delivered synthetic conversations.
Viewports do not qualify physical devices, and these checks do not replace
independent security review. Earlier assurance reports retain their dated scope.
