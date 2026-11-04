import { build } from "../apps/web/node_modules/esbuild/lib/main.js";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
const out = path.resolve(
  process.env.HAVEN_CLIENT_BUILD_DIR || ".local/verified-client/web",
);
const marker = path.join(out, ".haven-client-build");
if (fs.existsSync(out) && fs.readdirSync(out).length) {
  if (!fs.existsSync(marker))
    throw new Error(
      "Refusing to replace a directory not created by this client builder",
    );
  fs.rmSync(out, { recursive: true });
}
fs.mkdirSync(out, { recursive: true, mode: 0o700 });
const inputs = [];
for (const base of [
  "apps/web/src",
  "apps/web/public",
  "apps/verified-client/web",
]) {
  const scan = (p) => {
    for (const e of fs.readdirSync(p, { withFileTypes: true })) {
      const child = p + "/" + e.name;
      if (e.isDirectory()) scan(child);
      else if (e.isFile()) inputs.push(child);
    }
  };
  scan(base);
}
inputs.push(
  "apps/web/package.json",
  "apps/web/package-lock.json",
  "apps/web/tsconfig.json",
  "scripts/build-verified-client.mjs",
);
const sourceHash = crypto.createHash("sha256");
for (const p of inputs.sort())
  sourceHash.update(p + "\0").update(fs.readFileSync(p));
fs.writeFileSync(
  marker,
  JSON.stringify({
    domain: "haven/client-build-inputs/v1",
    sha256: sourceHash.digest("hex"),
  }),
);
const result = await build({
  entryPoints: ["apps/verified-client/web/main.tsx"],
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "es2022",
  outdir: out + "/assets",
  nodePaths: [path.resolve("apps/web/node_modules")],
  entryNames: "client-[hash]",
  assetNames: "[name]-[hash]",
  loader: { ".woff2": "file" },
  minify: true,
  sourcemap: false,
  metafile: true,
  tsconfig: "apps/web/tsconfig.json",
  define: { "process.env.NODE_ENV": '"production"' },
});
const outputs = Object.entries(result.metafile.outputs);
const entry = outputs.find(([, v]) => v.entryPoint)?.[0];
const css = entry && result.metafile.outputs[entry].cssBundle;
if (!entry || !css) throw new Error("Missing complete client assets");
const url = (p) =>
  "/" + path.relative(out, path.resolve(p)).replaceAll(path.sep, "/");
fs.writeFileSync(
  out + "/index.html",
  `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HAVEN · Private community</title><link rel="stylesheet" href="${url(css)}"></head><body><div id="root"></div><script type="module" src="${url(entry)}"></script></body></html>`,
);
for (const name of [
  "crypto-worker.js",
  "vault-worker-v2.js",
  "crypto/haven_crypto.js",
  "crypto/haven_crypto_bg.wasm",
]) {
  fs.mkdirSync(path.dirname(out + "/" + name), { recursive: true });
  fs.copyFileSync("apps/web/public/" + name, out + "/" + name);
}
const assets = [];
function walk(p) {
  for (const e of fs.readdirSync(p, { withFileTypes: true })) {
    const child = p + "/" + e.name;
    if (e.isDirectory()) walk(child);
    else if (
      !child.endsWith("/sw.js") &&
      !child.endsWith("/.haven-client-build")
    )
      assets.push("/" + path.relative(out, child).replaceAll(path.sep, "/"));
  }
}
walk(out);
const revision = crypto.createHash("sha256");
for (const p of assets.sort()) revision.update(fs.readFileSync(out + p));
const worker = `const PREFIX=new URL("./",self.location.href).pathname;const CACHE="haven-verified-web-"+PREFIX.split("/")[2];const FILES=${JSON.stringify(assets.map((x) => (x === "/index.html" ? "/" : x)))};const ASSETS=["/","/client-config.json",...FILES.filter(p=>p!=="/").map(p=>PREFIX+p.slice(1))];self.addEventListener("install",e=>e.waitUntil((async()=>{const c=await caches.open(CACHE);try{const response=await fetch("/client-config.json",{cache:"no-store",credentials:"omit"});const config=await response.clone().json();if(config.digest!==PREFIX.split("/")[2])throw new Error("Client revision mismatch");await c.put("/client-config.json",response);for(const p of ASSETS.filter(p=>p!=="/client-config.json")){const r=await fetch(p,{credentials:"omit",cache:"reload"});if(!r.ok)throw new Error("Missing signed asset");await c.put(p,r)}}catch(e){await caches.delete(CACHE);throw e}})()));self.addEventListener("activate",e=>e.waitUntil((async()=>{for(const k of await caches.keys())if(k.startsWith("haven-verified-web-")&&k!==CACHE)await caches.delete(k);await self.clients.claim()})()));self.addEventListener("fetch",e=>{const u=new URL(e.request.url);if(e.request.method!=="GET"||u.origin!==location.origin||!ASSETS.includes(u.pathname))return;e.respondWith((async()=>{const c=await caches.open(CACHE);if(u.pathname!=="/"&&u.pathname!=="/client-config.json"){const r=await c.match(u.pathname);if(r)return r}try{return await fetch(e.request)}catch{return await c.match(u.pathname)||Response.error()}})())});`;

fs.writeFileSync(out + "/sw.js", worker);
console.log("Built complete client UI, workers, WASM and fonts into " + out);
