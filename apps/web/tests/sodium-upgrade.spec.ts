import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { test, expect } from "./fixtures";

const directory = process.env.HAVEN_SODIUM_COMPAT_DIR;

test("sodium upgrade opens old encrypted checkpoints and history; old worker opens new records", async ({
  page,
}) => {
  test.skip(!directory, "Requires preserved pre-upgrade vault worker");
  await page.route("**/__previous_vault_worker.js", (route) =>
    route.fulfill({
      body: fs.readFileSync(path.join(directory!, "previous-vault-worker.js")),
      contentType: "text/javascript",
      headers: { "Cache-Control": "no-store" },
    }),
  );
  await page.goto("/pof.html");
  const expected = createHash("sha256")
    .update(fs.readFileSync("public/vault-worker.js"))
    .digest("hex");
  const actual = await page.evaluate(async () => {
    const response = await fetch("/vault-worker.js", { cache: "no-store" });
    if (!response.ok) throw new Error("Updated worker unavailable");
    return Array.from(
      new Uint8Array(
        await crypto.subtle.digest("SHA-256", await response.arrayBuffer()),
      ),
      (b) => b.toString(16).padStart(2, "0"),
    ).join("");
  });
  expect(actual).toBe(expected);
  const result = await page.evaluate(async () => {
    const previous = new Worker("/__previous_vault_worker.js");
    const current = new Worker("/vault-worker.js");
    let id = 0;
    const request = (worker: Worker, data: Record<string, unknown>) =>
      new Promise<any>((resolve, reject) => {
        const requestId = ++id;
        const timeout = setTimeout(
          () => reject(new Error("Vault compatibility operation timed out")),
          20000,
        );
        const listener = (event: MessageEvent) => {
          if (event.data.id !== requestId) return;
          clearTimeout(timeout);
          worker.removeEventListener("message", listener);
          resolve(event.data);
        };
        worker.addEventListener("message", listener);
        worker.postMessage({ id: requestId, ...data });
      });
    const secret = Array.from(crypto.getRandomValues(new Uint8Array(32)), (b) =>
      b.toString(16).padStart(2, "0"),
    ).join("");
    const scope = "synthetic-upgrade-vault";
    const value = {
      v: 3,
      state: "synthetic serialized checkpoint",
      history: [{ seq: 1, text: "سلام 🗝", nested: [null, true, 42] }],
    };
    const results = [];
    try {
      for (const binding of [undefined, "history:" + crypto.randomUUID()]) {
        const common = { scope, secret, binding };
        const oldRecord = await request(previous, {
          ...common,
          op: "seal",
          value,
        });
        const opened = await request(current, {
          ...common,
          op: "open",
          value: oldRecord.value,
        });
        const newRecord = await request(current, {
          ...common,
          op: "seal",
          value: opened.value,
        });
        const reopened = await request(previous, {
          ...common,
          op: "open",
          value: newRecord.value,
        });
        const ciphertext = newRecord.value.ciphertext;
        const corrupt = {
          ...newRecord.value,
          ciphertext: (ciphertext[0] === "A" ? "B" : "A") + ciphertext.slice(1),
        };
        const tampered = await request(current, {
          ...common,
          op: "open",
          value: corrupt,
        });
        const wrongScope = await request(current, {
          ...common,
          scope: scope + "-other",
          op: "open",
          value: newRecord.value,
        });
        const wrongSecret = await request(current, {
          ...common,
          secret: secret + "x",
          op: "open",
          value: newRecord.value,
        });
        const wrongBinding = await request(current, {
          ...common,
          binding: "history:" + crypto.randomUUID(),
          op: "open",
          value: newRecord.value,
        });
        results.push({
          oldToNew: JSON.stringify(opened.value) === JSON.stringify(value),
          newToOld: JSON.stringify(reopened.value) === JSON.stringify(value),
          version: newRecord.value.v,
          kdf: newRecord.value.kdf,
          freshNonce: oldRecord.value.nonce !== newRecord.value.nonce,
          rejected: [tampered, wrongScope, wrongSecret, wrongBinding].every(
            (r) => r.error === "VAULT_REJECTED",
          ),
        });
      }
      return results;
    } finally {
      previous.terminate();
      current.terminate();
    }
  });
  expect(result).toEqual(
    Array.from({ length: 2 }, () => ({
      oldToNew: true,
      newToOld: true,
      version: 1,
      kdf: "argon2id-3-64MiB",
      freshNonce: true,
      rejected: true,
    })),
  );
});
