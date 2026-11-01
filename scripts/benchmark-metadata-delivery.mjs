// Companion to benchmark-metadata-delivery.py. Synthetic isolated services only.
import { chromium } from "../apps/web/node_modules/playwright/index.mjs";
import fs from "node:fs";
import path from "node:path";
const config = JSON.parse(
  fs.readFileSync(process.env.HAVEN_BENCH_CONFIG, "utf8"),
);
const origin = new URL(config.origin);
if (origin.hostname !== "127.0.0.1" || !["8450", "8451"].includes(origin.port))
  throw new Error("Isolated benchmark origins required");
const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: true,
  env: {
    PATH: process.env.PATH,
    HOME: path.resolve(".local/browser-home"),
    LD_LIBRARY_PATH: path.resolve(
      ".local/browser-libs/usr/lib/x86_64-linux-gnu",
    ),
  },
});
const contexts = await Promise.all([0, 1].map(() => browser.newContext()));
const pages = await Promise.all(contexts.map((c) => c.newPage()));
let measured = false;
const requests = [];
try {
  for (const p of pages) {
    p.on("requestfinished", (request) => {
      if (!measured || !new URL(request.url()).pathname.startsWith("/api/v1/"))
        return;
      requests.push(
        (async () => ({
          request_bytes: request.postDataBuffer()?.length || 0,
          response_bytes: (await (await request.response()).body()).length,
        }))(),
      );
    });
    await p.goto(config.origin + "/__integration__/");
    await p.waitForFunction(() => !!window.havenIntegration);
  }
  const [a, b] = pages;
  const invites = await a.evaluate(async (config) => {
    const h = window.havenIntegration;
    await h.api("auth/login", "POST", {
      username: config.username,
      password: config.password,
    });
    return await Promise.all(
      [0, 1].map(() => h.api("admin/invitations", "POST", { hours: 1 })),
    );
  }, config);
  for (const [i, p] of pages.entries())
    await p.evaluate(async (token) => {
      const w = window,
        h = w.havenIntegration;
      const user = (
        await h.api("invitations/redeem", "POST", {
          token,
          username: "bench_" + crypto.randomUUID().slice(0, 12),
          password: crypto.randomUUID() + crypto.randomUUID(),
          display_name: "Synthetic benchmark",
        })
      ).user;
      w.m = await h.Messenger.create(
        user.id,
        crypto.randomUUID() + crypto.randomUUID(),
        "Synthetic benchmark",
      );
    }, invites[i].token);
  const devices = await Promise.all(
    pages.map((p) =>
      p.evaluate(async () => {
        const w = window;
        return (await w.havenIntegration.api("devices")).find(
          (d) => d.id === w.m.state.device_id,
        );
      }),
    ),
  );
  for (const p of pages)
    await p.evaluate(async (devices) => {
      const w = window;
      for (const d of devices)
        await w.m.pin(d, await w.havenIntegration.fingerprintOf(d.public_key));
    }, devices);
  const cid = await a.evaluate(() => window.m.create("group"));
  let detail = await a.evaluate(
    (cid) => window.havenIntegration.api(`conversations/${cid}`),
    cid,
  );
  await a.evaluate(
    ({ detail, device }) => window.m.changeMember(detail, device, "add"),
    { detail, device: devices[1] },
  );
  detail = await a.evaluate(
    (cid) => window.havenIntegration.api(`conversations/${cid}`),
    cid,
  );
  await b.evaluate((detail) => window.m.sync(detail), detail);
  // Signals parent to snapshot per-database stats after setup, before measured operations.
  process.stdout.write("READY\n");
  await new Promise((resolve) => process.stdin.once("data", resolve));
  measured = true;
  const send = [],
    receive = [];
  for (let i = 0; i < 30; i++) {
    send.push(
      await a.evaluate(
        async ({ detail, i }) => {
          const t = performance.now();
          await window.m.send(detail, {
            type: "text",
            text: "x".repeat(128) + i,
          });
          return performance.now() - t;
        },
        { detail, i },
      ),
    );
    detail = await a.evaluate(
      (cid) => window.havenIntegration.api(`conversations/${cid}`),
      cid,
    );
    receive.push(
      await b.evaluate(async (detail) => {
        const t = performance.now();
        await window.m.sync(detail);
        return performance.now() - t;
      }, detail),
    );
  }
  const vault = await a.evaluate(async (cid) => {
    const samples = [];
    for (let i = 0; i < 30; i++) {
      const t = performance.now();
      await window.m.draft(cid, "synthetic draft " + i);
      samples.push(performance.now() - t);
    }
    return samples;
  }, cid);
  const idle = await b.evaluate(async (detail) => {
    const samples = [];
    for (let i = 0; i < 10; i++) {
      const t = performance.now();
      await window.m.syncIfChanged(detail);
      samples.push(performance.now() - t);
    }
    return samples;
  }, detail);
  const reconnect = await b.evaluate(async () => {
    const samples = [];
    for (let i = 0; i < 10; i++)
      samples.push(
        await new Promise((resolve, reject) => {
          const t = performance.now();
          const s = new WebSocket(
            location.origin.replace("https:", "wss:") + "/ws/v1",
          );
          const timer = setTimeout(() => {
            s.close();
            reject(new Error("Reconnect timed out"));
          }, 10000);
          s.onerror = () => {
            clearTimeout(timer);
            reject(new Error("Reconnect failed"));
          };
          s.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.kind === "hello")
              s.send(JSON.stringify({ v: 1, kind: "heartbeat" }));
            if (data.kind === "heartbeat") {
              clearTimeout(timer);
              s.close();
              resolve(performance.now() - t);
            }
          };
        }),
      );
    return samples;
  });
  const count = await b.evaluate(
    () => window.m.state.events.filter((e) => e.type === "text").length,
  );
  if (count !== 30) throw new Error("Durable delivery count mismatch");
  const traffic = await Promise.all(requests);
  const summarize = (values) => {
    const sorted = [...values].sort((a, b) => a - b);
    return {
      samples: values.length,
      median_ms: sorted[Math.floor(sorted.length / 2)],
      p95_ms: sorted[Math.ceil(sorted.length * 0.95) - 1],
      total_ms: values.reduce((a, b) => a + b, 0),
    };
  };
  console.log(
    JSON.stringify({
      send: summarize(send),
      receive_sync: summarize(receive),
      encrypted_vault_draft: summarize(vault),
      idle_sync: summarize(idle),
      wss_connect_and_heartbeat: summarize(reconnect),
      delivered_messages: count,
      http_api_bodies: {
        requests: traffic.length,
        upload_bytes: traffic.reduce((a, b) => a + b.request_bytes, 0),
        download_bytes: traffic.reduce((a, b) => a + b.response_bytes, 0),
      },
      scope:
        "30 sequential real browser MLS sends and durable recipient syncs; same current client for both API versions; excludes TLS/header bandwidth, mobile battery and production throughput",
    }),
  );
} finally {
  for (const c of contexts) await c.close();
  await browser.close();
}
