import { build } from "../apps/web/node_modules/esbuild/lib/main.js";
import fs from "node:fs";
fs.mkdirSync(".local/integration", { recursive: true, mode: 0o700 });
await build({
  entryPoints: ["scripts/integration-client.ts"],
  bundle: true,
  format: "iife",
  platform: "browser",
  target: "es2022",
  outfile: ".local/integration/client.js",
  sourcemap: false,
});
fs.writeFileSync(
  ".local/integration/index.html",
  '<!doctype html><meta charset="utf-8"><title>HAVEN integration harness — TEST ONLY</title><script src="/__integration__/client.js" defer></script>',
);
