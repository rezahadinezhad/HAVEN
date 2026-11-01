import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
);

test("paged encrypted history: >16 MB, incremental writes, atomic failure, tamper rejection and reload", async ({
  page,
}) => {
  test.setTimeout(180000);
  await page.goto("https://127.0.0.1:8445/__integration__/");
  await page.waitForFunction(() => !!(window as any).havenIntegration);
  const result = await page.evaluate(async () => {
    const h = (window as any).havenIntegration,
      user = crypto.randomUUID(),
      secret = crypto.randomUUID() + crypto.randomUUID();
    const state = {
      v: 1,
      profile: "haven-delivery-v2",
      device_id: crypto.randomUUID(),
      device: {
        label: "Capacity regression",
        identity: "synthetic",
        public_key: "",
      },
      crypto: "preserved-ratchet",
      revision: 1,
      heads: {},
      pins: {},
      cursor: {},
      drafts: {},
      outbox: {},
      events: Array.from({ length: 1000 }, () => ({
        id: crypto.randomUUID(),
        conversation_id: crypto.randomUUID(),
        sender: crypto.randomUUID(),
        time: new Date().toISOString(),
        type: "text",
        text: "x".repeat(20000),
        state: "recipient_synced",
      })),
    };
    await h.saveVault(user, secret, state, 0);
    const db = await h.vaultDB(),
      stored = await h.loadVault(user);
    const original = await h.unseal(secret, user, stored.sealed);
    const keys = original.history_records.map((r: any) => r.key);
    const reopened = await h.openVault(user, secret, stored);
    const next = {
      ...reopened,
      revision: 2,
      drafts: { example: "Small draft" },
    };
    await h.saveVault(user, secret, next, 1);
    const draftManifest = await h.unseal(
      secret,
      user,
      (await h.loadVault(user)).sealed,
    );
    const unchanged = draftManifest.history_records.every(
      (r: any, i: number) => r.key === keys[i],
    );
    let conflict = false;
    try {
      await h.saveVault(user, secret, next, 1);
    } catch {
      conflict = true;
    }
    // Inject failure after a new encrypted record has been queued, before checkpoint write.
    const put = IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put = function (...args: any[]) {
      if (this.name === "vault")
        throw new DOMException("Injected full storage", "QuotaExceededError");
      return put.apply(this, args as any);
    };
    let failed = false;
    const changed = {
      ...next,
      revision: 3,
      events: [
        { ...next.events[0], text: "Must roll back" },
        ...next.events.slice(1),
      ],
    };
    try {
      await h.saveVault(user, secret, changed, 2);
    } catch {
      failed = true;
    } finally {
      IDBObjectStore.prototype.put = put;
    }
    const afterFailure = await h.openVault(
      user,
      secret,
      await h.loadVault(user),
    );
    const countAfterFailure = await db.count("history");
    const record = await db.get("history", [user, keys[0]]);
    const other = await db.get("history", [user, keys[1]]);
    await db.put("history", other, [user, keys[0]]);
    let tamper = false;
    try {
      await h.openVault(user, secret, await h.loadVault(user));
    } catch {
      tamper = true;
    }
    await db.put("history", record, [user, keys[0]]);
    const kit = await h.recoveryKit(user, secret, afterFailure);
    const exported = await h.unseal(
      kit.recovery,
      user,
      JSON.parse(kit.kit).sealed,
    );
    return {
      bytes: new TextEncoder().encode(JSON.stringify(state)).length,
      events: reopened.events.length,
      ratchet: reopened.crypto,
      format: stored.format,
      noInlineHistory: original.events.length === 0,
      unchanged,
      conflict,
      failed,
      failureRevision: afterFailure.revision,
      failureText: afterFailure.events[0].text,
      countAfterFailure,
      tamper,
      exportCount: exported.events.length,
      exportRatchet: exported.crypto,
    };
  });
  expect(result.bytes).toBeGreaterThan(16000000);
  expect(result).toMatchObject({
    events: 1000,
    ratchet: "preserved-ratchet",
    format: 2,
    noInlineHistory: true,
    unchanged: true,
    conflict: true,
    failed: true,
    failureRevision: 2,
    countAfterFailure: 1000,
    tamper: true,
    exportCount: 1000,
    exportRatchet: "",
  });
  expect(result.failureText).toBe("x".repeat(20000));
});

test("real server and MLS: quarantine invalid application content, reload, idle sync, reject bad ciphertext", async ({
  browser,
}) => {
  test.setTimeout(180000);
  const contexts = await Promise.all([0, 1].map(() => browser.newContext()));
  const [a, b] = await Promise.all(contexts.map((c) => c.newPage()));
  try {
    for (const page of [a, b]) {
      await page.goto("https://127.0.0.1:8445/__integration__/");
      await page.waitForFunction(() => !!(window as any).havenIntegration);
    }
    await loginBootstrap(a, credentials);
    const invites = await a.evaluate(async () =>
      Promise.all(
        [0, 1].map(() =>
          (window as any).havenIntegration.api("admin/invitations", "POST", {
            hours: 1,
          }),
        ),
      ),
    );
    for (const [i, page] of [a, b].entries())
      await page.evaluate(
        async ({ token, i }) => {
          const w = window as any,
            h = w.havenIntegration;
          w.u = (
            await h.api("invitations/redeem", "POST", {
              token,
              username: `rg_${crypto.randomUUID().slice(0, 12)}`,
              password: crypto.randomUUID() + crypto.randomUUID(),
              display_name: `Regression ${i}`,
            })
          ).user;
          w.secret = crypto.randomUUID() + crypto.randomUUID();
          w.m = await h.Messenger.create(
            w.u.id,
            w.secret,
            "Regression browser",
          );
        },
        { token: invites[i].token, i },
      );
    const devices = await Promise.all(
      [a, b].map((page) =>
        page.evaluate(async () => {
          const w = window as any;
          return (await w.havenIntegration.api("devices"))[0];
        }),
      ),
    );
    for (const page of [a, b])
      await page.evaluate(async (devices) => {
        const w = window as any;
        for (const d of devices)
          await w.m.pin(
            d,
            await w.havenIntegration.fingerprintOf(d.public_key),
          );
      }, devices);
    const cid = await a.evaluate(async () => (window as any).m.create("group"));
    await a.evaluate(
      async ({ cid, device }) => {
        const w = window as any;
        await w.m.changeMember(
          await w.havenIntegration.api(`conversations/${cid}`),
          device,
          "add",
        );
      },
      { cid, device: devices[1] },
    );
    await b.evaluate(async (cid) => {
      const w = window as any;
      await w.m.sync(await w.havenIntegration.api(`conversations/${cid}`));
    }, cid);
    const send = async (tamper = false) =>
      a.evaluate(
        async ({ cid, tamper }) => {
          const w = window as any,
            h = w.havenIntegration;
          const hash = async (data: Uint8Array) =>
            Array.from(
              new Uint8Array(
                await crypto.subtle.digest("SHA-256", data as any),
              ),
              (x) => x.toString(16).padStart(2, "0"),
            ).join("");
          const events = tamper
            ? ["corrupt"]
            : ["{", JSON.stringify({ invalid: true }), "binding", "valid"];
          for (const input of events) {
            const c = await h.api(`conversations/${cid}`),
              id = crypto.randomUUID();
            const event = {
              id,
              conversation_id: cid,
              sender:
                input === "binding" ? crypto.randomUUID() : w.m.state.device_id,
              time: new Date().toISOString(),
              type: "text",
              text: "A valid message after invalid content",
            };
            const x = await h.cryptoCall(w.m.state.crypto, {
              op: "encrypt",
              group_id: c.group_id,
              plaintext: ["valid", "binding"].includes(input)
                ? JSON.stringify(event)
                : input,
            });
            w.m.state.crypto = x.state;
            const bytes = Uint8Array.from(atob(x.result.ciphertext), (c) =>
              c.charCodeAt(0),
            );
            if (tamper) bytes[bytes.length - 1] ^= 1;
            const ciphertext = btoa(String.fromCharCode(...bytes));
            const header = {
              domain: "haven/envelope/v1",
              v: 1,
              conversation_id: cid,
              group_id: c.group_id,
              sender_device: w.m.state.device_id,
              client_message_id: id,
              epoch: c.epoch,
              seq: c.last_seq + 1,
              previous_hash: c.head_hash,
              ciphertext_hash: await hash(bytes),
              transition: null,
            };
            const canonical = JSON.stringify(
              Object.fromEntries(
                Object.entries(header).sort(([a], [b]) => a.localeCompare(b)),
              ),
            );
            const signature = (
              await h.cryptoCall(w.m.state.crypto, {
                op: "sign",
                payload: btoa(
                  String.fromCharCode(...new TextEncoder().encode(canonical)),
                ),
              })
            ).result.signature;
            await h.api(`conversations/${cid}/messages`, "POST", {
              v: 1,
              client_message_id: id,
              epoch: c.epoch,
              ciphertext,
              header,
              signature,
            });
          }
        },
        { cid, tamper },
      );
    await send();
    const result = await b.evaluate(async (cid) => {
      const w = window as any,
        h = w.havenIntegration;
      await w.m.sync(await h.api(`conversations/${cid}`));
      const before = w.m.state.cursor[cid];
      w.m.lock();
      w.m = await h.Messenger.unlock(w.u.id, w.secret);
      await w.m.sync(await h.api(`conversations/${cid}`));
      return {
        before,
        after: w.m.state.cursor[cid],
        count: w.m.state.rejected_event_count,
        text: w.m.state.events.at(-1).text,
      };
    }, cid);
    expect(result).toMatchObject({
      before: 5,
      after: 5,
      count: 3,
      text: "A valid message after invalid content",
    });
    const requests: string[] = [];
    b.on("request", (r) => {
      if (r.url().includes("/api/")) requests.push(r.url());
    });
    await b.evaluate(async (cid) => {
      const w = window as any,
        c = await w.havenIntegration.api(`conversations/${cid}`);
      await w.m.syncIfChanged(c);
      await w.m.syncIfChanged(c);
    }, cid);
    expect(requests).toHaveLength(1); // caller's detail fetch only, no idle sync I/O
    await send(true);
    const failed = await b.evaluate(async (cid) => {
      const w = window as any;
      let rejected = false;
      try {
        await w.m.sync(await w.havenIntegration.api(`conversations/${cid}`));
      } catch {
        rejected = true;
      }
      return {
        rejected,
        cursor: w.m.state.cursor[cid],
        count: w.m.state.rejected_event_count,
      };
    }, cid);
    expect(failed).toEqual({ rejected: true, cursor: 5, count: 3 });
  } finally {
    await Promise.all(contexts.map((c) => c.close()));
  }
});

test("legacy vault migrates without restoring ratchets; history updates remove old encrypted records", async ({
  page,
}) => {
  await page.goto("https://127.0.0.1:8445/__integration__/");
  await page.waitForFunction(() => !!(window as any).havenIntegration);
  const result = await page.evaluate(async () => {
    const h = (window as any).havenIntegration,
      user = crypto.randomUUID(),
      secret = crypto.randomUUID() + crypto.randomUUID();
    const state = {
      v: 1,
      profile: "haven-delivery-v2",
      device_id: crypto.randomUUID(),
      device: { label: "Legacy", identity: "synthetic", public_key: "" },
      crypto: "original-live-ratchet",
      revision: 1,
      heads: {},
      pins: {},
      cursor: {},
      drafts: {},
      outbox: {},
      events: [
        {
          id: crypto.randomUUID(),
          conversation_id: crypto.randomUUID(),
          sender: crypto.randomUUID(),
          time: new Date().toISOString(),
          type: "text",
          text: "Legacy history",
          state: "recipient_synced",
        },
      ],
    };
    const worker = new Worker("/vault-worker.js");
    const sealed = await new Promise<any>((resolve, reject) => {
      worker.onmessage = (e) =>
        e.data.error ? reject(new Error(e.data.error)) : resolve(e.data.value);
      worker.postMessage({
        id: 1,
        op: "seal",
        scope: user,
        secret,
        value: state,
      });
    });
    worker.terminate();
    const db = await h.vaultDB();
    await db.put("vault", { sealed, revision: 1 }, user);
    const legacy = await h.openVault(user, secret, await h.loadVault(user));
    await h.saveVault(user, secret, { ...legacy, revision: 2 }, 1);
    const first = await h.unseal(
      secret,
      user,
      (await h.loadVault(user)).sealed,
    );
    h.stopVaultWorker();
    const reopened = await h.openVault(user, secret, await h.loadVault(user));
    await h.saveVault(
      user,
      secret,
      {
        ...reopened,
        revision: 3,
        events: [{ ...reopened.events[0], text: "Updated history" }],
      },
      2,
    );
    const current = await h.openVault(user, secret, await h.loadVault(user));
    const removed =
      (await db.get("history", [user, first.history_records[0].key])) ===
      undefined;
    await h.saveVault(user, secret, { ...current, revision: 4, events: [] }, 3);
    const cleared = await h.openVault(user, secret, await h.loadVault(user));
    return {
      legacyText: legacy.events[0].text,
      migrated: (await h.loadVault(user)).format,
      ratchet: cleared.crypto,
      updated: current.events[0].text,
      removed,
      count: await db.count("history"),
      cleared: cleared.events.length,
    };
  });
  expect(result).toEqual({
    legacyText: "Legacy history",
    migrated: 2,
    ratchet: "original-live-ratchet",
    updated: "Updated history",
    removed: true,
    count: 0,
    cleared: 0,
  });
});
