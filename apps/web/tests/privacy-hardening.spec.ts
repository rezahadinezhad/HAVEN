import { test, expect, loginBootstrap, navigate } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
import nodeCrypto from "node:crypto";
const origin = "https://127.0.0.1:8445";
const credentials = JSON.parse(
  fs.readFileSync(path.resolve("../../.local/ui-credentials.json"), "utf8"),
);

test("bucketed media: real AEAD, legacy bytes, corruption, scope, length, retry and view-once", async ({
  page,
}) => {
  await page.goto(`${origin}/__integration__/`);
  await page.waitForFunction(() => !!(window as any).havenIntegration);
  const results = await page.evaluate(async () => {
    const h = (window as any).havenIntegration;
    await h.sodium.ready;
    const realFetch = window.fetch;
    const controller = new AbortController();
    const cid = crypto.randomUUID();
    const data = new Uint8Array(512 * 1024 + 17).map((_, i) => i % 251);
    const file = new File([data], "private-name.bin");
    const meta = await h.prepareUpload(file, cid, controller.signal);
    const db = await h.vaultDB();
    const chunks = await Promise.all(
      Array.from({ length: meta.count }, (_, i) =>
        db.get("ciphertextChunks", `${meta.id}:${i}`),
      ),
    );
    const download = async (m = meta) => {
      const blob = await h.downloadDecrypt(m);
      const result = new Uint8Array(await blob.arrayBuffer());
      return (
        result.length === data.length && result.every((b, i) => b === data[i])
      );
    };
    let fetches = 0,
      mode = "normal",
      failAtOne = false;
    window.fetch = (async (url: string) => {
      const i = Number(String(url).split("/").at(-1));
      fetches++;
      if (failAtOne && i === 1) {
        failAtOne = false;
        throw new TypeError("Synthetic network interruption");
      }
      let body: Uint8Array = chunks[i].slice();
      if (mode === "tamper") body[0] ^= 1;
      if (mode === "truncate") body = body.slice(0, -1);
      if (mode === "extra") body = new Uint8Array([...body, 0]);
      if (mode === "reorder") body = chunks[meta.count - 1 - i];
      return new Response(new Blob([body as Uint8Array<ArrayBuffer>]));
    }) as typeof fetch;
    const denied: string[] = [];
    try {
      if (!(await download())) throw Error("v2 plaintext changed");
      for (const attack of ["tamper", "truncate", "extra", "reorder"]) {
        mode = attack;
        try {
          await download();
          throw Error("Accepted " + attack);
        } catch (e) {
          if (String(e).includes("Accepted ")) throw e;
          denied.push(attack);
        }
      }
      mode = "normal";
      for (const attack of [
        { ...meta, size: meta.size + 1 },
        { ...meta, conversation_id: crypto.randomUUID() },
        { ...meta, format: 3 },
        { ...meta, padded_size: meta.padded_size + 1 },
        { ...meta, size: -1 },
      ]) {
        try {
          await download(attack);
          throw Error("Accepted metadata");
        } catch (e) {
          if (String(e).includes("Accepted metadata")) throw e;
          denied.push("metadata");
        }
      }
      failAtOne = true;
      fetches = 0;
      try {
        await download();
      } catch (e) {
        if (!(e instanceof TypeError)) throw e;
      }
      if (!(await download()) || fetches !== 3)
        throw Error("Verified ciphertext resume failed");
      // Legacy v1 fixture uses the unchanged old AAD and deterministic chunk nonce.
      const s = h.sodium,
        plain = new Uint8Array([1, 2, 3]),
        key = s.randombytes_buf(32),
        prefix = s.randombytes_buf(16);
      const legacy = {
        id: crypto.randomUUID(),
        conversation_id: cid,
        count: 1,
        size: 3,
        name: "legacy",
        mime: "application/octet-stream",
        key: s.to_base64(key),
        prefix: s.to_base64(prefix),
      };
      const nonce = new Uint8Array(24);
      nonce.set(prefix);
      const cipher = s.crypto_aead_xchacha20poly1305_ietf_encrypt(
        plain,
        s.from_string(
          JSON.stringify(["haven-attachment", 1, cid, legacy.id, 0, 1]),
        ),
        null,
        nonce,
        key,
      );
      window.fetch = (async () =>
        new Response(new Blob([cipher]))) as typeof fetch;
      const recovered = new Uint8Array(
        await (await h.downloadDecrypt(legacy)).arrayBuffer(),
      );
      if (recovered.join() !== plain.join())
        throw Error("Legacy format changed");
      s.memzero(key);
      const once = await h.prepareUpload(
        new File([data.slice(0, 30)], "video.mp4", { type: "video/mp4" }),
        cid,
        controller.signal,
        true,
      );
      const onceCipher = await db.get("ciphertextChunks", `${once.id}:0`);
      window.fetch = (async () =>
        new Response(new Blob([onceCipher]))) as typeof fetch;
      await h.downloadDecrypt(once, { viewOnceToken: "synthetic-capability" });
      if (
        (await db.getAllKeys("ciphertextChunks")).some((k: string) =>
          String(k).startsWith(`download:${once.id}:`),
        )
      )
        throw Error("Persisted received view-once bytes");
      await h.discardUpload(once);
      const samples = [
        0,
        1,
        4095,
        4096,
        65536,
        65537,
        1048576,
        1048577,
        25 * 1024 * 1024,
      ].map((size) => ({ size, padded: h.paddedAttachmentSize(size) }));
      return { denied, format: meta.format, samples };
    } finally {
      window.fetch = realFetch;
      await h.discardUpload(meta);
    }
  });
  expect(results.format).toBe(2);
  expect(results.denied).toHaveLength(9);
  expect(
    results.samples.every(
      (x) => x.padded >= x.size && x.padded <= 25 * 1024 * 1024,
    ),
  ).toBe(true);
  expect(results.samples.find((x) => x.size === 65537)?.padded).toBe(81920);
});

test("locked storage, UUID-only offline unlock, privacy profile and generic sharing", async ({
  page,
}) => {
  await page.goto(`${origin}/__integration__/`);
  await page.waitForFunction(() => !!(window as any).havenIntegration);
  await loginBootstrap(page, credentials);
  const account = {
    username: `private_${nodeCrypto.randomBytes(8).toString("hex")}`,
    password: nodeCrypto.randomBytes(24).toString("hex"),
    display_name: "NEVER_CACHE_THIS_PROFILE",
  };
  const secret = nodeCrypto.randomBytes(24).toString("hex");
  const id = await page.evaluate(
    async ({ account, secret }) => {
      const h = (window as any).havenIntegration;
      const invite = await h.api("admin/invitations", "POST", { hours: 1 });
      const { user } = await h.api("invitations/redeem", "POST", {
        token: invite.token,
        ...account,
      });
      const m = await h.Messenger.create(user.id, secret, "Browser");
      m.lock();
      localStorage.setItem("haven-local-user", JSON.stringify(user));
      localStorage.setItem(
        "haven-privacy",
        JSON.stringify({
          typing: true,
          presence: true,
          receipts: true,
          notifications: true,
        }),
      );
      return user.id;
    },
    { account, secret },
  );
  const response = await page.goto(origin);
  expect(response?.headers()["content-security-policy"]).not.toContain(
    "'unsafe-eval'",
  );
  await expect(
    page.getByRole("button", { name: "Open menu", exact: true }),
  ).toBeVisible();
  const stored = await page.evaluate(() => ({ ...localStorage }));
  expect(stored["haven-local-user"]).toBeUndefined();
  expect(stored["haven-account-id"]).toBe(id);
  expect(JSON.stringify(stored)).not.toContain(account.username);
  expect(JSON.stringify(stored)).not.toContain(account.display_name);
  await expect(page.locator(".profile")).not.toContainText(
    account.display_name,
  );
  await expect(page.locator(".profile")).not.toContainText(account.username);
  await navigate(page, "Settings");
  await page
    .getByRole("button", { name: "Use high-privacy settings", exact: true })
    .click();
  await expect
    .poll(() =>
      page.evaluate(() => JSON.parse(localStorage.getItem("haven-privacy")!)),
    )
    .toEqual({
      notifications: false,
      typing: false,
      presence: false,
      receipts: false,
    });
  await page.screenshot({
    path: "../../docs/security/privacy-hardening/evidence/privacy-settings-en.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "فارسی", exact: true }).click();
  await expect(
    page.getByRole("button", {
      name: "استفاده از تنظیمات حریم خصوصی بیشتر",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "English", exact: true }).click();
  // A failed HTTP bootstrap can locate, unlock and show encrypted local data without cached authority.
  await page.context().setOffline(true);
  await page.reload();
  await navigate(page, "Start a chat");
  await page.getByLabel("Unlock passphrase", { exact: true }).fill(secret);
  await page
    .getByRole("button", { name: "Unlock and continue", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Lock vault", exact: true }),
  ).toHaveCount(1);
  await page.context().setOffline(false);
});

test("padded attachment delivery through real MLS, PostgreSQL quotas and view-once authorization", async ({
  browser,
}) => {
  const contexts = await Promise.all([
    browser.newContext(),
    browser.newContext(),
  ]);
  const pages = await Promise.all(contexts.map((c) => c.newPage()));
  try {
    for (const p of pages) {
      await p.goto(`${origin}/__integration__/`);
      await p.waitForFunction(() => !!(window as any).havenIntegration);
    }
    await loginBootstrap(pages[0], credentials);
    const invites = await pages[0].evaluate(async () => {
      const h = (window as any).havenIntegration;
      return [
        (await h.api("admin/invitations", "POST", { hours: 1 })).token,
        (await h.api("admin/invitations", "POST", { hours: 1 })).token,
      ];
    });
    const devices = [];
    for (let i = 0; i < pages.length; i++)
      devices.push(
        await pages[i].evaluate(async (token) => {
          const w = window as any,
            h = w.havenIntegration;
          const { user } = await h.api("invitations/redeem", "POST", {
            token,
            username: `media_${crypto.randomUUID().slice(0, 12)}`,
            password: crypto.randomUUID() + crypto.randomUUID(),
          });
          w.m = await h.Messenger.create(
            user.id,
            crypto.randomUUID() + crypto.randomUUID(),
            "Synthetic media browser",
          );
          const device = (await h.api("devices")).find(
            (d: any) => d.id === w.m.state.device_id,
          );
          return {
            ...device,
            contact_token: (
              await h.api("devices/contact-introduction", "POST", {})
            ).token,
          };
        }, invites[i]),
      );
    const conv = await pages[0].evaluate(async (peer) => {
      const w = window as any,
        h = w.havenIntegration;
      const card = h.contactLink(location.origin, {
        v: 1,
        device_id: peer.id,
        fingerprint: (await h.fingerprintOf(peer.public_key)).replace(
          /\s/g,
          "",
        ),
        introduction: peer.contact_token,
      });
      const introduced = await h.lookupContact(card);
      await w.m.pin(introduced, await h.fingerprintOf(introduced.public_key));
      return w.m.startDirect(introduced);
    }, devices[1]);
    await pages[1].evaluate(
      async ({ conv, peer }) => {
        const w = window as any,
          h = w.havenIntegration;
        await w.m.pin(peer, await h.fingerprintOf(peer.public_key));
        await w.m.sync(conv);
      },
      { conv, peer: devices[0] },
    );
    const uploaded = await pages[0].evaluate(async (conv) => {
      const w = window as any,
        h = w.havenIntegration,
        controller = new AbortController();
      const normal = await h.prepareUpload(
        new File([new Uint8Array(65537).fill(37)], "private-name.bin"),
        conv.id,
        controller.signal,
      );
      await h.resumeUpload(normal, () => {}, controller.signal);
      await w.m.send(conv, { type: "file", file: normal });
      const once = await h.prepareUpload(
        new File([new Uint8Array(17).fill(11)], "private-photo.png", {
          type: "image/png",
        }),
        conv.id,
        controller.signal,
        true,
      );
      await h.resumeUpload(once, () => {}, controller.signal);
      const completed = await h.api(`conversations/${conv.id}`);
      await w.m.send(completed, { type: "file", file: once });
      return { normal, once };
    }, conv);
    const result = await pages[1].evaluate(
      async ({ conv, uploaded }) => {
        const w = window as any,
          h = w.havenIntegration;
        await w.m.sync(await h.api(`conversations/${conv.id}`));
        const files = w.m.state.events
          .filter((e: any) => e.type === "file")
          .map((e: any) => e.file);
        const normal = files.find((f: any) => f.id === uploaded.normal.id),
          once = files.find((f: any) => f.id === uploaded.once.id);
        const bytes = new Uint8Array(
          await (await h.downloadDecrypt(normal)).arrayBuffer(),
        );
        const token =
          crypto.randomUUID().replaceAll("-", "") +
          crypto.randomUUID().replaceAll("-", "");
        const state = await h.api(`attachments/${once.id}/view-once`);
        await h.api(`attachments/${once.id}/view-once`, "POST", { token });
        const onceBytes = new Uint8Array(
          await (
            await h.downloadDecrypt(once, { viewOnceToken: token })
          ).arrayBuffer(),
        );
        let denied = false;
        try {
          await h.api(`attachments/${once.id}/view-once`, "POST", {
            token: "a".repeat(64),
          });
        } catch {
          denied = true;
        }
        return {
          normal: bytes.length === 65537 && bytes.every((x) => x === 37),
          once: onceBytes.length === 17 && onceBytes.every((x) => x === 11),
          state: state.state,
          denied,
        };
      },
      { conv, uploaded },
    );
    expect(result).toEqual({
      normal: true,
      once: true,
      state: "available",
      denied: true,
    });
    expect(uploaded.normal.padded_size).toBe(81920);
  } finally {
    await Promise.all(contexts.map((c) => c.close()));
  }
});
