import { test, expect } from "./fixtures";
import { spawn, execFileSync, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import https from "node:https";
const root = path.resolve("../..");
const origin = "https://127.0.0.1:8446";
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
const ca = fs.readFileSync(root + "/.local/tls/root.crt");
async function ready() {
  for (let i = 0; i < 100; i++) {
    const ok = await new Promise<boolean>((resolve) => {
      const req = https.get(origin + "/api/v1/health", { ca }, (r) => {
        r.resume();
        resolve(r.statusCode === 200);
      });
      req.on("error", () => resolve(false));
      req.setTimeout(500, () => req.destroy());
    });
    if (ok) return;
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("Owned restart-test service did not become ready");
}
function apiProcess() {
  return spawn(
    root + "/apps/api/.venv/bin/uvicorn",
    [
      "haven.asgi:application",
      "--host",
      "127.0.0.1",
      "--port",
      "8102",
      "--no-access-log",
      "--proxy-headers",
    ],
    {
      cwd: root + "/apps/api",
      env: {
        ...process.env,
        ...environment,
        HAVEN_HOSTS: "127.0.0.1",
        HAVEN_ORIGINS: origin,
        DJANGO_SETTINGS_MODULE: "haven.integration_settings",
      },
      stdio: "ignore",
    },
  );
}
async function stop(
  p: ChildProcess | undefined,
  signal: NodeJS.Signals = "SIGTERM",
) {
  if (!p || p.exitCode !== null || p.signalCode) return;
  const ended = new Promise((r) => p.once("exit", r));
  p.kill(signal);
  await ended;
}
test("actual API SIGKILL after durable acceptance: browser reload retries the exact ciphertext once", async ({
  browser,
}) => {
  test.setTimeout(120000);
  let server: ChildProcess | undefined, proxy: ChildProcess | undefined;
  const contexts = [];
  try {
    server = apiProcess();
    proxy = spawn(process.execPath, ["scripts/dev-proxy.mjs"], {
      cwd: root,
      env: {
        ...process.env,
        HAVEN_DEV_PORT: "8446",
        HAVEN_DEV_API_PORT: "8102",
        HAVEN_INTEGRATION: "1",
      },
      stdio: "ignore",
    });
    await ready();
    const aContext = await browser.newContext(),
      bContext = await browser.newContext();
    contexts.push(aContext, bContext);
    const a = await aContext.newPage(),
      b = await bContext.newPage();
    for (const p of [a, b]) {
      await p.goto(origin + "/__integration__/");
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
        w.u = (
          await h.api("invitations/redeem", "POST", {
            token,
            username: "restart_" + crypto.randomUUID().slice(0, 10),
            password: crypto.randomUUID() + crypto.randomUUID(),
            display_name: "Restart test",
          })
        ).user;
        w.secret = crypto.randomUUID() + crypto.randomUUID();
        w.m = await h.Messenger.create(w.u.id, w.secret, "Restart test device");
      }, invites[i].token);
    const devices = await Promise.all(
      [a, b].map((p) =>
        p.evaluate(async () => {
          const w = window as any;
          return (await w.havenIntegration.api("devices"))[0];
        }),
      ),
    );
    for (const p of [a, b])
      await p.evaluate(async (devices) => {
        const w = window as any;
        for (const d of devices)
          await w.m.pin(
            d,
            await w.havenIntegration.fingerprintOf(d.public_key),
          );
      }, devices);
    const id = await a.evaluate(async () => (window as any).m.create("direct"));
    let detail = await a.evaluate(
      async (id) => (window as any).havenIntegration.api(`conversations/${id}`),
      id,
    );
    await a.evaluate(
      async ({ detail, device }) =>
        (window as any).m.changeMember(detail, device, "add"),
      { detail, device: devices[1] },
    );
    detail = await a.evaluate(
      async (id) => (window as any).havenIntegration.api(`conversations/${id}`),
      id,
    );
    await b.evaluate(async (d) => (window as any).m.sync(d), detail);
    const local = await a.evaluate(async (detail) => {
      const w = window as any,
        original = window.fetch.bind(window);
      window.fetch = async (...args) => {
        const response = await original(...args);
        if (String(args[0]).endsWith("/messages") && args[1]?.method === "POST")
          throw new TypeError("Lost ACK before process crash");
        return response;
      };
      try {
        await w.m.send(detail, {
          type: "text",
          text: "One message survives an actual process kill",
        });
      } finally {
        window.fetch = original;
      }
      return {
        user: w.u.id,
        secret: w.secret,
        pending: Object.keys(w.m.state.outbox).length,
      };
    }, detail);
    expect(local.pending).toBe(1);
    await stop(server, "SIGKILL");
    server = undefined;
    await a.reload();
    await a.waitForFunction(() => !!(window as any).havenIntegration);
    await a.evaluate(async (local) => {
      const w = window as any;
      w.m = await w.havenIntegration.Messenger.unlock(local.user, local.secret);
    }, local);
    server = apiProcess();
    await ready();
    await a.evaluate(async () => {
      const w = window as any;
      await w.m.connect();
      await w.m.flush();
    });
    detail = await a.evaluate(
      async (id) => (window as any).havenIntegration.api(`conversations/${id}`),
      id,
    );
    await b.evaluate(async (d) => (window as any).m.sync(d), detail);
    expect(
      await b.evaluate(
        () =>
          (window as any).m.state.events.filter(
            (e: any) =>
              e.text === "One message survives an actual process kill",
          ).length,
      ),
    ).toBe(1);
    expect(
      await a.evaluate(
        () => Object.keys((window as any).m.state.outbox).length,
      ),
    ).toBe(0);
    const compose = [
      "compose",
      "--env-file",
      root + "/.local/test.env",
      "-f",
      root + "/infrastructure/compose.test.yml",
    ];
    try {
      execFileSync("docker", [...compose, "stop", "redis"], {
        stdio: "ignore",
      });
      // Existing authenticated HTTP readers still decrypt real PostgreSQL-backed MLS envelopes.
      await b.evaluate(async (d) => (window as any).m.sync(d), detail);
      await a.evaluate(
        async (d) =>
          (window as any).m.send(d, {
            type: "text",
            text: "Encrypted delivery after Redis recovery",
          }),
        detail,
      );
      expect(
        await a.evaluate(
          () => Object.keys((window as any).m.state.outbox).length,
        ),
      ).toBe(1);
    } finally {
      execFileSync("docker", [...compose, "start", "redis"], {
        stdio: "ignore",
      });
    }
    for (let i = 0; i < 10; i++) {
      try {
        await a.evaluate(async () => (window as any).m.flush());
        break;
      } catch {
        await new Promise((r) => setTimeout(r, 200));
      }
    }
    detail = await a.evaluate(
      async (id) => (window as any).havenIntegration.api(`conversations/${id}`),
      id,
    );
    await b.evaluate(async (d) => (window as any).m.sync(d), detail);
    expect(
      await b.evaluate(
        () =>
          (window as any).m.state.events.filter(
            (e: any) => e.text === "Encrypted delivery after Redis recovery",
          ).length,
      ),
    ).toBe(1);
  } finally {
    for (const c of contexts) await c.close();
    await stop(server);
    await stop(proxy);
  }
});
