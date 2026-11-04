// Editable, deterministic artwork. No external assets, generated UI, or runtime requests.
import fs from "node:fs";
import path from "node:path";
const directory = path.resolve(import.meta.dirname, "../.github/assets");
const C = {
  ink: "#182332",
  blue: "#1769f4",
  muted: "#596879",
  pale: "#edf3ff",
  glacier: "#f3f6fb",
  line: "#ccd9ee",
  white: "#ffffff",
};
const escape = (s) =>
  s.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
const text = (x, y, label, size = 22, color = C.ink, weight = 400) =>
  `<text x="${x}" y="${y}" fill="${color}" font-size="${size}" font-weight="${weight}">${escape(label)}</text>`;
const box = (x, y, w, h, fill = C.white, stroke = C.line) =>
  `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12" fill="${fill}" stroke="${stroke}"/>`;
const line = (x1, y1, x2, y2, arrow = false) =>
  `<path d="M${x1} ${y1} L${x2} ${y2}" fill="none" stroke="${C.blue}" stroke-width="2.5"${arrow ? ' marker-end="url(#arrow)"' : ""}${arrow === "both" ? ' marker-start="url(#arrow)"' : ""}/>`;
const shell = (width, height, title, description, body) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="title description"><title id="title">${escape(title)}</title><desc id="description">${escape(description)}</desc><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10z" fill="${C.blue}"/></marker></defs><g font-family="Arial, Helvetica, sans-serif">${body}</g></svg>\n`;
const mark = (x, y) =>
  `<g transform="translate(${x} ${y})"><rect width="42" height="42" rx="12" fill="${C.blue}"/><path d="M11 12h21v15H21l-8 6v-6h-2z" fill="none" stroke="white" stroke-width="2" stroke-linejoin="round"/><g fill="white"><circle cx="17" cy="19.5" r="1.2"/><circle cx="22" cy="19.5" r="1.2"/><circle cx="27" cy="19.5" r="1.2"/></g></g>`;
const hero = `<rect width="1200" height="320" rx="16" fill="${C.glacier}"/>${mark(44, 36)}${text(101, 65, "HAVEN", 25, C.ink, 700)}${text(44, 156, "Private conversations.", 47, C.ink, 700)}${text(44, 215, "Explicit trust.", 47, C.ink, 700)}${text(46, 275, "For small, trusted communities.", 21, C.muted)}${box(690, 68, 458, 84, C.white)}${text(716, 103, "On your device", 23, C.blue, 700)}${text(716, 133, "Keys and readable history", 21, C.muted)}${line(916, 153, 916, 182)}${box(690, 184, 458, 84, C.pale)}${text(716, 219, "On your service", 23, C.blue, 700)}${text(716, 249, "Delivery and routing", 21, C.muted)}`;
fs.writeFileSync(
  path.join(directory, "haven-hero.svg"),
  shell(
    1200,
    320,
    "HAVEN — Private conversations. Explicit trust.",
    "A self-hosted messenger for small trusted communities. Keys and readable history belong on the device; the service coordinates delivery and routing. Independent security review is pending.",
    hero,
  ),
);
const social = `<rect width="1200" height="630" fill="${C.glacier}"/>${mark(58, 46)}${text(116, 75, "HAVEN", 26, C.ink, 700)}${text(58, 208, "Private conversations.", 61, C.ink, 700)}${text(58, 283, "Explicit trust.", 61, C.ink, 700)}${text(61, 345, "A self-hosted messenger for small, trusted communities.", 27, C.muted)}${box(60, 399, 520, 106, C.white)}${text(84, 441, "On your device", 24, C.blue, 700)}${text(84, 478, "Keys and readable history", 23, C.muted)}${box(620, 399, 520, 106, C.pale)}${text(644, 441, "On your service", 24, C.blue, 700)}${text(644, 478, "Delivery and routing", 23, C.muted)}${line(581, 450, 618, 450)}${text(61, 568, "MLS encryption · Approved devices · Signed client delivery", 22, C.blue, 700)}${text(61, 605, "Implemented software · Independent security review pending", 18, C.muted)}`;
fs.writeFileSync(
  path.join(directory, "haven-social.svg"),
  shell(
    1200,
    630,
    "HAVEN — Private conversations. Explicit trust.",
    "Self-hosted private messaging, explicit device approval, encrypted local history and signed client delivery. Independent review pending.",
    social,
  ),
);
const architecture = `<rect width="1120" height="780" rx="16" fill="${C.glacier}"/>
${text(36, 48, "Different responsibilities. Clear trust boundaries.", 30, C.ink, 700)}
${box(30, 82, 430, 576, C.white)}${text(55, 122, "Your device", 26, C.blue, 700)}${text(55, 152, "Private state while unlocked", 19, C.muted)}
${box(55, 188, 380, 88, C.pale)}${text(77, 224, "Conversation interface", 23, C.ink, 700)}${text(77, 254, "Verification, consent and local use", 18, C.muted)}
${line(245, 277, 245, 311, true)}${box(55, 318, 380, 98)}${text(77, 354, "Rust / OpenMLS worker", 23, C.ink, 700)}${text(77, 387, "Encrypt and verify messages", 19, C.muted)}
<path d="M55 250 H42 V508 H54" fill="none" stroke="${C.blue}" stroke-width="2.5" marker-end="url(#arrow)"/>${box(55, 452, 380, 112)}${text(77, 488, "Encrypted local storage", 23, C.ink, 700)}${text(77, 521, "Vault · History · Drafts · Outbox", 19, C.muted)}
${text(55, 608, "Plaintext and unwrapped keys can", 19, C.muted)}${text(55, 636, "exist in memory while unlocked.", 19, C.muted)}
${box(650, 82, 440, 576, C.white)}${text(675, 122, "Messaging service", 26, C.blue, 700)}${text(675, 152, "Authenticated coordination", 19, C.muted)}
${box(675, 188, 390, 88, C.pale)}${text(696, 224, "Django API", 23, C.ink, 700)}${text(696, 254, "Current authority and ordered delivery", 18, C.muted)}
${line(880, 277, 880, 311, true)}${box(675, 318, 390, 98)}${text(696, 354, "PostgreSQL", 23, C.ink, 700)}${text(696, 387, "Durable ciphertext and public records", 18, C.muted)}
${line(880, 418, 880, 445, true)}${box(675, 452, 390, 112)}${text(696, 488, "Workers and Redis hints", 23, C.ink, 700)}${text(696, 521, "Notifications · Retention · Retirement", 18, C.muted)}
${text(675, 608, "Active relationships and routing", 19, C.muted)}${text(675, 636, "remain visible to the service.", 19, C.muted)}
${line(437, 231, 671, 231, "both")}${text(489, 199, "HTTPS", 21, C.blue, 700)}${text(482, 276, "Ciphertext", 18, C.muted)}${text(482, 303, "Public proofs", 18, C.muted)}${text(482, 330, "Authentication", 18, C.muted)}
${box(30, 686, 1060, 64, C.pale)}${text(53, 725, "Independent retirement journal · Retirement records kept outside SQL backups", 21, C.ink, 700)}`;
fs.writeFileSync(
  path.join(directory, "architecture.svg"),
  shell(
    1120,
    780,
    "HAVEN architecture — device and service responsibilities",
    "The client interface coordinates OpenMLS encryption and encrypted local storage. HTTPS carries ciphertext, public proofs and authentication to the Django API. PostgreSQL is durable; workers and Redis provide maintenance and transient hints. An independent retirement journal guards SQL restoration. The service sees active metadata; unlocked devices expose plaintext to trusted local code. This is a responsibility map, not a network topology.",
    architecture,
  ),
);
console.log("Built compact hero, social artwork and architecture SVGs.");
