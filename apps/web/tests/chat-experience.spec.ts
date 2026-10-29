import { test, expect, loginBootstrap, selectAttachment } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
);
const origin = "https://127.0.0.1:8445";
const evidence = (name: string) =>
  `../../docs/evidence/chat-${name}${process.env.HAVEN_BROWSER === "firefox" ? "-firefox" : ""}.png`;

test("conversation UX: encrypted messages, keyboard/IME, drafts, replies, scrolling, media, mobile and RTL", async ({
  browser,
}) => {
  test.setTimeout(240000);
  const contexts = await Promise.all([
    browser.newContext(),
    browser.newContext(),
  ]);
  const [a, b] = await Promise.all(
    contexts.map((context) => context.newPage()),
  );
  const foreign: string[] = [],
    bodies: string[] = [];
  for (const page of [a, b]) {
    page.setDefaultTimeout(15000);
    page.on("request", (r) => {
      if (
        !r.url().startsWith("data:") &&
        !r.url().startsWith("blob:") &&
        new URL(r.url()).hostname !== "127.0.0.1"
      )
        foreign.push(r.url());
      if (r.url().includes("/messages") && r.postData())
        bodies.push(r.postData()!);
    });
    await page.addInitScript(() => {
      (window as any).cspViolations = [];
      document.addEventListener("securitypolicyviolation", (e) =>
        (window as any).cspViolations.push(
          `${e.effectiveDirective}:${e.blockedURI}`,
        ),
      );
    });
  }
  try {
    for (const page of [a, b]) {
      await page.goto(`${origin}/__integration__/`);
      await page.waitForFunction(() => !!(window as any).havenIntegration);
    }
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
    const secrets: string[] = [],
      devices: any[] = [];
    for (const [i, page] of [a, b].entries()) {
      const setup = await page.evaluate(
        async ({ token, name }) => {
          const w = window as any,
            h = w.havenIntegration;
          w.secret = crypto.randomUUID() + crypto.randomUUID();
          const account = await h.api("invitations/redeem", "POST", {
            token,
            username: `chatux_${crypto.randomUUID().slice(0, 12)}`,
            password: crypto.randomUUID() + crypto.randomUUID(),
            display_name: name,
          });
          w.m = await h.Messenger.create(
            account.user.id,
            w.secret,
            `${name}'s QA browser`,
          );
          return {
            secret: w.secret,
            device: (await h.api("devices")).find(
              (d: any) => d.id === w.m.state.device_id,
            ),
          };
        },
        { token: invitations[i].token, name: i ? "Nora" : "Maya" },
      );
      secrets.push(setup.secret);
      devices.push(setup.device);
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
      async (device) => (await (window as any).m.startDirect(device)).id,
      devices[1],
    );
    await b.evaluate(async (cid) => {
      const w = window as any,
        c = await w.havenIntegration.api(`conversations/${cid}`);
      await w.m.sync(c);
      await w.m.send(c, {
        type: "text",
        text: "Hey Maya! Shall we meet at the garden tomorrow? 🌿",
      });
    }, cid);
    await a.evaluate(async (cid) => {
      const w = window as any,
        c = await w.havenIntegration.api(`conversations/${cid}`);
      await w.m.sync(c);
      await w.m.send(c, {
        type: "text",
        text: "That sounds lovely. I’ll bring the coffee ☕",
      });
      for (let i = 0; i < 16; i++)
        await w.m.send(c, {
          type: "text",
          text: `Planning note ${i + 1}: Let’s take the path by the water. We can find a quiet spot and catch up before heading home.`,
        });
    }, cid);
    async function unlock(page: typeof a, secret: string) {
      await page.locator(".connect-entry").click();
      await page.getByLabel("Unlock passphrase", { exact: true }).fill(secret);
      await page
        .getByRole("button", { name: "Unlock and continue", exact: true })
        .click();
      await expect(
        page.getByText("This browser is ready", { exact: true }),
      ).toBeVisible();
      await page.getByRole("button", { name: "Messages", exact: true }).click();
      await page.locator(".conversation-row").click();
      await expect(page.getByLabel("Message", { exact: true })).toBeEnabled();
    }
    for (const [i, page] of [a, b].entries()) {
      await page.goto(origin);
      await unlock(page, secrets[i]);
    }
    await expect(a.locator(".chat-heading")).toContainText("Nora");
    await expect(a.locator(".message-log")).toHaveCount(1);
    await expect(a.locator(".message-log")).not.toContainText(
      "server_accepted",
    );
    await expect(a.locator(".day-separator")).toHaveCount(1);
    await expect(
      a.locator('.delivery-state[aria-label="Sent to server"]').first(),
    ).toBeAttached();
    const input = a.getByLabel("Message", { exact: true });
    await input.fill("First line");
    await input.press("Shift+Enter");
    await expect(input).toHaveValue("First line\n");
    await input.type("Second line");
    await expect(input).toHaveValue("First line\nSecond line");
    await input.press("Enter");
    await expect(b.locator(".message-log")).toContainText(
      "First line\nSecond line",
      { timeout: 20000 },
    );
    await expect(input).toHaveValue("");
    await input.fill("IME confirmation stays a draft");
    await input.dispatchEvent("compositionstart", { data: "" });
    await input.press("Enter");
    await input.dispatchEvent("compositionend", { data: "" });
    await expect(
      a
        .locator(".bubble")
        .filter({ hasText: "IME confirmation stays a draft" }),
    ).toHaveCount(0);
    await input.fill("A draft I want to keep");
    const original = a.locator(".bubble").filter({
      has: a.getByText("That sounds lovely. I’ll bring the coffee ☕", {
        exact: true,
      }),
    });
    await original
      .getByRole("button", { name: "Message actions", exact: true })
      .click();
    await original
      .getByRole("button", { name: "Send a heart", exact: true })
      .click();
    await expect(original.locator(".message-reactions")).toContainText("♡");
    await expect(input).toHaveValue("A draft I want to keep");
    await original
      .getByRole("button", { name: "Message actions", exact: true })
      .click();
    await original.getByRole("button", { name: "Edit", exact: true }).click();
    await expect(a.locator(".composer-context")).toContainText("Edit message");
    await input.fill("Actually, I’ll bring tea 🍵");
    await input.press("Enter");
    await expect(b.locator(".message-log")).toContainText(
      "Actually, I’ll bring tea 🍵",
      { timeout: 20000 },
    );
    await expect(input).toHaveValue("A draft I want to keep");
    const edited = a.locator(".bubble").filter({
      has: a.getByText("Actually, I’ll bring tea 🍵", { exact: true }),
    });
    await edited
      .getByRole("button", { name: "Message actions", exact: true })
      .click();
    await edited.getByRole("button", { name: "Edit", exact: true }).click();
    await expect(input).toHaveValue("Actually, I’ll bring tea 🍵");
    await a.getByRole("button", { name: "Cancel edit", exact: true }).click();
    await expect(input).toHaveValue("A draft I want to keep");
    await a.reload();
    await unlock(a, secrets[0]);
    await expect(input).toHaveValue("A draft I want to keep");
    await input.fill("");
    const received = a.locator(".bubble").filter({
      has: a.getByText("Hey Maya! Shall we meet at the garden tomorrow? 🌿", {
        exact: true,
      }),
    });
    await received.getByRole("button", { name: "Reply", exact: true }).click();
    await expect(a.locator(".composer-context")).toContainText("Nora");
    await expect(a.locator(".composer-context")).toContainText("Shall we meet");
    await input.fill("Tomorrow at ten works for me!");
    await input.press("Enter");
    const reply = b.locator(".bubble").filter({
      has: b.getByText("Tomorrow at ten works for me!", { exact: true }),
    });
    await expect(reply.locator(".reply-quote")).toContainText("Shall we meet", {
      timeout: 20000,
    });
    await a
      .getByRole("button", { name: "Search this conversation", exact: true })
      .click();
    await a
      .getByRole("textbox", { name: "Search this conversation", exact: true })
      .fill("bring tea");
    await expect(a.locator(".bubble")).toHaveCount(1);
    await expect(a.locator(".message-log")).toContainText(
      "Actually, I’ll bring tea",
    );
    await a.getByRole("button", { name: "Close search", exact: true }).click();
    await input.fill("A little emoji ");
    await input.press("End");
    await a.getByRole("button", { name: "Add emoji", exact: true }).click();
    await a.getByRole("button", { name: "😊", exact: true }).click();
    await expect(input).toHaveValue("A little emoji 😊");
    await input.fill("");
    await a.locator(".message-log").evaluate((node) => {
      node.scrollTop = 0;
      node.dispatchEvent(new Event("scroll"));
    });
    await expect(
      a.getByRole("button", { name: "Jump to latest", exact: true }),
    ).toBeVisible();
    await b
      .getByLabel("Message", { exact: true })
      .fill("I’ll save us a spot by the water.");
    await b.getByRole("button", { name: "Send", exact: true }).click();
    await expect(
      a.getByRole("button", {
        name: "New messages · jump to latest",
        exact: true,
      }),
    ).toBeVisible({ timeout: 20000 });
    expect(
      await a.locator(".message-log").evaluate((node) => node.scrollTop),
    ).toBeLessThan(80);
    await a
      .getByRole("button", {
        name: "New messages · jump to latest",
        exact: true,
      })
      .click();
    await expect(
      a.getByRole("button", { name: "Jump to latest", exact: true }),
    ).toHaveCount(0);
    await expect(
      a.getByLabel("View once photos and videos", { exact: true }),
    ).toHaveCount(0);
    await a
      .getByRole("button", { name: "Add attachment", exact: true })
      .click();
    await expect(a.locator("#attachment-menu").getByRole("button")).toHaveCount(
      3,
    );
    await a.locator("#attachment-menu").evaluate(async (node) => {
      await Promise.all(
        node
          .getAnimations()
          .map((animation) => animation.finished.catch(() => {})),
      );
    });
    const menuBox = await a.locator("#attachment-menu").boundingBox(),
      clipBox = await a
        .getByRole("button", { name: "Add attachment", exact: true })
        .boundingBox();
    expect(Math.abs(menuBox!.x - clipBox!.x)).toBeLessThan(1);
    await a.screenshot({ path: evidence("attachment-menu"), fullPage: true });
    await a.keyboard.press("Escape");
    await expect(a.locator("#attachment-menu")).not.toBeVisible();
    await a.evaluate(() => {
      const original = URL.revokeObjectURL.bind(URL);
      (window as any).previewRevoked = [];
      URL.revokeObjectURL = (value) => {
        (window as any).previewRevoked.push(value);
        original(value);
      };
    });
    let uploadInits = 0;
    a.on("request", (request) => {
      if (
        request.method() === "POST" &&
        request.url().endsWith("/attachments/init")
      )
        uploadInits++;
    });
    const photo = await a.evaluate(() => {
      const c = document.createElement("canvas");
      c.width = 480;
      c.height = 320;
      const x = c.getContext("2d")!;
      x.fillStyle = "#b8d8c9";
      x.fillRect(0, 0, 480, 320);
      x.fillStyle = "#31594c";
      x.fillRect(0, 220, 480, 100);
      x.fillStyle = "#f0e8be";
      x.beginPath();
      x.arc(350, 80, 35, 0, Math.PI * 2);
      x.fill();
      return c.toDataURL("image/png").split(",")[1];
    });
    await a
      .locator(".bubble")
      .filter({
        has: a.getByText("I’ll save us a spot by the water.", { exact: true }),
      })
      .getByRole("button", { name: "Reply", exact: true })
      .click();
    await input.fill("Keep this draft while sharing a photo");
    await selectAttachment(a, "media", {
      name: "garden-plan.png",
      mimeType: "image/png",
      buffer: Buffer.from(photo, "base64"),
    });
    const selectedPhoto = a.getByRole("img", {
      name: "Selected photo preview",
      exact: true,
    });
    await expect
      .poll(() =>
        selectedPhoto.evaluate((node: HTMLImageElement) => node.naturalWidth),
      )
      .toBe(480);
    const photoURL = await selectedPhoto.getAttribute("src");
    expect(uploadInits).toBe(0);
    const photoOption = a
      .locator(".attachment-confirmation")
      .getByLabel("View once photos and videos", { exact: true });
    await expect(photoOption).not.toBeChecked();
    await photoOption.check();
    await expect(
      a.locator(".attachment-confirmation .view-once-explanation"),
    ).toBeVisible();
    await a
      .locator(".composer-area")
      .screenshot({ path: evidence("attachment-mode") });
    expect(await selectedPhoto.getAttribute("src")).toBe(photoURL);
    await photoOption.uncheck();
    const ordinaryInit = a.waitForRequest(
      (r) => r.url().endsWith("/attachments/init") && r.method() === "POST",
    );
    await a
      .getByRole("button", { name: "Send attachment", exact: true })
      .click();
    expect((await ordinaryInit).postDataJSON().view_once).toBe(false);
    await expect(selectedPhoto).toHaveCount(0);
    expect(
      await a.evaluate(
        (url) => (window as any).previewRevoked.includes(url),
        photoURL,
      ),
    ).toBe(true);
    await expect(
      a.getByLabel("View once photos and videos", { exact: true }),
    ).toHaveCount(0);
    await expect(
      b.getByRole("button", { name: "Open photo", exact: false }),
    ).toBeVisible({ timeout: 20000 });
    await expect(
      b
        .locator(".bubble")
        .filter({
          has: b.getByRole("button", { name: "Open photo", exact: false }),
        })
        .locator(".reply-quote"),
    ).toContainText("spot by the water");
    await expect(input).toHaveValue("Keep this draft while sharing a photo");
    await expect(a.locator(".composer-context")).toHaveCount(0);
    await input.fill("");
    expect(await b.locator(".message-log img").count()).toBe(0);
    await b.getByRole("button", { name: "Open photo", exact: false }).click();
    await expect(
      b.getByRole("dialog", { name: "Photo preview", exact: true }),
    ).toBeVisible();
    await expect
      .poll(() =>
        b
          .locator(".media-preview-stage img")
          .evaluate((n: HTMLImageElement) => n.naturalWidth),
      )
      .toBe(480);
    await b.keyboard.press("Escape");
    await expect(b.locator(".media-preview-stage img")).toHaveCount(0);
    await expect(b.locator(".media-viewer[open]")).toHaveCount(0);
    const video = await a.evaluate(async () => {
      const canvas = document.createElement("canvas");
      canvas.width = 160;
      canvas.height = 120;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "#31594c";
      ctx.fillRect(0, 0, 160, 120);
      const stream = canvas.captureStream(10);
      const recorder = new MediaRecorder(stream, { mimeType: "video/webm" });
      const parts: Blob[] = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) parts.push(event.data);
      };
      const ended = new Promise<void>((resolve) => {
        recorder.onstop = () => resolve();
      });
      recorder.start();
      const timer = setInterval(() => {
        ctx.fillStyle = `hsl(${Date.now() % 360} 40% 35%)`;
        ctx.fillRect(0, 0, 160, 120);
      }, 80);
      await new Promise((resolve) => setTimeout(resolve, 1800));
      recorder.stop();
      await ended;
      clearInterval(timer);
      stream.getTracks().forEach((track) => track.stop());
      return btoa(
        Array.from(
          new Uint8Array(
            await new Blob(parts, { type: "video/webm" }).arrayBuffer(),
          ),
          (byte) => String.fromCharCode(byte),
        ).join(""),
      );
    });
    await selectAttachment(a, "media", {
      name: "garden-walk.webm",
      mimeType: "video/webm",
      buffer: Buffer.from(video, "base64"),
    });
    await expect(a.locator(".attachment-confirmation")).toContainText(
      "garden-walk.webm",
    );
    const selectedVideo = a.getByLabel("Selected video preview", {
      exact: true,
    });
    await expect
      .poll(() =>
        selectedVideo.evaluate((node: HTMLVideoElement) => node.readyState),
      )
      .toBeGreaterThanOrEqual(2);
    const replacedVideoURL = await selectedVideo.getAttribute("src");
    const videoOption = a
      .locator(".attachment-confirmation")
      .getByLabel("View once photos and videos", { exact: true });
    await expect(videoOption).not.toBeChecked();
    await videoOption.check();
    // Replacing the selected media with a document drops the per-file mode.
    await selectAttachment(a, "file", {
      name: "notes.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("QA document, never uploaded"),
    });
    expect(
      await a.evaluate(
        (url) => (window as any).previewRevoked.includes(url),
        replacedVideoURL,
      ),
    ).toBe(true);
    await expect(a.locator(".selected-file-preview iframe")).toHaveCount(0);
    await expect(a.locator(".selected-file-fallback")).toBeVisible();
    await expect(
      a.getByLabel("View once photos and videos", { exact: true }),
    ).toHaveCount(0);
    await selectAttachment(a, "media", {
      name: "garden-walk.webm",
      mimeType: "video/webm",
      buffer: Buffer.from(video, "base64"),
    });
    await expect(videoOption).not.toBeChecked();
    await videoOption.check();
    await expect(
      b.getByRole("button", { name: "Open video", exact: false }),
    ).toHaveCount(0);
    const removedVideoURL = await selectedVideo.getAttribute("src");
    await a
      .getByRole("button", { name: "Remove attachment", exact: true })
      .click();
    expect(
      await a.evaluate(
        (url) => (window as any).previewRevoked.includes(url),
        removedVideoURL,
      ),
    ).toBe(true);
    await expect(a.locator(".attachment-confirmation")).toHaveCount(0);
    await expect(
      a.getByLabel("View once photos and videos", { exact: true }),
    ).toHaveCount(0);
    await selectAttachment(a, "media", {
      name: "garden-walk.webm",
      mimeType: "video/webm",
      buffer: Buffer.from(video, "base64"),
    });
    await expect(videoOption).not.toBeChecked();
    await expect
      .poll(() =>
        selectedVideo.evaluate((node: HTMLVideoElement) => node.videoWidth),
      )
      .toBe(160);
    await a
      .locator(".attachment-confirmation")
      .screenshot({ path: evidence("selected-video") });
    const sentVideoURL = await selectedVideo.getAttribute("src");
    const ordinaryVideoInit = a.waitForRequest(
      (r) => r.url().endsWith("/attachments/init") && r.method() === "POST",
    );
    await a
      .getByRole("button", { name: "Send attachment", exact: true })
      .click();
    expect((await ordinaryVideoInit).postDataJSON().view_once).toBe(false);
    expect(
      await a.evaluate(
        (url) => (window as any).previewRevoked.includes(url),
        sentVideoURL,
      ),
    ).toBe(true);
    await expect(
      b.getByRole("button", { name: "Open video", exact: false }),
    ).toBeVisible({ timeout: 20000 });
    await b.getByRole("button", { name: "Open video", exact: false }).click();
    const movie = b
      .getByRole("dialog", { name: "Video preview", exact: true })
      .locator("video");
    await expect(movie).toBeVisible();
    await expect
      .poll(() =>
        movie.evaluate((node) => (node as HTMLVideoElement).readyState),
      )
      .toBeGreaterThanOrEqual(2);
    expect(
      await movie.evaluate(async (node) => {
        const v = node as HTMLVideoElement;
        v.currentTime = 0;
        await v.play();
        return !v.paused;
      }),
    ).toBe(true);
    await b.getByRole("button", { name: "Close preview", exact: true }).click();
    await expect(b.locator(".media-preview-stage video")).toHaveCount(0);
    await b.getByRole("button", { name: "Open photo", exact: false }).click();
    await expect(b.locator(".media-preview-stage img")).toBeVisible();
    await b.evaluate(() => window.dispatchEvent(new Event("haven:lock")));
    await expect(b.locator(".media-viewer[open]")).toHaveCount(0);
    await expect(b.locator(".media-preview-stage img")).toHaveCount(0);
    // Music/audio selection previews locally, then travels through the existing encrypted file flow.
    const sampleCount = 16000,
      wave = Buffer.alloc(44 + sampleCount * 2);
    wave.write("RIFF", 0);
    wave.writeUInt32LE(wave.length - 8, 4);
    wave.write("WAVEfmt ", 8);
    wave.writeUInt32LE(16, 16);
    wave.writeUInt16LE(1, 20);
    wave.writeUInt16LE(1, 22);
    wave.writeUInt32LE(8000, 24);
    wave.writeUInt32LE(16000, 28);
    wave.writeUInt16LE(2, 32);
    wave.writeUInt16LE(16, 34);
    wave.write("data", 36);
    wave.writeUInt32LE(sampleCount * 2, 40);
    for (let i = 0; i < sampleCount; i++)
      wave.writeInt16LE(
        Math.round(Math.sin((i * 2 * Math.PI * 440) / 8000) * 12000),
        44 + i * 2,
      );
    await selectAttachment(a, "audio", {
      name: "preview-tone.wav",
      mimeType: "audio/wav",
      buffer: wave,
    });
    await expect(
      a.getByLabel("View once photos and videos", { exact: true }),
    ).toHaveCount(0);
    const selectedAudio = a.getByLabel("Selected audio preview", {
      exact: true,
    });
    await expect
      .poll(() =>
        selectedAudio.evaluate((node: HTMLAudioElement) => node.readyState),
      )
      .toBeGreaterThanOrEqual(1);
    expect(
      await selectedAudio.evaluate(async (node: HTMLAudioElement) => {
        await node.play();
        return !node.paused;
      }),
    ).toBe(true);
    const audioHandle = await selectedAudio.elementHandle(),
      audioURL = await selectedAudio.getAttribute("src");
    await a
      .locator(".attachment-confirmation")
      .screenshot({ path: evidence("selected-audio") });
    await a
      .getByRole("button", { name: "Send attachment", exact: true })
      .click();
    expect(
      await a.evaluate(
        (url) => (window as any).previewRevoked.includes(url),
        audioURL,
      ),
    ).toBe(true);
    expect(await audioHandle!.getAttribute("src")).toBeNull();
    expect(
      await audioHandle!.evaluate((node: HTMLAudioElement) => node.paused),
    ).toBe(true);
    await expect(
      b.getByRole("button", {
        name: "Decrypt and play audio",
        exact: true,
      }),
    ).toBeVisible({ timeout: 20000 });
    await b
      .getByRole("button", { name: "Decrypt and play audio", exact: true })
      .click();
    expect(
      await b
        .locator(".message-log audio")
        .evaluate(async (node: HTMLAudioElement) => {
          await node.play();
          return !node.paused;
        }),
    ).toBe(true);
    await selectAttachment(a, "media", {
      name: "invalid.png",
      mimeType: "image/png",
      buffer: Buffer.from("Not an image"),
    });
    await expect(a.locator(".selected-file-preview")).toContainText(
      "This browser cannot preview this file",
    );
    await a
      .getByRole("button", { name: "Remove attachment", exact: true })
      .click();
    await selectAttachment(a, "file", {
      name: "inert.svg",
      mimeType: "image/svg+xml",
      buffer: Buffer.from(
        '<svg xmlns="http://www.w3.org/2000/svg"><script>window.previewXss=true</script></svg>',
      ),
    });
    await expect(
      a.locator(
        ".selected-file-preview img, .selected-file-preview iframe, .selected-file-preview object",
      ),
    ).toHaveCount(0);
    expect(await a.evaluate(() => !!(window as any).previewXss)).toBe(false);
    await a
      .getByRole("button", { name: "Remove attachment", exact: true })
      .click();
    await selectAttachment(a, "media", {
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Wrong category"),
    });
    await expect(a.locator(".composer-area")).toContainText(
      "Choose a photo or video, or use File",
    );
    await expect(a.locator(".attachment-confirmation")).toHaveCount(0);
    await a.screenshot({ path: evidence("desktop"), fullPage: true });
    await expect(
      a.locator(".composer-area").getByText("Chat tips", { exact: true }),
    ).toHaveCount(0);
    await a.setViewportSize({ width: 900, height: 800 });
    expect(
      await a.evaluate(() => document.documentElement.scrollWidth > innerWidth),
    ).toBe(false);
    await a.screenshot({ path: evidence("tablet"), fullPage: true });
    await a.setViewportSize({ width: 1280, height: 820 });
    await a
      .getByRole("button", { name: "Switch to dark mode", exact: true })
      .click();
    await a.screenshot({ path: evidence("dark"), fullPage: true });
    await a.setViewportSize({ width: 390, height: 844 });
    await expect(a.locator(".sidebar")).toBeHidden();
    await expect(input).toBeVisible();
    await a.screenshot({ path: evidence("mobile"), fullPage: true });
    for (const size of [
      { width: 320, height: 568 },
      { width: 390, height: 450 },
    ]) {
      await a.setViewportSize(size);
      expect(
        await a.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
      ).toBe(false);
      const box = await a.locator(".composer").boundingBox();
      expect(box!.y + box!.height).toBeLessThanOrEqual(size.height);
    }
    await a.setViewportSize({ width: 390, height: 844 });
    await a
      .getByRole("button", { name: "Back to conversations", exact: true })
      .click();
    await a.getByRole("button", { name: "فارسی", exact: true }).click();
    await a.locator(".conversation-row").click();
    await expect(a.locator("html")).toHaveAttribute("dir", "rtl");
    await a.getByLabel("پیام", { exact: true }).fill("سلام، فردا می‌بینمت 🌱");
    await a.evaluate(() => document.fonts.ready.then(() => {}));
    await a.screenshot({ path: evidence("mobile-rtl"), fullPage: true });
    await selectAttachment(a, "media", {
      name: "garden-plan.png",
      mimeType: "image/png",
      buffer: Buffer.from(photo, "base64"),
    });
    const rtlMode = a.locator(".attachment-confirmation input[type=checkbox]");
    await expect(rtlMode).not.toBeChecked();
    await rtlMode.check();
    await a.screenshot({
      path: evidence("attachment-mode-rtl"),
      fullPage: true,
    });
    await a.setViewportSize({ width: 390, height: 450 });
    const pendingComposer = await a.locator(".composer").boundingBox();
    expect(pendingComposer!.y + pendingComposer!.height).toBeLessThanOrEqual(
      450,
    );
    expect(
      await a.evaluate(
        () => document.documentElement.scrollHeight > innerHeight,
      ),
    ).toBe(false);
    await a.setViewportSize({ width: 390, height: 844 });
    await a
      .locator(".attachment-confirmation")
      .getByRole("button", { name: "حذف پیوست", exact: true })
      .click();
    expect(
      await a.evaluate(() => document.documentElement.scrollWidth > innerWidth),
    ).toBe(false);
    await a.emulateMedia({ reducedMotion: "reduce" });
    expect(
      await a
        .locator(".message-tools")
        .first()
        .evaluate((n) => getComputedStyle(n).transitionDuration),
    ).toBe("0s");
    await a.setViewportSize({ width: 1280, height: 820 });
    await selectAttachment(a, "media", {
      name: "garden-plan.png",
      mimeType: "image/png",
      buffer: Buffer.from(photo, "base64"),
    });
    const lockImage = a.locator(".selected-file-preview img");
    await expect
      .poll(() =>
        lockImage.evaluate((node: HTMLImageElement) => node.naturalWidth),
      )
      .toBe(480);
    const lockURL = await lockImage.getAttribute("src"),
      lockNode = await lockImage.elementHandle();
    await a.getByRole("button", { name: "قفل کردن مخزن", exact: true }).click();
    await expect(a.locator(".attachment-confirmation")).toHaveCount(0);
    expect(await lockNode!.getAttribute("src")).toBeNull();
    expect(
      await a.evaluate(
        (url) => (window as any).previewRevoked.includes(url),
        lockURL,
      ),
    ).toBe(true);
    for (const page of [a, b])
      expect(await page.evaluate(() => (window as any).cspViolations)).toEqual(
        [],
      );
    expect(foreign).toEqual([]);
    expect(bodies.join("\n")).not.toContain("Tomorrow at ten works for me!");
    expect(bodies.join("\n")).not.toContain("Actually, I’ll bring tea");
    expect(bodies.join("\n")).not.toContain("garden-plan.png");
  } finally {
    await Promise.all(contexts.map((context) => context.close()));
  }
});
