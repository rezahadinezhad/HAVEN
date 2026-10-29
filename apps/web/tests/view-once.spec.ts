import { test, expect, loginBootstrap, selectAttachment } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
);

test("view-once real UI: encrypted photo/video, account-wide consume, independent group recipients, no cache/export/reopen", async ({
  browser,
}) => {
  test.setTimeout(240000);
  const contexts = await Promise.all(
    [0, 1, 2, 3].map(() => browser.newContext()),
  );
  try {
    const pages = await Promise.all(contexts.map((ctx) => ctx.newPage()));
    for (const page of pages) {
      await page.goto("https://127.0.0.1:8445/__integration__/");
      await page.waitForFunction(() => !!(window as any).havenIntegration);
    }
    for (const page of pages) page.setDefaultTimeout(12000);
    console.log(
      "View-once: creating three accounts and a second approved recipient device",
    );
    const [a, b, c, b2] = pages;
    await loginBootstrap(a, credentials);
    const invites = await a.evaluate(async (credentials) => {
      const h = (window as any).havenIntegration;
      return Promise.all(
        [0, 1, 2].map(() => h.api("admin/invitations", "POST", { hours: 1 })),
      );
    }, credentials);
    for (const [i, page] of [a, b, c].entries())
      await page.evaluate(async (token) => {
        const w = window as any,
          h = w.havenIntegration;
        w.password = crypto.randomUUID() + crypto.randomUUID();
        w.u = (
          await h.api("invitations/redeem", "POST", {
            token,
            username: "once_" + crypto.randomUUID().slice(0, 12),
            password: w.password,
            display_name: "View once test",
          })
        ).user;
        w.secret = crypto.randomUUID() + crypto.randomUUID();
        w.m = await h.Messenger.create(w.u.id, w.secret, "View once browser");
      }, invites[i].token);
    const account = await b.evaluate(() => ({
      username: (window as any).u.username,
      password: (window as any).password,
    }));
    await b2.evaluate(async (account) => {
      const w = window as any,
        h = w.havenIntegration;
      w.u = (await h.api("auth/login", "POST", account)).user;
      w.secret = crypto.randomUUID() + crypto.randomUUID();
      w.m = await h.Messenger.create(
        w.u.id,
        w.secret,
        "Recipient second device",
      );
    }, account);
    const devices = await Promise.all(
      pages.map((page) =>
        page.evaluate(async () => {
          const w = window as any;
          return (await w.havenIntegration.api("devices")).find(
            (d: any) => d.id === w.m.state.device_id,
          );
        }),
      ),
    );
    for (const page of pages)
      await page.evaluate(async (devices) => {
        const w = window as any;
        for (const d of devices)
          await w.m.pin(
            d,
            await w.havenIntegration.fingerprintOf(d.public_key),
          );
      }, devices);
    await b.evaluate(
      async (device) => (window as any).m.approve(device),
      devices[3],
    );
    await b2.evaluate(async () => {
      const w = window as any;
      await w.m.connect();
      await w.m.package();
    });
    console.log(
      "View-once: device enrollment and fingerprint verification complete",
    );
    const cid = await a.evaluate(async () => (window as any).m.create("group"));
    for (const device of devices.slice(1)) {
      await a.evaluate(
        async ({ cid, device }) => {
          const w = window as any;
          await w.m.changeMember(
            await w.havenIntegration.api(`conversations/${cid}`),
            device,
            "add",
          );
        },
        { cid, device },
      );
    }
    const detail = await a.evaluate(
      async (cid) =>
        (window as any).havenIntegration.api(`conversations/${cid}`),
      cid,
    );
    for (const page of [b, c, b2])
      await page.evaluate(
        async (detail) => (window as any).m.sync(detail),
        detail,
      );
    console.log("View-once: four-device MLS group synchronized");
    const secrets = await Promise.all(
      pages.map((page) => page.evaluate(() => (window as any).secret)),
    );
    const photo = await a.evaluate(() => {
      const canvas = document.createElement("canvas");
      canvas.width = 640;
      canvas.height = 480;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "#1769f4";
      ctx.fillRect(0, 0, 640, 480);
      ctx.fillStyle = "white";
      ctx.font = "bold 36px sans-serif";
      ctx.fillText("One private moment", 80, 240);
      return canvas.toDataURL("image/png").split(",")[1];
    });
    const video = await a.evaluate(async () => {
      const canvas = document.createElement("canvas");
      canvas.width = 320;
      canvas.height = 240;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "#1769f4";
      ctx.fillRect(0, 0, 320, 240);
      const stream = canvas.captureStream(12),
        recorder = new MediaRecorder(stream, { mimeType: "video/webm" }),
        parts: Blob[] = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size) parts.push(e.data);
      };
      const ended = new Promise<void>((r) => (recorder.onstop = () => r()));
      recorder.start();
      const interval = setInterval(() => {
        ctx.fillStyle = `hsl(${Date.now() % 360} 65% 45%)`;
        ctx.fillRect(0, 0, 320, 240);
      }, 80);
      await new Promise((r) => setTimeout(r, 1800));
      recorder.stop();
      await ended;
      clearInterval(interval);
      stream.getTracks().forEach((t) => t.stop());
      const bytes = new Uint8Array(
        await new Blob(parts, { type: "video/webm" }).arrayBuffer(),
      );
      return btoa(Array.from(bytes, (b) => String.fromCharCode(b)).join(""));
    });
    console.log("View-once: synthetic photo/video fixtures generated");
    for (const [i, page] of pages.entries()) {
      await page.goto("https://127.0.0.1:8445/");
      await page.getByRole("button", { name: "Devices", exact: true }).click();
      await page
        .getByLabel("Local unlock passphrase", { exact: true })
        .fill(secrets[i]);
      await page
        .getByRole("button", { name: "Unlock vault", exact: true })
        .click();
      await page.getByRole("button", { name: "Messages", exact: true }).click();
      await page.locator(".conversation-row").first().click();
    }
    await expect(
      a.getByLabel("View once photos and videos", { exact: true }),
    ).toHaveCount(0);
    const initPromise = a.waitForRequest(
      (r) => r.url().endsWith("/attachments/init") && r.method() === "POST",
    );
    await selectAttachment(a, "media", {
      name: "private-photo.png",
      mimeType: "image/png",
      buffer: Buffer.from(photo, "base64"),
    });
    const photoMode = a
      .locator(".attachment-confirmation")
      .getByLabel("View once photos and videos", { exact: true });
    await expect(photoMode).not.toBeChecked();
    await photoMode.check();
    await expect(a.locator(".attachment-confirmation")).toContainText(
      "Opening is recorded",
    );
    await a
      .getByRole("button", { name: "Send attachment", exact: true })
      .click();
    const init = (await initPromise).postDataJSON();
    expect(init.view_once).toBe(true);
    await expect(
      a.getByLabel("View once photos and videos", { exact: true }),
    ).toHaveCount(0);
    await expect(
      a.getByText("View-once media sent", { exact: true }),
    ).toBeVisible();
    for (const page of [b, c, b2])
      await expect(
        page.getByRole("button", { name: "Open photo once", exact: false }),
      ).toBeVisible({ timeout: 20000 });
    expect(await b.locator(".message-log img").count()).toBe(0);
    expect(
      await b
        .locator(".message-log")
        .getByRole("button", { name: /Download/ })
        .count(),
    ).toBe(0);
    // A failed durable local tombstone must stop BEFORE any server claim.
    let claims = 0;
    b.on("request", (r) => {
      if (r.url().endsWith("/view-once") && r.method() === "POST") claims++;
    });
    await b.evaluate(() => {
      const original = IDBObjectStore.prototype.put;
      (window as any).onceOriginalPut = original;
      IDBObjectStore.prototype.put = function (...args: any[]) {
        if (this.name === "vault")
          throw new DOMException("Storage unavailable", "QuotaExceededError");
        return (original as any).apply(this, args);
      };
    });
    await b
      .getByRole("button", { name: "Open photo once", exact: false })
      .click();
    await expect(b.getByRole("dialog").getByRole("alert")).toContainText(
      "No media was displayed",
    );
    expect(claims).toBe(0);
    await b
      .getByRole("button", { name: "Close view-once media", exact: true })
      .click();
    await b.evaluate(() => {
      IDBObjectStore.prototype.put = (window as any).onceOriginalPut;
    });
    await b.evaluate(() => {
      const original = URL.revokeObjectURL.bind(URL);
      (window as any).viewOnceRevokedURLs = [];
      URL.revokeObjectURL = (value) => {
        (window as any).viewOnceRevokedURLs.push(value);
        original(value);
      };
    });
    await b.setViewportSize({ width: 390, height: 844 });
    await b
      .getByRole("button", { name: "Open photo once", exact: false })
      .click();
    const viewer = b.getByRole("dialog", {
        name: "View-once photo",
        exact: true,
      }),
      image = viewer.getByRole("img");
    await expect(image).toBeVisible();
    expect(
      await image.evaluate((n) => (n as HTMLImageElement).naturalWidth),
    ).toBe(640);
    const blobURL = await image.getAttribute("src");
    await b.screenshot({
      path: `../../docs/evidence/view-once-photo${process.env.HAVEN_BROWSER === "firefox" ? "-firefox" : ""}.png`,
    });
    // The same account's other approved device cannot claim a second opening.
    expect(
      await b2.evaluate(async (aid) => {
        const csrf = (await (await fetch("/api/v1/auth/csrf")).json()).csrf;
        return (
          await fetch(`/api/v1/attachments/${aid}/view-once`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": csrf,
            },
            body: JSON.stringify({ token: "a".repeat(64) }),
          })
        ).status;
      }, init.id),
    ).toBe(403);
    await b
      .getByRole("button", { name: "Close view-once media", exact: true })
      .click();
    await expect(viewer).not.toBeVisible();
    await expect(b.locator(".view-once-card").first()).toBeDisabled();
    expect(
      await b.evaluate(
        (url) => (window as any).viewOnceRevokedURLs.includes(url),
        blobURL,
      ),
    ).toBe(true);
    const cacheBlocked = await b.evaluate(
      async (url) =>
        new Promise<boolean>((resolve) => {
          const img = new Image();
          img.onload = () => resolve(false);
          img.onerror = () => resolve(true);
          img.src = url!;
        }),
      blobURL,
    );
    console.log(
      "Revoked URL reload blocked by engine:",
      cacheBlocked,
      "(decoded-memory cache is outside the view-once guarantee)",
    );
    expect(
      await b.evaluate(async () => {
        const db = await new Promise<IDBDatabase>((resolve, reject) => {
          const r = indexedDB.open("haven-v1");
          r.onsuccess = () => resolve(r.result);
          r.onerror = () => reject(r.error);
        });
        return new Promise<number>((resolve) => {
          const r = db
            .transaction("ciphertextChunks")
            .objectStore("ciphertextChunks")
            .getAllKeys();
          r.onsuccess = () => {
            resolve(r.result.length);
            db.close();
          };
        });
      }),
    ).toBe(0);
    // Another group recipient still gets their OWN opening.
    await c
      .getByRole("button", { name: "Open photo once", exact: false })
      .click();
    await expect(c.getByRole("dialog").getByRole("img")).toBeVisible();
    await c.keyboard.press("Escape");
    await expect(c.getByRole("dialog")).not.toBeVisible();
    // A real recorded WebM exercises decryption, decoder, playback and automatic close.
    await selectAttachment(a, "media", {
      name: "private-video.webm",
      mimeType: "video/webm",
      buffer: Buffer.from(video, "base64"),
    });
    const videoMode = a
      .locator(".attachment-confirmation")
      .getByLabel("View once photos and videos", { exact: true });
    await expect(videoMode).not.toBeChecked();
    await videoMode.check();
    await a
      .getByRole("button", { name: "Send attachment", exact: true })
      .click();
    await expect(
      b.getByRole("button", { name: "Open video once", exact: false }),
    ).toBeVisible({ timeout: 20000 });
    await b
      .getByRole("button", { name: "Open video once", exact: false })
      .click();
    const movie = b
      .getByRole("dialog", { name: "View-once video", exact: true })
      .locator("video");
    await expect(movie).toBeVisible();
    await movie.evaluate(async (n) => {
      await (n as HTMLVideoElement).play();
    });
    await expect(b.getByRole("dialog")).not.toBeVisible({ timeout: 15000 });
    // Reload cannot resurrect the opened photo/video.
    await b.reload();
    await b.getByRole("button", { name: "Devices", exact: true }).click();
    await b
      .getByLabel("Local unlock passphrase", { exact: true })
      .fill(secrets[1]);
    await b.getByRole("button", { name: "Unlock vault", exact: true }).click();
    await b.getByRole("button", { name: "Messages", exact: true }).click();
    await b.locator(".conversation-row").first().click();
    await expect(b.locator(".view-once-card")).toHaveCount(2);
    for (const card of await b.locator(".view-once-card").all())
      await expect(card).toBeDisabled();
    // Mobile chat gives its entire surface to the thread; return to navigation.
    await b
      .getByRole("button", { name: "Back to conversations", exact: true })
      .click();
    // Real history export has no view-once entries or file keys.
    await b.getByRole("button", { name: "Settings", exact: true }).click();
    b.once("dialog", (d) => d.accept());
    const downloadPromise = b.waitForEvent("download");
    await b
      .getByRole("button", {
        name: "Export decrypted local history",
        exact: true,
      })
      .click();
    const download = await downloadPromise;
    const exported = JSON.parse(
      fs.readFileSync((await download.path())!, "utf8"),
    );
    expect(exported.events.some((e: any) => e.file?.view_once)).toBe(false);
    // Inspect durable tombstones and recovery export; old imported copies are ignored.
    await b.goto("https://127.0.0.1:8445/__integration__/");
    await b.waitForFunction(() => !!(window as any).havenIntegration);
    expect(
      await b.evaluate(
        async ({ secret, uid, aid }) => {
          const w = window as any,
            h = w.havenIntegration,
            m = await h.Messenger.unlock(uid, secret);
          const events = m.state.events.filter((e: any) => e.file?.view_once);
          const redacted = events.every(
            (e: any) => !e.file.key && !e.file.prefix && !e.file.name,
          );
          const kit = await h.recoveryKit(uid, secret, m.state),
            value = await h.unseal(
              kit.recovery,
              uid,
              JSON.parse(kit.kit).sealed,
            );
          const before = m.state.events.length;
          await m.importHistory({
            ...m.state,
            events: [
              {
                ...events[0],
                id: crypto.randomUUID(),
                file: { ...events[0].file, key: "old-backup-key" },
              },
            ],
          });
          return {
            redacted,
            tombstone: !!m.state.view_once_opened[aid],
            exported: value.events.some((e: any) => e.file?.view_once),
            ratchets: value.crypto,
            imported: m.state.events.length !== before,
          };
        },
        { secret: secrets[1], uid: devices[1].user_id, aid: init.id },
      ),
    ).toEqual({
      redacted: true,
      tombstone: true,
      exported: false,
      ratchets: "",
      imported: false,
    });
  } finally {
    await Promise.allSettled(contexts.map((ctx) => ctx.close()));
  }
});
