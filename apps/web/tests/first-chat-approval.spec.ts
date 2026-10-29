import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
import nodeCrypto from "node:crypto";
const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
);
const origin = "https://127.0.0.1:8445";

test("guide preserves pending browser keys; administrator invitation controls and normal crypto gate remain effective", async ({
  browser,
}) => {
  test.setTimeout(120000);
  const contexts = await Promise.all([
    browser.newContext(),
    browser.newContext(),
    browser.newContext(),
  ]);
  const [admin, first, second] = await Promise.all(
    contexts.map((c) => c.newPage()),
  );
  for (const page of [admin, first, second]) page.setDefaultTimeout(15000);
  let policy: any;
  const account = {
    username: `approval_${nodeCrypto.randomBytes(6).toString("hex")}`,
    password: nodeCrypto.randomBytes(32).toString("hex"),
    display_name: "Approval member",
  };
  const secret = "pending browser unrelated words secret 123";
  try {
    for (const page of [admin, first]) {
      await page.goto(`${origin}/__integration__/`);
      await page.waitForFunction(() => !!(window as any).havenIntegration);
    }
    await loginBootstrap(admin, credentials);
    const invite = await admin.evaluate(async (credentials) => {
      const h = (window as any).havenIntegration;
      return h.api("admin/invitations", "POST", { hours: 1 });
    }, credentials);
    policy = await admin.evaluate(() =>
      (window as any).havenIntegration.api("admin/system-status"),
    );
    await first.evaluate(
      async ({ account, token }) => {
        const h = (window as any).havenIntegration;
        const result = await h.api("invitations/redeem", "POST", {
          ...account,
          token,
        });
        (window as any).firstVault = await h.Messenger.create(
          result.user.id,
          "first browser unrelated words secret 123",
          "First browser",
        );
      },
      { account, token: invite.token },
    );
    await second.goto(origin);
    await second.getByLabel("Username", { exact: true }).fill(account.username);
    await second.getByLabel("Password", { exact: true }).fill(account.password);
    await second.locator("form button.primary").click();
    await second.locator(".connect-entry").click();
    await second.getByLabel("Unlock passphrase", { exact: true }).fill(secret);
    await second
      .getByLabel("Confirm unlock passphrase", { exact: true })
      .fill(secret);
    await second
      .getByRole("button", { name: "Set up and continue", exact: true })
      .click();
    await expect(
      second.getByRole("heading", {
        name: "Approve this browser from a trusted device",
      }),
    ).toBeVisible();
    await expect(
      second.getByRole("button", { name: "Invite a friend", exact: true }),
    ).toHaveCount(0);
    const pending = await second.evaluate(async () =>
      (await (await fetch("/api/v1/devices")).json()).find(
        (d: any) => d.trust_state === "pending",
      ),
    );
    expect(pending).toBeTruthy();
    await second.reload();
    await second.locator(".connect-entry").click();
    await expect(
      second.getByRole("heading", { name: "Unlock this browser", exact: true }),
    ).toBeVisible();
    await second.getByLabel("Unlock passphrase", { exact: true }).fill(secret);
    await second
      .getByRole("button", { name: "Unlock and continue", exact: true })
      .click();
    await expect(
      second.getByRole("heading", {
        name: "Approve this browser from a trusted device",
      }),
    ).toBeVisible();
    await expect(second.locator(".approved-browser-list")).toContainText(
      "First browser",
    );
    await expect(second.locator(".approval-steps li")).toHaveCount(3);
    await second
      .getByRole("button", { name: "Check approval", exact: true })
      .click();
    await expect(second.locator(".connect-error")).toContainText(
      "still waiting for approval",
    );
    await expect(second.locator(".connect-error")).not.toContainText(
      '{"detail"',
    );
    await expect(second.locator(".toast.error")).toHaveCount(0);
    await second
      .getByText("I can’t access the approved browser", { exact: true })
      .click();
    await expect(second.locator(".approval-help")).toContainText(
      "No account recovery method is configured",
    );
    await second.screenshot({
      path: `../../docs/evidence/chat-browser-approval${process.env.HAVEN_BROWSER === "firefox" ? "-firefox" : ""}.png`,
      fullPage: true,
    });
    // Trusted device explicitly approves the same public credential; no reset.
    await first.evaluate(async (device) => {
      const h = (window as any).havenIntegration;
      await (window as any).firstVault.pin(
        device,
        await h.fingerprintOf(device.public_key),
      );
      await (window as any).firstVault.approve(device);
    }, pending);
    await second
      .getByRole("button", { name: "Check approval", exact: true })
      .click();
    await expect(
      second.getByText("This browser is ready", { exact: true }),
    ).toBeVisible();
    const devices = await second.evaluate(
      async () => await (await fetch("/api/v1/devices")).json(),
    );
    expect(devices).toHaveLength(2);
    expect(devices.find((d: any) => d.id === pending.id)?.public_key).toBe(
      pending.public_key,
    );

    await admin.goto(origin);
    await admin
      .getByRole("button", { name: "Operator console", exact: true })
      .click();
    await admin
      .getByRole("button", { name: "Disable member invitations", exact: true })
      .click();
    await expect(
      admin.getByRole("button", {
        name: "Enable member invitations",
        exact: true,
      }),
    ).toBeVisible();
    await second.getByRole("button", { name: "Messages", exact: true }).click();
    await second.locator(".connect-entry").click();
    await expect(
      second.getByText(
        "Ask the administrator for a signup invitation. You can still share a friend link with an existing member.",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      second.getByRole("button", { name: "Invite a friend", exact: true }),
    ).toBeDisabled();
    await expect(
      second.getByRole("button", { name: "Share my friend link", exact: true }),
    ).toBeEnabled();

    await second.goto("https://127.0.0.1:8443/");
    await second.locator(".connect-entry").click();
    await expect(
      second.getByText(
        "Messaging is unavailable until security qualification is complete. An administrator cannot bypass this gate.",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      second.getByRole("button", { name: "Set up and continue", exact: true }),
    ).toBeDisabled();
  } finally {
    if (policy) {
      await admin.goto(`${origin}/__integration__/`);
      await admin.waitForFunction(() => !!(window as any).havenIntegration);
      await admin.evaluate(async (p) => {
        await (window as any).havenIntegration.api(
          "admin/system-status",
          "PATCH",
          {
            member_invitations: p.member_invitations,
            invitations_paused: p.invitations_paused,
          },
        );
      }, policy);
    }
    await Promise.all(contexts.map((c) => c.close()));
  }
});
