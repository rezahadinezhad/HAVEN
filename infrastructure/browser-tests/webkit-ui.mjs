// UI renderer qualification only: Linux WebKit is not physical iOS Safari.
import { webkit } from "/work/node_modules/playwright/index.mjs";
import { expect } from "/work/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";
const login = JSON.parse(fs.readFileSync("/run/haven-test-login.json", "utf8"));
const browser = await webkit.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const foreign = [],
    violations = [];
  page.on("request", (r) => {
    if (
      !r.url().startsWith("data:") &&
      new URL(r.url()).hostname !== "127.0.0.1"
    )
      foreign.push(r.url());
  });
  await page.addInitScript(() => {
    window.havenCspDiagnostics = [];
    document.addEventListener("securitypolicyviolation", (e) =>
      window.havenCspDiagnostics.push({
        effective: e.effectiveDirective,
        blocked: e.blockedURI,
        sample: e.sample,
      }),
    );
  });
  page.on("console", (m) => {
    if (
      /violates.*security policy|Refused to.*(?:style|script|font)/i.test(
        m.text(),
      )
    )
      violations.push(m.text());
  });
  // Diagnostic reporting only: report-sample does not permit inline styles.
  // Fetch/fulfill preserves the verified response and its per-response nonce.
  await page.route("https://127.0.0.1:8445/", async (route) => {
    const response = await route.fetch();
    const headers = response.headers();
    headers["content-security-policy"] = headers[
      "content-security-policy"
    ].replace("style-src 'self'", "style-src 'report-sample' 'self'");
    await route.fulfill({ response, headers });
  });
  await page.goto("https://127.0.0.1:8445");
  await page.getByLabel("Username", { exact: true }).fill(login.username);
  await page.getByLabel("Password", { exact: true }).fill(login.password);
  await page.locator("form button.primary").click();
  await expect(
    page.getByRole("heading", { name: "Conversations", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".mobile-setup")).toBeVisible();
  await page.getByRole("button", { name: "More", exact: true }).click();
  await expect(page.locator("#mobile-more")).toBeVisible();
  await page.getByRole("button", { name: "Recovery kit", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Recovery kit", exact: true, level: 1 }),
  ).toBeVisible();
  await expect(page.locator("#mobile-more")).not.toBeVisible();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByLabel("Theme", { exact: true }).selectOption("dark");
  await page.getByLabel("Language", { exact: true }).selectOption("fa");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.evaluate(async () => {
    getComputedStyle(document.body).fontFamily;
    await document.fonts.ready;
    await Promise.all(
      document.getAnimations().map((a) => a.finished.catch(() => {})),
    );
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(foreign).toEqual([]);
  const diagnostics = await page.evaluate(() => window.havenCspDiagnostics);
  const nativeSelectWarnings = diagnostics.filter(
    (e) =>
      e.effective === "style-src-attr" &&
      e.blocked === "inline" &&
      e.sample === "text-overflow:inherit",
  );
  // Isolated native-select reproduction runs first. Do not suppress other CSP errors.
  expect(diagnostics).toEqual(nativeSelectWarnings);
  expect([0, 3]).toContain(nativeSelectWarnings.length);
  expect(violations.length).toBe(nativeSelectWarnings.length);
  console.log(
    "Known native-select engine CSP warnings:",
    nativeSelectWarnings.length,
  );
  console.log(
    "PASS trusted-IP Linux WebKit: actual login, mobile dock/native popover, recovery navigation, dark/Persian RTL, no horizontal overflow/foreign requests/unexpected CSP violations; native-select engine warnings reported above. NOT physical iOS Safari.",
  );
} finally {
  await browser.close();
}
