# Contributing to HAVEN

HAVEN is an experimental private messenger and security engineering project. Contributions should improve a concrete user behavior or a testable security property. Independent review is still required before production qualification.

## Before making a change

Read README.md, SECURITY_STATUS.md and the relevant architecture decision in docs/adr. For client work, preserve the established responsive English/Persian interface, accessibility, reduced motion, and honest delivery/trust states. Read apps/web/AGENTS.md and the installed Next.js documentation before changing framework code.

For security changes, explain the threat, current failure, expected behavior, and a meaningful regression test. Do not invent cryptographic primitives, silently reset identities/ratchets, weaken certificate verification, or bypass the source-level release gate. Provider changes need source provenance, native/WASM builds, interoperability checks, and the relevant protocol tests.

## Working locally

Follow the local evaluation instructions in README.md. Use synthetic accounts and media. Each running web server uses an immutable build snapshot: rebuild and restart before testing changed assets. Run API and browser suites sequentially when they share Redis test state; API fixtures clear that cache.

Run checks appropriate to the change, including TypeScript, Python lint/format, applicable tests and schema drift checks. Public CI checks source hygiene, dependency advisories, provider source integrity, native tests and the browser compilation target. Physical-device, deployment and independent security-review results are separate evidence.

Before submitting, run the repository safety/secret scanner, update the relevant documentation, and regenerate `SOURCE_MANIFEST.sha256` with `python3 scripts/source-manifest.py`. Keep secrets, runtime data and `.local` outside Git. Never commit process-environment dumps, personal browser profiles, private keys or real conversation captures. Preserve third-party licenses and notices.

## Pull requests

Describe the concrete problem, resulting behavior, tests and remaining limits. Keep changes focused and include screenshots for interface changes using synthetic data. A passing dependency scan is not an independent security assessment. Do not claim a test, audit or deployment that did not occur.

Use private vulnerability reporting for security disclosures as described in SECURITY.md. Public issues are for non-sensitive bugs and feature discussions.
