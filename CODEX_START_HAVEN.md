# Codex — Start building HAVEN

Read `EMERGENCY_MESSENGER_CODEX_MASTER_SPEC.md` **in full** before touching source code. It is the product requirements document, security architecture, and implementation contract.

Your task is to **build the entire working private, domainless, browser-based encrypted messenger**, not just propose one.

Proceed autonomously in measurable stages, following the document's PoF and security gates. Use Django/DRF/Channels, Next.js, PostgreSQL, Redis, Docker, and a verified browser-compatible implementation of standardized MLS cryptography. Host all runtime resources locally. Do not invent encryption protocols, bypass TLS, silently downgrade to plaintext, or pretend that any untested/audit-dependent condition has passed.

First inspect the repository, then create the plans/status files required in Section A. Implement vertical slices, run real tests and fix failures. Continue until all work that can be completed in the current environment is done. For unavailable VPS credentials, iPhone/Android hardware, Iranian carrier tests, or external audits, provide exact operator runbooks and explicitly mark that gate blocked or unreviewed. Provide a truthful `SECURITY_STATUS.md`, `TEST_REPORT.md` and `IMPLEMENTATION_STATUS.md` at the end.

Do not request permission for ordinary engineering decisions; document them and proceed. Do not overwrite unrelated existing code. Your final response must state what is actually implemented and tested versus what remains unverified.
