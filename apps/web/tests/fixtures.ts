import { test as base, expect, firefox } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import type { Page, FileChooser } from "@playwright/test";

// Bootstrap accounts are shared across sequential integration tests. Respect
// the real account limiter instead of weakening it or clearing Redis in tests.
export async function loginBootstrap(
  page: Page,
  credentials: { username: string; password: string },
) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const result = await page.evaluate(async (value) => {
      try {
        return {
          ok: true,
          user: (
            await (window as any).havenIntegration.api(
              "auth/login",
              "POST",
              value,
            )
          ).user,
        };
      } catch (error) {
        if ((error as { status?: number }).status === 429) return { ok: false };
        throw error;
      }
    }, credentials);
    if (result.ok) return result.user;
    if (!attempt) {
      console.log(
        "QA bootstrap respects the account limiter; waiting its 60-second retry window.",
      );
      await new Promise((resolve) => setTimeout(resolve, 60_000));
    }
  }
  throw new Error("QA bootstrap remained rate limited after its retry window");
}
// Firefox loads private CA roots from an NSS profile. Each test context gets a separate
// temporary profile containing only the independently prepared TEST root trust database.
export const test = base.extend({
  browser: async ({ browser }, use) => {
    if (process.env.HAVEN_BROWSER !== "firefox") return use(browser);
    const contexts: Awaited<
      ReturnType<typeof firefox.launchPersistentContext>
    >[] = [];
    const dirs: string[] = [];
    const original = browser.newContext.bind(browser);
    browser.newContext = async (options = {}) => {
      const dir = fs.mkdtempSync(path.join(os.tmpdir(), "haven-firefox-test-"));
      dirs.push(dir);
      for (const file of ["cert9.db", "key4.db", "pkcs11.txt"])
        fs.copyFileSync(
          path.resolve("../../.local/firefox-profile", file),
          path.join(dir, file),
        );
      const context = await firefox.launchPersistentContext(dir, {
        ...options,
        headless: true,
        env: {
          PATH: process.env.PATH || "/usr/bin:/bin",
          LANG: "C.UTF-8",
          HOME: path.resolve("../../.local/browser-home"),
          LD_LIBRARY_PATH: path.resolve(
            "../../.local/browser-libs/usr/lib/x86_64-linux-gnu",
          ),
        },
      });
      contexts.push(context);
      return context;
    };
    try {
      await use(browser);
    } finally {
      browser.newContext = original;
      for (const context of contexts) await context.close();
      for (const dir of dirs) fs.rmSync(dir, { recursive: true, force: true });
    }
  },
});
export { expect };

// Exercise the real paperclip/menu/native chooser path rather than bypassing it
// through a hidden file input. Accept hints are verified separately from policy.
export async function selectAttachment(
  page: Page,
  category: "media" | "audio" | "file",
  files: Parameters<FileChooser["setFiles"]>[0],
) {
  const fa = (await page.locator("html").getAttribute("lang")) === "fa";
  await page
    .getByRole("button", {
      name: fa ? "افزودن پیوست" : "Add attachment",
      exact: true,
    })
    .click();
  const menu = page.locator("#attachment-menu");
  await expect(menu).toBeVisible();
  const box = await menu.boundingBox(),
    viewport = page.viewportSize();
  if (box && viewport) {
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
    expect(box.y).toBeGreaterThanOrEqual(0);
    expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
  }
  const chooserEvent = page.waitForEvent("filechooser");
  const labels = fa
    ? { media: "عکس و ویدیو", audio: "صدا", file: "فایل" }
    : { media: "Photos & videos", audio: "Audio", file: "File" };
  await menu
    .getByRole("button", { name: labels[category], exact: true })
    .click();
  const chooser = await chooserEvent;
  expect(await chooser.element().getAttribute("accept")).toBe(
    category === "media"
      ? "image/*,video/*"
      : category === "audio"
        ? "audio/*"
        : null,
  );
  await chooser.setFiles(files);
  await expect(menu).not.toBeVisible();
}
