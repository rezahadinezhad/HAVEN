import { test, expect, loginBootstrap } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

const root = path.resolve("../..");
const credentials = JSON.parse(
  fs.readFileSync(root + "/.local/ui-credentials.json", "utf8"),
);
const environment = Object.fromEntries(
  fs
    .readFileSync(root + "/.local/test.env", "utf8")
    .split("\n")
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => {
      const at = line.indexOf("=");
      return [line.slice(0, at), line.slice(at + 1)];
    }),
);

test("retired server ciphertext: persisted browser MLS state reloads and continues across rekey", async ({
  browser,
}) => {
  test.setTimeout(120000);
  const contexts = await Promise.all([0, 1].map(() => browser.newContext()));
  try {
    const pages = await Promise.all(
      contexts.map((context) => context.newPage()),
    );
    for (const page of pages) {
      await page.goto("https://127.0.0.1:8445/__integration__/");
      await page.waitForFunction(() => !!(window as any).havenIntegration);
    }
    const [a, b] = pages;
    await loginBootstrap(a, credentials);
    const invitations = await a.evaluate(async (credentials) => {
      const h = (window as any).havenIntegration;
      return Promise.all(
        [0, 1].map(() => h.api("admin/invitations", "POST", { hours: 1 })),
      );
    }, credentials);
    const identities = [];
    for (const [i, page] of pages.entries()) {
      identities.push(
        await page.evaluate(async (token) => {
          const w = window as any,
            h = w.havenIntegration;
          w.user = (
            await h.api("invitations/redeem", "POST", {
              token,
              username: `privacy_${crypto.randomUUID().slice(0, 12)}`,
              password: crypto.randomUUID() + crypto.randomUUID(),
              display_name: "Privacy test",
            })
          ).user;
          w.secret = crypto.randomUUID() + crypto.randomUUID();
          w.m = await h.Messenger.create(
            w.user.id,
            w.secret,
            "Privacy browser",
          );
          const device = (await h.api("devices"))[0];
          return { device, user: w.user, secret: w.secret };
        }, invitations[i].token),
      );
    }
    for (const page of pages)
      await page.evaluate(async (identities) => {
        const w = window as any;
        for (const identity of identities)
          await w.m.pin(
            identity.device,
            await w.havenIntegration.fingerprintOf(identity.device.public_key),
          );
      }, identities);
    const cid = await a.evaluate(async () =>
      (window as any).m.create("direct"),
    );
    const detail = () =>
      a.evaluate(
        async (cid) =>
          (window as any).havenIntegration.api(`conversations/${cid}`),
        cid,
      );
    await a.evaluate(
      async ({ conv, device }) =>
        (window as any).m.changeMember(conv, device, "add"),
      { conv: await detail(), device: identities[1].device },
    );
    await b.evaluate(
      async (conv) => (window as any).m.sync(conv),
      await detail(),
    );
    await a.evaluate(
      async (conv) =>
        (window as any).m.send(conv, {
          type: "text",
          text: "Retained locally after server cleanup",
        }),
      await detail(),
    );
    await b.evaluate(
      async (conv) => (window as any).m.sync(conv),
      await detail(),
    );
    const result = execFileSync(
      root + "/apps/api/.venv/bin/python",
      [
        "manage.py",
        "shell",
        "-c",
        `
import json, os
from datetime import timedelta
from django.utils import timezone
from core.models import MessageEnvelope
from core.retention import retire_delivered
rows = MessageEnvelope.objects.filter(conversation_id=os.environ['HAVEN_RETENTION_TEST_CONVERSATION'])
rows.filter(kind='application').update(received_at=timezone.now()-timedelta(days=2))
retire_delivered(timezone.now())
print(json.dumps({'retired':rows.filter(ciphertext_retired=True, ciphertext=b'', received_at=None).count(), 'controls':rows.filter(kind='commit', ciphertext_retired=False).count()}))
`,
      ],
      {
        cwd: root + "/apps/api",
        env: {
          ...process.env,
          ...environment,
          HAVEN_RETENTION_TEST_CONVERSATION: cid,
        },
        encoding: "utf8",
      },
    );
    expect(JSON.parse(result.trim().split("\n").at(-1)!)).toEqual({
      retired: 1,
      controls: 1,
    });
    // Honest persisted state resumes without requesting the deleted payload.
    for (const [i, page] of pages.entries()) {
      await page.reload();
      await page.waitForFunction(() => !!(window as any).havenIntegration);
      await page.evaluate(async (identity) => {
        const w = window as any;
        w.m = await w.havenIntegration.Messenger.unlock(
          identity.user.id,
          identity.secret,
        );
      }, identities[i]);
    }
    await b.evaluate(
      async (conv) => (window as any).m.sync(conv),
      await detail(),
    );
    expect(
      await b.evaluate(() =>
        (window as any).m.state.events.some(
          (e: any) => e.text === "Retained locally after server cleanup",
        ),
      ),
    ).toBe(true);
    await a.evaluate(
      async ({ conv, device }) =>
        (window as any).m.changeMember(conv, device, "update"),
      { conv: await detail(), device: identities[0].device },
    );
    await b.evaluate(
      async (conv) => (window as any).m.sync(conv),
      await detail(),
    );
    await b.evaluate(
      async (conv) =>
        (window as any).m.send(conv, {
          type: "text",
          text: "Fresh epoch after retention",
        }),
      await detail(),
    );
    await a.evaluate(
      async (conv) => (window as any).m.sync(conv),
      await detail(),
    );
    expect(
      await a.evaluate(() => (window as any).m.state.events.at(-1).text),
    ).toBe("Fresh epoch after retention");
    expect(
      await b.evaluate(async (cid) => {
        const r = await fetch(
          `/api/v1/conversations/${cid}/messages?after_seq=0`,
        );
        return { status: r.status, body: await r.json() };
      }, cid),
    ).toEqual({
      status: 410,
      body: { error: "history_retired_use_verified_fresh_device" },
    });
  } finally {
    for (const context of contexts) await context.close();
  }
});
