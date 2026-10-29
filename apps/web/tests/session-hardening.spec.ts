import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
import { randomBytes } from "node:crypto";

test("real vault: pagehide, suspended inactivity, offline access and confirmed remote logout", async ({
  browser,
}) => {
  test.setTimeout(120000);
  const credentials = JSON.parse(
    fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
  );
  const context = await browser.newContext();
  const page = await context.newPage();
  const secret = randomBytes(32).toString("base64url");
  const origin = "https://127.0.0.1:8445";
  const requests: string[] = [];
  page.on("request", (request) =>
    requests.push(request.url() + " " + (request.postData() || "")),
  );
  try {
    await page.goto(`${origin}/__integration__/`);
    await page.waitForFunction(() => !!(window as any).havenIntegration);
    await loginBootstrap(page, credentials);
    await page.evaluate(async () => {
      const h = (window as any).havenIntegration;
      const invite = await h.api("admin/invitations", "POST", { hours: 1 });
      await h.api("invitations/redeem", "POST", {
        token: invite.token,
        username: "session_" + crypto.randomUUID().slice(0, 12),
        password: crypto.randomUUID() + crypto.randomUUID(),
        display_name: "Session safety QA",
      });
    });
    await page.goto(origin);
    await page.locator(".connect-entry").click();
    await page.getByLabel("Unlock passphrase", { exact: true }).fill(secret);
    await page
      .getByLabel("Confirm unlock passphrase", { exact: true })
      .fill(secret);
    await page.getByRole("button", { name: "Set up and continue" }).click();
    const shortcut = page.locator(".sidebar .vault-shortcut");
    await expect(shortcut).toHaveText("Lock vault");
    const devices = await page.evaluate(async () =>
      (await (await fetch("/api/v1/devices")).json()).map((d: any) => d.id),
    );

    async function unlock() {
      await page.locator(".connect-entry").click();
      await page.getByLabel("Unlock passphrase", { exact: true }).fill(secret);
      await page.getByRole("button", { name: "Unlock and continue" }).click();
      await expect(shortcut).toHaveText("Lock vault");
    }

    await page.evaluate(() =>
      window.dispatchEvent(
        new PageTransitionEvent("pagehide", { persisted: true }),
      ),
    );
    await expect(shortcut).toHaveText("Open your vault");
    await unlock();
    await page.evaluate(() =>
      window.dispatchEvent(
        new PageTransitionEvent("pageshow", { persisted: true }),
      ),
    );
    await expect(shortcut).toHaveText("Open your vault");
    await unlock();
    // Simulate suspended timers: the first key event must lock before it can
    // replace the old activity deadline. No real six-minute sleep is needed.
    await page.evaluate(() => {
      const original = Date.now;
      Date.now = () => original() + 6 * 60 * 1000;
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Shift" }));
      Date.now = original;
    });
    await expect(shortcut).toHaveText("Open your vault");
    await unlock();
    expect(
      await page.evaluate(async () =>
        (await (await fetch("/api/v1/devices")).json()).map((d: any) => d.id),
      ),
    ).toEqual(devices);

    // A wall-clock rollback cannot extend the deadline measured by the
    // monotonic clock. Restore both browser clocks before the next unlock.
    await page.evaluate(() => {
      const wall = Date.now,
        monotonic = performance.now.bind(performance),
        descriptor = Object.getOwnPropertyDescriptor(performance, "now");
      try {
        Date.now = () => wall() - 6 * 60 * 1000;
        Object.defineProperty(performance, "now", {
          configurable: true,
          value: () => monotonic() + 6 * 60 * 1000,
        });
        window.dispatchEvent(new KeyboardEvent("keydown", { key: "Shift" }));
      } finally {
        Date.now = wall;
        if (descriptor) Object.defineProperty(performance, "now", descriptor);
        else delete (performance as any).now;
      }
    });
    await expect(shortcut).toHaveText("Open your vault");
    await unlock();

    await page.evaluate(() => {
      const w = window as any;
      w.originalNow = Date.now;
      w.sessionClockOffset = 31000;
      Date.now = () => w.originalNow() + w.sessionClockOffset;
    });
    const offlineProbe = page.waitForEvent("requestfailed", {
      predicate: (r) => r.url().endsWith("/api/v1/auth/me"),
      timeout: 20000,
    });
    await context.setOffline(true);
    await offlineProbe;
    await expect(shortcut).toHaveText("Lock vault");
    const onlineProbe = page.waitForResponse(
      (r) => r.url().endsWith("/api/v1/auth/me") && r.status() === 200,
    );
    await context.setOffline(false);
    await onlineProbe;
    const ended = await page.evaluate(async () => {
      const csrf = (await (await fetch("/api/v1/auth/csrf")).json()).csrf;
      const response = await fetch("/api/v1/auth/logout-all", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: "{}",
      });
      (window as any).sessionClockOffset += 31000;
      return response.ok;
    });
    expect(ended).toBe(true);
    await expect(
      page.getByRole("heading", { name: "Open your private space" }),
    ).toBeVisible({ timeout: 20000 });
    await expect(
      page.getByText(
        "Your sign-in expired or was revoked. Your vault is locked. Sign in again to continue.",
      ),
    ).toBeVisible();
    expect(
      await page.evaluate(() => localStorage.getItem("haven-local-user")),
    ).toBeNull();
    expect(requests.some((value) => value.includes(secret))).toBe(false);
    // Device identity was preserved before logout; neither lifecycle lock
    // creates a replacement identity nor sends the local vault secret.
    expect(devices).toHaveLength(1);
  } finally {
    await context.close();
  }
});
