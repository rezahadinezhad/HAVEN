import { test, expect } from "./fixtures";
import type { BrowserContext, Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { randomBytes } from "node:crypto";
import { createInterface } from "node:readline";
import { spawn, execFileSync, type ChildProcess } from "node:child_process";
import https from "node:https";
const root = path.resolve("../..");
const nginx =
  "nginx:1.28.3-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236";
const credentials = JSON.parse(
  fs.readFileSync(root + "/.local/ui-credentials.json", "utf8"),
);
const environment = Object.fromEntries(
  fs
    .readFileSync(root + "/.local/test.env", "utf8")
    .split("\n")
    .filter((l) => l && !l.startsWith("#"))
    .map((l) => {
      const i = l.indexOf("=");
      return [l.slice(0, i), l.slice(i + 1)];
    }),
);
function installBridgeCertificate(kind: "valid" | "wrong") {
  const folder = root + "/.local/bridge-test-tls/";
  fs.copyFileSync(folder + kind + ".crt", folder + "leaf.next");
  fs.renameSync(folder + "leaf.next", folder + "leaf.crt");
}
const ca = fs.readFileSync(root + "/.local/tls/root.crt");
const primaryOrigin = "https://127.0.0.1:8448",
  backupOrigin = "https://127.0.0.2:8447";
async function probe(url: string) {
  return new Promise<boolean>((resolve) => {
    const req = https.get(url + "/api/v1/health", { ca, agent: false }, (r) => {
      r.resume();
      resolve(r.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(700, () => req.destroy());
  });
}
async function health(url: string) {
  await expect.poll(() => probe(url), { timeout: 20000 }).toBe(true);
}
async function stop(p: ChildProcess | undefined) {
  if (!p || p.exitCode !== null || p.signalCode) return;
  const ended = new Promise((r) => p.once("exit", r));
  p.kill("SIGTERM");
  await ended;
}
async function detail(p: Page, id: string) {
  return p.evaluate(
    async (id) => (window as any).havenIntegration.api(`conversations/${id}`),
    id,
  );
}
async function sync(p: Page, c: any) {
  await p.evaluate(async (c) => (window as any).m.sync(c), c);
}
async function send(p: Page, c: any, text: string) {
  await p.evaluate(
    async ({ c, text }) => (window as any).m.send(c, { type: "text", text }),
    { c, text },
  );
}
async function change(p: Page, c: any, d: any, action: "add" | "transfer") {
  await p.evaluate(
    async ({ c, d, action }) => (window as any).m.changeMember(c, d, action),
    { c, d, action },
  );
}
async function count(p: Page, text: string) {
  return p.evaluate(
    (text) =>
      (window as any).m.state.events.filter((e: any) => e.text === text).length,
    text,
  );
}

test("prepared distinct IP origins: verified private TLS, fail-closed mismatch, fenced database promotion and continuing MLS messages", async ({
  browser,
}) => {
  test.setTimeout(240000);
  const token = randomBytes(8).toString("hex"),
    primary = "haven-bridge-test-" + token,
    backup = "haven-edge-test-" + token;
  const config = root + "/.local/standby-proxy-" + token;
  const contexts: BrowserContext[] = [],
    owned: string[] = [];
  let server: ChildProcess | undefined,
    proxy: ChildProcess | undefined,
    drill: ChildProcess | undefined;
  const docker = (args: string[]) =>
    execFileSync("docker", args, { stdio: "pipe" });
  const password = randomBytes(32).toString("hex");
  const startApi = (port: string) =>
    spawn(
      root + "/apps/api/.venv/bin/uvicorn",
      [
        "haven.asgi:application",
        "--host",
        "127.0.0.1",
        "--port",
        "8103",
        "--no-access-log",
        "--proxy-headers",
      ],
      {
        cwd: root + "/apps/api",
        env: {
          ...process.env,
          ...environment,
          POSTGRES_HOST: "127.0.0.1",
          POSTGRES_PORT: port,
          POSTGRES_DB: "haven",
          POSTGRES_USER: "haven",
          POSTGRES_PASSWORD: password,
          HAVEN_HOSTS: "127.0.0.1,127.0.0.2",
          HAVEN_ORIGINS: primaryOrigin + "," + backupOrigin,
          DJANGO_SETTINGS_MODULE: "haven.integration_settings",
        },
        stdio: "ignore",
      },
    );
  try {
    execFileSync("bash", [root + "/scripts/prepare-bridge-test.sh"], {
      cwd: root,
      stdio: "pipe",
    });
    execFileSync(
      "python3",
      [
        root + "/scripts/render-standby-proxies.py",
        "--output",
        config,
        "--primary-connect-ip",
        "127.0.0.1",
        "--backup-peer-ip",
        "127.0.0.1",
        "--local-test",
      ],
      { stdio: "pipe" },
    );
    drill = spawn("python3", [root + "/scripts/failover-drill.py"], {
      cwd: root,
      env: {
        ...process.env,
        HAVEN_DRILL_INTERACTIVE: "1",
        HAVEN_DRILL_PASSWORD: password,
      },
      stdio: ["pipe", "pipe", "pipe"],
    });
    // Only phase/status JSON is emitted; passwords never enter browser state or evidence.
    const phases: any[] = [];
    createInterface({ input: drill.stdout! }).on("line", (line) => {
      try {
        phases.push(JSON.parse(line));
      } catch {}
    });
    await expect
      .poll(() => phases.some((p) => p.phase === "ready"), { timeout: 60000 })
      .toBe(true);
    server = startApi(
      String(phases.find((p) => p.phase === "ready").primary_port),
    );
    proxy = spawn("node", [root + "/scripts/dev-proxy.mjs"], {
      env: {
        ...process.env,
        HAVEN_DEV_PORT: "8448",
        HAVEN_DEV_API_PORT: "8103",
        HAVEN_INTEGRATION: "1",
      },
      stdio: "ignore",
    });
    const common = [
      "--network",
      "host",
      "--read-only",
      "--cap-drop",
      "ALL",
      "--user",
      `${process.getuid!()}:${process.getgid!()}`,
      "--tmpfs",
      "/var/run:rw,size=1m,mode=1777",
      "--tmpfs",
      "/var/cache/nginx:rw,size=32m,mode=1777",
      "--entrypoint",
      "nginx",
    ];
    docker([
      "run",
      "-d",
      "--name",
      primary,
      "--label",
      "haven.bridge-test=" + token,
      ...common,
      "-v",
      config + ":/etc/haven/config:ro",
      "-v",
      root + "/.local/bridge-test-tls:/etc/haven/bridge-tls:ro",
      nginx,
      "-c",
      "/etc/haven/config/primary-bridge.conf",
      "-g",
      "daemon off;",
    ]);
    owned.push(primary);
    docker([
      "run",
      "-d",
      "--name",
      backup,
      "--label",
      "haven.bridge-test=" + token,
      ...common,
      "-v",
      config + ":/etc/haven/config:ro",
      "-v",
      root + "/.local/bridge-test-tls/backup:/etc/haven/tls:ro",
      "-v",
      root + "/.local/tls/root.crt:/etc/haven/primary-roots.pem:ro",
      "-v",
      root + "/.local/integration:/etc/haven/integration:ro",
      nginx,
      "-c",
      "/etc/haven/config/standby-preparation.conf",
      "-g",
      "daemon off;",
    ]);
    owned.push(backup);
    await health(primaryOrigin);
    await health(backupOrigin);
    // Two real browser profiles, each with an independently enrolled device at each IP origin.
    for (let i = 0; i < 2; i++) contexts.push(await browser.newContext());
    const a = await contexts[0].newPage(),
      b = await contexts[1].newPage(),
      sa = await contexts[0].newPage(),
      sb = await contexts[1].newPage();
    const pages = [a, b, sa, sb];
    for (const [i, p] of pages.entries()) {
      await p.goto(
        (i < 2 ? primaryOrigin : backupOrigin) + "/__integration__/",
      );
      await p.waitForFunction(() => !!(window as any).havenIntegration);
    }
    const invites = await a.evaluate(async (credentials) => {
      const h = (window as any).havenIntegration;
      await h.api("auth/login", "POST", credentials);
      return Promise.all(
        [0, 1].map(() => h.api("admin/invitations", "POST", { hours: 1 })),
      );
    }, credentials);
    for (const [i, p] of [a, b].entries())
      await p.evaluate(async (token) => {
        const w = window as any,
          h = w.havenIntegration;
        w.password = crypto.randomUUID() + crypto.randomUUID();
        w.u = (
          await h.api("invitations/redeem", "POST", {
            token,
            username: "edge_" + crypto.randomUUID().slice(0, 12),
            password: w.password,
            display_name: "Standby test",
          })
        ).user;
        w.secret = crypto.randomUUID() + crypto.randomUUID();
        w.m = await h.Messenger.create(w.u.id, w.secret, "Primary origin");
      }, invites[i].token);
    for (const [i, p] of [sa, sb].entries()) {
      const account = await [a, b][i].evaluate(() => ({
        username: (window as any).u.username,
        password: (window as any).password,
      }));
      await p.evaluate(async (account) => {
        const w = window as any,
          h = w.havenIntegration;
        w.u = (await h.api("auth/login", "POST", account)).user;
        w.secret = crypto.randomUUID() + crypto.randomUUID();
        w.m = await h.Messenger.create(
          w.u.id,
          w.secret,
          "Prepared backup origin",
        );
      }, account);
    }
    const devices = await Promise.all(
      pages.map((p) =>
        p.evaluate(async () => {
          const w = window as any;
          return (await w.havenIntegration.api("devices")).find(
            (d: any) => d.id === w.m.state.device_id,
          );
        }),
      ),
    );
    expect(new Set(devices.map((d) => d.public_key)).size).toBe(4);
    for (const p of pages)
      await p.evaluate(async (devices) => {
        const w = window as any;
        for (const d of devices)
          await w.m.pin(
            d,
            await w.havenIntegration.fingerprintOf(d.public_key),
          );
      }, devices);
    for (const i of [0, 1]) {
      await pages[i].evaluate(
        async (d) => (window as any).m.approve(d),
        devices[i + 2],
      );
      await pages[i + 2].evaluate(async () => {
        const w = window as any;
        await w.m.connect();
        await w.m.package();
      });
    }
    const id = await a.evaluate(async () => (window as any).m.create("direct"));
    await change(a, await detail(a, id), devices[1], "add");
    await sync(b, await detail(a, id));
    await send(a, await detail(a, id), "History before backup devices joined");
    for (const i of [2, 3])
      await change(a, await detail(a, id), devices[i], "add");
    for (const p of [sa, sb]) {
      await sync(p, await detail(p, id));
      expect(await count(p, "History before backup devices joined")).toBe(0);
    }
    await change(a, await detail(a, id), devices[2], "transfer");
    for (const p of [sa, sb, b]) await sync(p, await detail(p, id));
    expect(
      await sa.evaluate(
        () =>
          new Promise<boolean>((resolve) => {
            const ws = new WebSocket(
              location.origin.replace("https:", "wss:") + "/ws/v1",
            );
            const timer = setTimeout(() => {
              ws.close();
              resolve(false);
            }, 5000);
            ws.onopen = () =>
              ws.send(JSON.stringify({ v: 1, kind: "heartbeat" }));
            ws.onmessage = (e) => {
              if (JSON.parse(e.data).kind === "heartbeat") {
                clearTimeout(timer);
                ws.close();
                resolve(true);
              }
            };
            ws.onerror = () => {
              clearTimeout(timer);
              resolve(false);
            };
          }),
      ),
    ).toBe(true);
    await send(
      sa,
      await detail(sa, id),
      "Backup origin uses the single primary writer",
    );
    await sync(a, await detail(a, id));
    expect(await count(a, "Backup origin uses the single primary writer")).toBe(
      1,
    );
    installBridgeCertificate("wrong");
    docker(["kill", "--signal", "HUP", primary]);
    await expect.poll(() => probe(backupOrigin)).toBe(false);
    const current = await detail(a, id);
    await send(sa, current, "Held while private TLS identity is invalid");
    expect(
      await sa.evaluate(
        () => Object.keys((window as any).m.state.outbox).length,
      ),
    ).toBe(1);
    installBridgeCertificate("valid");
    docker(["kill", "--signal", "HUP", primary]);
    await health(backupOrigin);
    await sa.evaluate(async () => (window as any).m.flush());
    await sync(sb, await detail(sb, id));
    expect(await count(sb, "Held while private TLS identity is invalid")).toBe(
      1,
    );
    // Stop the primary API and public route, then require actual database fencing before promotion.
    await stop(proxy);
    await stop(server);
    proxy = undefined;
    server = undefined;
    drill.stdin!.write("PROMOTE\n");
    await expect
      .poll(() => phases.some((p) => p.phase === "promoted"), {
        timeout: 60000,
      })
      .toBe(true);
    docker(["stop", "--time", "5", primary]);
    // Explicit operator routing change after fencing; no automatic/insecure TLS fallback.
    const conf = config + "/standby-preparation.conf";
    fs.writeFileSync(
      conf,
      fs
        .readFileSync(conf, "utf8")
        .replaceAll("https://127.0.0.1:9443", "http://127.0.0.1:8103"),
    );
    server = startApi(
      String(phases.find((p) => p.phase === "ready").standby_port),
    );
    docker(["kill", "--signal", "HUP", backup]);
    await health(backupOrigin);
    expect(await probe(primaryOrigin)).toBe(false);
    await send(
      sa,
      await detail(sa, id),
      "After fenced promotion at the prepared backup IP",
    );
    await sync(sb, await detail(sb, id));
    expect(
      await count(sb, "After fenced promotion at the prepared backup IP"),
    ).toBe(1);
    // A real self-update at the promoted writer establishes a new MLS epoch.
    await sa.evaluate(
      async (c) =>
        (window as any).m.changeMember(
          c,
          (await (window as any).havenIntegration.api("devices")).find(
            (d: any) => d.id === (window as any).m.state.device_id,
          ),
          "update",
        ),
      await detail(sa, id),
    );
    await sync(sb, await detail(sb, id));
    await send(sa, await detail(sa, id), "New epoch after primary removal");
    await sync(sb, await detail(sb, id));
    expect(await count(sb, "New epoch after primary removal")).toBe(1);
    fs.writeFileSync(
      root + "/docs/evidence/standby-origin-result.json",
      JSON.stringify(
        {
          status: "PASS_LOCAL_PREPARED_ORIGIN_FAILOVER",
          distinct_ipv4_origins: true,
          independently_approved_devices: 4,
          prejoin_history_excluded: true,
          verified_private_tls_and_wss: true,
          wrong_private_tls_identity_fail_closed: true,
          primary_api_and_route_stopped: true,
          primary_database_fenced_before_promotion: true,
          messages_and_mls_update_after_promotion: true,
          limitations: [
            "single physical host",
            "container-stop fencing only",
            "not a provider, domestic carrier or physical mobile test",
            "no old ratchet state transferred between origins",
          ],
        },
        null,
        2,
      ) + "\n",
    );
    drill.stdin!.write("FINISH\n");
    await new Promise((r) => drill!.once("exit", r));
  } finally {
    installBridgeCertificate("valid");
    for (const c of contexts) await c.close();
    await stop(proxy);
    await stop(server);
    await stop(drill);
    for (const name of owned.reverse()) {
      try {
        if (
          docker([
            "inspect",
            "--format",
            '{{index .Config.Labels "haven.bridge-test"}}',
            name,
          ])
            .toString()
            .trim() === token
        )
          docker(["rm", "-f", name]);
      } catch {}
    }
    fs.rmSync(config, { recursive: true, force: true });
  }
});
