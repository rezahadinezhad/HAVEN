import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
import { randomBytes } from "node:crypto";

const origin = process.env.HAVEN_HOSTNAME_QA_ORIGIN;

test("opt-in hostname: real vault setup, PRF enrollment, reload unlock and removal", async ({
  browser,
}) => {
  test.skip(
    !origin || process.env.HAVEN_BROWSER === "firefox",
    "Trusted hostname QA uses Chromium virtual authenticator",
  );
  const credentials = JSON.parse(
    fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
  );
  test.setTimeout(180000);
  const context = await browser.newContext();
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  const secret = randomBytes(32).toString("base64url");
  const requests: string[] = [];
  page.on("request", (request) =>
    requests.push(request.url() + " " + (request.postData() || "")),
  );
  try {
    await cdp.send("WebAuthn.enable");
    await cdp.send("WebAuthn.addVirtualAuthenticator", {
      options: {
        protocol: "ctap2",
        ctap2Version: "ctap2_1",
        transport: "internal",
        hasResidentKey: true,
        hasUserVerification: true,
        automaticPresenceSimulation: true,
        isUserVerified: true,
        hasPrf: true,
      },
    });
    await page.goto(`${origin}/__integration__/`);
    await page.waitForFunction(() => !!(window as any).havenIntegration);
    await loginBootstrap(page, credentials);
    const user = await page.evaluate(async () => {
      const h = (window as any).havenIntegration;
      const invitation = await h.api("admin/invitations", "POST", { hours: 1 });
      return (
        await h.api("invitations/redeem", "POST", {
          token: invitation.token,
          username: `device_unlock_${crypto.randomUUID().slice(0, 12)}`,
          password: crypto.randomUUID() + crypto.randomUUID(),
          display_name: "Device unlock QA",
        })
      ).user;
    });
    await page.goto(origin!);
    await page.locator(".connect-entry").click();
    await expect(
      page.getByRole("heading", { name: "Set up this browser" }),
    ).toBeVisible();
    await page.getByLabel("Unlock passphrase", { exact: true }).fill(secret);
    await page
      .getByLabel("Confirm unlock passphrase", { exact: true })
      .fill(secret);
    await page.getByRole("button", { name: "Set up and continue" }).click();
    await expect(
      page.getByText("This browser is ready", { exact: true }),
    ).toBeVisible();
    const before = await page.evaluate(
      async () => (await (await fetch("/api/v1/devices")).json())[0].id,
    );
    await page.locator('.sidebar .nav-item[aria-label="Settings"]').click();
    await expect(
      page.getByRole("button", { name: "Set up device unlock" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Set up device unlock" }).click();
    await expect(
      page.getByText(
        "Device unlock is ready. Your passphrase remains the fallback.",
      ),
    ).toBeVisible();
    const record = await page.evaluate(async (id) => {
      const database = await new Promise<IDBDatabase>((resolve, reject) => {
        const request = indexedDB.open("haven-device-unlock-v1", 1);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      const value = await new Promise<unknown>((resolve, reject) => {
        const request = database
          .transaction("records", "readonly")
          .objectStore("records")
          .get(id);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      database.close();
      return JSON.stringify(value);
    }, user.id);
    expect(record).not.toContain(secret);
    expect(record).toContain("ciphertext");
    await page.locator(".page-content").evaluate((element) => {
      element.scrollTop = 0;
    });
    await page.screenshot({
      path: "../../docs/evidence/device-unlock-hostname-settings.png",
      fullPage: true,
    });
    await page.reload();
    await page.locator(".connect-entry").click();
    await expect(
      page.getByRole("heading", { name: "Unlock this browser" }),
    ).toBeVisible();
    await page.screenshot({
      path: "../../docs/evidence/device-unlock-hostname-unlock.png",
      fullPage: true,
    });
    await page.getByRole("button", { name: "Unlock with this device" }).click();
    await expect(
      page.getByText("This browser is ready", { exact: true }),
    ).toBeVisible();
    const after = await page.evaluate(
      async () => (await (await fetch("/api/v1/devices")).json())[0].id,
    );
    expect(after).toBe(before);
    await page.locator('.sidebar .nav-item[aria-label="Settings"]').click();
    await page.getByRole("button", { name: "Remove device unlock" }).click();
    await expect(
      page.getByText(
        "Device unlock removed. Your vault passphrase still works.",
      ),
    ).toBeVisible();
    await page.reload();
    await page.locator(".connect-entry").click();
    await expect(
      page.getByRole("button", { name: "Unlock with this device" }),
    ).toHaveCount(0);
    await page.getByLabel("Unlock passphrase", { exact: true }).fill(secret);
    await page.getByRole("button", { name: "Unlock and continue" }).click();
    await expect(
      page.getByText("This browser is ready", { exact: true }),
    ).toBeVisible();
    expect(requests.some((request) => request.includes(secret))).toBe(false);
  } finally {
    await cdp.detach();
    await context.close();
  }
});
