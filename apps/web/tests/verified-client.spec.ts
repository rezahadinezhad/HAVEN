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
import { loginBootstrap, navigate } from "./fixtures";
const profile = process.env.HAVEN_VERIFIED_PROFILE;
const endpoint = process.env.HAVEN_VERIFIED_URL || "https://127.0.0.1:9455";
test.skip(!profile, "Explicit signed QA release/profile required");

test("signed local client preserves MLS, encrypted media and reload while API content stays data", async () => {
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
    for (const [i, page] of pages.entries())
      await page.evaluate(async (token) => {
        const w = window as any,
          h = w.havenIntegration;
        w.u = (
          await h.api("invitations/redeem", "POST", {
            token,
            username: "verified_" + crypto.randomUUID().slice(0, 12),
            password: crypto.randomUUID() + crypto.randomUUID(),
            display_name: "Verified client test",
          })
        ).user;
        w.secret = crypto.randomUUID() + crypto.randomUUID();
        w.m = await h.Messenger.create(
          w.u.id,
          w.secret,
          "Signed client browser",
        );
      }, invitations[i].token);
    const devices = await Promise.all(
      pages.map((p) =>
        p.evaluate(async () =>
          (window as any).havenIntegration.shareDevice(
            (window as any).m.state.device_id,
          ),
        ),
      ),
    );
    for (const p of pages)
      await p.evaluate(async (devices) => {
        const w = window as any;
        for (const d of devices)
          await w.m.pin(
            d,
            await w.havenIntegration.fingerprintOf(d.public_key),
          );
      }, devices);
    const cid = await a.evaluate(async () =>
      (window as any).m.create("direct"),
    );
    let detail = await a.evaluate(
      async (id) => (window as any).havenIntegration.api(`conversations/${id}`),
      cid,
    );
    await a.evaluate(
      async ({ detail, device }) =>
        (window as any).m.changeMember(detail, device, "add"),
      { detail, device: devices[1] },
    );
    detail = await a.evaluate(
      async (id) => (window as any).havenIntegration.api(`conversations/${id}`),
      cid,
    );
    await b.evaluate(async (c) => (window as any).m.sync(c), detail);
    await a.evaluate(
      async (c) =>
        (window as any).m.send(c, {
          type: "text",
          text: "Independent code, real encrypted delivery",
        }),
      detail,
    );
    detail = await a.evaluate(
      async (id) => (window as any).havenIntegration.api(`conversations/${id}`),
      cid,
    );
    await b.evaluate(async (c) => (window as any).m.sync(c), detail);
    expect(
      await b.evaluate(() => (window as any).m.state.events.at(-1).text),
    ).toBe("Independent code, real encrypted delivery");
    await a.evaluate(async (c) => {
      const w = window as any;
      const meta = await w.m.prepareAttachment(
        new File(
          [new TextEncoder().encode("Signed client encrypted attachment")],
          "proof.txt",
          { type: "text/plain" },
        ),
        c.id,
        new AbortController().signal,
      );
      await w.m.resumeAttachment(
        meta.id,
        () => {},
        new AbortController().signal,
      );
      await w.m.send(c, { type: "file", file: meta });
      await w.m.finishAttachment(meta.id);
    }, detail);
    detail = await a.evaluate(
      async (id) => (window as any).havenIntegration.api(`conversations/${id}`),
      cid,
    );
    await b.evaluate(async (c) => (window as any).m.sync(c), detail);
    expect(
      await b.evaluate(async () => {
        const w = window as any;
        const event = w.m.state.events.findLast((x: any) => x.file);
        const blob = await w.havenIntegration.downloadDecrypt(event.file);
        return blob.text();
      }),
    ).toBe("Signed client encrypted attachment");
    const restored = await b.evaluate(() => {
      const w = window as any;
      const v = { user: w.u.id, secret: w.secret };
      w.m.lock();
      return v;
    });
    await b.reload();
    // The production UI, rather than the QA helper, unlocks the persisted vault.
    await expect(
      b.getByRole("heading", { name: "Conversations", exact: true }),
    ).toBeVisible();
    await navigate(b, "Devices");
    await b
      .getByLabel("Local unlock passphrase", { exact: true })
      .fill(restored.secret);
    await b.getByRole("button", { name: "Unlock vault", exact: true }).click();
    await expect(b.locator(".key-state")).toContainText(
      "Verified devices only",
    );
    expect(
      await b.evaluate(
        async () =>
          (await fetch("/releases/" + "0".repeat(64) + "/crypto-worker.js"))
            .status,
      ),
    ).toBe(404);
    const attackFile = process.env.HAVEN_TEST_ATTACK_FILE;
    if (attackFile) {
      const worker = await b.evaluate(async () => {
        const c = await (await fetch("/client-config.json")).json();
        const url = "/releases/" + c.digest + "/crypto-worker.js";
        return { url, body: await (await fetch(url)).text() };
      });
      fs.writeFileSync(attackFile, "controlled hostile backend test\n", {
        mode: 0o600,
      });
      try {
        expect(
          await b.evaluate(
            async () => (await fetch("/api/v1/compromised-origin")).status,
          ),
        ).toBe(502);
        expect(
          await b.evaluate(
            async () =>
              new Promise((resolve) => {
                const s = document.createElement("script");
                s.src = "/api/v1/compromised-origin";
                s.onload = () => resolve(true);
                s.onerror = () => resolve(false);
                document.head.append(s);
              }),
          ),
        ).toBe(false);
        expect(
          await b.evaluate(() =>
            Boolean((window as any).__originAttackExecuted),
          ),
        ).toBe(false);
        expect(
          await b.evaluate(
            async (url) => await (await fetch(url)).text(),
            worker.url,
          ),
        ).toBe(worker.body);
        expect(await b.evaluate(async () => (await fetch("/")).status)).toBe(
          200,
        );
        await expect(b.locator(".key-state")).toContainText(
          "Verified devices only",
        );
      } finally {
        fs.rmSync(attackFile, { force: true });
      }
    }
    expect(foreign).toEqual([]);
    expect(errors).toEqual([]);
    await b.screenshot({
      path: path.join(
        root,
        `docs/security/client-delivery/evidence/client-${binary}.png`,
      ),
      fullPage: true,
    });
  } finally {
    for (const c of contexts) await c.close();
    fs.rmSync(temp, { recursive: true, force: true });
  }
});
