# Flowing aurora verification · November 4, 2026

The earlier effect had small movements over 22–28 seconds and a nearly opaque
lower fade, which made it look static. The current effect uses three overlapping
blue, mint/teal and rose/coral gradient layers. Their paths travel vertically and
horizontally across the canvas over 14, 18 and 22 seconds. A light edge vignette
keeps the lower chat area visible.

## Reference and implementation

The owner supplied the desired behavior and Gemini screenshots. Google's
[official Neural Expressive reference](https://blog.google/innovation-and-ai/products/gemini-app/next-evolution-gemini-app/)
describes fluid animation and vibrant colors. The live Gemini endpoint did not
expose a usable signed-in reference in this environment. This is an independent
CSS implementation of the requested visual direction; no Google code, media,
branding, external request or new dependency enters HAVEN.

Layers use static gradients and transform animation, with capped dimensions.
There is no JavaScript frame loop, canvas/WebGL renderer or message-driven color
calculation. Opaque messages and controls preserve readable content. Pause,
hidden-document handling, reduced motion and forced colors remain supported.

## Browser evidence

The signed synthetic-account workflow checks actual wall-clock transform
progression, and verifies that pausing holds the transforms still. Existing
motion, typing/expiry, menu, encrypted request, responsiveness and RTL checks
remain in the same workflow. The regular Next.js image runs the design and
strict-CSP workflows. Production and QA signatures/keys remain separate.

`HAVEN_CAPTURE_AURORA=1` additionally records the real QA browser, then captures
four frames three seconds apart while showing only a delivered synthetic chat.
The full recording remains in the ignored local QA directory. Only its final
chat segment is used for the shareable motion demonstration. This opt-in does
not record the owner's browser, account or vault.

An already-loaded owner tab was confirmed to retain the older bundle (the
22/28-second effect inside the old chat panel), while the maintained endpoints
served the newer release. Existing tabs must reload after a release to run its
new code. Reloading can require local vault unlock; it does not delete history.

## Local test infrastructure

The development API leaf expired November 4 during this pass. It was renewed for
three days under the same existing trusted TEST root and key; the root, origins
and certificate validation were preserved. The initial date-validation failure
was a test-environment failure, not an animation result. An initial independent
capture also encountered a transient browser network-change error while Docker
network setup was running; the rerun starts after that setup has settled.

These tests do not replace independent security review or physical-phone
qualification. Earlier assurance reports keep their original scope and dates.

## Result

Chrome and Firefox passed the signed workspace workflow, including actual
animation progression and pause checks. The regular Next.js responsive/CSP
workflows passed after the test-leaf renewal. TypeScript and both pinned Node
production builds passed. Frame inspection confirmed visible movement in the top,
middle and bottom of the chat; the trimmed WebM shows only the final synthetic
conversation. A first recording export attempted to save after closing its
persistent browser; it was corrected to save while the browser remained alive,
then rerun successfully. No private browser recording is involved.

## Maintained installation

Signed release5 and the regular frontend are active at the same three endpoints.
Publisher/TLS roots, browser origins and user state are preserved. A trusted-TLS
read-only smoke passed with no QA helper, foreign requests or page errors.
The owner's existing tab was refreshed and its three new layers were observed
running. Its already-locked vault can be unlocked by the owner; no personal
passphrase was accessed. See [the installation record](../security/client-delivery/local-installation.md).
