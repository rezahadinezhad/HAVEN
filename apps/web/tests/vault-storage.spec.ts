import { test, expect } from "./fixtures";

test("vault key rotation reencrypts every history record and never reuses records sealed with an old secret", async ({
  page,
}) => {
  await page.goto("https://127.0.0.1:8445/__integration__/");
  await page.waitForFunction(() => !!(window as any).havenIntegration);
  const result = await page.evaluate(async () => {
    const h = (window as any).havenIntegration,
      user = crypto.randomUUID(),
      secret = crypto.randomUUID() + crypto.randomUUID(),
      fresh = crypto.randomUUID() + crypto.randomUUID();
    const state = {
      v: 1,
      profile: "haven-delivery-v2",
      device_id: crypto.randomUUID(),
      device: { label: "Rotation", identity: "synthetic", public_key: "" },
      crypto: "preserved-ratchet",
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
          text: "Preserved history",
          state: "recipient_synced",
        },
      ],
    };
    await h.saveVault(user, secret, state, 0);
    const old = await h.unseal(secret, user, (await h.loadVault(user)).sealed);
    await h.saveVault(user, fresh, { ...state, revision: 2 }, 1);
    const current = await h.loadVault(user),
      opened = await h.openVault(user, fresh, current);
    let rejected = false;
    try {
      await h.openVault(user, secret, current);
    } catch {
      rejected = true;
    }
    const db = await h.vaultDB();
    return {
      rejected,
      ratchet: opened.crypto,
      text: opened.events[0].text,
      oldGone:
        (await db.get("history", [user, old.history_records[0].key])) ===
        undefined,
      records: await db.count("history"),
    };
  });
  expect(result).toEqual({
    rejected: true,
    ratchet: "preserved-ratchet",
    text: "Preserved history",
    oldGone: true,
    records: 1,
  });
});

test("API conversation helper follows all continuation headers and preserves the array contract", async ({
  page,
}) => {
  await page.goto("https://127.0.0.1:8445/__integration__/");
  await page.waitForFunction(() => !!(window as any).havenIntegration);
  let requests = 0;
  await page.route("**/api/v1/conversations*", async (route) => {
    const offset = Number(
      new URL(route.request().url()).searchParams.get("cursor") || 0,
    );
    requests++;
    const rows = Array.from(
      { length: Math.min(100, 205 - offset) },
      (_, i) => ({
        id: String(offset + i),
        kind: "group",
        group_id: String(offset + i),
        epoch: 0,
        last_seq: 0,
        status: "active",
        head_hash: "",
        receipt_version: 0,
      }),
    );
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers:
        offset + 100 < 205
          ? { "X-Haven-Next-Cursor": String(offset + 100) }
          : {},
      body: JSON.stringify(rows),
    });
  });
  const rows = await page.evaluate(async () =>
    (window as any).havenIntegration.api("conversations"),
  );
  expect(rows).toHaveLength(205);
  expect(new Set(rows.map((x: any) => x.id)).size).toBe(205);
  expect(requests).toBe(3);
});

test("locking while a save awaits storage or hashing cannot recreate a secret-bearing worker", async ({
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
      device: { label: "Cancellation", identity: "synthetic", public_key: "" },
      crypto: "preserved-ratchet",
      revision: 1,
      heads: {},
      pins: {},
      cursor: {},
      drafts: {},
      outbox: {},
      events: [],
    };
    await h.saveVault(user, secret, state, 0);
    const WorkerClass = window.Worker,
      originalDigest = crypto.subtle.digest.bind(crypto.subtle);
    let workers = 0,
      release!: () => void,
      entered!: () => void;
    const reached = new Promise<void>((r) => (entered = r)),
      gate = new Promise<void>((r) => (release = r));
    window.Worker = new Proxy(WorkerClass, {
      construct(target, args) {
        workers++;
        return Reflect.construct(target, args);
      },
    });
    crypto.subtle.digest = (async (...args: any[]) => {
      entered();
      await gate;
      return originalDigest(...(args as [any, any]));
    }) as any;
    const saving = h
      .saveVault(
        user,
        secret,
        { ...state, revision: 2, drafts: { test: "Must not persist" } },
        1,
      )
      .then(
        () => false,
        () => true,
      );
    await reached;
    h.stopVaultWorker();
    release();
    const rejected = await saving;
    crypto.subtle.digest = originalDigest;
    window.Worker = WorkerClass;
    const revision = (await h.loadVault(user)).revision;
    // Also cancel a save that is queued behind another Web Lock holder.
    let unlock!: () => void, acquired!: () => void;
    const held = new Promise<void>((r) => (acquired = r)),
      wait = new Promise<void>((r) => (unlock = r));
    const holding = navigator.locks.request("haven-vault:" + user, async () => {
      acquired();
      await wait;
    });
    await held;
    const queued = h.saveVault(user, secret, { ...state, revision: 2 }, 1).then(
      () => false,
      () => true,
    );
    h.stopVaultWorker();
    unlock();
    await holding;
    const queuedRejected = await queued;
    return {
      rejected,
      workers,
      revision,
      queuedRejected,
      finalRevision: (await h.loadVault(user)).revision,
    };
  });
  expect(result).toEqual({
    rejected: true,
    workers: 0,
    revision: 1,
    queuedRejected: true,
    finalRevision: 1,
  });
});
