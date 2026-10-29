import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
);
const origin = "https://127.0.0.1:8445";
const evidence = (name: string) =>
  `../../docs/evidence/passphrase-${name}${process.env.HAVEN_BROWSER === "firefox" ? "-firefox" : ""}.png`;

async function member(page: import("@playwright/test").Page) {
  await page.goto(`${origin}/__integration__/`);
  await page.waitForFunction(() => !!(window as any).havenIntegration);
  await loginBootstrap(page, credentials);
  const user = await page.evaluate(async () => {
    const h = (window as any).havenIntegration;
    const invitation = await h.api("admin/invitations", "POST", { hours: 1 });
    return (
      await h.api("invitations/redeem", "POST", {
        token: invitation.token,
        username: `generator_${crypto.randomUUID().slice(0, 12)}`,
        password: crypto.randomUUID() + crypto.randomUUID(),
        display_name: "Generator member",
      })
    ).user;
  });
  await page.goto(origin);
  await page.locator(".connect-entry").click();
  await expect(
    page.getByRole("heading", { name: "Set up this browser", exact: true }),
  ).toBeVisible();
  return user;
}

test("generator uses exactly 32 CSPRNG bytes, lossless base64url and fails closed without secure randomness", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await page.goto(`${origin}/__integration__/`);
    await page.waitForFunction(() => !!(window as any).havenIntegration);
    const results = await page.evaluate(() => {
      const generate = (window as any).havenIntegration
        .generateUnlockPassphrase;
      const descriptor = Object.getOwnPropertyDescriptor(
        crypto,
        "getRandomValues",
      );
      const originalRandom = Math.random;
      let size = 0,
        buffer: Uint8Array | undefined;
      try {
        Math.random = () => {
          throw new Error("Non-cryptographic fallback forbidden");
        };
        Object.defineProperty(crypto, "getRandomValues", {
          configurable: true,
          value: (value: Uint8Array) => {
            size = value.length;
            buffer = value;
            value.forEach((_, index) => {
              value[index] = index;
            });
            return value;
          },
        });
        const vector = generate();
        const cleared = buffer?.every((value) => value === 0);
        let missing = false,
          failed = false;
        Object.defineProperty(crypto, "getRandomValues", {
          configurable: true,
          value: undefined,
        });
        try {
          generate();
        } catch {
          missing = true;
        }
        Object.defineProperty(crypto, "getRandomValues", {
          configurable: true,
          value: () => {
            throw new Error("RNG unavailable");
          },
        });
        try {
          generate();
        } catch {
          failed = true;
        }
        if (descriptor)
          Object.defineProperty(crypto, "getRandomValues", descriptor);
        else delete (crypto as any).getRandomValues;
        const samples = Array.from({ length: 16 }, () => generate());
        return {
          size,
          vector,
          cleared,
          missing,
          failed,
          shape: samples.every((value) => /^[A-Za-z0-9_-]{43}$/.test(value)),
          distinct: new Set(samples).size,
        };
      } finally {
        Math.random = originalRandom;
        if (descriptor)
          Object.defineProperty(crypto, "getRandomValues", descriptor);
        else delete (crypto as any).getRandomValues;
      }
    });
    expect(results).toEqual({
      size: 32,
      vector: "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8",
      cleared: true,
      missing: true,
      failed: true,
      shape: true,
      distinct: 16,
    });
  } finally {
    await context.close();
  }
});

test("new vault: generate, reveal/copy, regenerate/manual reset, save confirmation and real reload/unlock without network disclosure", async ({
  browser,
}) => {
  test.setTimeout(180000);
  const context = await browser.newContext();
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  const requests: string[] = [],
    foreign: string[] = [],
    secrets: string[] = [];
  page.on("request", (request) => {
    requests.push(request.url() + " " + (request.postData() || ""));
    if (
      !request.url().startsWith("data:") &&
      new URL(request.url()).hostname !== "127.0.0.1"
    )
      foreign.push(request.url());
  });
  try {
    const user = await member(page);
    requests.length = 0;
    await page
      .getByRole("button", {
        name: "Generate a secure passphrase",
        exact: true,
      })
      .click();
    await expect(
      page.getByText("Passphrase hidden", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByLabel("Generated passphrase", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Set up and continue", exact: true }),
    ).toBeDisabled();
    await expect(page.getByRole("checkbox")).toBeDisabled();
    await page
      .locator(".connect-setup form")
      .evaluate((form) => (form as HTMLFormElement).requestSubmit());
    await expect(page.locator(".connect-setup").getByRole("alert")).toHaveText(
      "Save your generated passphrase and confirm before continuing",
    );
    await page
      .getByRole("button", { name: "Show passphrase", exact: true })
      .click();
    const initial = await page
      .getByLabel("Generated passphrase", { exact: true })
      .inputValue();
    secrets.push(initial);
    expect(/^[A-Za-z0-9_-]{43}$/.test(initial)).toBe(true);
    await page
      .getByRole("checkbox", {
        name: "I’ve saved my passphrase somewhere private",
      })
      .check();
    await page
      .getByRole("button", { name: "Generate another", exact: true })
      .click();
    await expect(page.getByRole("checkbox")).not.toBeChecked();
    await expect(
      page.getByText("Passphrase hidden", { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("checkbox")).toBeDisabled();
    await page
      .getByRole("button", { name: "Show passphrase", exact: true })
      .click();
    const replacement = await page
      .getByLabel("Generated passphrase", { exact: true })
      .inputValue();
    secrets.push(replacement);
    expect(replacement !== initial).toBe(true);
    await page
      .getByRole("button", { name: "Use my own passphrase", exact: true })
      .click();
    expect(
      (await page.getByLabel("Unlock passphrase", { exact: true }).inputValue())
        .length === 0,
    ).toBe(true);
    await expect(
      page.getByLabel("Confirm unlock passphrase", { exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", {
        name: "Generate a secure passphrase",
        exact: true,
      })
      .click();
    await page
      .getByRole("button", { name: "Show passphrase", exact: true })
      .click();
    const secret = await page
      .getByLabel("Generated passphrase", { exact: true })
      .inputValue();
    secrets.push(secret);
    for (const width of [320, 390, 1440]) {
      await page.setViewportSize({ width, height: 960 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
    await page.screenshot({
      path: evidence("desktop"),
      mask: [page.locator("#generated-unlock-passphrase")],
      maskColor: "#dfe6ef",
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Hide passphrase", exact: true })
      .click();
    if (process.env.HAVEN_BROWSER !== "firefox")
      await context.grantPermissions(["clipboard-read", "clipboard-write"], {
        origin,
      });
    await page
      .getByRole("button", { name: "Copy passphrase", exact: true })
      .click();
    await expect(page.locator(".passphrase-copy-status")).toContainText(
      "Passphrase copied",
    );
    if (process.env.HAVEN_BROWSER !== "firefox")
      expect(
        await page.evaluate(
          async (value) => (await navigator.clipboard.readText()) === value,
          secret,
        ),
      ).toBe(true);
    await expect(page.getByRole("checkbox")).not.toBeChecked();
    await page
      .getByRole("checkbox", {
        name: "I’ve saved my passphrase somewhere private",
      })
      .check();
    expect(requests.some((value) => value.includes("devices/enrollment"))).toBe(
      false,
    );
    await page
      .getByRole("button", { name: "Set up and continue", exact: true })
      .click();
    await expect(
      page.getByText("This browser is ready", { exact: true }),
    ).toBeVisible();
    const device = await page.evaluate(
      async () => (await (await fetch("/api/v1/devices")).json())[0],
    );
    await page.reload();
    await page.locator(".connect-entry").click();
    await expect(
      page.getByRole("heading", { name: "Unlock this browser", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: "Generate a secure passphrase",
        exact: true,
      }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Generate another", exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText(
        "Built-in device unlock needs a trusted hostname. Direct IP addresses cannot use browser passkeys; your vault remains protected by its passphrase.",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: "Unlock with this device",
        exact: true,
      }),
    ).toHaveCount(0);
    expect(
      await page
        .getByLabel("Unlock passphrase", { exact: true })
        .getAttribute("autocomplete"),
    ).toBe("section-haven-vault current-password");
    await page.getByLabel("Unlock passphrase", { exact: true }).fill(secret);
    await page
      .getByRole("button", { name: "Unlock and continue", exact: true })
      .click();
    await expect(
      page.getByText("This browser is ready", { exact: true }),
    ).toBeVisible();
    const after = await page.evaluate(
      async () => await (await fetch("/api/v1/devices")).json(),
    );
    expect(after.length === 1 && after[0].id === device.id).toBe(true);
    await page.locator('.sidebar .nav-item[aria-label="Settings"]').click();
    await expect(
      page.getByRole("heading", { name: "Unlock with this device" }),
    ).toBeVisible();
    await expect(
      page.getByText("This IP-only address cannot use browser passkeys.", {
        exact: false,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Set up device unlock" }),
    ).toHaveCount(0);
    const storage = await page.evaluate(() =>
      JSON.stringify({ ...localStorage, ...sessionStorage }),
    );
    expect(secrets.some((value) => storage.includes(value))).toBe(false);
    expect(
      secrets.some((value) =>
        requests.some((request) => request.includes(value)),
      ),
    ).toBe(false);
    expect(foreign).toEqual([]);
    await page.goto(`${origin}/__integration__/`);
    await page.waitForFunction(() => !!(window as any).havenIntegration);
    expect(
      await page.evaluate(
        async ({ user, secret }) => {
          const stored = await (window as any).havenIntegration.loadVault(
            user.id,
          );
          return !!stored && !JSON.stringify(stored).includes(secret);
        },
        { user, secret },
      ),
    ).toBe(true);
  } finally {
    await context.close();
  }
});

test("generator failure and clipboard denial remain usable; cancellation discards unsaved state; RTL and source gate", async ({
  browser,
}) => {
  test.setTimeout(150000);
  const context = await browser.newContext();
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  try {
    await member(page);
    await page.evaluate(() => {
      (window as any).savedRandom = crypto.getRandomValues;
      Object.defineProperty(crypto, "getRandomValues", {
        configurable: true,
        value: () => {
          throw new Error("Unavailable for test");
        },
      });
    });
    await page
      .getByRole("button", {
        name: "Generate a secure passphrase",
        exact: true,
      })
      .click();
    await expect(
      page.locator(".connect-setup").getByRole("alert"),
    ).toContainText("Secure passphrase generation is unavailable");
    await expect(
      page.getByLabel("Unlock passphrase", { exact: true }),
    ).toBeVisible();
    await page.evaluate(() => {
      Object.defineProperty(crypto, "getRandomValues", {
        configurable: true,
        value: (window as any).savedRandom,
      });
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: {
          writeText: async () => {
            throw new Error("Clipboard denied for test");
          },
        },
      });
    });
    await page
      .getByRole("button", {
        name: "Generate a secure passphrase",
        exact: true,
      })
      .click();
    await page
      .getByRole("button", { name: "Copy passphrase", exact: true })
      .click();
    await expect(page.locator(".passphrase-copy-status")).toContainText(
      "Automatic copying is unavailable",
    );
    await expect(
      page.getByText("Passphrase hidden", { exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Show passphrase", exact: true })
      .click();
    await expect(
      page.getByLabel("Generated passphrase", { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("checkbox")).not.toBeChecked();
    await expect(
      page.getByRole("button", { name: "Set up and continue", exact: true }),
    ).toBeDisabled();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("button", { name: "فارسی", exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: evidence("mobile-rtl"),
      mask: [page.locator("#generated-unlock-passphrase")],
      maskColor: "#dfe6ef",
      fullPage: true,
    });
    await page.getByRole("button", { name: "English", exact: true }).click();
    await page.setViewportSize({ width: 1440, height: 960 });
    await page.getByRole("button", { name: "Messages", exact: true }).click();
    await page.locator(".connect-entry").click();
    await expect(
      page.getByRole("button", {
        name: "Generate a secure passphrase",
        exact: true,
      }),
    ).toBeVisible();
    expect(
      (await page.getByLabel("Unlock passphrase", { exact: true }).inputValue())
        .length === 0,
    ).toBe(true);
    expect(
      await page.evaluate(
        async () => (await (await fetch("/api/v1/devices")).json()).length,
      ),
    ).toBe(0);
    await page.goto("https://127.0.0.1:8443/");
    await page.locator(".connect-entry").click();
    await expect(
      page.getByRole("button", {
        name: "Generate a secure passphrase",
        exact: true,
      }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "Set up and continue", exact: true }),
    ).toBeDisabled();
  } finally {
    await context.close();
  }
});
