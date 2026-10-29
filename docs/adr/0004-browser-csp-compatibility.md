# Browser CSP compatibility during the UI redesign

Status: implemented; Linux WebKit has a reproduced native-select engine warning.

Real WebKit login/navigation exposed a blocked Function probe in Zod's optional JIT and inline-style diagnostics. Zod now uses one shared jitless configuration, imported before all local event/WebSocket schemas. Strict schema validation remains in place. Chrome and Firefox regressions passed after this change.

An initial narrow style hash experiment did not resolve WebKit's attribute checks and was removed. The shipped CSP is unchanged: same-origin resources/per-response nonces, no general inline styles/scripts or production unsafe-eval. TLS verification is unchanged.

## Accessibility announcer

As a separate precaution against dependency inline styling, an explicit build-time patch in `apps/web/scripts/patch-next-announcer.mjs` replaces Next 16.4.3's two constant cssText assignments with a class and a shadow part. The same static rules live in the self-hosted stylesheet. ARIA/live-region/portal behavior is retained. Both ESM/CJS files are checked; a changed Next version or unexpected source fails the build and requires review. The patch runs explicitly in dev/build commands, including container and offline builds; npm lifecycle scripts remain disabled during installation. Review this local modification on Next upgrades.

Chrome/Firefox tests verify the actual announcer remains assertive and visually hidden, with no style attributes, and that arbitrary inline scripts/styles are still blocked. The announcer patch did **not** eliminate the native-select warning below; attributing that warning to Next would be incorrect.

## Reproduced Linux WebKit limitation

`infrastructure/browser-tests/webkit-select-repro.mjs` serves a minimal isolated HTML fixture with two native selects, no HAVEN/React code, and enforced nonce-based CSP. Both `appearance:auto` and `appearance:none` reproduce two `style-src-attr` violations whose exact sample is `text-overflow:inherit`. One select is parsed; one is created using DOM APIs. No page style attribute is written. This isolates the observed warning to native select handling in the tested engine, rather than proving a general Safari bug or a particular upstream fix.

The actual UI test records three identical warnings for its three native selects. It accepts only this exact directive/blocked URI/sample and zero or three occurrences; every other policy violation fails. It prints the known-warning count explicitly. For diagnosis only, interception of the initial public GET adds `report-sample` to the existing style-src directive, retaining the actual response nonce and all enforcement. Node and browser both verify the private TEST certificate; no TLS bypass is used. The deployed policy is unchanged and has no report destination.

Upstream context: [WebKit issue 322676](https://bugs.webkit.org/show_bug.cgi?id=322676) discusses native select field-content's `text-overflow:inherit` styling. This is context, not evidence that its change resolves our pinned Linux engine's CSP behavior.

Playwright's WebKit screenshot helper also injects a stylesheet for animation synchronization and trips enforced CSP. The final WebKit functional test therefore takes no screenshot. Visual screenshots come from Chrome/Firefox. Linux WebKit qualification is not physical iOS Safari certification.
