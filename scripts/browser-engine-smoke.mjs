import { firefox, webkit } from "../apps/web/node_modules/playwright/index.mjs";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
const profile = path.resolve(".local/firefox-profile");
fs.mkdirSync(profile, { recursive: true, mode: 0o700 });
if (!fs.existsSync(path.join(profile, "cert9.db")))
  execFileSync("certutil", ["-N", "-d", `sql:${profile}`, "--empty-password"]);
try {
  execFileSync(
    "certutil",
    ["-D", "-n", "HAVEN test root", "-d", `sql:${profile}`],
    { stdio: "ignore" },
  );
} catch {}
execFileSync("certutil", [
  "-A",
  "-n",
  "HAVEN test root",
  "-d",
  `sql:${profile}`,
  "-t",
  "C,,",
  "-i",
  path.resolve(".local/tls/root.crt"),
]);
for (const [name, type] of [
  ["firefox", firefox],
  ["webkit", webkit],
]) {
  let context, browser;
  try {
    const env = {
      ...process.env,
      LD_LIBRARY_PATH: path.resolve(
        ".local/browser-libs/usr/lib/x86_64-linux-gnu",
      ),
      SSL_CERT_FILE: path.resolve(".local/tls/root.crt"),
    };
    context =
      name === "firefox"
        ? await type.launchPersistentContext(profile, { headless: true, env })
        : await (browser = await type.launch({
            headless: true,
            env,
            executablePath: path.resolve(".local/browser-webkit/pw_run.sh"),
          })).newContext();
    const page = await context.newPage();
    await page.goto("https://127.0.0.1:8443/pof.html");
    await page.waitForFunction(() => !!window.havenPoF);
    const result = await page.evaluate(() => {
      const call = window.havenPoF.call;
      let a = call("", { op: "init", identity: "engine-a" }).state,
        b = call("", { op: "init", identity: "engine-b" }).state;
      const kp = call(b, { op: "package" });
      b = kp.state;
      a = call(a, { op: "create", group_id: "engine" }).state;
      const add = call(a, {
        op: "add",
        group_id: "engine",
        key_package: kp.result.key_package,
      });
      a = add.state;
      b = call(b, {
        op: "join",
        group_id: "engine",
        welcome: add.result.welcome,
      }).state;
      const msg = call(a, {
        op: "encrypt",
        group_id: "engine",
        plaintext: "engine proof سلام",
      });
      return call(b, {
        op: "process",
        group_id: "engine",
        ciphertext: msg.result.ciphertext,
      }).result.plaintext;
    });
    console.log(
      `${name}: PASS trusted IP TLS + actual OpenMLS WASM: ${result === "engine proof سلام"}`,
    );
  } catch (e) {
    console.log(`${name}: BLOCKED: ${String(e.message).split("\n")[0]}`);
  } finally {
    await context?.close();
    await browser?.close();
  }
}
