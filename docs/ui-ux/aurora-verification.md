# Aurora workspace verification · November 4, 2026

This change replaces the persistent navigation rail/mobile dock with a temporary
native drawer, keeps conversations in two desktop panes, and adds a blue/teal
animated chat background. Existing saved theme choices are retained. The same
styles ship in the regular Next.js frontend and the signed installed/independent
client builds.

## Browser checks

The opt-in `showcase.spec.ts` passed in Chrome and Firefox using separate trusted
TLS profiles, disposable synthetic accounts, real fingerprint pins and OpenMLS
messages through the signed QA client. It checks:

- Local composer feedback with remote typing disabled, and no outgoing typing frames.
- Explicit opt-in on both clients, actual authenticated remote hints, five-second
  expiry, content-free frame fields and outgoing opt-out.
- Pausing the background, saved motion preference and reduced-motion CSS.
- Native modal navigation, keyboard access, Escape and restored trigger focus.
- Full-width settings, 320–1024px layouts and a Persian RTL drawer.
- Delivered encrypted history, absence of synthetic plaintext/vault secrets from
  observed message request bodies, no foreign browser requests or page errors,
  and the real `ACTIVE_REVIEW_PENDING` operational status.

The existing `verified-client.spec.ts` also passed in both browsers. It exercises
signed-client MLS messaging, encrypted media and reload while hostile API content
remains data. The TypeScript check and pinned Node 26.13.0 standalone-client and
Next.js production builds passed.

The broader browser review also caught a manual-creation defect: choosing Group
was being overridden to Direct. Creation now passes the selected kind to the
existing closure-capable conversation API; group creation is asserted in the
real UI workflow.

## Regular web regressions

Seven focused workflows passed against the pinned Next.js production image:
conversation interactions/IME/drafts/media/RTL; responsive navigation/themes;
strict-CSP positive/negative checks; guided first chat; invalid contact/fingerprint
handling; real group membership/messaging/voice/offline queued delivery; and vault
lifecycle/offline access/confirmed remote logout. Navigation fixtures now open the
same menu drawer that people use, including the translated vault-lock action.
The group workflow explicitly checks that manual Group selection creates a group.

## Privacy and limits

Remote typing remains off by default. Enabling it permits sending/displaying the
existing ephemeral signal. The service and conversation participants can observe
live activity, but the hint carries no draft text and is not written to message
history. The existing server checks current device/session/membership authority
and rate limits. The client clears stale hints on conversation/vault/preference
changes and ignores callbacks from stopped connections.

The aurora uses local CSS gradients and transform/opacity animation. It adds no
runtime package, external request, canvas rendering loop or message-derived
visual state. It pauses in hidden documents; reduced motion and forced colors
remove animation/decorations. Media viewers retain their native dialog boundary;
no transition snapshots of private pixels are introduced.

The [current captures](../../.github/assets/README.md) demonstrate real application
behavior with synthetic accounts. Viewports are not physical-phone qualification.
These checks do not replace independent security review or relabel older assurance
reports as tests of this revision.

## Maintained installation

The regular frontend and both signed-client endpoints were upgraded in place.
Signed release3 uses the existing publisher root, TLS identities and browser origins.
The production bundle contains no QA helper. A trusted-TLS read-only smoke loaded
all three sign-in screens and the shipped Aurora styles without foreign requests
or page errors. No operator login, personal device enrollment or database migration
was needed. See [the installation record](../security/client-delivery/local-installation.md).
