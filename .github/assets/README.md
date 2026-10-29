# HAVEN presentation assets

- `haven-hero.svg`: original vector artwork for this project; editable source, no external images or fonts.
- `haven-social.png`: 1200×630 raster export of the vector, suitable for a repository social preview. Recreate with `node scripts/render-brand.mjs` after installing the documented web tooling and Chrome.
- `conversation-*.png`: actual HAVEN interface captures using disposable synthetic Maya/Nora accounts and a real encrypted conversation in the isolated loopback evaluation environment. No personal profile, passphrase or real conversation is shown. The production-review notice remains visible.

Capture the application again with `HAVEN_CAPTURE_SHOWCASE=1 npx playwright test tests/showcase.spec.ts --reporter=line` from `apps/web`, after starting the prepared local evaluation services. This workflow checks the rendered conversation, light/dark/mobile views, the review notice, and absence of the synthetic plaintext in observed message request bodies. It is documentation evidence, not independent security verification.

Original artwork and project-authored captures are covered by the root MIT license. Application fonts/icons retain their third-party notices.
