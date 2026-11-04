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
          ...(process.env.HAVEN_CAPTURE_AURORA === "1" && i === 0
            ? {
                recordVideo: {
                  dir: path.join(root, ".local/flowing/raw-video"),
                  size: { width: 1440, height: 940 },
                },
              }
            : {}),
        }),
      );
    }
    const pages = await Promise.all(contexts.map((c) => c.newPage()));
    const foreign: string[] = [],
      errors: string[] = [];
    const typingFrames: string[][] = [[], []];
    pages.forEach((page, index) =>
      page.on("websocket", (socket) =>
        socket.on("framesent", (event) => {
          const payload = String(event.payload);
          if (payload.includes("ephemeral.typing"))
            typingFrames[index].push(payload);
        }),
      ),
    );
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
    for (const [index, page] of pages.entries()) {
      await page.evaluate(() => (window as any).m.lock());
      await page.reload();
      await navigate(page, "Devices");
      await page
        .getByLabel("Local unlock passphrase", { exact: true })
        .fill(secrets[index]);
      await page
        .getByRole("button", { name: "Unlock vault", exact: true })
        .click();
      await expect(page.locator(".key-state")).toContainText(
        "Verified devices only",
      );
      await navigate(page, "Messages");
      await page.locator(".conversation-row").click();
      await expect(page.locator(".message-log")).toContainText(
        statements.at(-1)!,
      );
    }
    await expect(a.locator(".chat-heading")).toContainText("Nora");
    // Check actual running motion, rather than only the presence of keyframe CSS.
    const initialTransforms = await a
      .locator(".aurora-field")
      .evaluateAll((nodes) =>
        nodes.map((el) => getComputedStyle(el).transform),
      );
    await expect
      .poll(() =>
        a
          .locator(".aurora-field")
          .evaluateAll((nodes) =>
            nodes.map((el) => getComputedStyle(el).transform),
          ),
      )
      .not.toEqual(initialTransforms);

    const listBox = (await a.locator(".conversation-panel").boundingBox())!;
    const headerBox = (await a.locator(".chat-header").boundingBox())!;
    expect(listBox.x).toBeGreaterThan(0);
    expect(headerBox.x - listBox.x - listBox.width).toBeGreaterThan(0);
    // Local feedback works with the privacy default: no remote frame is sent.
    await a
      .getByLabel("Message", { exact: true })
      .fill("A private unsent draft");
    await expect(a.locator(".chat-panel")).toHaveAttribute(
      "data-composing",
      "true",
    );
    await expect(a.locator(".chat-panel")).toHaveAttribute(
      "data-composing",
      "false",
      { timeout: 2500 },
    );
    expect(typingFrames).toEqual([[], []]);
    await expect(b.locator(".typing-indicator")).toHaveCount(0);
    await a.getByLabel("Message", { exact: true }).fill("");
    // Both participants explicitly enable the existing authenticated signal.
    for (const page of pages) {
      await navigate(page, "Settings");
      await expect(
        page.getByLabel("Typing indicators", { exact: true }),
      ).not.toBeChecked();
      await page.getByLabel("Typing indicators", { exact: true }).check();
      await expect(page.locator(".conversation-panel")).toHaveCount(0);
      await navigate(page, "Messages");
    }
    // Wait for the reconfigured socket; filling repeatedly models ongoing typing.
    await expect
      .poll(
        async () => {
          await b
            .getByLabel("Message", { exact: true })
            .fill("An unsent remote draft " + Date.now());
          return typingFrames[1].length;
        },
        { timeout: 8000 },
      )
      .toBeGreaterThan(0);
    await expect(a.locator(".typing-indicator")).toContainText(
      "Another participant is typing",
    );
    const arrived = Date.now();
    await expect(a.locator(".typing-indicator")).toHaveCount(0, {
      timeout: 6500,
    });
    expect(Date.now() - arrived).toBeGreaterThan(3500);
    expect(
      typingFrames[1].every((frame) => {
        const packet = JSON.parse(frame);
        return (
          packet.kind === "ephemeral.typing" &&
          packet.conversation_id === cid &&
          Object.keys(packet).sort().join(",") === "conversation_id,kind,v"
        );
      }),
    ).toBe(true);
    // Disabling the preference stops outgoing signals and clears received state.
    await navigate(b, "Settings");
    await b.getByLabel("Typing indicators", { exact: true }).uncheck();
    await navigate(b, "Messages");
    const sentBefore = typingFrames[1].length;
    await b
      .getByLabel("Message", { exact: true })
      .fill("Still local after opting out");
    await expect(b.locator(".chat-panel")).toHaveAttribute(
      "data-composing",
      "false",
      { timeout: 2500 },
    );
    expect(typingFrames[1]).toHaveLength(sentBefore);
    await b.getByLabel("Message", { exact: true }).fill("");
    await navigate(a, "Settings");
    await a.getByLabel("Typing indicators", { exact: true }).uncheck();
    await a.getByLabel("Animated chat background", { exact: true }).uncheck();
    await navigate(a, "Messages");
    await expect(a.locator(".aurora-backdrop")).toHaveAttribute(
      "data-animated",
      "false",
    );
    expect(
      await a
        .locator(".aurora-field-blue")
        .evaluate((el) => getComputedStyle(el).animationPlayState),
    ).toBe("paused");
    expect(
      await a.evaluate(() => localStorage.getItem("haven-ambient-motion")),
    ).toBe("off");
    const pausedTransforms = await a
      .locator(".aurora-field")
      .evaluateAll((nodes) =>
        nodes.map((el) => getComputedStyle(el).transform),
      );
    // Observation interval: a paused backdrop must remain still in wall-clock time.
    await a.waitForTimeout(250);
    expect(
      await a
        .locator(".aurora-field")
        .evaluateAll((nodes) =>
          nodes.map((el) => getComputedStyle(el).transform),
        ),
    ).toEqual(pausedTransforms);
    await a.emulateMedia({ reducedMotion: "reduce" });
    expect(
      await a
        .locator(".aurora-field-blue")
        .evaluate((el) => getComputedStyle(el).animationName),
    ).toBe("none");
    await a.locator(".members-toggle").hover();
    await a.mouse.down();
    expect(
      await a
        .locator(".members-toggle")
        .evaluate((el) => getComputedStyle(el).transform),
    ).toBe("none");
    await a.mouse.move(0, 0);
    await a.mouse.up();
    await a.emulateMedia({ reducedMotion: "no-preference" });
    await navigate(a, "Settings");
    await a.getByLabel("Animated chat background", { exact: true }).check();
    await navigate(a, "Messages");
    await expect(a.locator(".aurora-backdrop")).toHaveAttribute(
      "data-animated",
      "true",
    );
    // Native modal navigation traps focus, dismisses with Escape, restores trigger.
    await a.getByRole("button", { name: "Open menu", exact: true }).click();
    await expect(
      a.getByRole("dialog", { name: "Navigation menu" }),
    ).toBeVisible();
    await a.keyboard.press("Tab");
    expect(
      await a
        .locator(".workspace-menu")
        .evaluate((el) => el.contains(document.activeElement)),
    ).toBe(true);
    await a.locator(".workspace-menu").evaluate(async (node) => {
      await Promise.all(
        node
          .getAnimations()
          .map((animation) => animation.finished.catch(() => {})),
      );
    });
    const menuBox = (await a.locator(".workspace-menu").boundingBox())!;
    expect(menuBox.x).toBeGreaterThan(0);
    expect(menuBox.y).toBeGreaterThan(0);
    expect(menuBox.y + menuBox.height).toBeLessThan(a.viewportSize()!.height);
    await a.screenshot({ path: "../../.local/aurora/navigation.png" });
    await a.keyboard.press("Escape");
    await expect(a.locator(".workspace-menu")).not.toBeVisible();
    await expect(
      a.getByRole("button", { name: "Open menu", exact: true }),
    ).toBeFocused();
    await a.keyboard.press("Enter");
    await expect(a.locator(".workspace-menu")).toBeVisible();
    await a.mouse.click(1400, 90);
    await expect(a.locator(".workspace-menu")).not.toBeVisible();
    await navigate(a, "Settings");
    await a.locator(".page-content").evaluate(async (node) => {
      await Promise.all(
        node
          .getAnimations()
          .map((animation) => animation.finished.catch(() => {})),
      );
    });
    const cardWidths = await a
      .locator(".page-content > .card")
      .evaluateAll((nodes) =>
        nodes.map((el) => el.getBoundingClientRect().width),
      );
    expect(Math.max(...cardWidths) - Math.min(...cardWidths)).toBeLessThan(2);
    await a.screenshot({ path: "../../.local/floating/settings.png" });
    await navigate(a, "Messages");
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
    await a.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(
        document
          .getAnimations()
          .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
          .map((a) => a.finished.catch(() => {})),
      );
    });
    await a.screenshot({
      path: "../../.github/assets/conversation-desktop.png",
      fullPage: true,
    });
    await a.getByRole("button", { name: "Switch to dark mode" }).click();
    await expect(a.locator("html")).toHaveAttribute("data-theme", "dark");
    await a.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(
        document
          .getAnimations()
          .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
          .map((a) => a.finished.catch(() => {})),
      );
    });
    await a.screenshot({
      path: "../../.github/assets/conversation-dark.png",
      fullPage: true,
    });
    await a.setViewportSize({ width: 390, height: 844 });
    await expect(a.locator(".message-log")).toContainText(statements.at(-1)!);
    await a.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(
        document
          .getAnimations()
          .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
          .map((a) => a.finished.catch(() => {})),
      );
    });
    await a.screenshot({
      path: "../../.github/assets/conversation-mobile.png",
      fullPage: true,
    });
    // Small viewport, RTL drawer, and full-width settings stay inside the viewport.
    for (const width of [320, 390, 760, 768, 1024]) {
      await a.setViewportSize({ width, height: 844 });
      expect(
        await a.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
    await a.setViewportSize({ width: 390, height: 844 });
    await navigate(a, "Settings");
    await a.getByLabel("Language", { exact: true }).selectOption("fa");
    await a.getByRole("button", { name: "باز کردن منو", exact: true }).click();
    await expect(a.getByRole("dialog")).toBeVisible();
    await expect
      .poll(() =>
        a
          .locator(".workspace-menu")
          .evaluate(
            (el) =>
              Math.abs(el.getBoundingClientRect().right - (innerWidth - 8)) < 2,
          ),
      )
      .toBe(true);
    await a.screenshot({ path: "../../.local/aurora/navigation-rtl.png" });
    await a.keyboard.press("Escape");
    expect(
      await a.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(errors).toEqual([]);
    expect(foreign).toEqual([]);
    expect(
      secrets.some((secret) => bodies.some((body) => body.includes(secret))),
    ).toBe(false);
    if (process.env.HAVEN_CAPTURE_AURORA === "1") {
      await a.setViewportSize({ width: 1440, height: 940 });
      await a.getByLabel("زبان", { exact: true }).selectOption("en");
      await a.getByLabel("Theme", { exact: true }).selectOption("dark");
      await navigate(a, "Messages");
      await a.locator(".conversation-row").click();
      await a.getByLabel("Message", { exact: true }).fill("");
      await a.locator(".chat-heading").click();
      await a.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all(
          document
            .getAnimations()
            .filter(
              (animation) =>
                animation.effect?.getComputedTiming().iterations !== Infinity,
            )
            .map((animation) => animation.finished.catch(() => {})),
        );
      });
      const bounds = await a.locator(".chat-panel").boundingBox();
      fs.writeFileSync(
        path.join(root, ".local/flowing/motion-bounds.json"),
        JSON.stringify(bounds),
      );
      for (let frame = 0; frame < 4; frame++) {
        await a.screenshot({
          path: path.join(root, `.local/flowing/motion-${frame}.png`),
        });
        await a.waitForTimeout(3000);
      }
      const video = a.video()!;
      const saving = video.saveAs(
        path.join(root, ".local/flowing/qa-motion-full.webm"),
      );
      await a.close();
      await saving;
    }
  } finally {
    for (const c of contexts) await c.close();
    fs.rmSync(temp, { recursive: true, force: true });
  }
});
