import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
);
test("browser MLS → Django/PostgreSQL: verified group, bidirectional delivery, durable retry, media, removal and reload", async ({
  browser,
}) => {
  test.setTimeout(180000);
  const contexts = await Promise.all([0, 1, 2].map(() => browser.newContext()));
  const pages = await Promise.all(contexts.map((c) => c.newPage()));
  const foreign: string[] = [];
  for (const page of pages) {
    await page.route("**/*", (route) =>
      new URL(route.request().url()).hostname === "127.0.0.1"
        ? route.continue()
        : route.abort(),
    );
    page.on("request", (r) => {
      if (new URL(r.url()).hostname !== "127.0.0.1") foreign.push(r.url());
    });
    await page.goto("https://127.0.0.1:8445/__integration__/");
    await page.waitForFunction(() => !!(window as any).havenIntegration);
  }
  const [a, b, c] = pages;
  await loginBootstrap(a, credentials);
  const invites = await a.evaluate(async () => {
    const h = (window as any).havenIntegration;
    return Promise.all(
      [0, 1, 2].map(() => h.api("admin/invitations", "POST", { hours: 1 })),
    );
  });
  for (const [i, p] of pages.entries())
    await p.evaluate(
      async ({ token, i }) => {
        const h = (window as any).havenIntegration;
        const x = await h.api("invitations/redeem", "POST", {
          token,
          username: `it_${crypto.randomUUID().slice(0, 12)}`,
          password: ((window as any).accountPassword =
            crypto.randomUUID() + crypto.randomUUID()),
          display_name: `Integration ${i}`,
        });
        (window as any).u = x.user;
      },
      { token: invites[i].token, i },
    );
  for (const p of pages)
    await p.evaluate(async () => {
      const w = window as any,
        h = w.havenIntegration;
      w.secret = crypto.randomUUID() + crypto.randomUUID();
      w.m = await h.Messenger.create(w.u.id, w.secret, "Integration browser");
    });
  const devices = await Promise.all(
    pages.map((p) =>
      p.evaluate(async () => {
        const w = window as any;
        return (await w.havenIntegration.api("devices")).find(
          (d: any) => d.id === w.m.state.device_id,
        );
      }),
    ),
  );
  for (const p of pages)
    await p.evaluate(async (devices) => {
      const w = window as any;
      for (const d of devices)
        await w.m.pin(d, await w.havenIntegration.fingerprintOf(d.public_key));
    }, devices);
  const directID = await a.evaluate(async () =>
    (window as any).m.create("direct"),
  );
  let direct = await a.evaluate(
    async (id) => (window as any).havenIntegration.api(`conversations/${id}`),
    directID,
  );
  await a.evaluate(
    async ({ detail, device }) =>
      (window as any).m.changeMember(detail, device, "add"),
    { detail: direct, device: devices[1] },
  );
  direct = await a.evaluate(
    async (id) => (window as any).havenIntegration.api(`conversations/${id}`),
    directID,
  );
  await b.evaluate(async (detail) => (window as any).m.sync(detail), direct);
  await a.evaluate(
    async (detail) =>
      (window as any).m.send(detail, {
        type: "text",
        text: "Private direct conversation",
      }),
    direct,
  );
  direct = await a.evaluate(
    async (id) => (window as any).havenIntegration.api(`conversations/${id}`),
    directID,
  );
  await b.evaluate(async (detail) => (window as any).m.sync(detail), direct);
  expect(
    await b.evaluate(() => (window as any).m.state.events.at(-1).text),
  ).toBe("Private direct conversation");
  const cid = await a.evaluate(async () => {
    const w = window as any;
    return w.m.create("group");
  });
  const conv = () =>
    a.evaluate(async (cid) => {
      const w = window as any;
      return w.havenIntegration.api(`conversations/${cid}`);
    }, cid);
  let detail = await conv();
  await a.evaluate(
    async ({ detail, device }) =>
      (window as any).m.changeMember(detail, device, "add"),
    { detail, device: devices[1] },
  );
  detail = await conv();
  await b.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  await a.evaluate(
    async ({ detail, device }) =>
      (window as any).m.changeMember(detail, device, "add"),
    { detail, device: devices[2] },
  );
  detail = await conv();
  for (const p of [b, c])
    await p.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  expect(
    await a.evaluate(async () => {
      const w = window as any,
        original = navigator.locks.request.bind(navigator.locks);
      let rejected = false;
      navigator.locks.request = async (...args: any[]) => {
        const result = await (original as any)(...args);
        w.m.lock();
        return result;
      };
      try {
        await w.m.draft("lock-race-test", "encrypted draft survives locking");
      } catch {
        rejected = true;
      } finally {
        navigator.locks.request = original;
      }
      const cleared =
        !w.m.state.crypto &&
        !w.m.state.events.length &&
        !Object.keys(w.m.state.outbox).length;
      w.m = await w.havenIntegration.Messenger.unlock(w.u.id, w.secret);
      return (
        rejected &&
        cleared &&
        w.m.state.drafts["lock-race-test"] ===
          "encrypted draft survives locking"
      );
    }),
  ).toBe(true);
  expect(
    await a.evaluate(async (detail) => {
      const w = window as any,
        state = w.m.state.crypto,
        revision = w.m.state.revision,
        original = IDBObjectStore.prototype.put;
      let rejected = false;
      IDBObjectStore.prototype.put = function (...args) {
        if (this.name === "vault")
          throw new DOMException(
            "Simulated full storage",
            "QuotaExceededError",
          );
        return original.apply(this, args);
      };
      try {
        await w.m.send(detail, {
          type: "text",
          text: "Must not leave the device",
        });
      } catch {
        rejected = true;
      } finally {
        IDBObjectStore.prototype.put = original;
      }
      return (
        rejected &&
        state === w.m.state.crypto &&
        revision === w.m.state.revision
      );
    }, detail),
  ).toBe(true);
  // Explicit opt-in emits scoped reachability hints over the actual authenticated WSS/Redis path.
  for (const p of [a, b])
    await p.evaluate(async (cid) => {
      const w = window as any;
      w.presenceReceived = false;
      w.stopPresence = w.havenIntegration.connectionLoop(
        async () => {},
        () => {},
        undefined,
        {
          conversation: () => cid,
          received: (id: string) => {
            if (id === cid) w.presenceReceived = true;
          },
        },
      );
    }, cid);
  for (const p of [a, b])
    await p.waitForFunction(
      () => (window as any).presenceReceived,
      {},
      { timeout: 30000 },
    );
  for (const p of [a, b])
    await p.evaluate(() => (window as any).stopPresence());
  await a.evaluate(
    async (detail) =>
      (window as any).m.send(detail, {
        type: "text",
        text: "E2EE integration سلام",
      }),
    detail,
  );
  detail = await conv();
  for (const p of [b, c])
    await p.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  expect(
    await b.evaluate(() => (window as any).m.state.events.at(-1).text),
  ).toBe("E2EE integration سلام");
  await a.evaluate(
    async (detail) =>
      (window as any).m.send(detail, { type: "text", text: "snapshot-first" }),
    detail,
  );
  const snapshot = await conv();
  await a.evaluate(
    async (detail) =>
      (window as any).m.send(detail, { type: "text", text: "snapshot-next" }),
    snapshot,
  );
  detail = await conv();
  const snapshotRead = await b.evaluate(async (snapshot) => {
    const w = window as any,
      original = window.fetch.bind(window);
    window.fetch = async (...args) =>
      String(args[0]) === `/api/v1/conversations/${snapshot.id}`
        ? new Response(JSON.stringify(snapshot), {
            status: 200,
            headers: { "content-type": "application/json" },
          })
        : original(...args);
    try {
      await w.m.sync(snapshot);
      return {
        last: w.m.state.events.at(-1).text,
        seq: w.m.state.heads[snapshot.id].seq,
      };
    } finally {
      window.fetch = original;
    }
  }, snapshot);
  expect(snapshotRead).toEqual({
    last: "snapshot-first",
    seq: snapshot.last_seq,
  });
  for (const p of [b, c])
    await p.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  expect(
    await b.evaluate(async (detail) => {
      const w = window as any,
        original = window.fetch.bind(window);
      let proofs = 0;
      window.fetch = async (...args) => {
        if (String(args[0]).includes("/proofs?")) proofs++;
        return original(...args);
      };
      try {
        await w.m.sync(detail);
        return proofs;
      } finally {
        window.fetch = original;
      }
    }, detail),
  ).toBe(0);
  await b.evaluate(
    async (detail) =>
      (window as any).m.send(detail, {
        type: "text",
        text: "reply from second device",
      }),
    detail,
  );
  detail = await conv();
  await a.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  expect(
    await a.evaluate(() => (window as any).m.state.events.at(-1).text),
  ).toBe("reply from second device");
  // Drop the first HTTP ACK after the database has accepted it. Retry must preserve ciphertext and deduplicate.
  await a.evaluate(() => {
    const w = window as any,
      original = window.fetch.bind(window);
    let dropped = false;
    w.originalFetch = original;
    window.fetch = async (...args) => {
      const response = await original(...args);
      if (
        !dropped &&
        String(args[0]).endsWith("/messages") &&
        args[1]?.method === "POST"
      ) {
        dropped = true;
        throw new TypeError("Simulated lost ACK");
      }
      return response;
    };
  });
  await a.evaluate(
    async (detail) =>
      (window as any).m.send(detail, {
        type: "text",
        text: "one durable send",
      }),
    detail,
  );
  expect(
    await a.evaluate(() => Object.keys((window as any).m.state.outbox).length),
  ).toBe(1);
  await a.evaluate(() => {
    window.fetch = (window as any).originalFetch;
  });
  await a.evaluate(async () => {
    await (window as any).m.flush();
  });
  detail = await conv();
  await b.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  expect(
    await b.evaluate(
      () =>
        (window as any).m.state.events.filter(
          (e: any) => e.text === "one durable send",
        ).length,
    ),
  ).toBe(1);
  const file = await a.evaluate(
    async ({ cid, detail }) => {
      const w = window as any;
      const f = new File([new Uint8Array(700000).fill(173)], "secret-name.bin");
      const meta = await w.m.prepareAttachment(
        f,
        cid,
        new AbortController().signal,
      );
      // The encrypted vault and ciphertext chunks must survive a restart before the first upload.
      w.m.lock();
      w.m = await w.havenIntegration.Messenger.unlock(w.u.id, w.secret);
      await w.m.resumeAttachment(
        meta.id,
        () => {},
        new AbortController().signal,
      );
      await w.m.send(detail, { type: "file", file: meta });
      await w.m.finishAttachment(meta.id);
      return meta;
    },
    { cid, detail },
  );
  detail = await conv();
  await b.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  const received = await b.evaluate(
    () => (window as any).m.state.events.at(-1).file,
  );
  expect(
    Object.keys(file).every((k) => received[k] === file[k]) &&
      Object.keys(received).length === Object.keys(file).length,
  ).toBe(true);
  expect(
    await b.evaluate(async (meta) => {
      const w = window as any,
        original = window.fetch.bind(window);
      let interrupted = false,
        requestedZero = false;
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith("/chunks/1"))
          throw new TypeError("Temporary download disconnection");
        return original(...args);
      };
      try {
        await w.havenIntegration.downloadDecrypt(meta);
      } catch {
        interrupted = true;
      } finally {
        window.fetch = original;
      }
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith("/chunks/0")) requestedZero = true;
        return original(...args);
      };
      try {
        const blob = await w.havenIntegration.downloadDecrypt(meta);
        return interrupted && !requestedZero && blob.size === meta.size;
      } finally {
        window.fetch = original;
      }
    }, received),
  ).toBe(true);
  const media = await b.evaluate(async (meta) => {
    const w = window as any;
    const blob = await w.havenIntegration.downloadDecrypt(meta);
    return {
      size: blob.size,
      first: new Uint8Array(await blob.arrayBuffer())[0],
    };
  }, received);
  expect(media).toEqual({ size: 700000, first: 173 });
  // Wrong file nonce/key and modified ciphertext must fail before a Blob is returned.
  expect(
    await b.evaluate(async () => {
      const w = window as any,
        meta = w.m.state.events.at(-1).file;
      let failures = 0;
      for (const changed of [
        { ...meta, prefix: btoa(String.fromCharCode(...new Uint8Array(16))) },
        { ...meta, key: btoa(String.fromCharCode(...new Uint8Array(32))) },
      ]) {
        try {
          await w.havenIntegration.downloadDecrypt(changed);
        } catch {
          failures++;
        }
      }
      const original = window.fetch.bind(window);
      window.fetch = async (...args) => {
        const r = await original(...args);
        if (String(args[0]).includes("/chunks/")) {
          const bytes = new Uint8Array(await r.arrayBuffer());
          bytes[0] ^= 1;
          return new Response(bytes);
        }
        return r;
      };
      try {
        await w.havenIntegration.downloadDecrypt(meta);
      } catch {
        failures++;
      } finally {
        window.fetch = original;
      }
      return failures;
    }),
  ).toBe(3);
  // A lost commit ACK leaves the old active epoch intact; explicit reconciliation adopts only the exact accepted candidate.
  const lostCommit = await a.evaluate(async (detail) => {
    const w = window as any,
      original = window.fetch.bind(window),
      before = w.m.state.crypto;
    window.fetch = async (...args) => {
      const r = await original(...args);
      if (
        String(args[0]).endsWith("/crypto-events") &&
        args[1]?.method === "POST"
      )
        throw new TypeError("Simulated lost commit ACK");
      return r;
    };
    try {
      await w.m.changeMember(
        detail,
        { ...w.m.state.device, id: w.m.state.device_id, user_id: w.u.id },
        "update",
      );
    } catch {
    } finally {
      window.fetch = original;
    }
    const unchanged = before === w.m.state.crypto,
      pending = Object.keys(w.m.state.outbox).length;
    await w.m.cancelPendingControl(detail);
    return {
      unchanged,
      pending,
      remaining: Object.keys(w.m.state.outbox).length,
      advanced: before !== w.m.state.crypto,
    };
  }, detail);
  expect(lostCommit).toEqual({
    unchanged: true,
    pending: 1,
    remaining: 0,
    advanced: true,
  });
  detail = await conv();
  for (const p of [b, c])
    await p.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  // An additional device has a distinct credential, needs a verified existing-device signature and gets no old plaintext.
  const extraContext = await browser.newContext(),
    extra = await extraContext.newPage();
  await extra.goto("https://127.0.0.1:8445/__integration__/");
  await extra.waitForFunction(() => !!(window as any).havenIntegration);
  const account = await b.evaluate(() => ({
    username: (window as any).u.username,
    password: (window as any).accountPassword,
  }));
  await extra.evaluate(async (account) => {
    const w = window as any,
      h = w.havenIntegration;
    w.u = (await h.api("auth/login", "POST", account)).user;
    w.secret = crypto.randomUUID() + crypto.randomUUID();
    w.m = await h.Messenger.create(
      w.u.id,
      w.secret,
      "Additional verified device",
    );
  }, account);
  const extraDevice = await extra.evaluate(async () =>
    (await (window as any).havenIntegration.api("devices")).find(
      (d: any) => d.id === (window as any).m.state.device_id,
    ),
  );
  expect(extraDevice.trust_state).toBe("pending");
  expect(
    await extra.evaluate(async () => {
      try {
        await (window as any).m.package();
        return false;
      } catch {
        return true;
      }
    }),
  ).toBe(true);
  await b.evaluate(async (d) => {
    const w = window as any;
    await w.m.pin(d, await w.havenIntegration.fingerprintOf(d.public_key));
    await w.m.approve(d);
  }, extraDevice);
  await extra.evaluate(async () => {
    const w = window as any;
    await w.m.connect();
    await w.m.package();
  });
  for (const p of pages)
    await p.evaluate(async (d) => {
      const w = window as any;
      await w.m.pin(d, await w.havenIntegration.fingerprintOf(d.public_key));
    }, extraDevice);
  await extra.evaluate(async (devices) => {
    const w = window as any;
    for (const d of devices)
      await w.m.pin(d, await w.havenIntegration.fingerprintOf(d.public_key));
  }, devices);
  await a.evaluate(
    async ({ detail, device }) =>
      (window as any).m.changeMember(detail, device, "add"),
    { detail, device: extraDevice },
  );
  detail = await conv();
  for (const p of [b, c, extra])
    await p.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  expect(
    await extra.evaluate(() => (window as any).m.state.events.length),
  ).toBe(0);
  await a.evaluate(
    async (detail) =>
      (window as any).m.send(detail, {
        type: "text",
        text: "Both devices receive this epoch",
      }),
    detail,
  );
  detail = await conv();
  for (const p of [b, extra]) {
    await p.evaluate(async (detail) => (window as any).m.sync(detail), detail);
    expect(
      await p.evaluate(() => (window as any).m.state.events.at(-1).text),
    ).toBe("Both devices receive this epoch");
  }
  await extraContext.close();
  await a.evaluate(
    async ({ detail, device }) =>
      (window as any).m.changeMember(detail, device, "remove"),
    { detail, device: extraDevice },
  );
  detail = await conv();
  for (const p of [b, c])
    await p.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  await a.evaluate(
    async ({ detail, device }) =>
      (window as any).m.changeMember(detail, device, "role", "moderator"),
    { detail, device: devices[1] },
  );
  detail = await conv();
  for (const p of [b, c])
    await p.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  // Two authorized committers: reject the stale candidate, adopt the accepted peer commit, require an explicit retry.
  await a.evaluate(async (detail) => {
    const w = window as any,
      original = window.fetch.bind(window);
    window.fetch = async (...args) => {
      if (
        String(args[0]).endsWith("/crypto-events") &&
        args[1]?.method === "POST"
      )
        throw new TypeError("Hold candidate before delivery");
      return original(...args);
    };
    try {
      await w.m.changeMember(
        detail,
        { ...w.m.state.device, id: w.m.state.device_id, user_id: w.u.id },
        "update",
      );
    } catch {
    } finally {
      window.fetch = original;
    }
  }, detail);
  await b.evaluate(async (detail) => {
    const w = window as any;
    await w.m.changeMember(
      detail,
      { ...w.m.state.device, id: w.m.state.device_id, user_id: w.u.id },
      "update",
    );
  }, detail);
  expect(
    await a.evaluate(async () => {
      const w = window as any;
      let warned = false;
      try {
        await w.m.flush();
      } catch (e) {
        warned = String(e).includes("Review the updated roster");
      }
      return warned && Object.keys(w.m.state.outbox).length === 0;
    }),
  ).toBe(true);
  detail = await conv();
  for (const p of [a, b, c])
    await p.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  // Device revocation fences application writes but must still allow an authorized removal commit.
  await c.evaluate(
    async (device) =>
      (window as any).havenIntegration.api(
        `devices/${device.id}/revoke`,
        "POST",
        {},
      ),
    devices[2],
  );
  await a.evaluate(
    async ({ detail, device }) =>
      (window as any).m.changeMember(detail, device, "remove"),
    { detail, device: devices[2] },
  );
  detail = await conv();
  await b.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  await a.evaluate(
    async (detail) =>
      (window as any).m.send(detail, { type: "text", text: "after removal" }),
    detail,
  );
  const removed = await c.evaluate(async (cid) => {
    try {
      await (window as any).havenIntegration.api(
        `conversations/${cid}/messages`,
      );
      return false;
    } catch {
      return true;
    }
  }, cid);
  expect(removed).toBe(true);
  await b.evaluate(async () => {
    const w = window as any;
    w.m.lock();
    w.m = await w.havenIntegration.Messenger.unlock(w.u.id, w.secret);
  });
  detail = await conv();
  await b.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  expect(
    await b.evaluate(() => (window as any).m.state.events.at(-1).text),
  ).toBe("after removal");
  // Signed-history tampering is rejected without advancing the encrypted checkpoint.
  const tamper = await b.evaluate(async (detail) => {
    const w = window as any,
      old = window.fetch.bind(window),
      rev = w.m.state.revision;
    // Exercise the full-verification path used to upgrade older v2 checkpoint metadata.
    delete w.m.state.heads[detail.id].genesis_hash;
    window.fetch = async (...args) => {
      const r = await old(...args);
      if (String(args[0]).includes("/proofs?")) {
        const value = await r.json();
        if (value.proofs.length)
          value.proofs[0].header.previous_hash = "0".repeat(64);
        return new Response(JSON.stringify(value), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return r;
    };
    let rejected = false;
    try {
      await w.m.sync(detail);
    } catch {
      rejected = true;
    } finally {
      window.fetch = old;
    }
    return { rejected, unchanged: w.m.state.revision === rev };
  }, detail);
  expect(tamper).toEqual({ rejected: true, unchanged: true });
  expect(
    await b.evaluate(async (detail) => {
      const w = window as any,
        before = w.m.state.crypto;
      await w.m.sync(detail);
      return (
        before === w.m.state.crypto && !!w.m.state.heads[detail.id].genesis_hash
      );
    }, detail),
  ).toBe(true);
  expect(
    await b.evaluate(async (detail) => {
      const w = window as any,
        original = window.fetch.bind(window),
        revision = w.m.state.revision;
      window.fetch = async (...args) => {
        const r = await original(...args);
        if (String(args[0]) === `/api/v1/conversations/${detail.id}`) {
          const body = await r.json();
          body.head_hash = "0".repeat(64);
          return new Response(JSON.stringify(body), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        }
        return r;
      };
      let rejected = false;
      try {
        await w.m.sync(detail);
      } catch {
        rejected = true;
      } finally {
        window.fetch = original;
      }
      return rejected && w.m.state.revision === revision;
    }, detail),
  ).toBe(true);

  // Recover a saved history kit into fresh MLS keys. Server password alone is not used to decrypt it.
  const kit = await b.evaluate(async () => {
    const w = window as any;
    await w.m.provisionRecovery();
    const kit = await w.havenIntegration.recoveryKit(
      w.u.id,
      w.secret,
      w.m.state,
    );
    return { ...kit, user: w.u.id, oldDevice: w.m.state.device_id };
  });
  const rc = await browser.newContext(),
    rp = await rc.newPage();
  await rp.goto("https://127.0.0.1:8445/__integration__/");
  await rp.waitForFunction(() => !!(window as any).havenIntegration);
  const recovered = await rp.evaluate(async (kit) => {
    const w = window as any,
      h = w.havenIntegration,
      parsed = JSON.parse(kit.kit),
      history = await h.unseal(kit.recovery, kit.user, parsed.sealed);
    w.m = await h.Messenger.recover(
      kit.user,
      crypto.randomUUID() + crypto.randomUUID(),
      history,
      crypto.randomUUID() + crypto.randomUUID(),
      "Recovered test browser",
    );
    const devices = await h.api("devices");
    return {
      device: devices.find((d: any) => d.id === w.m.state.device_id),
      oldRevoked: devices.find((d: any) => d.id === kit.oldDevice).trust_state,
      heads: Object.keys(w.m.state.heads).length,
      history: w.m.state.events.length,
    };
  }, kit);
  expect(recovered.oldRevoked).toBe("revoked");
  expect(recovered.heads).toBe(0);
  expect(recovered.history).toBeGreaterThan(0);
  await a.evaluate(async (device) => {
    const w = window as any;
    await w.m.pin(
      device,
      await w.havenIntegration.fingerprintOf(device.public_key),
    );
  }, recovered.device);
  detail = await conv();
  await a.evaluate(
    async ({ detail, device }) =>
      (window as any).m.changeMember(detail, device, "remove"),
    { detail, device: devices[1] },
  );
  detail = await conv();
  await a.evaluate(
    async ({ detail, device }) =>
      (window as any).m.changeMember(detail, device, "add"),
    { detail, device: recovered.device },
  );
  detail = await conv();
  await rp.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  await a.evaluate(
    async (detail) =>
      (window as any).m.send(detail, {
        type: "text",
        text: "fresh device after security reset",
      }),
    detail,
  );
  detail = await conv();
  await rp.evaluate(async (detail) => (window as any).m.sync(detail), detail);
  expect(
    await rp.evaluate(() => (window as any).m.state.events.at(-1).text),
  ).toBe("fresh device after security reset");
  // A brand-new account can verify removed/revoked historical signers without gaining their old ciphertext.
  const newcomerContext = await browser.newContext(),
    newcomer = await newcomerContext.newPage();
  await newcomer.goto("https://127.0.0.1:8445/__integration__/");
  await newcomer.waitForFunction(() => !!(window as any).havenIntegration);
  await loginBootstrap(newcomer, credentials);
  await newcomer.evaluate(async (credentials) => {
    const w = window as any,
      h = w.havenIntegration;
    const invite = await h.api("admin/invitations", "POST", { hours: 1 });
    w.u = (
      await h.api("invitations/redeem", "POST", {
        token: invite.token,
        username: "new_" + crypto.randomUUID().slice(0, 12),
        password: crypto.randomUUID() + crypto.randomUUID(),
        display_name: "New after revocation",
      })
    ).user;
    w.secret = crypto.randomUUID() + crypto.randomUUID();
    w.m = await h.Messenger.create(w.u.id, w.secret, "New after revocation");
  }, credentials);
  const newcomerDevice = await newcomer.evaluate(async () => {
    const w = window as any;
    return (await w.havenIntegration.api("devices")).find(
      (d: any) => d.id === w.m.state.device_id,
    );
  });
  for (const p of [a, rp])
    await p.evaluate(async (d) => {
      const w = window as any;
      await w.m.pin(d, await w.havenIntegration.fingerprintOf(d.public_key));
    }, newcomerDevice);
  await newcomer.evaluate(
    async (devices) => {
      const w = window as any;
      for (const d of devices)
        await w.m.pin(d, await w.havenIntegration.fingerprintOf(d.public_key));
    },
    [devices[0], recovered.device],
  );
  detail = await conv();
  await a.evaluate(
    async ({ detail, device }) =>
      (window as any).m.changeMember(detail, device, "add"),
    { detail, device: newcomerDevice },
  );
  detail = await conv();
  expect(
    await newcomer.evaluate(async (detail) => {
      const w = window as any,
        revision = w.m.state.revision;
      let rejected = false;
      try {
        await w.m.sync(detail);
      } catch (e) {
        rejected = String(e).includes("Verify device fingerprint");
      }
      return rejected && w.m.state.revision === revision;
    }, detail),
  ).toBe(true);
  for (const known of [devices[1], devices[2], extraDevice]) {
    expect(
      await newcomer.evaluate(async (known) => {
        const w = window as any,
          actual = (
            await w.havenIntegration.api(`crypto/key-packages/${known.id}`)
          ).device;
        if (actual.public_key !== known.public_key) return false;
        await w.m.pin(
          actual,
          await w.havenIntegration.fingerprintOf(known.public_key),
        );
        return true;
      }, known),
    ).toBe(true);
  }
  await newcomer.evaluate(
    async (detail) => (window as any).m.sync(detail),
    detail,
  );
  expect(
    await newcomer.evaluate(() => (window as any).m.state.events.length),
  ).toBe(0);
  await a.evaluate(
    async (detail) =>
      (window as any).m.send(detail, {
        type: "text",
        text: "New member verified historical signers",
      }),
    detail,
  );
  detail = await conv();
  await newcomer.evaluate(
    async (detail) => (window as any).m.sync(detail),
    detail,
  );
  expect(
    await newcomer.evaluate(() => (window as any).m.state.events.at(-1).text),
  ).toBe("New member verified historical signers");
  await newcomerContext.close();
  await rc.close();
  expect(foreign).toEqual([]);
  for (const context of contexts) await context.close();
});
