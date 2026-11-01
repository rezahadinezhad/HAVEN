import { test, expect } from "./fixtures";

test("padded OpenMLS messages keep lengths coarse across browser reload and rekey", async ({
  page,
}) => {
  await page.goto("/pof.html");
  await page.waitForFunction(() => !!(window as any).havenPoF);
  const saved = await page.evaluate(() => {
    const states: Record<string, string> = {};
    const run = (who: string, command: any) => {
      const out = (window as any).havenPoF.call(states[who] || "", command);
      states[who] = out.state;
      return out.result;
    };
    run("a", { op: "init", identity: "padding-browser-a" });
    run("b", { op: "init", identity: "padding-browser-b" });
    const kp = run("b", { op: "package" });
    run("a", { op: "create", group_id: "padding-browser" });
    const add = run("a", {
      op: "add",
      group_id: "padding-browser",
      key_package: kp.key_package,
    });
    run("b", { op: "join", group_id: "padding-browser", welcome: add.welcome });
    const lengths: number[] = [];
    for (const size of [1, 16, 64, 128]) {
      const message = run("a", {
        op: "encrypt",
        group_id: "padding-browser",
        plaintext: "x".repeat(size),
      });
      lengths.push(atob(message.ciphertext).length);
      const result = run("b", {
        op: "process",
        group_id: "padding-browser",
        ciphertext: message.ciphertext,
      });
      if (result.plaintext !== "x".repeat(size))
        throw new Error("Padded plaintext changed");
    }
    return { states, lengths };
  });
  expect(new Set(saved.lengths).size).toBe(1);
  await page.reload();
  await page.waitForFunction(() => !!(window as any).havenPoF);
  const result = await page.evaluate(({ states }) => {
    const run = (who: string, command: any) => {
      const out = (window as any).havenPoF.call(states[who], command);
      states[who] = out.state;
      return out.result;
    };
    const update = run("a", { op: "update", group_id: "padding-browser" });
    run("b", {
      op: "process",
      group_id: "padding-browser",
      ciphertext: update.commit,
    });
    const message = run("b", {
      op: "encrypt",
      group_id: "padding-browser",
      plaintext: "پس از بارگذاری دوباره",
    });
    const received = run("a", {
      op: "process",
      group_id: "padding-browser",
      ciphertext: message.ciphertext,
    });
    let replay = false;
    try {
      run("a", {
        op: "process",
        group_id: "padding-browser",
        ciphertext: message.ciphertext,
      });
    } catch {
      replay = true;
    }
    return { plaintext: received.plaintext, replay };
  }, saved);
  expect(result).toEqual({ plaintext: "پس از بارگذاری دوباره", replay: true });
});
