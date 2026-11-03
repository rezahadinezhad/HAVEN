import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
);
test("mutual closure persists complete encrypted archives before consent and survives offline reload", async ({
  browser,
}) => {
  test.setTimeout(180000);
  const contexts = await Promise.all([
    browser.newContext(),
    browser.newContext(),
  ]);
  const pages = await Promise.all(contexts.map((c) => c.newPage()));
  try {
    for (const p of pages) {
      await p.route("**/*", (r) =>
        new URL(r.request().url()).hostname === "127.0.0.1"
          ? r.continue()
          : r.abort(),
      );
      await p.goto("https://127.0.0.1:8445/__integration__/");
      await p.waitForFunction(() => !!(window as any).havenIntegration);
    }
    const [a, b] = pages;
    await loginBootstrap(a, credentials);
    const invitations = await a.evaluate(async () => {
      const h = (window as any).havenIntegration;
      return await Promise.all(
        [0, 1].map(() => h.api("admin/invitations", "POST", { hours: 1 })),
      );
    });
    for (const [i, p] of pages.entries()) {
      await p.evaluate(async (token) => {
        const w = window as any,
          h = w.havenIntegration;
        w.u = (
          await h.api("invitations/redeem", "POST", {
            token,
            username: `close_${crypto.randomUUID().slice(0, 12)}`,
            password: crypto.randomUUID() + crypto.randomUUID(),
            display_name: "Closure test",
          })
        ).user;
        w.secret = crypto.randomUUID() + crypto.randomUUID();
        w.m = await h.Messenger.create(w.u.id, w.secret, "Closure browser");
      }, invitations[i].token);
    }
    const devices = await Promise.all(
      pages.map((p) =>
        p.evaluate(async () => {
          const w = window as any;
          return w.havenIntegration.shareDevice(w.m.state.device_id);
        }),
      ),
    );
    for (const p of pages)
      await p.evaluate(async (ds) => {
        const w = window as any;
        for (const d of ds)
          await w.m.pin(
            d,
            await w.havenIntegration.fingerprintOf(d.public_key),
          );
      }, devices);
    const cid = await a.evaluate(async () =>
      (window as any).m.create("direct", undefined, true),
    );
    const detail = await a.evaluate(
      async ({ cid, device }) => {
        const w = window as any,
          h = w.havenIntegration;
        await w.m.changeMember(
          await h.api(`conversations/${cid}`),
          device,
          "add",
        );
        return h.api(`conversations/${cid}`);
      },
      { cid, device: devices[1] },
    );
    for (const p of pages)
      await p.evaluate(async (c) => {
        const w = window as any;
        w.c = c;
        await w.m.sync(c);
      }, detail);
    for (const [i, p] of pages.entries())
      await p.evaluate(async (i) => {
        const w = window as any;
        await w.m.send(w.c, {
          type: "text",
          text: `Archive private message ${i}`,
        });
      }, i);
    await a.evaluate(async () => {
      const w = window as any;
      await w.m.proposeClosure(w.c);
    });
    // A failed durable save must never submit preparation to the server.
    expect(
      await a.evaluate(async () => {
        const w = window as any,
          h = w.havenIntegration,
          put = IDBObjectStore.prototype.put;
        let rejected = false;
        IDBObjectStore.prototype.put = function (...args) {
          if (this.name === "vault")
            throw new DOMException(
              "Fixture full storage",
              "QuotaExceededError",
            );
          return put.apply(this, args);
        };
        try {
          await w.m.prepareClosure(w.c);
        } catch {
          rejected = true;
        } finally {
          IDBObjectStore.prototype.put = put;
        }
        const r = await h.api(`conversations/${w.c.id}/closure`);
        return (
          rejected &&
          Object.keys(r.preparations).length === 0 &&
          !w.m.state.closure_archives?.[w.c.id]
        );
      }),
    ).toBe(true);
    expect(
      await a.evaluate(async () => {
        const w = window as any,
          original = window.fetch;
        window.fetch = async (...args) => {
          const response = await original(...args);
          if (String(args[0]).includes("closure?action=prepare"))
            throw new TypeError("Fixture response lost after acceptance");
          return response;
        };
        let lost = false;
        try {
          await w.m.prepareClosure(w.c);
        } catch {
          lost = true;
        } finally {
          window.fetch = original;
        }
        const saved = structuredClone(w.m.state.closure_archives[w.c.id]);
        await w.m.prepareClosure(w.c);
        return (
          lost &&
          saved.archive_hash ===
            w.m.state.closure_archives[w.c.id].archive_hash &&
          saved.prepare_request.signature ===
            w.m.state.closure_archives[w.c.id].prepare_request.signature
        );
      }),
    ).toBe(true);
    // A genuine offline queued message must flush before the peer prepares.
    await b.context().setOffline(true);
    expect(
      await b.evaluate(async () => {
        const w = window as any;
        try {
          await w.m.send(w.c, {
            type: "text",
            text: "Final queued peer message",
          });
        } catch {}
        return Object.keys(w.m.state.outbox).length > 0;
      }),
    ).toBe(true);
    await b.context().setOffline(false);
    await b.evaluate(async () => {
      const w = window as any;
      await w.m.prepareClosure(w.c);
    });
    const frozen = await a.evaluate(async () => {
      const w = window as any;
      return w.m.prepareClosure(w.c);
    });
    expect(frozen.state).toBe("closing");
    for (const p of pages)
      expect(
        await p.evaluate(async () => {
          const w = window as any;
          try {
            await w.m.send(w.c, {
              type: "text",
              text: "Forbidden after preparation",
            });
            return false;
          } catch {
            return true;
          }
        }),
      ).toBe(true);
    // Consent also requires a successful encrypted checkpoint before its network request.
    expect(
      await a.evaluate(async () => {
        const w = window as any,
          h = w.havenIntegration,
          put = IDBObjectStore.prototype.put;
        let rejected = false;
        IDBObjectStore.prototype.put = function (...args) {
          if (this.name === "vault")
            throw new DOMException(
              "Fixture full storage",
              "QuotaExceededError",
            );
          return put.apply(this, args);
        };
        try {
          await w.m.consentClosure(w.c);
        } catch {
          rejected = true;
        } finally {
          IDBObjectStore.prototype.put = put;
        }
        return (
          rejected &&
          Object.keys((await h.api(`conversations/${w.c.id}/closure`)).consents)
            .length === 0
        );
      }),
    ).toBe(true);
    await a.evaluate(async () => {
      const w = window as any;
      await w.m.consentClosure(w.c);
    });
    // The second consent finalizes the server, but a failed final-certificate
    // save must withhold the receipt needed by destructive retirement.
    expect(
      await b.evaluate(async () => {
        const w = window as any,
          originalFetch = window.fetch,
          originalPut = IDBObjectStore.prototype.put;
        window.fetch = async (...args) => {
          const response = await originalFetch(...args);
          if (String(args[0]).includes("closure?action=consent")) {
            IDBObjectStore.prototype.put = function (...values) {
              if (this.name === "vault")
                throw new DOMException(
                  "Fixture final certificate save failure",
                  "QuotaExceededError",
                );
              return originalPut.apply(this, values);
            };
          }
          return response;
        };
        let failed = false;
        try {
          await w.m.consentClosure(w.c);
        } catch {
          failed = true;
        } finally {
          IDBObjectStore.prototype.put = originalPut;
          window.fetch = originalFetch;
        }
        const record = await w.havenIntegration.api(
          `conversations/${w.c.id}/closure`,
        );
        return (
          failed &&
          record.state === "finalized" &&
          !record.final_receipts[w.m.state.device_id] &&
          !w.m.state.closure_archives[w.c.id].certificate
        );
      }),
    ).toBe(true);
    expect(
      (
        await b.evaluate(async () => {
          const w = window as any;
          return w.m.refreshClosure(w.c);
        })
      ).state,
    ).toBe("finalized");
    await a.evaluate(async () => {
      const w = window as any;
      await w.m.refreshClosure(w.c);
    });
    expect(
      await a.evaluate(async () => {
        const w = window as any;
        const r = await w.havenIntegration.api(
          `conversations/${w.c.id}/closure`,
        );
        return Object.keys(r.final_receipts).length;
      }),
    ).toBe(2);
    let uiSecret = "";
    for (const p of pages) {
      const saved = await p.evaluate(async () => {
        const w = window as any,
          h = w.havenIntegration;
        const json = await w.m.exportClosureArchive(w.c.id),
          e = JSON.parse(json);
        const restored = await h.unseal(w.secret, e.scope, e.sealed);
        const state = await h.openVault(
          w.u.id,
          w.secret,
          await h.loadVault(w.u.id),
        );
        return {
          json,
          events: restored.archive.events
            .filter((x: any) => x.type === "text")
            .map((x: any) => x.text),
          finalized: restored.archive.certificate.state,
          receipt: state.closure_archives[w.c.id].receipt_confirmed,
        };
      });
      expect(saved.json).not.toContain("Archive private message");
      expect(saved.events).toEqual(
        expect.arrayContaining([
          "Archive private message 0",
          "Archive private message 1",
          "Final queued peer message",
        ]),
      );
      expect(saved.finalized).toBe("finalized");
      expect(saved.receipt).toBe(true);
      const local = await p.evaluate(() => {
        const w = window as any;
        return { u: w.u.id, secret: w.secret, cid: w.c.id };
      });
      if (p === a) uiSecret = local.secret;
      await p.evaluate(async () => {
        await navigator.serviceWorker.register("/sw.js");
        await navigator.serviceWorker.ready;
        if (!navigator.serviceWorker.controller)
          await new Promise<void>((resolve) =>
            navigator.serviceWorker.addEventListener(
              "controllerchange",
              () => resolve(),
              { once: true },
            ),
          );
      });
      await p.reload();
      await p.waitForFunction(() => !!(window as any).havenIntegration);
      expect(
        await p.evaluate(async () => {
          const keys = await caches.keys();
          return (
            !!navigator.serviceWorker.controller &&
            (
              await Promise.all(
                keys.map(
                  async (key) =>
                    !!(await (
                      await caches.open(key)
                    ).match("/vault-worker.js")),
                ),
              )
            ).some(Boolean)
          );
        }),
      ).toBe(true);
      // Playwright routing disables the browser HTTP cache. Restore the normal
      // request path before testing native worker startup through the offline shell.
      await p.unroute("**/*");
      await p.context().setOffline(true);
      expect(
        await p.evaluate(
          async (v) => {
            const w = window as any;
            w.m = await w.havenIntegration.Messenger.unlock(v.u, v.secret);
            const originalCrypto = w.m.state.crypto;
            const authority = JSON.stringify({
              heads: w.m.state.heads,
              pins: w.m.state.pins,
              cursor: w.m.state.cursor,
              outbox: w.m.state.outbox,
            });
            const n = w.m.next();
            delete n.closure_archives[v.cid];
            await w.m.persist(n);
            let wrongSecretRejected = false;
            try {
              await w.m.importClosureArchive(
                v.exported,
                "incorrect archive passphrase",
              );
            } catch {
              wrongSecretRejected = true;
            }
            await w.m.importClosureArchive(v.exported, v.secret);
            const unchanged =
              originalCrypto === w.m.state.crypto &&
              authority ===
                JSON.stringify({
                  heads: w.m.state.heads,
                  pins: w.m.state.pins,
                  cursor: w.m.state.cursor,
                  outbox: w.m.state.outbox,
                });
            const texts = w.m
              .closedHistory(v.cid)
              .filter((x: any) => x.type === "text")
              .map((x: any) => x.text);
            w.m.lock();
            let denied = false;
            try {
              w.m.closedHistory(v.cid);
            } catch {
              denied = true;
            }
            return (
              texts.length === 3 &&
              denied &&
              !w.m.state.closure_archives &&
              unchanged &&
              wrongSecretRejected
            );
          },
          { ...local, exported: saved.json },
        ),
      ).toBe(true);
      await p.context().setOffline(false);
    }
    await a.goto("https://127.0.0.1:8445/");
    await a.getByRole("button", { name: "Start a chat", exact: true }).click();
    await a.getByLabel("Unlock passphrase", { exact: true }).fill(uiSecret);
    await a
      .getByRole("button", { name: "Unlock and continue", exact: true })
      .click();
    await expect(
      a.getByRole("button", { name: "Lock vault", exact: true }),
    ).toBeVisible();
    await a.getByRole("button", { name: "Messages", exact: true }).click();
    await a.locator(".conversation-row").first().click();
    await expect(
      a.getByRole("button", { name: "Add attachment", exact: true }),
    ).toBeDisabled();
    await expect(
      a.getByRole("button", { name: "Record voice note", exact: true }),
    ).toBeDisabled();
    await a.getByRole("button", { name: "Chat details", exact: true }).click();
    await expect(
      a.getByRole("region", { name: "Mutual conversation closure" }),
    ).toContainText("Finalized");
    await a.screenshot({
      path: "../../docs/security/conversation-closure/evidence/closure-en.png",
      fullPage: true,
    });
    await a.getByRole("button", { name: "Recovery kit", exact: true }).click();
    await expect(
      a.getByRole("heading", {
        name: "Closed conversation archives",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      a.getByRole("heading", {
        name: "Restore a closed conversation archive",
        exact: true,
      }),
    ).toBeVisible();
    await a.getByRole("button", { name: "فارسی", exact: true }).click();
    await expect(
      a.getByRole("heading", {
        name: "بایگانی گفتگوهای بسته‌شده",
        exact: true,
      }),
    ).toBeVisible();
    await a
      .getByRole("heading", { name: "بایگانی گفتگوهای بسته‌شده", exact: true })
      .scrollIntoViewIfNeeded();
    await a.screenshot({
      path: "../../docs/security/conversation-closure/evidence/archives-fa.png",
      fullPage: true,
    });
  } finally {
    for (const c of contexts) await c.close();
  }
});
