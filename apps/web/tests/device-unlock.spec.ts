import { test, expect } from "./fixtures";
import { build } from "esbuild";
import fs from "node:fs";
import https from "node:https";
import path from "node:path";
import type { AddressInfo } from "node:net";
import type { Page } from "@playwright/test";

// Isolated localhost origin with a test-root-signed TLS leaf. Browser TLS
// verification remains enabled; no production account or vault is touched.
let server: https.Server;
let origin: string;
const secret = "vault-test-phrase-of-sufficient-length-2026";

test.beforeAll(async () => {
  const root = path.resolve("../..");
  const cert = fs.readFileSync(
    path.join(root, ".local/tls/localhost-test.crt"),
  );
  const key = fs.readFileSync(path.join(root, ".local/tls/localhost-test.key"));
  const bundle = await build({
    entryPoints: ["src/lib/device-unlock.ts"],
    bundle: true,
    write: false,
    platform: "browser",
    format: "iife",
    globalName: "HavenDeviceUnlock",
  });
  server = https.createServer(
    { cert, key, minVersion: "TLSv1.2" },
    (req, res) => {
      res.setHeader("Cache-Control", "no-store");
      res.setHeader("X-Content-Type-Options", "nosniff");
      if (req.url === "/bundle.js") {
        res.setHeader("Content-Type", "application/javascript");
        res.end(bundle.outputFiles[0].text);
      } else {
        res.setHeader("Content-Type", "text/html; charset=utf-8");
        res.end(
          '<!doctype html><meta charset="utf-8"><script src="/bundle.js"></script>',
        );
      }
    },
  );
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  origin = `https://localhost:${(server.address() as AddressInfo).port}`;
});

test.afterAll(async () => {
  if (server)
    await new Promise<void>((resolve) => server.close(() => resolve()));
});

async function authenticator(page: Page, hasPrf: boolean, verified = true) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: {
      protocol: "ctap2",
      ctap2Version: "ctap2_1",
      transport: "internal",
      hasResidentKey: true,
      hasUserVerification: true,
      automaticPresenceSimulation: true,
      isUserVerified: verified,
      hasPrf,
    },
  });
  return cdp;
}

test("device verified PRF wraps the passphrase locally, survives reload, and can be removed", async ({
  browser,
}) => {
  test.skip(
    process.env.HAVEN_BROWSER === "firefox",
    "Chrome CDP virtual authenticator test",
  );
  test.setTimeout(120000);
  const context = await browser.newContext();
  const page = await context.newPage();
  const cdp = await authenticator(page, true);
  try {
    await page.goto(origin);
    expect(
      await page.evaluate(
        () => isSecureContext && location.protocol === "https:",
      ),
    ).toBe(true);
    const result = await page.evaluate(async (value) => {
      const device = (window as any).HavenDeviceUnlock;
      const environment = await device.deviceUnlockEnvironment();
      await device.enrollDeviceUnlock("test-user", "test-device", value);
      const record = await device.loadDeviceUnlock("test-user");
      const first = await device.unlockWithDevice("test-user");
      return { environment, stored: JSON.stringify(record), first };
    }, secret);
    expect(result.environment).toBe("ready");
    expect(result.stored).not.toContain(secret);
    expect(result.stored).toContain("ciphertext");
    expect(result.first).toEqual({ secret, deviceId: "test-device" });
    await page.reload();
    expect(
      await page.evaluate(async () =>
        (window as any).HavenDeviceUnlock.unlockWithDevice("test-user"),
      ),
    ).toEqual({ secret, deviceId: "test-device" });
    expect(
      await page.evaluate(async () => {
        const device = (window as any).HavenDeviceUnlock;
        await device.removeDeviceUnlock("test-user");
        return (await device.loadDeviceUnlock("test-user")) === undefined;
      }),
    ).toBe(true);
  } finally {
    await cdp.detach();
    await context.close();
  }
});

test("no PRF means no stored unlock record", async ({ browser }) => {
  test.skip(
    process.env.HAVEN_BROWSER === "firefox",
    "Chrome CDP virtual authenticator test",
  );
  test.setTimeout(120000);
  const context = await browser.newContext();
  const page = await context.newPage();
  const cdp = await authenticator(page, false);
  try {
    await page.goto(origin);
    const result = await page.evaluate(async (value) => {
      const device = (window as any).HavenDeviceUnlock;
      let failed = false;
      try {
        await device.enrollDeviceUnlock("test-user", "test-device", value);
      } catch {
        failed = true;
      }
      return { failed, stored: !!(await device.loadDeviceUnlock("test-user")) };
    }, secret);
    expect(result).toEqual({ failed: true, stored: false });
  } finally {
    await cdp.detach();
    await context.close();
  }
});

test("user verification failure cannot enroll a device unlock", async ({
  browser,
}) => {
  test.skip(
    process.env.HAVEN_BROWSER === "firefox",
    "Chrome CDP virtual authenticator test",
  );
  test.setTimeout(120000);
  const context = await browser.newContext();
  const page = await context.newPage();
  const cdp = await authenticator(page, true, false);
  try {
    await page.goto(origin);
    const result = await page.evaluate(async (value) => {
      const device = (window as any).HavenDeviceUnlock;
      let failed = false;
      try {
        await device.enrollDeviceUnlock("test-user", "test-device", value);
      } catch {
        failed = true;
      }
      return { failed, stored: !!(await device.loadDeviceUnlock("test-user")) };
    }, secret);
    expect(result).toEqual({ failed: true, stored: false });
  } finally {
    await cdp.detach();
    await context.close();
  }
});

test("copied encrypted record cannot unlock another account", async ({
  browser,
}) => {
  test.skip(
    process.env.HAVEN_BROWSER === "firefox",
    "Chrome CDP virtual authenticator test",
  );
  test.setTimeout(120000);
  const context = await browser.newContext();
  const page = await context.newPage();
  const cdp = await authenticator(page, true);
  try {
    await page.goto(origin);
    const result = await page.evaluate(async (value) => {
      const device = (window as any).HavenDeviceUnlock;
      await device.enrollDeviceUnlock("test-user", "test-device", value);
      const record = await device.loadDeviceUnlock("test-user");
      const database = await new Promise<IDBDatabase>((resolve, reject) => {
        const request = indexedDB.open("haven-device-unlock-v1", 1);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      await new Promise<void>((resolve, reject) => {
        const tx = database.transaction("records", "readwrite");
        tx.objectStore("records").put(record, "other-user");
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
      database.close();
      let rejected = false;
      try {
        await device.unlockWithDevice("other-user");
      } catch {
        rejected = true;
      }
      return {
        rejected,
        originalStillWorks:
          (await device.unlockWithDevice("test-user")).secret === value,
      };
    }, secret);
    expect(result).toEqual({ rejected: true, originalStillWorks: true });
  } finally {
    await cdp.detach();
    await context.close();
  }
});

test("direct IP origin never offers WebAuthn unlock", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await page.goto(origin.replace("localhost", "127.0.0.1"));
    const status = await page.evaluate(() =>
      (window as any).HavenDeviceUnlock.deviceUnlockEnvironment(),
    );
    expect(status).toBe("ip-address");
  } finally {
    await context.close();
  }
});
