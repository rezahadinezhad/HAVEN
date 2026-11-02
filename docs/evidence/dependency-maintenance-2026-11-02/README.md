# Dependency qualification evidence — 2026-11-02

See [decisions and limitations](../../security/dependency-maintenance-2026-11-02.md). These are synthetic local qualification results, with exact application source/artifact hashes in `qualification-source.sha256` and `qualification-source.json`. Native and backend tests use the updated locked graph. `browser-summary.json` preserves initial fixture failures and actual focused reruns, without replacing failed history. Two conditional Chromium and six conditional Firefox cases are skipped.

No private credentials, native MLS snapshots, test signing keys, full browser HTML/error attachments or raw scanner match values are published. Full raw browser/scanner diagnostics stay in protected `.local` storage. Image scan counts use the disclosed stale database after two failed update routes and are not a fresh OS security verdict. The ordinary release gate remains BLOCKED. Previous 20/s and two-hour measurements belong to earlier commits and were not repeated here.

Published text logs normalize trailing whitespace only; original raw logs remain in protected local diagnostics. The initial modified-build-label scanner probe used a benign phrase skipped by the default scanner; the final probe uses a generated high-entropy modification and exercises the exact-value boundary.
