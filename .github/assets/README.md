# HAVEN presentation assets

The presentation uses editable project artwork and actual application captures. No generated interface or private conversation is presented as product evidence.

## Artwork

- `haven-hero.svg`: compact 1200×320 README identity artwork. Its device/service labels describe responsibilities, not an audit or complete threat model.
- `haven-social.svg` and `haven-social.png`: 1200×630 social-preview artwork with current wording and the independent-review qualification. The PNG is ready for GitHub's custom social-preview upload; committing it does not itself change that repository setting.
- `architecture.svg`: current responsibility map. The client handles encryption/local private state; the service coordinates durable ciphertext/public/auth records, hints and maintenance. The journal is separate from SQL snapshots. Read [the architecture guide](../../docs/architecture/README.md) for trust and flow details.

Rebuild the deterministic vectors and raster export with the prepared web tooling and Chrome:

```bash
node scripts/build-presentation-assets.mjs
node scripts/render-brand.mjs
```

The scripts use no external images/fonts. Essential introduction and architecture explanations also exist as real Markdown. Diagram arrows show a simplified responsibility/flow map, not container/network isolation.

## Real application captures

`conversation-desktop.png`, `conversation-dark.png` and `conversation-mobile.png` were refreshed November 4, 2026 using disposable synthetic Maya/Nora accounts, actual signed device enrollment/fingerprint pins and a real OpenMLS conversation through the isolated verified QA client. The application UI unlocks the persisted vault and displays the delivered conversation. Its real operational state is checked; no warning or UI state is painted over.

The current Aurora workspace uses a two-pane desktop layout, a compact rounded navigation panel and a blue/teal background. Dark and mobile captures show the same delivered conversation in the dark theme. The refreshed captures show the flowing blue/mint/rose aurora and detached rounded surfaces. The motion capture opt-in also records a disposable synthetic conversation for visual inspection; raw recordings stay outside the repository. The workflow also verifies optional remote typing, motion controls, inset menus, consistent settings widths and RTL navigation; see [Aurora verification](../../docs/ui-ux/aurora-verification.md).

The capture checks that the synthetic plaintext and vault secrets are absent from the observed message request bodies, that browser traffic stays on the client origin, that the page has no script errors, and that the backend reports `ACTIVE_REVIEW_PENDING`. Credentials, private keys and recovery material are never shown. The mobile image demonstrates a viewport layout; it is not physical-phone qualification or independent security review.

After preparing an isolated test backend and signed QA client as described in [client verification](../../docs/security/client-delivery/verification.md), run from `apps/web`:

```bash
HAVEN_CAPTURE_SHOWCASE=1 HAVEN_VERIFIED_PROFILE=/private/qa-client-profile \
  npx playwright test tests/showcase.spec.ts --reporter=line
```

The QA release must contain the explicit integration helper and use the corresponding test API; production packaging refuses that helper. Never use a real publisher key, personal browser profile or live user credentials for this capture. [Presentation verification](../../docs/project-presentation/verification.md) records the refreshed check.

Original artwork and project-authored captures use the root MIT license. Fonts, icons and other dependencies retain their third-party notices.
