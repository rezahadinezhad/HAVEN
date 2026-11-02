import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
import https from "node:https";

const root = path.resolve("../..");
const credentials = JSON.parse(
  fs.readFileSync(root + "/.local/ui-credentials.json", "utf8"),
);
const ca = fs.readFileSync(root + "/.local/tls/root.crt");

test("opaque enrollment context keeps strict device/domain/key checks before actual worker signing", async ({
  page,
}) => {
  await page.goto("https://127.0.0.1:8445/__integration__/");
  await page.waitForFunction(() => !!(window as any).havenIntegration);
  await loginBootstrap(page, credentials);
  const invitation = await page.evaluate(() =>
    (window as any).havenIntegration.api("admin/invitations", "POST", {
      hours: 1,
    }),
  );
  await page.evaluate(async (token) => {
    const w = window as any,
      h = w.havenIntegration;
    const user = (
      await h.api("invitations/redeem", "POST", {
        token,
        username: "challenge_" + crypto.randomUUID().slice(0, 12),
        password: crypto.randomUUID() + crypto.randomUUID(),
        display_name: "Synthetic challenge test",
      })
    ).user;
    w.m = await h.Messenger.create(
      user.id,
      crypto.randomUUID() + crypto.randomUUID(),
      "Challenge browser",
    );
    w.signCalls = 0;
    const actual = Worker.prototype.postMessage;
    // Observe only an operation count, forward every real worker message intact.
    // No private state/keys/command payload is retained or returned by this spy.
    (Worker.prototype as any).postMessage = function (
      this: Worker,
      ...args: any[]
    ) {
      if (args[0]?.command?.op === "sign") w.signCalls++;
      return (actual as any).apply(this, args);
    };
  }, invitation.token);
  let completeRequests = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      new URL(request.url()).pathname.endsWith("/devices/enrollment/complete")
    )
      completeRequests++;
  });
  const endpoint = "**/api/v1/devices/enrollment/request";
  for (const attack of ["device", "domain", "key"]) {
    await page.route(endpoint, async (route) => {
      const request = route.request();
      const headers = await request.allHeaders();
      // Explicit test-CA trust for Node forwarding; browser TLS remains verified.
      // Generic failures avoid Playwright's HTTP call log containing cookie headers.
      const forwarded = await new Promise<{ status: number; body: string }>(
        (resolve, reject) => {
          const remote = https.request(
            request.url(),
            {
              ca,
              method: request.method(),
              headers,
            },
            (response) => {
              const chunks: Buffer[] = [];
              let size = 0;
              response.on("data", (chunk) => {
                size += chunk.length;
                if (size > 16384) remote.destroy();
                else chunks.push(chunk);
              });
              response.on("end", () =>
                resolve({
                  status: response.statusCode || 503,
                  body: Buffer.concat(chunks).toString(),
                }),
              );
            },
          );
          remote.on("error", () =>
            reject(new Error("Verified enrollment forwarding failed")),
          );
          remote.setTimeout(10000, () => remote.destroy());
          remote.end(request.postDataBuffer());
        },
      );
      const body = JSON.parse(forwarded.body);
      const parts = body.signing_payload.split(":");
      if (attack === "device")
        parts[2] = "00000000-0000-4000-8000-000000000001";
      if (attack === "domain") parts[0] = "haven/envelope/v1";
      if (attack === "key")
        body.public_key = Buffer.alloc(32, 42).toString("base64");
      body.signing_payload = parts.join(":");
      await route.fulfill({ status: forwarded.status, json: body });
    });
    const rejected = await page.evaluate(async () => {
      const w = window as any;
      try {
        await w.m.connect();
        return "ACCEPTED";
      } catch (error) {
        return (error as Error).message;
      }
    });
    expect(rejected).toBe("Session challenge binding failed");
    expect(await page.evaluate(() => (window as any).signCalls)).toBe(0);
    expect(completeRequests).toBe(0);
    await page.unroute(endpoint);
  }
  await page.evaluate(() => (window as any).m.connect());
  expect(await page.evaluate(() => (window as any).signCalls)).toBe(1);
  expect(completeRequests).toBe(1);
});
