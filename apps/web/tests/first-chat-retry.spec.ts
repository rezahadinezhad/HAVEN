import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
import https from "node:https";
const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
);
const origin = "https://127.0.0.1:8445";

test("direct-chat setup recovers an accepted request after a lost response and reload; concurrent retries reuse one chat", async ({
  browser,
}) => {
  test.setTimeout(90000);
  const contexts = await Promise.all([
    browser.newContext(),
    browser.newContext(),
  ]);
  const [a, b] = await Promise.all(contexts.map((c) => c.newPage()));
  try {
    for (const page of [a, b]) {
      await page.goto(`${origin}/__integration__/`);
      await page.waitForFunction(() => !!(window as any).havenIntegration);
    }
    await loginBootstrap(a, credentials);
    const token = await a.evaluate(async (credentials) => {
      const h = (window as any).havenIntegration;
      const invitation = await h.api("admin/invitations", "POST", { hours: 1 });
      const account = await h.api("invitations/redeem", "POST", {
        token: invitation.token,
        username: `retry_${crypto.randomUUID().slice(0, 12)}`,
        password: crypto.randomUUID() + crypto.randomUUID(),
        display_name: "Retry Alice",
      });
      (window as any).retryVault = await h.Messenger.create(
        account.user.id,
        "retry browser unrelated words secret 123",
        "Retry browser",
      );
      return (await h.api("invitations", "POST", {})).token;
    }, credentials);
    const peer = await b.evaluate(async (token) => {
      const h = (window as any).havenIntegration;
      const account = await h.api("invitations/redeem", "POST", {
        token,
        username: `retry_${crypto.randomUUID().slice(0, 12)}`,
        password: crypto.randomUUID() + crypto.randomUUID(),
        display_name: "Retry Bob",
      });
      const vault = await h.Messenger.create(
        account.user.id,
        "peer retry unrelated words secret 123",
        "Retry peer",
      );
      const device = (await h.api("devices")).find(
        (d: any) => d.id === vault.state.device_id,
      );
      vault.lock();
      return device;
    }, token);
    await a.route(
      "**/api/v1/conversations",
      async (route) => {
        if (route.request().method() !== "POST") return route.continue();
        // Relay through independently prepared TEST root trust. No TLS bypass.
        const status = await new Promise<number | undefined>(
          (resolve, reject) => {
            const request = https.request(
              route.request().url(),
              {
                method: "POST",
                headers: route.request().headers(),
                ca: fs.readFileSync(path.resolve("../../.local/tls/root.crt")),
              },
              (response) => {
                response.resume();
                response.on("end", () => resolve(response.statusCode));
              },
            );
            request.on("error", reject);
            request.end(route.request().postDataBuffer());
          },
        );
        expect(status).toBe(201);
        await route.abort("failed");
      },
      { times: 1 },
    );
    const uncertain = await a.evaluate(async (device) => {
      const h = (window as any).havenIntegration,
        v = (window as any).retryVault;
      await v.pin(device, await h.fingerprintOf(device.public_key), "Bob");
      let rejected = false;
      try {
        await v.startDirect(device);
      } catch {
        rejected = true;
      }
      const result = {
        rejected,
        intent: v.state.connection_intents[device.id],
        pending: Object.keys(v.state.outbox).length,
      };
      v.lock();
      return result;
    }, peer);
    expect(uncertain.rejected).toBe(true);
    expect(uncertain.pending).toBe(1);
    await a.reload();
    await a.waitForFunction(() => !!(window as any).havenIntegration);
    const result = await a.evaluate(async (device) => {
      const h = (window as any).havenIntegration;
      const v = await h.Messenger.unlock(
        (await h.api("auth/me")).user.id,
        "retry browser unrelated words secret 123",
      );
      const pair = await Promise.all([
        v.startDirect(device),
        v.startDirect(device),
      ]);
      const list = await h.api("conversations");
      const detail = await h.api(`conversations/${pair[0].id}`);
      const result = {
        ids: pair.map((c) => c.id),
        count: list.length,
        members: detail.members.length,
        pending: Object.keys(v.state.outbox).length,
      };
      v.lock();
      return result;
    }, peer);
    expect(result).toEqual({
      ids: [uncertain.intent, uncertain.intent],
      count: 1,
      members: 2,
      pending: 0,
    });
  } finally {
    await Promise.all(contexts.map((c) => c.close()));
  }
});
