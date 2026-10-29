import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
import nodeCrypto from "node:crypto";
const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
);
test("real UI: vault enrollment, fingerprint verification, MLS group, text, offline shell and queued send", async ({
  browser,
}) => {
  test.setTimeout(180000);
  const contexts = await Promise.all(
      [0, 1].map(() => browser.newContext({ permissions: ["microphone"] })),
    ),
    pages = await Promise.all(contexts.map((c) => c.newPage()));
  await contexts[0].routeWebSocket("**/ws/v1", (socket) => socket.close());
  for (const p of pages) {
    await p.goto("https://127.0.0.1:8445/__integration__/");
    await p.waitForFunction(() => !!(window as any).havenIntegration);
  }
  const [a, b] = pages;
  await loginBootstrap(a, credentials);
  const invites = await a.evaluate(async () => {
    const h = (window as any).havenIntegration;
    return Promise.all(
      [0, 1].map(() => h.api("admin/invitations", "POST", { hours: 1 })),
    );
  });
  const secrets = [
    nodeCrypto.randomBytes(32).toString("hex"),
    nodeCrypto.randomBytes(32).toString("hex"),
  ];
  const devices = [];
  for (const [i, p] of pages.entries()) {
    await p.evaluate(async (token) => {
      const h = (window as any).havenIntegration;
      await h.api("invitations/redeem", "POST", {
        token,
        username: `ui_${crypto.randomUUID().slice(0, 12)}`,
        password: crypto.randomUUID() + crypto.randomUUID(),
        display_name: "UI test",
      });
    }, invites[i].token);
    await p.goto("https://127.0.0.1:8445/");
    await p.getByRole("button", { name: "Devices", exact: true }).click();
    await p
      .getByLabel("Local unlock passphrase", { exact: true })
      .fill(secrets[i]);
    await p.getByLabel("Device label", { exact: true }).fill(`UI browser ${i}`);
    await p
      .getByRole("button", { name: "Create device vault", exact: true })
      .click();
    await expect(p.locator(".device-row")).toHaveCount(1);
    devices.push(
      await p.evaluate(async () => {
        const r = await fetch("/api/v1/devices");
        return (await r.json())[0];
      }),
    );
  }
  for (const [i, p] of pages.entries()) {
    const other = devices[1 - i];
    await p
      .getByRole("button", { name: "People & trust", exact: true })
      .click();
    await p.getByLabel("Device ID", { exact: true }).fill(other.id);
    await p
      .getByRole("button", { name: "Look up a known device", exact: true })
      .click();
    const card = p
      .locator("section.card")
      .filter({ has: p.getByText(other.identity, { exact: true }) });
    await card
      .getByLabel("Confirm fingerprint", { exact: true })
      .fill(
        nodeCrypto
          .createHash("sha256")
          .update(Buffer.from(other.public_key, "base64"))
          .digest("hex"),
      );
    await card
      .getByRole("button", { name: "Verify fingerprint", exact: true })
      .click();
  }
  await a.getByRole("button", { name: "Messages", exact: true }).click();
  await a
    .getByRole("button", { name: "New conversation", exact: true })
    .click();
  await a.getByText("Advanced conversation tools", { exact: true }).click();
  await a.getByLabel("Conversation type").selectOption("group");
  await a
    .getByRole("button", { name: "Create conversation manually", exact: true })
    .click();
  await a.getByRole("button", { name: "Group & members", exact: true }).click();
  await a.getByLabel("Device ID", { exact: true }).fill(devices[1].id);
  await a
    .locator(".member-controls")
    .getByRole("button", { name: "Verify fingerprint", exact: true })
    .click();
  await expect(
    a.getByRole("heading", { name: "People & trust", exact: true }),
  ).toBeVisible();
  await a.getByRole("button", { name: "Messages", exact: true }).click();
  if (!(await a.locator(".member-controls").isVisible()))
    await a
      .getByRole("button", { name: "Group & members", exact: true })
      .click();
  await a
    .locator(".member-controls > div")
    .filter({ has: a.getByText(devices[1].id, { exact: true }) })
    .getByRole("button", { name: "Add member", exact: true })
    .click();
  await b.getByRole("button", { name: "Messages", exact: true }).click();
  await expect(b.locator(".conversation-row")).toHaveCount(1, {
    timeout: 15000,
  });
  await b.locator(".conversation-row").click();
  await a
    .getByLabel("Message", { exact: true })
    .fill("UI encrypted message سلام");
  await a.getByRole("button", { name: "Send", exact: true }).click();
  await expect(b.locator(".message-log")).toContainText(
    "UI encrypted message سلام",
    { timeout: 15000 },
  );
  const originalBubble = b
    .locator(".bubble")
    .filter({ has: b.getByText("UI encrypted message سلام", { exact: true }) });
  await originalBubble
    .getByRole("button", { name: "Reply", exact: true })
    .click();
  await b.getByLabel("Message", { exact: true }).fill("An authenticated reply");
  await b.getByRole("button", { name: "Send", exact: true }).click();
  await expect(a.locator(".message-log")).toContainText(
    "An authenticated reply",
    { timeout: 15000 },
  );
  const attack = '<img src=x onerror="window.havenXss=true">';
  await a.getByLabel("Message", { exact: true }).fill(attack);
  await a.getByRole("button", { name: "Send", exact: true }).click();
  await expect(b.locator(".message-log")).toContainText(attack, {
    timeout: 15000,
  });
  expect(await b.evaluate(() => !!(window as any).havenXss)).toBe(false);
  expect(await b.locator(".message-log img").count()).toBe(0);
  const attackBubble = a
    .locator(".bubble")
    .filter({ has: a.getByText(attack, { exact: true }) });
  await attackBubble
    .getByRole("button", { name: "Message actions", exact: true })
    .click();
  await attackBubble.getByRole("button", { name: "Edit", exact: true }).click();
  await a
    .getByLabel("Message", { exact: true })
    .fill("Edited authenticated text");
  await a.getByRole("button", { name: "Send", exact: true }).click();
  await expect(b.locator(".message-log")).toContainText(
    "Edited authenticated text",
    { timeout: 15000 },
  );
  const editedBubble = a
    .locator(".bubble")
    .filter({ has: a.getByText("Edited authenticated text", { exact: true }) });
  await editedBubble
    .getByRole("button", { name: "Message actions", exact: true })
    .click();
  a.once("dialog", (dialog) => dialog.accept());
  await editedBubble
    .getByRole("button", { name: "Delete", exact: true })
    .click();
  await expect(b.locator(".message-log")).toContainText("[deleted]", {
    timeout: 15000,
  });
  await b
    .getByLabel("Search on this device", { exact: true })
    .fill("UI encrypted");
  await expect(b.locator(".bubble")).toHaveCount(1);
  await b.getByLabel("Search on this device", { exact: true }).fill("");
  await a
    .getByRole("button", { name: "Record voice note", exact: true })
    .click();
  await expect(
    a.getByRole("button", { name: "Stop recording", exact: true }),
  ).toBeVisible();
  await a
    .getByRole("button", { name: "Discard recording", exact: true })
    .click();
  await expect(
    a.getByRole("button", { name: "Record voice note", exact: true }),
  ).toBeVisible();
  await expect(
    b.getByRole("button", { name: "Decrypt and play voice note", exact: true }),
  ).toHaveCount(0);
  // Test-generated microphone input exercises capture, encrypted transfer and decrypted browser playback.
  await a
    .getByRole("button", { name: "Record voice note", exact: true })
    .click();
  await expect(
    a.getByRole("button", { name: "Stop recording", exact: true }),
  ).toBeVisible();
  await a.waitForTimeout(1200);
  await a.getByRole("button", { name: "Stop recording", exact: true }).click();
  await expect(
    b.getByRole("button", { name: "Decrypt and play voice note", exact: true }),
  ).toBeVisible({ timeout: 20000 });
  await b
    .getByRole("button", { name: "Decrypt and play voice note", exact: true })
    .click();
  const audio = b.locator("audio");
  await expect(audio).toBeVisible();
  expect(
    await audio.evaluate(async (node) => {
      const a = node as HTMLAudioElement;
      await a.play();
      return !a.paused;
    }),
  ).toBe(true);
  await b.waitForFunction(async () => {
    await navigator.serviceWorker.ready;
    return (await caches.keys()).some((k) => k.startsWith("haven-shell-"));
  });
  await contexts[1].setOffline(true);
  await b.reload();
  await b.getByRole("button", { name: "Devices", exact: true }).click();
  await b
    .getByLabel("Local unlock passphrase", { exact: true })
    .fill(secrets[1]);
  await b.getByRole("button", { name: "Unlock vault", exact: true }).click();
  await b.getByRole("button", { name: "Messages", exact: true }).click();
  await b.locator(".conversation-row").click();
  await expect(b.locator(".message-log")).toContainText(
    "UI encrypted message سلام",
  );
  await b.getByLabel("Message", { exact: true }).fill("queued offline UI");
  await b.getByRole("button", { name: "Send", exact: true }).click();
  await expect(b.locator(".message-log")).toContainText("queued offline UI");
  await a
    .getByLabel("Message", { exact: true })
    .fill("Peer accepted before the offline queue");
  await a.getByRole("button", { name: "Send", exact: true }).click();
  await expect(a.locator(".message-log")).toContainText(
    "Peer accepted before the offline queue",
  );
  await contexts[1].setOffline(false);
  await expect(a.locator(".message-log")).toContainText("queued offline UI", {
    timeout: 25000,
  });
  await expect(b.locator(".message-log")).toContainText(
    "Peer accepted before the offline queue",
    { timeout: 20000 },
  );
  const ordering = await b.locator(".bubble > p").allTextContents();
  expect(
    ordering.indexOf("Peer accepted before the offline queue"),
  ).toBeLessThan(ordering.indexOf("queued offline UI"));
  await b.setViewportSize({ width: 390, height: 844 });
  await b.screenshot({
    path: "../../docs/evidence/mobile-live-messenger.png",
    fullPage: true,
  });
  // Confirmed remote logout must automatically lock an otherwise active UI.
  expect(
    await b.evaluate(async () => {
      const csrf = (await (await fetch("/api/v1/auth/csrf")).json()).csrf;
      const r = await fetch("/api/v1/auth/logout-all", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: "{}",
      });
      return r.ok;
    }),
  ).toBe(true);
  await expect(
    b.getByRole("heading", { name: "Open your private space" }),
  ).toBeVisible({ timeout: 40000 });
  for (const context of contexts) await context.close();
});
