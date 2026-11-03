import { build } from "../apps/web/node_modules/esbuild/lib/main.js";
for(const outfile of ["apps/web/public/vault-worker.js","apps/web/public/vault-worker-v2.js"]) await build({
  entryPoints: ["apps/web/src/lib/vault-worker.ts"],
  bundle: true,
  format: "iife",
  platform: "browser",
  target: "es2022",
  outfile,
  minify: true,
  sourcemap: false,
});
