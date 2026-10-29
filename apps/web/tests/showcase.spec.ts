import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";

// Documentation images are actual application captures with disposable synthetic
// data. This opt-in workflow never changes personal browser profiles or accounts.
test("public showcase: real encrypted conversation, responsive layout and review notice", async ({
  browser,
}) => {
  test.skip(
    process.env.HAVEN_CAPTURE_SHOWCASE !== "1",
    "Opt-in documentation capture",
  );
  test.setTimeout(120000);
  const origin = "https://127.0.0.1:8445";
  const credentials = JSON.parse(
    fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
  );
  const contexts = await Promise.all([
    browser.newContext({ viewport: { width: 1440, height: 940 } }),
    browser.newContext(),
  ]);
  const [a, b] = await Promise.all(contexts.map((c) => c.newPage()));
  const bodies: string[] = [];
  const statements = [
    "Hey Maya, are we still on for the garden tomorrow?",
    "Absolutely. I’ll bring the coffee ☕",
    "Perfect. I found a quiet spot by the water.",
    "I’ll send you the photos here afterward.",
    "Sounds good. See you at ten 🌿",
  ];
  for (const page of [a, b])
    page.on("request", (r) => {
      if (r.url().includes("/messages") && r.postData())
        bodies.push(r.postData()!);
    });
  try {
    for (const page of [a, b]) {
      await page.goto(origin + "/__integration__/");
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
    const devices: any[] = [],
      secrets: string[] = [];
    for (const [i, page] of [a, b].entries()) {
      const answer = await page.evaluate(
        async ({ token, name }) => {
          const w = window as any,
            h = w.havenIntegration;
          const account = await h.api("invitations/redeem", "POST", {
            token,
            username: "showcase_" + crypto.randomUUID().slice(0, 10),
            password: crypto.randomUUID() + crypto.randomUUID(),
            display_name: name,
          });
          w.secret = crypto.randomUUID() + crypto.randomUUID();
          w.m = await h.Messenger.create(
            account.user.id,
            w.secret,
            "Documentation browser",
          );
          return {
            secret: w.secret,
            device: (await h.api("devices")).find(
              (d: any) => d.id === w.m.state.device_id,
            ),
          };
        },
        { token: invites[i].token, name: i ? "Nora" : "Maya" },
      );
      secrets.push(answer.secret);
      devices.push(answer.device);
    }
    for (const [i, page] of [a, b].entries())
      await page.evaluate(
        async ({ device, name }) => {
          const w = window as any;
          await w.m.pin(
            device,
            await w.havenIntegration.fingerprintOf(device.public_key),
            name,
          );
        },
        { device: devices[1 - i], name: i ? "Maya" : "Nora" },
      );
    const cid = await a.evaluate(
      async (d) => (await (window as any).m.startDirect(d)).id,
      devices[1],
    );
    for (const [i, text] of statements.entries()) {
      const page = i % 2 ? a : b;
      await page.evaluate(
        async ({ cid, text }) => {
          const w = window as any,
            c = await w.havenIntegration.api(`conversations/${cid}`);
          await w.m.sync(c);
          await w.m.send(c, { type: "text", text });
        },
        { cid, text },
      );
    }
    await a.evaluate(async (cid) => {
      const w = window as any;
      await w.m.sync(await w.havenIntegration.api(`conversations/${cid}`));
    }, cid);
    expect(
      statements.every((text) => !bodies.some((body) => body.includes(text))),
    ).toBe(true);
    await a.goto(origin);
    await a.locator(".connect-entry").click();
    await a.getByLabel("Unlock passphrase", { exact: true }).fill(secrets[0]);
    await a
      .getByRole("button", { name: "Unlock and continue", exact: true })
      .click();
    await expect(
      a.getByText("This browser is ready", { exact: true }),
    ).toBeVisible();
    await a.getByRole("button", { name: "Messages", exact: true }).click();
    await a.locator(".conversation-row").click();
    await expect(a.locator(".chat-heading")).toContainText("Nora");
    await expect(a.locator(".message-log")).toContainText(statements.at(-1)!);
    await expect(
      a.getByText(
        "Experimental cryptographic integration. Not approved for production use.",
      ),
    ).toBeVisible();
    await a.getByLabel("Message", { exact: true }).fill("");
    await a.locator(".chat-heading").click();
    await a.screenshot({
      path: "../../.github/assets/conversation-desktop.png",
      fullPage: true,
    });
    await a.getByRole("button", { name: "Switch to dark mode" }).click();
    await expect(a.locator("html")).toHaveAttribute("data-theme", "dark");
    await a.screenshot({
      path: "../../.github/assets/conversation-dark.png",
      fullPage: true,
    });
    await a.getByRole("button", { name: "Switch to light mode" }).click();
    await a.setViewportSize({ width: 390, height: 844 });
    await expect(a.locator(".message-log")).toContainText(statements.at(-1)!);
    await a.screenshot({
      path: "../../.github/assets/conversation-mobile.png",
      fullPage: true,
    });
    expect(
      secrets.some((secret) => bodies.some((body) => body.includes(secret))),
    ).toBe(false);
  } finally {
    for (const context of contexts) await context.close();
  }
});
