import fs from "node:fs";
import { test, expect } from "./fixtures";
test("real OpenMLS WASM: two-way, persisted reload, reordering, add/remove, tamper and replay", async ({
  page,
}) => {
  await page.goto("/pof.html");
  await page.waitForFunction(() => !!(window as any).havenPoF);
  const result = await page.evaluate(async () => {
    const call = (s: string, c: any) => (window as any).havenPoF.call(s, c);
    const states: Record<string, string> = {};
    const run = (who: string, c: any) => {
      const x = call(states[who] || "", c);
      states[who] = x.state;
      return x.result;
    };
    for (const name of ["a", "b", "c"])
      run(name, { op: "init", identity: name });
    const kp = run("b", { op: "package" });
    run("a", { op: "create", group_id: "pof-group" });
    const add = run("a", {
      op: "add",
      group_id: "pof-group",
      key_package: kp.key_package,
    });
    run("b", { op: "join", group_id: "pof-group", welcome: add.welcome });
    const a0 = run("a", {
      op: "encrypt",
      group_id: "pof-group",
      plaintext: "hello سلام",
    });
    const b0 = run("b", {
      op: "process",
      group_id: "pof-group",
      ciphertext: a0.ciphertext,
    });
    const b1 = run("b", {
      op: "encrypt",
      group_id: "pof-group",
      plaintext: "reply",
    });
    const a1 = run("a", {
      op: "process",
      group_id: "pof-group",
      ciphertext: b1.ciphertext,
    });
    const e1 = run("a", {
      op: "encrypt",
      group_id: "pof-group",
      plaintext: "first",
    });
    const e2 = run("a", {
      op: "encrypt",
      group_id: "pof-group",
      plaintext: "second",
    });
    const second = run("b", {
      op: "process",
      group_id: "pof-group",
      ciphertext: e2.ciphertext,
    });
    const first = run("b", {
      op: "process",
      group_id: "pof-group",
      ciphertext: e1.ciphertext,
    });
    let replay = false;
    try {
      run("b", {
        op: "process",
        group_id: "pof-group",
        ciphertext: e1.ciphertext,
      });
    } catch {
      replay = true;
    }
    const cp = run("c", { op: "package" });
    const add3 = run("a", {
      op: "add",
      group_id: "pof-group",
      key_package: cp.key_package,
    });
    run("b", { op: "process", group_id: "pof-group", ciphertext: add3.commit });
    run("c", { op: "join", group_id: "pof-group", welcome: add3.welcome });
    let prejoin = false;
    try {
      run("c", {
        op: "process",
        group_id: "pof-group",
        ciphertext: a0.ciphertext,
      });
    } catch {
      prejoin = true;
    }
    const third = run("c", {
      op: "encrypt",
      group_id: "pof-group",
      plaintext: "third member",
    });
    const thirdReceived = run("b", {
      op: "process",
      group_id: "pof-group",
      ciphertext: third.ciphertext,
    });
    const cindex = run("a", {
      op: "inspect",
      group_id: "pof-group",
    }).members.find((m: any) => m.identity === "c").index;
    const remove = run("a", {
      op: "remove",
      group_id: "pof-group",
      index: cindex,
    });
    run("b", {
      op: "process",
      group_id: "pof-group",
      ciphertext: remove.commit,
    });
    const future = run("a", {
      op: "encrypt",
      group_id: "pof-group",
      plaintext: "after removal",
    });
    let removed = false;
    try {
      run("c", {
        op: "process",
        group_id: "pof-group",
        ciphertext: future.ciphertext,
      });
    } catch {
      removed = true;
    }
    const allowed = run("b", {
      op: "process",
      group_id: "pof-group",
      ciphertext: future.ciphertext,
    });
    const bytes = Uint8Array.from(atob(future.ciphertext), (x) =>
      x.charCodeAt(0),
    );
    bytes[bytes.length - 1] ^= 1;
    let tamper = false;
    try {
      run("b", {
        op: "process",
        group_id: "pof-group",
        ciphertext: btoa(String.fromCharCode(...bytes)),
      });
    } catch {
      tamper = true;
    }
    let stale = false;
    try {
      run("b", {
        op: "process",
        group_id: "pof-group",
        ciphertext: add3.commit,
      });
    } catch {
      stale = true;
    }
    let duplicateWelcome = false;
    try {
      run("b", { op: "join", group_id: "pof-group", welcome: add.welcome });
    } catch {
      duplicateWelcome = true;
    }
    // Encrypt provider snapshots through the actual Argon2id/XChaCha worker before IndexedDB.
    const w = new Worker("/vault-worker.js");
    const seal = await new Promise<any>((resolve, reject) => {
      w.onmessage = (e) =>
        e.data.error ? reject(new Error(e.data.error)) : resolve(e.data.value);
      w.postMessage({
        id: 1,
        op: "seal",
        secret: "test-only unlock phrase 12345!",
        scope: "pof",
        value: states,
      });
    });
    w.terminate();
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const r = indexedDB.open("haven-pof", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("state");
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => reject(r.error);
    });
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction("state", "readwrite");
      tx.objectStore("state").put(seal, "snapshot");
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    return {
      twoWay: b0.plaintext === "hello سلام" && a1.plaintext === "reply",
      reordered: second.plaintext === "second" && first.plaintext === "first",
      replay,
      prejoin,
      removed,
      tamper,
      stale,
      duplicateWelcome,
      third: thirdReceived.plaintext === "third member",
      allowed: allowed.plaintext === "after removal",
    };
  });
  expect(Object.values(result).every(Boolean)).toBeTruthy();
  await page.reload();
  await page.waitForFunction(() => !!(window as any).havenPoF);
  const reload = await page.evaluate(async () => {
    const db = await new Promise<IDBDatabase>((resolve) => {
      const r = indexedDB.open("haven-pof");
      r.onsuccess = () => resolve(r.result);
    });
    const sealed = await new Promise<any>((resolve) => {
      const r = db.transaction("state").objectStore("state").get("snapshot");
      r.onsuccess = () => resolve(r.result);
    });
    const w = new Worker("/vault-worker.js");
    const states = await new Promise<any>((resolve, reject) => {
      w.onmessage = (e) =>
        e.data.error ? reject(new Error(e.data.error)) : resolve(e.data.value);
      w.postMessage({
        id: 2,
        op: "open",
        secret: "test-only unlock phrase 12345!",
        scope: "pof",
        value: sealed,
      });
    });
    w.terminate();
    const c = (s: string, cmd: any) => (window as any).havenPoF.call(s, cmd);
    const sent = c(states.b, {
      op: "encrypt",
      group_id: "pof-group",
      plaintext: "after actual reload",
    });
    return c(states.a, {
      op: "process",
      group_id: "pof-group",
      ciphertext: sent.result.ciphertext,
    }).result.plaintext;
  });
  expect(reload).toBe("after actual reload");
});
test("vault rejects wrong secret and modified ciphertext", async ({ page }) => {
  await page.goto("/pof.html");
  const result = await page.evaluate(async () => {
    const w = new Worker("/vault-worker.js");
    let id = 0;
    const ask = (op: string, secret: string, value: any) =>
      new Promise<any>((resolve) => {
        w.onmessage = (e) => resolve(e.data);
        w.postMessage({ id: ++id, op, secret, scope: "negative", value });
      });
    const sealed = await ask("seal", "long test only unlock secret", {
      private: "test key",
    });
    const wrong = await ask(
      "open",
      "incorrect long unlock secret",
      sealed.value,
    );
    const encoded = sealed.value.ciphertext
      .replace(/-/g, "+")
      .replace(/_/g, "/");
    const bytes = Uint8Array.from(atob(encoded), (value) =>
      value.charCodeAt(0),
    );
    bytes[0] ^= 1; // Always alter authenticated bytes; a replacement "A" could already match.
    sealed.value.ciphertext = btoa(String.fromCharCode(...bytes))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
    const tamper = await ask(
      "open",
      "long test only unlock secret",
      sealed.value,
    );
    w.terminate();
    return !!wrong.error && !!tamper.error;
  });
  expect(result).toBeTruthy();
});

test("native Rust snapshot and MLS ciphertext interoperate with browser WASM", async ({
  page,
}) => {
  const fixture = JSON.parse(
    fs.readFileSync("../../.local/native-wasm-golden.json", "utf8"),
  );
  await page.goto("/pof.html");
  await page.waitForFunction(() => !!(window as any).havenPoF);
  const result = await page.evaluate(
    (fixture) =>
      (window as any).havenPoF.call(fixture.state, {
        op: "process",
        group_id: "native-wasm-golden",
        ciphertext: fixture.ciphertext,
      }).result.plaintext,
    fixture,
  );
  expect(result).toBe("Native → WASM: سلام 🗝");
});
