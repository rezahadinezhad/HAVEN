import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
import nodeCrypto from "node:crypto";

const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
);
const origin = "https://127.0.0.1:8445";
const secret = () => nodeCrypto.randomBytes(32).toString("hex");

test("ordinary members: guided setup, private invitation, explicit mutual verification, chat and unlock", async ({
  browser,
}) => {
  test.setTimeout(180000);
  const contexts = await Promise.all([
    browser.newContext(),
    browser.newContext(),
  ]);
  const [a, b] = await Promise.all(contexts.map((c) => c.newPage()));
  for (const page of [a, b]) page.setDefaultTimeout(15000);
  const foreign: string[] = [],
    leakedFragments: string[] = [];
  for (const page of [a, b])
    page.on("request", (r) => {
      if (
        !r.url().startsWith("data:") &&
        new URL(r.url()).hostname !== "127.0.0.1"
      )
        foreign.push(r.url());
      if (r.url().includes("connect=") || r.url().includes("invite="))
        leakedFragments.push(r.url());
    });
  const aSecret = secret(),
    bSecret = secret();
  try {
    await a.goto(`${origin}/__integration__/`);
    await a.waitForFunction(() => !!(window as any).havenIntegration);
    await loginBootstrap(a, credentials);
    const account = {
      username: `guided_${secret().slice(0, 12)}`,
      password: secret(),
      display_name: "Alice",
    };
    await a.evaluate(
      async ({ credentials, account }) => {
        const h = (window as any).havenIntegration;
        const invitation = await h.api("admin/invitations", "POST", {
          hours: 1,
        });
        await h.api("invitations/redeem", "POST", {
          token: invitation.token,
          ...account,
        });
      },
      { credentials, account },
    );
    await a.goto(origin);
    await a.locator(".connect-entry").click();
    await expect(
      a.getByRole("heading", { name: "Set up this browser", exact: true }),
    ).toBeVisible();
    await a.getByLabel("Unlock passphrase", { exact: true }).fill(aSecret);
    await a
      .getByLabel("Confirm unlock passphrase", { exact: true })
      .fill(aSecret);
    await a
      .getByRole("button", { name: "Set up and continue", exact: true })
      .click();
    await expect(
      a.getByText("This browser is ready", { exact: true }),
    ).toBeVisible();
    await expect(
      a.getByText("Signup invitations left today: 3", { exact: true }),
    ).toBeVisible();
    await a.getByText("My security code", { exact: true }).click();
    const aCode = await a
      .locator(".connect-own-code .security-code")
      .innerText();
    expect(aCode.replace(/\s/g, "")).toMatch(/^[a-f0-9]{64}$/);
    await a
      .getByRole("button", { name: "Invite a friend", exact: true })
      .click();
    const invite = await a.getByLabel("Link to share").inputValue();
    expect(invite).toContain("#connect=");
    expect(invite).toContain("&invite=");
    await expect(
      a.getByRole("img", { name: "Friend link QR code" }),
    ).toBeVisible();
    await a.screenshot({
      path: "../../docs/evidence/first-chat-invitation.png",
      mask: [
        a.locator(".connect-share textarea"),
        a.locator(".connect-share .qr"),
      ],
      fullPage: true,
    });

    await b.goto(invite);
    await expect(
      b.getByLabel("Invitation token", { exact: true }),
    ).not.toHaveValue("");
    expect(new URL(b.url()).hash).toBe("");
    await b
      .getByLabel("Username", { exact: true })
      .fill(`guided_${secret().slice(0, 12)}`);
    await b.getByLabel("Password", { exact: true }).fill(secret());
    await b.getByLabel("Display name", { exact: true }).fill("Bob");
    await b.locator("form button.primary").click();
    await expect(
      b.getByRole("heading", { name: "Set up this browser", exact: true }),
    ).toBeVisible();
    await b.getByLabel("Unlock passphrase", { exact: true }).fill(bSecret);
    await b
      .getByLabel("Confirm unlock passphrase", { exact: true })
      .fill(bSecret);
    await b
      .getByRole("button", { name: "Set up and continue", exact: true })
      .click();
    await expect(
      b.getByRole("heading", { name: "Compare your friend’s security code" }),
    ).toBeVisible();
    await expect(b.locator(".connect-verify .security-code")).toHaveText(aCode);
    await expect(
      b.getByRole("button", { name: "Verify and continue" }),
    ).toBeDisabled();
    const before = await b.evaluate(async () => ({
      conversations: await (await fetch("/api/v1/conversations")).json(),
      admin: (await fetch("/api/v1/admin/users")).status,
    }));
    expect(before.conversations).toHaveLength(0);
    expect(before.admin).toBe(403);
    await b.screenshot({
      path: "../../docs/evidence/first-chat-verify.png",
      fullPage: true,
    });
    await b
      .getByRole("checkbox", {
        name: "I compared the entire code with my friend through another trusted channel",
      })
      .check();
    await b.getByRole("button", { name: "Verify and continue" }).click();
    await expect(b.getByLabel("Message", { exact: true })).toBeEnabled();
    await b
      .getByLabel("Message", { exact: true })
      .fill("Hello Alice, from the guided flow.");
    await b.getByRole("button", { name: "Send", exact: true }).click();
    await b.locator(".connect-entry").click();
    await b.getByText("My security code", { exact: true }).click();
    const bCode = await b
      .locator(".connect-own-code .security-code")
      .innerText();

    await a.getByRole("button", { name: "Messages", exact: true }).click();
    await expect(a.locator(".conversation-row")).toHaveCount(1, {
      timeout: 20000,
    });
    await a.locator(".conversation-row").click();
    await expect(
      a.getByRole("heading", { name: "Compare your friend’s security code" }),
    ).toBeVisible();
    await expect(a.locator(".toast")).not.toContainText(
      "Verify device fingerprint before accepting:",
    );
    await expect(a.locator(".incoming-verification .security-code")).toHaveText(
      bCode,
    );
    await expect(a.getByLabel("Message", { exact: true })).toBeDisabled();
    await expect(a.locator(".message-log")).not.toContainText(
      "Hello Alice, from the guided flow.",
    );
    await a.getByLabel("Friend’s name", { exact: true }).fill("Bob");
    await a
      .getByRole("checkbox", {
        name: "I compared the entire code with my friend through another trusted channel",
      })
      .check();
    await a.getByRole("button", { name: "Verify and continue" }).click();
    await expect(a.locator(".message-log")).toContainText(
      "Hello Alice, from the guided flow.",
      { timeout: 20000 },
    );
    await a
      .getByLabel("Message", { exact: true })
      .fill("Hello Bob. It works both ways.");
    await a.getByRole("button", { name: "Send", exact: true }).click();
    await b.getByRole("button", { name: "Messages", exact: true }).click();
    await b.locator(".conversation-row").click();
    await expect(b.locator(".message-log")).toContainText(
      "Hello Bob. It works both ways.",
      { timeout: 20000 },
    );
    await expect(a.locator(".chat-heading")).toContainText("Bob");
    await a.screenshot({
      path: "../../docs/evidence/first-chat-conversation.png",
      fullPage: true,
    });

    const originalDevice = await a.evaluate(
      async () => (await (await fetch("/api/v1/devices")).json())[0].id,
    );
    await a.reload();
    await a.locator(".connect-entry").click();
    await expect(
      a.getByRole("heading", { name: "Unlock this browser", exact: true }),
    ).toBeVisible();
    await expect(
      a.getByLabel("Confirm unlock passphrase", { exact: true }),
    ).toHaveCount(0);
    await a.getByLabel("Unlock passphrase", { exact: true }).fill(aSecret);
    await a
      .getByRole("button", { name: "Unlock and continue", exact: true })
      .click();
    await expect(
      a.getByText("This browser is ready", { exact: true }),
    ).toBeVisible();
    const devices = await a.evaluate(
      async () => await (await fetch("/api/v1/devices")).json(),
    );
    expect(devices).toHaveLength(1);
    expect(devices[0].id).toBe(originalDevice);
    await a.getByRole("button", { name: "Messages", exact: true }).click();
    await a.locator(".conversation-row").click();
    await expect(a.locator(".message-log")).toContainText(
      "Hello Bob. It works both ways.",
    );
    await a.locator(".connect-entry").click();
    await a
      .getByRole("button", { name: "Invite a friend", exact: true })
      .click();
    await expect(
      a.getByRole("heading", { name: "Your friend’s invitation", exact: true }),
    ).toBeVisible();
    await a
      .getByRole("button", { name: "Revoke this invitation", exact: true })
      .click();
    await expect(
      a.getByRole("heading", { name: "Your friend link", exact: true }),
    ).toBeVisible();
    expect(
      await a.getByLabel("Link to share", { exact: true }).inputValue(),
    ).not.toContain("&invite=");
    const remaining = await a.evaluate(
      async () => await (await fetch("/api/v1/invitations")).json(),
    );
    expect(remaining.pending_invitations).toHaveLength(0);
    expect(remaining.remaining_today).toBe(1);
    expect(foreign).toEqual([]);
    expect(leakedFragments).toEqual([]);
  } finally {
    await Promise.all(contexts.map((c) => c.close()));
  }
});

test("friend links reject foreign origins, mismatched fingerprints, changed pins; responsive RTL guide", async ({
  browser,
}) => {
  test.setTimeout(150000);
  const context = await browser.newContext();
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  try {
    await page.goto(`${origin}/__integration__/`);
    await page.waitForFunction(() => !!(window as any).havenIntegration);
    await loginBootstrap(page, credentials);
    const valid = await page.evaluate(async (credentials) => {
      const h = (window as any).havenIntegration;
      const card = {
        v: 1,
        device_id: crypto.randomUUID(),
        fingerprint: "a".repeat(64),
        name: "Friend",
      };
      const url = h.contactLink(location.origin, card);
      const attacks = [
        url.replace(location.origin, "https://evil.invalid"),
        url.replace("https:", "http:"),
        `${url}&connect={}`,
        location.origin + "/?connect=x" + new URL(url).hash,
        location.origin +
          "/#connect=" +
          encodeURIComponent(JSON.stringify({ ...card, v: 2 })),
        "x".repeat(4097),
      ];
      for (const attack of attacks) {
        let rejected = false;
        try {
          h.readContactLink(attack, location.origin);
        } catch {
          rejected = true;
        }
        if (!rejected) throw new Error("Malformed friend link was accepted");
      }
      const invite = await h.api("admin/invitations", "POST", { hours: 1 });
      await h.api("invitations/redeem", "POST", {
        token: invite.token,
        username: `links_${crypto.randomUUID().slice(0, 12)}`,
        password: crypto.randomUUID() + crypto.randomUUID(),
        display_name: "Link checks",
      });
      const vault = await h.Messenger.create(
        (await h.api("auth/me")).user.id,
        "link test unrelated words secret 123",
        "Link browser",
      );
      const peerInvite = await h.api("invitations", "POST", {});
      vault.lock();
      return peerInvite.token;
    }, credentials);
    // A second isolated regular member, enrolled through the actual protocol.
    const other = await browser.newContext();
    const peerPage = await other.newPage();
    let peer: any;
    try {
      await peerPage.goto(`${origin}/__integration__/`);
      await peerPage.waitForFunction(() => !!(window as any).havenIntegration);
      peer = await peerPage.evaluate(async (token) => {
        const h = (window as any).havenIntegration;
        const account = await h.api("invitations/redeem", "POST", {
          token,
          username: `peer_${crypto.randomUUID().slice(0, 12)}`,
          password: crypto.randomUUID() + crypto.randomUUID(),
          display_name: "Peer",
        });
        const vault = await h.Messenger.create(
          account.user.id,
          "peer test unrelated words secret 123",
          "Peer browser",
        );
        const devices = await h.api("devices");
        const device = devices.find((d: any) => d.id === vault.state.device_id);
        const card = {
          v: 1,
          device_id: device.id,
          fingerprint: (await h.fingerprintOf(device.public_key)).replace(
            /\s/g,
            "",
          ),
          name: "Peer",
        };
        const result = {
          device,
          url: h.contactLink(location.origin, card),
          bad: h.contactLink(location.origin, {
            ...card,
            fingerprint: "0".repeat(64),
          }),
        };
        vault.lock();
        return result;
      }, valid);
    } finally {
      await other.close();
    }
    await page.goto(origin);
    await page.locator(".connect-entry").click();
    await page
      .getByLabel("Unlock passphrase", { exact: true })
      .fill("link test unrelated words secret 123");
    await page
      .getByRole("button", { name: "Unlock and continue", exact: true })
      .click();
    await expect(
      page.getByText("This browser is ready", { exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "I have a friend link", exact: true })
      .click();
    await page.getByLabel("Friend link", { exact: true }).fill(peer.bad);
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await expect(
      page.locator(".connect-flow").getByRole("alert"),
    ).toContainText("The security code does not match this link");
    await expect(page.getByRole("checkbox")).toHaveCount(0);
    await page
      .getByLabel("Friend link", { exact: true })
      .fill(peer.url.replace(origin, "https://evil.invalid"));
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await expect(
      page.locator(".connect-flow").getByRole("alert"),
    ).toContainText("different server");
    await page.getByLabel("Friend link", { exact: true }).fill(peer.url);
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Verify and continue" }),
    ).toBeDisabled();
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 844 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
    await page.getByRole("button", { name: "فارسی", exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: "../../docs/evidence/first-chat-mobile-rtl.png",
      fullPage: true,
    });
    await page.getByRole("button", { name: "English", exact: true }).click();
    await page.setViewportSize({ width: 1280, height: 960 });
    // A previously verified different key for the same device must block this
    // guide, even when the new link correctly matches the current server key.
    await page.goto(`${origin}/__integration__/`);
    await page.waitForFunction(() => !!(window as any).havenIntegration);
    await page.evaluate(async (device) => {
      const h = (window as any).havenIntegration;
      const v = await h.Messenger.unlock(
        (await h.api("auth/me")).user.id,
        "link test unrelated words secret 123",
      );
      const fake = {
        ...device,
        public_key: btoa(
          String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))),
        ),
      };
      await v.pin(fake, await h.fingerprintOf(fake.public_key));
      v.lock();
    }, peer.device);
    await page.goto(origin);
    await page.locator(".connect-entry").click();
    await page
      .getByLabel("Unlock passphrase", { exact: true })
      .fill("link test unrelated words secret 123");
    await page
      .getByRole("button", { name: "Unlock and continue", exact: true })
      .click();
    await page
      .getByRole("button", { name: "I have a friend link", exact: true })
      .click();
    await page.getByLabel("Friend link", { exact: true }).fill(peer.url);
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await expect(
      page.locator(".connect-verify").getByRole("alert"),
    ).toContainText("This friend’s key changed");
    await expect(
      page.getByRole("button", { name: "Verify and continue" }),
    ).toBeDisabled();
    await expect(page.getByRole("checkbox")).toBeDisabled();
    expect(
      await page.evaluate(
        async () =>
          (await (await fetch("/api/v1/conversations")).json()).length,
      ),
    ).toBe(0);
  } finally {
    await context.close();
  }
});
