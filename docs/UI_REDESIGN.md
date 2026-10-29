# HAVEN interface redesign

The Liquid Calm interface replaces the previous olive layout with brighter conversation surfaces, blue actions, restrained frosted navigation, a compact header and a five-action mobile dock with a native More popover. Real conversation content, device trust and release qualification remain authoritative; no fake activity is inserted.

## Design and behavior

Apple iOS 27 / Liquid Glass informed the navigation materials, rounded controls and short, interruptible transitions. This is browser CSS, not an Apple component library. See [Apple materials guidance](https://developer.apple.com/design/human-interface-guidelines/materials) and [iOS 27 interface guidance](https://support.apple.com/en-ie/guide/iphone/iphfed2c4091/27/ios/27).

The interface includes light/dark themes, a locally hosted Persian variable font and RTL layouts, clearer device-setup actions, a phone conversation back button, outgoing message bubbles, recognizable icon controls and restrained press/sheet/selection transitions. Reduced motion/transparency and forced-color fallbacks are implemented. Glass is limited to controls/navigation so message content stays readable. Platform English fonts, Persian font and icon modules require no external CDN.

All 14 Neshino project-local frontend/testing skills were copied from the sibling project's `.agents/skills` into this project's `.agents/skills`, preserving references and license files. `skills-lock.json` retains their source metadata and SKILL.md hashes. No Neshino application configuration was imported. They can be discovered in subsequent project turns; relevant guidance was read directly for this redesign. `DESIGN.md` records the design decisions and applied skills.

## Verification and preview

The local integration preview is at `https://127.0.0.1:8445`; refresh the existing trusted browser tab to load the redesign. It uses isolated integration settings, not a production release approval. Port 8443 retains the normal closed crypto gate. The separate container staging origin is port 8444.

`TEST_REPORT.md` names the authoritative logs: 13 Chrome tests passed; 6 Firefox subset tests passed. Linux WebKit passed genuine MLS and actual mobile login/navigation/theme/RTL checks with three isolated native-select CSP engine warnings. The exact warning is reproduced without HAVEN/React code; other CSP violations fail. See `docs/adr/0004-browser-csp-compatibility.md` for diagnostics and the guarded Next announcer CSS patch. Physical iOS Safari/Android, full assistive-technology testing, independent cryptographic/security review and production infrastructure remain unqualified.

Screenshots under `docs/evidence/redesign-*.png` show actual QA login, empty authenticated desktop, mobile, Persian RTL and dark settings. No screenshot implies security approval. Responsive tests cover 320, 390, 430, 760, 768, 900, 1024 and 1440 CSS pixels; selected contrast-token checks are narrower than a full WCAG audit.

## Reproduce

With the isolated development/integration services and trusted browser test profiles prepared as described in README.md:

```sh
npm run build --prefix apps/web
# Restart the owned standalone web process using scripts/serve-web.sh.
npm run typecheck --prefix apps/web
(cd apps/web && node scripts/test-offline-shell.mjs)
npm test --prefix apps/web
HAVEN_BROWSER=firefox npm test --prefix apps/web -- crypto.spec.ts design.spec.ts integration.spec.ts
bash scripts/test-webkit-ui.sh
```

The isolated WebKit container trusts only the public TEST root. QA credentials stay in a protected, ignored file; scripts do not print their password. Do not disable certificate verification or weaken CSP for screenshots.

## Release preparation limits

The refreshed npm cache supports the recorded `npm ci --offline` install of the locked frontend dependencies. The service worker carries its build revision, rejects a mismatched manifest and selects the same cached shell after worker restart; its lifecycle harness complements the real browser offline-message test. The rebuilt web image and local staging checks have separate evidence. Existing signed 0.2.0 QA/offline archives predate this redesign and must be regenerated and reviewed against the updated source manifest before distribution. Existing container OS findings are not cleared by a UI rebuild. Normal TLS, key approval, crypto and release security gates remain intact; release status stays BLOCKED.
