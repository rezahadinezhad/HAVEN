# HAVEN GitHub presentation — review and rewrite plan

Prepared November 4, 2026. Implementation reviewed at `eba5a604328b90da27fdd55316c090c117d5161c`.

This records the editorial and visual brief used for the rewrite. The current [project overview](../../README.md), [architecture](../architecture/README.md), [security guide](../security/design-guide.md), and [verification record](verification.md) are the implementation; the section titles/sample copy below remain planning history. The review includes the current README, product/design notes, implementation and security status, relevant application code, deployment configuration, architecture decisions, verification records, existing artwork/screenshots, and live repository metadata.

## The story to tell

HAVEN is a messenger for small, invite-only communities. Its engineering treats privacy as the life of a conversation: joining, verifying a device, protecting local keys, delivering messages through failures, recovering readable history, retiring shared server records by agreement, and checking the software that handles those keys.

The presentation should make that connected design understandable. Show the work through concrete decisions and their consequences. Let readers see why a feature exists, how it works, what was checked, and where its guarantee ends.

Retain the established line **Private conversations. Explicit trust.** It already expresses the product's character. Replace the vague supporting phrase “exploring modern security engineering” with a direct description of the functioning messenger.

## What the review found

| Observation | Effect on a reader | Rewrite decision |
|---|---|---|
| The opening moves quickly into successive hardening initiatives and phase references | A newcomer meets project history before understanding the product | Introduce the messenger, community, interface and principal choices first; move initiative history into linked explanations |
| The capability table omits dedicated entries for mutual retirement and signed installed delivery | Some of the most substantial work looks like an appendix | Give each its own concise explanation and a route to its technical record |
| The architecture diagram shows the original browser/API/database shape | It does not explain the current delivery choices or independent retirement journal | Replace it with a current overview and a separate client-delivery comparison |
| The README repeats an older 70-test count, alongside unrelated historical totals | Readers cannot identify the revision or scope behind the apparent evidence | Organize evidence by behavior and recorded revision; link current CI and detailed reports; never sum overlapping suites |
| The hero, social preview and old screenshots still contain experimental-era wording | The visual introduction conflicts with current operational status | Regenerate presentation assets and recapture actual current UI using synthetic accounts; retain the independent-review qualification |
| The GitHub About description repeats the old “Experimental” description | Search/sidebar copy presents an earlier project state | Prepare matching, concise About copy; retain accurate assurance limits |
| Setup, source development, deployment constraints and verification commands share one long path | General readers and contributors have to navigate operational detail too early | Provide separate routes for evaluation, verified client operation, development and security review |
| The documentation contains substantial source-backed explanations | Valuable work is hard to discover from the entry page | Turn those records into a coherent reading path rather than duplicate every report |

The old screenshots and dated engineering records remain evidence of their own revisions. Refresh the public presentation without rewriting historical failures or painting over screenshot warnings.

## Serve three audiences in one reading path

| Reader | What they should understand | How the presentation helps |
|---|---|---|
| Someone considering the messenger | Who it is for, what conversations feel like, how device trust works, what setup involves | Plain opening, real interface, short capability descriptions and a clear getting-started route |
| A developer or operator | Where state lives, how components communicate, what runs where, how to build and maintain it | Architecture, message flow, repository map, deployment choices and authoritative runbooks |
| A security reviewer | Assets and adversaries, trust assumptions, protocol integration, failure behavior, evidence and unresolved limits | Explicit boundaries, claims tied to code/evidence, qualified language and a dedicated review reading path |

Use progressive detail. A reader should learn the essentials in the first few hundred words, follow the main narrative without opening every link, and reach the technical evidence without searching the repository. The full README can be approximately 1,500–2,000 words; that is a working budget, not a reason to omit an important boundary.

## Narrative order

The detailed [README outline and sample opening](outline.md) defines the writing sequence:

1. **Understand HAVEN.** Purpose, intended community, screenshot and a brief truthful status line.
2. **Recognize the experience.** Conversations, media, language/accessibility support and the three separate boundaries of login, device approval and local unlock.
3. **See the system.** Device-side encryption/storage, the API's responsibilities, PostgreSQL durability, transient Redis hints and background workers.
4. **Follow a message.** Encryption, atomic local checkpoint/outbox, durable server acceptance, recipient verification/storage and acknowledgement. Explain why retries reuse exact ciphertext and why acceptance is not a human read receipt.
5. **Understand the privacy choices.** Scoped disclosure, metadata minimization, view-once behavior, routine ciphertext retention and mutually agreed retirement. Keep these distinct.
6. **Understand client authenticity.** Compare ordinary web, independently delivered web and the signed installed Linux client. Explain the publisher/OS/browser trust that remains.
7. **Assess the work.** Problem → design decision → evidence → remaining limit. Show refinement through engineering choices, not a long list of phases or celebratory statistics.
8. **Try, build or review it.** Separate entry paths, source map, security/disclosure links and license.

## Content organization

| Surface | Job | Planned treatment |
|---|---|---|
| Root `README.md` | Complete introduction and navigation | Rewrite around the narrative above; remove duplicated commands and stale milestones |
| `docs/README.md` | Reliable documentation hub | Add user, operator, contributor and reviewer reading paths; bring verified delivery into the main table |
| Planned `docs/architecture/README.md` | Current technical system explanation | Explain data custody, state transitions, component responsibilities and deployment modes; link ADRs as decision history |
| Planned `docs/security/design-guide.md` | Connected explanation of difficult security problems | Use the source-backed problem/response/limit pattern; keep operational runbooks and dated reports authoritative |
| `SECURITY_STATUS.md` and `TEST_REPORT.md` | Current assurance and evidence indexes | Reconcile links/scope with the new presentation; avoid duplicating transient dependency versions or test totals in many places |
| `.github/assets/` | Brand, architecture illustrations and real product captures | Refresh hero/social art and current desktop/mobile/dark captures; preserve editable source, provenance and accessible descriptions |
| GitHub About, topics and social preview | Short introduction outside the README | Match final wording and real available destinations; do not insert an unhosted demo URL |
| Optional companion explainer | Interactive learning beyond GitHub Markdown | Build only where interaction adds understanding; keep the complete README useful without it |

Planned paths above are deliverables for the rewrite, not links to files that already exist. Existing specialist documents should be reused where they already explain the subject well.

## Visual direction

Keep HAVEN's existing calm blue identity, approachable interface and clear hierarchy. Use the visual vocabulary of the real messenger rather than stock cyber-security imagery.

| Role | Existing palette | Use |
|---|---|---|
| Glacier | `#f3f6fb` | Quiet background in custom artwork |
| Porcelain | `#ffffff` | Legible product surfaces |
| Ink | `#182332` | Principal labels and diagram text |
| Blue | `#1769f4` | HAVEN identity and meaningful connections |
| Muted ink | `#596879` | Secondary text with checked contrast |
| Amber | `#8a5309` | Qualifications and consequential actions |

GitHub supplies the body typography and layout. Use its native heading hierarchy, paragraphs, links, narrow comparison tables and a few purposeful disclosures. Preserve the established system/Arial-style lettering in editable artwork rather than invent a separate brand. Put important wording in real Markdown, with asset text only as a supplement.

The memorable visual should explain **what stays on a device and what the service handles**. That is specific to HAVEN and useful to the reader. The [diagram storyboard](diagrams.md) gives precise responsibilities and captions.

- A shorter hero, approximately 1200×320, should leave room for a useful introduction on the first screen.
- One decisive current conversation screenshot should lead the product presentation. Provide a full-resolution destination; avoid making UI text unreadable by putting several desktop captures in one row.
- Place mobile/dark views in a compact secondary gallery or disclosure, with clear captions.
- Use Mermaid or editable SVG for technical diagrams. Review the arrows and wording as technical claims.
- Check artwork and diagram readability in light/dark GitHub themes and on a narrow screen. Use text labels and line styles as well as color.
- Keep badges to information with a purpose, such as CI and license. Neither a green CI badge nor a padlock illustration should imply an independent audit.

### Image generation and live components

GPT Image is optional for a nontechnical cover illustration if it improves the visual concept. Do not use generated artwork as a product screenshot or as the authoritative source for architecture, protocol arrows, status labels or security claims. Those need editable, reviewable diagrams and real captures.

GitHub renders [Mermaid diagrams](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams). Its [markup pipeline removes scripts and inline styles](https://github.com/github/markup). Interactive React/JavaScript components therefore belong on a separate companion page, with a static diagram and ordinary link in the README.

A useful optional explorer would let a reader select **API compromise**, **frontend-host compromise**, or **publisher/device compromise**, then show the different trust boundaries of the three delivery modes. It should use synthetic data, require no account, load no analytics, offer keyboard controls and a readable static alternative, and clearly call itself an explanatory model rather than a security test.

The repository currently has no configured homepage or GitHub Pages site. Do not promise a live explorer or set an About homepage until there is a real reviewed destination.

## Writing and claim discipline

Use plain English first; introduce MLS, ratchets, WebAssembly and replay journals when the reader has a reason to understand them. Prefer a small concrete example to a string of security adjectives. Keep the technical names and exact distinctions available for specialists.

Describe work through its effect:

> An interrupted send reuses the ciphertext already saved in the encrypted outbox. Retrying the request does not create a second encryption operation or pretend that the recipient has read it.

> One participating approved device can represent an account during closure. Every historically affected account must agree, including former group members; missing consent retains the server history.

Avoid “unbreakable,” “military-grade,” “zero metadata,” “fully audited,” “guaranteed deletion,” “production-proven,” “best-in-class” and claims that the server stores nothing. Do not call the portable Linux client an independently audited native/mobile app. Explain the boundaries alongside the feature rather than collect all qualifications in distant fine print.

The [claims and evidence register](claims.md) is the factual checklist for every major statement. Current code/status overrides a superseded deployment statement in an old ADR; dated evidence remains bounded to its original revision.

## Execution sequence

| Stage | Concrete result | Completion check |
|---|---|---|
| Review and brief | This plan, outline, claims register and diagram storyboard | Every principal feature has an implementation/evidence pointer; unresolved presentation mismatches are identified |
| Core narrative | Rewritten README and a current architecture/security reading path | Product story reads continuously; different audiences can find their next step; claims satisfy the register |
| Visual production | Editable diagrams, refreshed hero/social art and current real captures | Diagrams match component behavior; no synthetic interface mockup masquerades as a screenshot; provenance recorded |
| Render review | GitHub-compatible desktop/mobile and light/dark presentation | Links, anchors, disclosures, code blocks, diagrams, image size/alt text and text contrast checked |
| Publication | Reviewed documentation changes plus matching repository metadata | Source manifest and publication scan pass; final diff reviewed; public destinations resolve; current application behavior is unaffected |
| Optional explainer | A separately reviewed static/interactive companion | Improves a specific concept, has an accessible fallback, and is linked only after a real destination exists |

There is no need to rerun cryptographic or backend suites for prose-only edits. Use documentation/link/render checks and publication hygiene. If screenshots require new fixture code or the explainer adds application behavior, verify those changes at the appropriate scope.

## Definition of done

- A newcomer can explain what HAVEN does without knowing the stack.
- A developer can trace a message and locate the responsible code.
- A reviewer can distinguish encryption, authentication, device trust, delivery, retention and code authenticity.
- Normal operational features are described as implemented; independent review and deployment/mobile qualification are described accurately.
- Per-device routine retention is never confused with per-account unanimous closure.
- The three client-delivery choices and their different trust assumptions are explicit.
- The work's depth is visible through concrete design choices, source links and scoped evidence.
- No unsupported anonymity, erasure, global fork-detection, performance or audit claim appears.
- README, About copy, social art, screenshots and documentation navigation tell the same current story.
- The result is usable on GitHub without JavaScript, external tracking or a separate website.
