import { test, expect, chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
) as { username: string; password: string };
test("trusted TLS, login, invitation and operator account flows, bilingual mobile layout", async ({
  page,
}) => {
  const foreign: string[] = [];
  page.on("request", (r) => {
    if (new URL(r.url()).hostname !== "127.0.0.1") foreign.push(r.url());
  });
  const response = await page.goto("/");
  const csp = response!.headers()["content-security-policy"];
  expect(csp).toContain("'nonce-");
  expect(csp).not.toContain("'unsafe-eval'");
  expect(csp).not.toContain("'unsafe-inline'");
  await expect(
    page.getByRole("heading", { name: "Open your private space" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../../docs/evidence/desktop-login.png",
    fullPage: true,
  });
  await page.getByLabel("Username", { exact: true }).fill(credentials.username);
  await page.getByLabel("Password", { exact: true }).fill(credentials.password);
  await page.locator("form button.primary").click();
  await expect(
    page.getByRole("button", { name: "Operator console", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("CRYPTO_NOT_READY")).toBeVisible();
  await page
    .getByRole("button", { name: "Operator console", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Create invitation", exact: true })
    .click();
  await expect(page.locator(".invite-output code")).toBeVisible();
  const token = await page.locator(".invite-output code").innerText();
  expect(token.length).toBeGreaterThan(40);
  await page.screenshot({
    path: "../../docs/evidence/desktop-admin.png",
    fullPage: true,
  });
  await page
    .locator("tbody tr")
    .first()
    .getByRole("button", { name: "Revoke", exact: true })
    .click();
  await page.getByRole("button", { name: "Devices", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Create device vault", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByLabel("Theme", { exact: true }).selectOption("light");
  await page.getByLabel("Language", { exact: true }).selectOption("fa");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../../docs/evidence/mobile-rtl-settings.png",
    fullPage: true,
  });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > innerWidth,
  );
  expect(overflow).toBeFalsy();
  await page.getByLabel("زبان", { exact: true }).selectOption("en");
  await page.setViewportSize({ width: 320, height: 720 });
  await page.getByRole("button", { name: "Messages", exact: true }).click();
  await page.screenshot({
    path: "../../docs/evidence/mobile-messages.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBeFalsy();
  expect(foreign).toEqual([]);
  const cookies = await page.context().cookies();
  const session = cookies.find((x) => x.name === "__Host-haven");
  expect(session?.secure).toBeTruthy();
  expect(session?.httpOnly).toBeTruthy();
});
test("untrusted browser rejects the IP certificate", async () => {
  const home = path.resolve("../../.local/untrusted-browser-home");
  fs.mkdirSync(home, { recursive: true });
  const browser = await chromium.launch({
    executablePath: "/usr/bin/google-chrome",
    env: { ...process.env, HOME: home },
    headless: true,
  });
  try {
    const page = await browser.newPage();
    await expect(page.goto("https://127.0.0.1:8443/")).rejects.toThrow(
      /ERR_CERT_AUTHORITY_INVALID|certificate/,
    );
  } finally {
    await browser.close();
  }
});

test("expired IP leaf is rejected even with the correct trusted test root", async ({
  page,
}) => {
  const https = await import("node:https");
  const cp = await import("node:child_process");
  const root = path.resolve("../..");
  cp.execFileSync(
    root + "/apps/api/.venv/bin/python",
    [root + "/scripts/expired-test-cert.py"],
    { stdio: "ignore" },
  );
  const server = https.createServer(
    {
      key: fs.readFileSync(root + "/.local/tls/leaf.key"),
      cert: fs.readFileSync(root + "/.local/tls/expired.crt"),
    },
    (_, res) => res.end("must not be trusted"),
  );
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const port = (server.address() as import("node:net").AddressInfo).port;
    await expect(page.goto(`https://127.0.0.1:${port}/`)).rejects.toThrow(
      /ERR_CERT_DATE_INVALID|certificate/,
    );
  } finally {
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
});
