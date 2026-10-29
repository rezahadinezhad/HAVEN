// Run after next build. All resources are prepared locally; no runtime package/CDN fetch.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
const root = ".next/static";
const files = [];
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(p);
    else if (/\.(js|css|woff2?)$/.test(p))
      files.push("/_next/static/" + path.relative(root, p));
  }
}
walk(root);
const assets = [
  "/",
  "/offline.html",
  "/offline.css",
  "/crypto-worker.js",
  "/vault-worker.js",
  "/crypto/haven_crypto.js",
  "/crypto/haven_crypto_bg.wasm",
  ...files.sort(),
];
const revision = crypto.createHash("sha256");
for (const item of assets) {
  if (item === "/") continue;
  revision.update(
    fs.readFileSync(
      item.startsWith("/_next/")
        ? ".next/static/" + item.slice("/_next/static/".length)
        : "public" + item,
    ),
  );
}
const buildRevision = revision.digest("hex");
fs.writeFileSync(
  "public/sw-assets.json",
  JSON.stringify({ revision: buildRevision, assets }),
);
// A new immutable shell must change the service-worker bytes so existing profiles
// install the new manifest as one unit instead of keeping a previous UI forever.
const worker = fs
  .readFileSync("public/sw.js", "utf8")
  .replace(
    /^(?:\/\/ shell-build:.*|const SHELL_BUILD_REVISION = "[0-9a-f]{64}";)\n/gm,
    "",
  );
fs.writeFileSync(
  "public/sw.js",
  `const SHELL_BUILD_REVISION = "${buildRevision}";\n${worker}`,
);
console.log(`Prepared ${assets.length} local offline shell assets`);
