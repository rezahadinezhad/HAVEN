import fs from "node:fs";
import { createHash } from "node:crypto";
import type { Page } from "@playwright/test";
import path from "node:path";
import { test, expect } from "./fixtures";

const directory = process.env.HAVEN_PROVIDER_COMPAT_DIR;

async function assertRebuiltArtifact(page: Page) {
  const expected = createHash("sha256")
    .update(fs.readFileSync("public/crypto/haven_crypto_bg.wasm"))
    .digest("hex");
  const actual = await page.evaluate(async () => {
    const response = await fetch("/crypto/haven_crypto_bg.wasm", {
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Rebuilt WASM unavailable");
    const hash = new Uint8Array(
      await crypto.subtle.digest("SHA-256", await response.arrayBuffer()),
    );
    return Array.from(hash, (value) =>
      value.toString(16).padStart(2, "0"),
    ).join("");
  });
  expect(actual).toBe(expected);
}

test("upstream provider backport exchanges MLS with previous browser build and opens previous snapshots", async ({
  page,
}) => {
  test.skip(!directory, "Requires preserved pre-upgrade engineering assets");
  await page.route("**/__prior_provider/*", async (route) => {
    const name = new URL(route.request().url()).pathname.split("/").pop()!;
    if (!["haven_crypto.js", "haven_crypto_bg.wasm"].includes(name))
      return route.abort();
    await route.fulfill({
      body: fs.readFileSync(path.join(directory!, "previous-crypto", name)),
      contentType: name.endsWith("wasm")
        ? "application/wasm"
        : "text/javascript",
      headers: { "Cache-Control": "no-store" },
    });
  });
  await page.goto("/pof.html");
  await page.waitForFunction(() => !!(window as any).havenPoF);
  await assertRebuiltArtifact(page);
  const result = await page.evaluate(async () => {
    const modulePath = "/__prior_provider/haven_crypto.js";
    const previous = await import(modulePath);
    await previous.default();
    const oldCall = (s: string, c: any) =>
      JSON.parse(previous.execute(s, JSON.stringify(c)));
    const newCall = (s: string, c: any) => (window as any).havenPoF.call(s, c);
    const states: Record<string, string> = {};
    const call = (who: string, fn: typeof oldCall, c: any) => {
      const answer = fn(states[who] || "", c);
      states[who] = answer.state;
      return answer.result;
    };
    for (const who of ["a", "b"])
      call(who, oldCall, { op: "init", identity: who });
    const kp = call("b", oldCall, { op: "package" });
    const group_id = "provider-compatibility";
    call("a", oldCall, { op: "create", group_id });
    const add = call("a", oldCall, {
      op: "add",
      group_id,
      key_package: kp.key_package,
    });
    call("b", oldCall, { op: "join", group_id, welcome: add.welcome });
    const oldMessage = call("a", oldCall, {
      op: "encrypt",
      group_id,
      plaintext: "Before upgrade سلام",
    });
    const received = call("b", newCall, {
      op: "process",
      group_id,
      ciphertext: oldMessage.ciphertext,
    });
    const newMessage = call("b", newCall, {
      op: "encrypt",
      group_id,
      plaintext: "After upgrade سلام",
    });
    const replied = call("a", oldCall, {
      op: "process",
      group_id,
      ciphertext: newMessage.ciphertext,
    });
    call("c", newCall, { op: "init", identity: "new-provider-carol" });
    const newPackage = call("c", newCall, { op: "package" });
    const addNew = call("a", oldCall, {
      op: "add",
      group_id,
      key_package: newPackage.key_package,
    });
    call("b", newCall, { op: "process", group_id, ciphertext: addNew.commit });
    call("c", newCall, { op: "join", group_id, welcome: addNew.welcome });
    const addedMessage = call("c", newCall, {
      op: "encrypt",
      group_id,
      plaintext: "New member",
    });
    const addedReceived = call("a", oldCall, {
      op: "process",
      group_id,
      ciphertext: addedMessage.ciphertext,
    });
    return [received.plaintext, replied.plaintext, addedReceived.plaintext];
  });
  expect(result).toEqual([
    "Before upgrade سلام",
    "After upgrade سلام",
    "New member",
  ]);
});

test("rebuilt native Rust provider snapshot interoperates with rebuilt WASM", async ({
  page,
}) => {
  test.skip(!directory, "Requires native provider-upgrade fixture");
  const fixture = JSON.parse(
    fs.readFileSync(path.join(directory!, "new-native.json"), "utf8"),
  );
  await page.goto("/pof.html");
  await page.waitForFunction(() => !!(window as any).havenPoF);
  await assertRebuiltArtifact(page);
  const plaintext = await page.evaluate(
    (fixture) =>
      (window as any).havenPoF.call(fixture.state, {
        op: "process",
        group_id: "native-wasm-golden",
        ciphertext: fixture.ciphertext,
      }).result.plaintext,
    fixture,
  );
  expect(plaintext).toBe("Native → WASM: سلام 🗝");
});
