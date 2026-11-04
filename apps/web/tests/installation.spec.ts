import { test, expect, navigate } from "./fixtures";
import fs from "node:fs";
import path from "node:path";

const endpoint = process.env.HAVEN_INSTALLED_URL;
const credentialPath = process.env.HAVEN_INSTALLED_CREDENTIALS;
test.skip(
  !endpoint || !credentialPath,
  "Explicit installed endpoint and protected credentials required",
);

test("installed product uses trusted TLS, clean operational UI and contextual service notices", async ({
  page,
}) => {
  test.setTimeout(90000);
  if (!endpoint || !credentialPath)
    throw new Error("Installed configuration missing");
  expect(fs.statSync(credentialPath).mode & 0o077).toBe(0);
  const credentials = JSON.parse(fs.readFileSync(credentialPath, "utf8"));
  expect(new URL(endpoint).protocol).toBe("https:");
  expect(new URL(credentials.url).origin).toBe(new URL(endpoint).origin);
  const errors: string[] = [],
    foreign: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const u = new URL(request.url());
    if (
      ["http:", "https:"].includes(u.protocol) &&
      u.origin !== new URL(endpoint).origin
    )
      foreign.push(u.origin);
  });
  const response = await page.goto(endpoint);
  expect(response?.status()).toBe(200);
  const csp = response!.headers()["content-security-policy"];
  expect(csp).toContain("'nonce-");
  expect(csp).not.toMatch(/'unsafe-(?:eval|inline)'/);
  expect(await page.evaluate(() => isSecureContext)).toBe(true);
  const health = await page.evaluate(async () =>
    (await fetch("/api/v1/health")).json(),
  );
  expect(health.crypto_ready).toBe(true);
  expect(health.experimental_closure).toBe(true);
  expect(health.release_status).toBe("ACTIVE_REVIEW_PENDING");
  expect(health.maintenance).toBe("");
  await expect(page.locator(".gate")).toHaveCount(0);
  await expect(
    page.getByText("Security qualification pending", { exact: true }),
  ).toBeVisible();
  const evidence = path.resolve(
    "../../docs/operations/installation-upgrade-2026-11-04/evidence",
  );
  const browser = process.env.HAVEN_BROWSER || "chromium";
  await page.screenshot({
    path: path.join(evidence, `live-${browser}-login.png`),
    fullPage: true,
  });
  await page.getByLabel("Username", { exact: true }).fill(credentials.username);
  await page.getByLabel("Password", { exact: true }).fill(credentials.password);
  await page.locator("form button.primary").click();
  await expect(
    page.getByRole("heading", { name: "Conversations", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".gate")).toHaveCount(0);
  await expect(
    page
      .locator(".welcome")
      .getByRole("button", { name: "Set up this device" }),
  ).toBeEnabled();
  await expect(page.locator("footer")).not.toContainText(
    /UNREVIEWED|CRYPTO_NOT_READY/,
  );
  await navigate(page, "Settings");
  await expect(
    page.getByRole("heading", { name: "What stays on the server" }),
  ).toBeVisible();
  await expect(page.locator(".server-privacy")).toContainText("Mutual closure");
  await page.getByLabel("Theme", { exact: true }).selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByLabel("Language", { exact: true }).selectOption("fa");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: path.join(evidence, `live-${browser}-settings-fa.png`),
    fullPage: true,
  });
  await page.getByLabel("زبان", { exact: true }).selectOption("en");
  await page.route("**/api/v1/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...health, crypto_ready: false }),
    });
  });
  await page.reload();
  await expect(page.locator(".gate")).toContainText("Messaging unavailable");
  await page.unrouteAll({ behavior: "wait" });
  await page.reload();
  await expect(page.locator(".gate")).toHaveCount(0);
  expect(errors).toEqual([]);
  expect(foreign).toEqual([]);
});
