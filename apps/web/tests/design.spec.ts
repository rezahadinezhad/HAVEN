import { test, expect } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
);

const screenshotPath = (name: string) =>
  `../../docs/evidence/redesign-${name}${process.env.HAVEN_BROWSER === "firefox" ? "-firefox" : ""}.png`;

test("redesigned real account: responsive navigation, setup, themes, RTL, reduced motion and local assets", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  const foreign: string[] = [],
    violations: string[] = [];
  page.on("request", (r) => {
    if (
      !r.url().startsWith("data:") &&
      new URL(r.url()).hostname !== "127.0.0.1"
    )
      foreign.push(r.url());
  });
  page.on("console", (m) => {
    if (
      /violates.*security policy|Refused to.*(?:style|script|font)/i.test(
        m.text(),
      )
    )
      violations.push(m.text());
  });
  try {
    await page.setViewportSize({ width: 1440, height: 960 });
    await page.goto("https://127.0.0.1:8445");
    await expect(
      page.getByRole("heading", { name: "Open your private space" }),
    ).toBeVisible();
    await page.evaluate(async () => {
      await Promise.all(
        document.getAnimations().map((a) => a.finished.catch(() => {})),
      );
    });
    await page.screenshot({
      path: screenshotPath("sign-in"),
      fullPage: true,
    });
    await page
      .getByLabel("Username", { exact: true })
      .fill(credentials.username);
    await page
      .getByLabel("Password", { exact: true })
      .fill(credentials.password);
    await page.locator("form button.primary").click();
    await expect(
      page.getByRole("heading", { name: "Conversations", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Security qualification pending", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      page
        .locator(".welcome")
        .getByRole("button", { name: "Set up this device" }),
    ).toBeEnabled();
    await page.evaluate(async () => {
      await Promise.all(
        document.getAnimations().map((a) => a.finished.catch(() => {})),
      );
    });
    await page.screenshot({
      path: screenshotPath("desktop"),
      fullPage: true,
    });
    await page
      .locator(".welcome")
      .getByRole("button", { name: "Set up this device" })
      .click();
    await expect(
      page.getByLabel("Unlock passphrase", { exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "What stays on the server" }),
    ).toBeVisible();
    await expect(page.locator(".server-privacy")).toContainText(
      "24-hour retry window",
    );
    await page
      .getByText("Understand the remaining limits", { exact: true })
      .click();
    await expect(page.locator(".server-privacy details")).toContainText(
      "This is not anonymous messaging",
    );
    await page
      .locator(".server-privacy")
      .screenshot({ path: screenshotPath("privacy-retention") });
    await page
      .getByText("Understand the remaining limits", { exact: true })
      .click();
    await page.getByLabel("Theme", { exact: true }).selectOption("dark");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.evaluate(async () => {
      await Promise.all(
        document.getAnimations().map((a) => a.finished.catch(() => {})),
      );
    });
    await page.screenshot({
      path: screenshotPath("dark-settings"),
      fullPage: true,
    });
    await page.getByLabel("Theme", { exact: true }).selectOption("light");
    await page.getByRole("button", { name: "Messages", exact: true }).click();
    for (const width of [1440, 1024, 900, 768, 760, 430, 390, 320]) {
      await page.setViewportSize({ width, height: width > 760 ? 960 : 844 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      if (width <= 760) {
        await expect(
          page.getByRole("button", { name: "More", exact: true }),
        ).toBeVisible();
        await expect(page.locator(".mobile-setup")).toBeVisible();
      }
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(async () => {
      await Promise.all(
        document.getAnimations().map((a) => a.finished.catch(() => {})),
      );
    });
    await page.screenshot({
      path: screenshotPath("mobile"),
      fullPage: true,
    });
    await page.getByRole("button", { name: "More", exact: true }).click();
    await expect(page.locator("#mobile-more")).toBeVisible();
    await page
      .getByRole("button", { name: "Recovery kit", exact: true })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Recovery kit",
        exact: true,
        level: 1,
      }),
    ).toBeVisible();
    await expect(page.locator("#mobile-more")).not.toBeVisible();
    await page.getByRole("button", { name: "More", exact: true }).click();
    await page.keyboard.press("Escape");
    await expect(page.locator("#mobile-more")).not.toBeVisible();
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await page.getByLabel("Language", { exact: true }).selectOption("fa");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(
      page.getByRole("heading", { name: "چه چیزی روی سرور باقی می‌ماند" }),
    ).toBeVisible();
    const font = await page.evaluate(async () => {
      const styles = getComputedStyle(document.body);
      const selected = styles
        .getPropertyValue("--font-persian")
        .split(",")[0]
        .trim()
        .replace(/["']/g, "");
      await document.fonts.ready;
      return {
        used: !!selected && styles.fontFamily.includes(selected),
        loaded: Array.from(document.fonts).some(
          (face) =>
            face.family.replace(/["']/g, "") === selected &&
            face.status === "loaded",
        ),
      };
    });
    expect(font).toEqual({ used: true, loaded: true });
    await page.evaluate(async () => {
      await Promise.all(
        document.getAnimations().map((a) => a.finished.catch(() => {})),
      );
    });
    await page.screenshot({
      path: screenshotPath("mobile-rtl"),
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(
      await page
        .locator(".nav-indicator")
        .evaluate((el) => getComputedStyle(el).transitionDuration),
    ).toBe("0s");
    expect(foreign).toEqual([]);
    expect(violations).toEqual([]);
  } finally {
    await context.close();
  }
});

test("CSP-safe accessible announcer and blocked arbitrary inline scripts/styles", async ({
  page,
}) => {
  const response = await page.goto("https://127.0.0.1:8445");
  const csp = response!.headers()["content-security-policy"];
  expect(csp).toContain("style-src 'self' 'nonce-");
  expect(csp).not.toContain("'unsafe-hashes'");
  await page.waitForFunction(() => {
    const root = document.querySelector("next-route-announcer");
    const live = root?.shadowRoot?.firstElementChild;
    return (
      root?.classList.contains("haven-route-announcer") &&
      !root.hasAttribute("style") &&
      live?.getAttribute("part") === "announcement" &&
      getComputedStyle(live).width === "1px" &&
      live.getAttribute("aria-live") === "assertive"
    );
  });
  expect(csp).not.toContain("'unsafe-inline'");
  expect(csp).not.toContain("'unsafe-eval'");
  const results = await page.evaluate(async () => {
    const violations: string[] = [];
    const capture = (e: SecurityPolicyViolationEvent) =>
      violations.push(e.effectiveDirective);
    document.addEventListener("securitypolicyviolation", capture);
    const script = document.createElement("script");
    script.textContent = "window.havenUnsafeInlineProbe=true";
    const styled = document.createElement("span");
    styled.textContent = "CSP negative test";
    styled.setAttribute(
      "style",
      "position:fixed;inset:0;background:red;z-index:100",
    );
    document.body.append(script, styled);
    // Policy events are asynchronous; give the browser two rendering turns.
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
    const blocked =
      !(window as any).havenUnsafeInlineProbe &&
      getComputedStyle(styled).position !== "fixed";
    script.remove();
    styled.remove();
    document.removeEventListener("securitypolicyviolation", capture);
    return {
      blocked,
      script: violations.some((v) => v.startsWith("script-src")),
      style: violations.some((v) => v.startsWith("style-src")),
    };
  });
  expect(results).toEqual({ blocked: true, script: true, style: true });
});
