# Proposed README structure and opening

This is the original writing blueprint. The implemented [project overview](../../README.md) follows this narrative with edited final copy; this draft is retained as planning history.

## Opening draft

# HAVEN

**Private conversations. Explicit trust.**

HAVEN is a self-hosted messenger for small, invite-only communities. It brings together end-to-end encryption for direct and group conversations, explicit device approval, encrypted local history, and a familiar interface in English and Persian.

Its design follows the life of a conversation: who can join, where keys live, how messages survive interrupted delivery, how readable history is recovered, and when shared server history can be retired by agreement. A signed installed client also separates the software handling your keys from the messaging server that carries your data.

Messaging, mutual conversation retirement and verified Linux client delivery are implemented. Independent security review and public-deployment qualification remain pending.

*Try HAVEN · Understand the architecture · Review the security model*

The final navigation labels will link to actual sections/documents. Keep this text in Markdown rather than bake the only readable copy into an image.

## Section-by-section writing brief

| Order | Working title | Purpose and content | Approximate budget |
|---|---|---|---|
| Opening | HAVEN | Position the project, intended community and current status; one compact hero, useful navigation, CI/license only | 100–140 words |
| Product | A familiar place for private conversations | One actual current conversation image; direct/groups, replies/edits/reactions, files/voice/media, local search, responsive EN/FA/RTL/themes. Describe observed delivery states carefully | 130–170 words |
| Trust | Signing in, trusting a device, unlocking your history | Three small definitions and a concrete new-browser example. A server password, approval and vault secret do different jobs | 120–150 words |
| Architecture | What runs on your device—and what the service handles | Main architecture diagram and component responsibilities. Define OpenMLS/WASM where first needed; distinguish message ciphertext from visible auth/routing/public proofs | 150–190 words |
| Reliability | What happens when you send a message | Actual ordered flow: encrypt → local checkpoint/outbox → server commit → recipient verification/local commit → ACK. Retries reuse saved bytes; Redis hints trigger authoritative sync | 120–160 words |
| Retention | Keep useful history. Retire shared server records by agreement. | Distinguish routine per-device-ACK ciphertext cleanup from account-wide closure; available encrypted archives, unanimous historical group consent, final receipts/journal and no erasure of old copies. State the pause/non-cancellation consequence | 170–210 words |
| Authenticity | Know which client code handles your keys | Three-mode comparison: same-origin web, independent web, installed verified client. Explain signed payload/root/update floor and the remaining signer/browser/OS trust | 130–170 words |
| Engineering | The decisions behind the behavior | A handful of problem/response examples: segmented encrypted history, exact retry bytes, current-authority fences, scoped disclosure, restore-deny journal, authenticated client delivery. Link the longer rationale | 150–190 words |
| Assurance | What has been checked, and what remains | Behavior/evidence table with source-scoped links; metadata/recipient/endpoint/backups limits. Independent review and physical/public-host qualification stated clearly | 140–180 words |
| Start | Choose your starting point | Evaluation, installed client and development routes; a short real setup command and prerequisites link; setup does not itself install a verified client | 100–140 words |
| Source | Find your way through the repository | Compact map including `apps/verified-client`, normal UI/API, crypto/contracts, infrastructure and decision/evidence records | 70–100 words |
| Close | Contribute, review or report a vulnerability | Existing contribution/security-reporting paths and MIT/third-party notices | 50–70 words |

Budgets guide the balance rather than constrain every sentence. Add no section merely to reach a target. Put detailed deployment commands, exact crypto/KDF parameters, limits and operator recovery procedures in linked documents with a clear purpose.

## Show the work through decisions

These are examples to expand in the architecture/security guides, not six identical marketing cards:

| Problem the design has to handle | Explanation to develop |
|---|---|
| A tab closes after encryption or a request loses its reply | Crypto state and pending ciphertext are checkpointed together; retry the same authenticated request |
| A conversation outgrows a single local vault record | Seal history in independent records and atomically update the encrypted checkpoint; preserve the last durable state on storage failure |
| A device is revoked while another request is in progress | Refresh current authority and serialize relevant account/conversation mutations; test the races rather than rely on a cached permission result |
| A service needs routing without copying unnecessary data everywhere | Purpose-scope API/worker reads, minimize redundant fields, separate notification credentials and pseudonymize transient routing labels; retain explicit graph-visibility limits |
| A group wants to end a shared conversation | Give every historically affected account a voice; save available local history, require final consent/receipts and retire only when dependencies permit |
| An old SQL backup contains already retired history | Keep authenticated retirement exclusions independently of that SQL snapshot; refuse unsafe resurrection |
| A compromised messaging origin changes browser code | Verify an installed release under an independently trusted publisher root and constrain the API to data; explain the different trust of web delivery |

The depth of the work should become visible in these causal explanations. Avoid implementation diaries, phase numbers in the introduction, claims about effort spent, or unsupported comparisons with other messengers.

## Proposed GitHub About copy

> A self-hosted messenger for small trusted communities: end-to-end encryption, explicit device approval, encrypted local history, mutual conversation retirement and signed Linux client delivery. Independent security review pending.

Keep the existing relevant topics; consider `openmls` and `privacy` if they improve discovery. Avoid claims such as `anonymous`, `zero-knowledge` or `audited`. Do not use a homepage field for a local evaluation address or an unhosted demo.

## Page rhythm

```text
Compact HAVEN identity
Plain product introduction + current assurance line + three useful links

One real conversation screenshot
Concise explanation of everyday use

The three trust steps
Architecture diagram + short component explanations
Message journey

Retention / mutual closure
Three client-delivery choices

Engineering decisions and evidence
Clear remaining boundaries

Try it / install the client / develop / review
Repository map
Contribute + disclosure + license
```

Keep the technical story and reassurance coherent: do not put an impressive feature headline in one section and retract its implied guarantee far below. Each important boundary belongs near the relevant claim.
