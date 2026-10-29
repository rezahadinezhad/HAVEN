import { build } from "../apps/web/node_modules/esbuild/lib/main.js";
await build({
  entryPoints: ["apps/web/src/lib/vault-worker.ts"],
  bundle: true,
  format: "iife",
  platform: "browser",
  target: "es2022",
  outfile: "apps/web/public/vault-worker.js",
  minify: true,
  sourcemap: false,
});
