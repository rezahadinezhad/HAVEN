import {
  test,
  expect,
  chromium,
  firefox,
  type BrowserContext,
} from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import configuration from "../playwright.config";
import { loginBootstrap } from "./fixtures";
const profile = process.env.HAVEN_VERIFIED_PROFILE;
const endpoint = process.env.HAVEN_VERIFIED_URL || "https://127.0.0.1:9455";
test.skip(
  !profile || process.env.HAVEN_CAPTURE_SHOWCASE !== "1",
  "Explicit signed QA profile and documentation-capture opt-in required",
);

test("public presentation: current encrypted conversation, desktop, dark and mobile", async () => {
  test.setTimeout(180000);
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "haven-client-browser-"));
  const contexts: BrowserContext[] = [];
  const binary =
    process.env.HAVEN_BROWSER === "firefox" ? "firefox" : "chromium";
  const root = path.resolve("../..");
  const localCA = path.join(profile!, "tls/root.crt");
  const launchEnv = { ...configuration.use!.launchOptions!.env } as Record<
    string,
    string
  >;
  const browserHome = path.join(temp, "trusted-home");
  fs.mkdirSync(browserHome, { recursive: true, mode: 0o700 });
  for (const folder of [".pki/nssdb", ".local/share/pki/nssdb"]) {
    const dir = path.join(browserHome, folder);
    fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
    execFileSync("certutil", ["-N", "-d", "sql:" + dir, "--empty-password"], {
      stdio: "pipe",
    });
    execFileSync(
      "certutil",
      [
        "-A",
        "-d",
        "sql:" + dir,
        "-n",
        "LOCAL CLIENT TEST",
        "-t",
        "C,,",
        "-i",
        localCA,
      ],
      { stdio: "pipe" },
    );
  }
  launchEnv.HOME = browserHome;
  try {
    for (const i of [0, 1]) {
      const dir = path.join(temp, "browser-" + i);
      fs.mkdirSync(dir, { mode: 0o700 });
      if (binary === "firefox") {
        execFileSync(
          "certutil",
          ["-N", "-d", "sql:" + dir, "--empty-password"],
          { stdio: "pipe" },
        );
        execFileSync(
          "certutil",
          [
            "-A",
            "-d",
            "sql:" + dir,
            "-n",
            "LOCAL CLIENT TEST",
            "-t",
            "C,,",
            "-i",
            localCA,
          ],
          { stdio: "pipe" },
        );
      }
      contexts.push(
        await (
          binary === "firefox" ? firefox : chromium
        ).launchPersistentContext(dir, {
          headless: true,
          env: launchEnv,
          executablePath:
            binary === "firefox"
              ? firefox.executablePath()
              : "/usr/bin/google-chrome",
          ...(binary === "chromium" ? { chromiumSandbox: true } : {}),
        }),
      );
    }
    const pages = await Promise.all(contexts.map((c) => c.newPage()));
    const foreign: string[] = [],
      errors: string[] = [];
    for (const page of pages) {
      page.on("pageerror", (e) => errors.push(e.message));
      page.on("request", (r) => {
        const u = new URL(r.url());
        if (
          ["http:", "https:", "ws:", "wss:"].includes(u.protocol) &&
          u.host !== new URL(endpoint).host
        )
          foreign.push(u.origin);
      });
      await page.goto(endpoint);
      await expect(
        page.getByRole("heading", { name: "Open your private space" }),
      ).toBeVisible();
      expect(await page.evaluate(() => isSecureContext)).toBe(true);
      await page.addScriptTag({ url: "/qa-client.js" });
      await page.evaluate(async () =>
        (window as any).havenIntegration.configureClientDelivery(
          await (await fetch("/client-config.json")).json(),
        ),
      );
    }
    const [a, b] = pages;
    await a.setViewportSize({ width: 1440, height: 940 });
    const bodies: string[] = [];
    const statements = [
      "Hey Maya, are we still on for the garden tomorrow?",
      "Absolutely. I’ll bring the coffee ☕",
      "Perfect. I found a quiet spot by the water.",
      "I’ll send you the photos here afterward.",
      "Sounds good. See you at ten 🌿",
    ];
    for (const p of pages)
      p.on("request", (r) => {
        if (r.url().includes("/messages") && r.postData())
          bodies.push(r.postData()!);
      });
    const credentials = JSON.parse(
      fs.readFileSync(path.join(root, ".local/ui-credentials.json"), "utf8"),
    );
    await loginBootstrap(a, credentials);
    const invitations = await a.evaluate(async () =>
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
            device: await h.shareDevice(w.m.state.device_id),
          };
        },
        { token: invitations[i].token, name: i ? "Nora" : "Maya" },
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
    await a.evaluate(() => (window as any).m.lock());
    await a.reload();
    await a.getByRole("button", { name: "Devices", exact: true }).click();
    await a
      .getByLabel("Local unlock passphrase", { exact: true })
      .fill(secrets[0]);
    await a.getByRole("button", { name: "Unlock vault", exact: true }).click();
    await expect(a.locator(".key-state")).toContainText(
      "Verified devices only",
    );
    await a.getByRole("button", { name: "Messages", exact: true }).click();
    await a.locator(".conversation-row").click();
    await expect(a.locator(".chat-heading")).toContainText("Nora");
    await expect(a.locator(".message-log")).toContainText(statements.at(-1)!);
    expect(
      await a.evaluate(
        async () =>
          (await (await fetch("/api/v1/health")).json()).release_status,
      ),
    ).toBe("ACTIVE_REVIEW_PENDING");
    expect(foreign).toEqual([]);
    expect(errors).toEqual([]);
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
    for (const c of contexts) await c.close();
    fs.rmSync(temp, { recursive: true, force: true });
  }
});
