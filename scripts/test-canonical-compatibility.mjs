// Signed metadata must keep the same RFC 8785 bytes across dependency upgrades.
import assert from "node:assert/strict";
import { generateKeyPairSync, sign, verify } from "node:crypto";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import canonicalize from "../apps/web/node_modules/canonicalize/lib/canonicalize.js";

const vectors = [
  null, true, false, 0, -0, 1e-7, 1e21,
  { numbers: [333333333.33333329, 1e30, 4.50, 2e-3, 0.000000000000000000000000001] },
  { string: "€$\u000f\nA'B\"\\\"/", literals: [null, true, false] },
  { "\u20ac": "Euro Sign", "\r": "Carriage Return", "\ufb33": "Hebrew", "1": "One", "\ud83d\ude00": "Emoji", "\u0080": "Control", "\u00f6": "Latin" },
  { domain: "haven/envelope/v1", v: 1, epoch: 0, seq: 1, transition: null, previous_hash: "0".repeat(64), ciphertext_hash: "1".repeat(64) },
  { domain: "haven/genesis/v1", members: [{ id: "synthetic-device", user_id: "synthetic-user", identity: "سلام 🗝", role: "owner" }], kind: "group" },
  { nested: [{ z: 3, a: ["é", "e\u0301", "سلام", "🗝"] }, {}] },
];
const result = spawnSync("apps/api/.venv/bin/python", ["-c", "import json,sys,rfc8785; print(json.dumps([rfc8785.dumps(v).decode() for v in json.load(sys.stdin)]))"], {
  input: JSON.stringify(vectors), encoding: "utf8",
});
assert.equal(result.status, 0, result.stderr);
const python = JSON.parse(result.stdout);
const { privateKey, publicKey } = generateKeyPairSync("ed25519");
let previous;
if (process.env.HAVEN_PREVIOUS_CANONICALIZE) {
  previous = createRequire(import.meta.url)(process.env.HAVEN_PREVIOUS_CANONICALIZE);
}
for (const [i, input] of vectors.entries()) {
  const current = canonicalize(input);
  assert.equal(current, python[i], `Python/Javascript canonical bytes differ for vector ${i}`);
  if (previous) assert.equal(current, previous(input), `Upgrade changed signed bytes for vector ${i}`);
  const signature = sign(null, Buffer.from(previous ? previous(input) : python[i]), privateKey);
  assert(verify(null, Buffer.from(current), publicKey, signature));
}
for (const input of [NaN, Infinity, -Infinity, "\ud800", "\udfff"]) {
  assert.throws(() => canonicalize(input));
}
console.log(`PASS: ${vectors.length} canonical vectors, Python parity, Ed25519 signatures, 5 invalid inputs${previous ? ", and pre-upgrade byte compatibility" : ""}`);
