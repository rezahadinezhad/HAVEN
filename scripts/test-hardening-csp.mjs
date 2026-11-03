// Exercise the exact production proxy with adversarial Host values; no server required.
import { build } from "../apps/web/node_modules/esbuild/lib/main.js";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";
import { NextRequest } from "../apps/web/node_modules/next/server.js";
const started=performance.now();
await build({entryPoints:["apps/web/src/proxy.ts"],bundle:true,platform:"node",format:"cjs",outfile:".local/privacy-proxy.cjs",logLevel:"silent"});
process.env.NODE_ENV="production";
const {proxy}=createRequire(import.meta.url)("../.local/privacy-proxy.cjs");
const check=(host)=>proxy(new NextRequest("https://127.0.0.1/",{headers:{host}}));
for(const host of ["999.0.0.1","127.00.0.1","127.0.0.1:0","127.0.0.1:65536","127.0.0.1:8443:evil","evil.invalid","127.0.0.1;script-src *"])
  if(check(host).status!==400) throw Error("Accepted invalid host");
const first=check("127.0.0.1:8443"),second=check("127.0.0.1:8443");
const csp=first.headers.get("Content-Security-Policy");
if(first.status!==200||!csp.includes("'wasm-unsafe-eval'")||csp.includes("'unsafe-eval'")||csp.includes("'unsafe-inline'")||csp===second.headers.get("Content-Security-Policy")) throw Error("Invalid production CSP/nonce");
console.log(JSON.stringify({status:"PASS",seconds:(performance.now()-started)/1000,invalid_hosts_rejected:7,production_nonce_unique:true,arbitrary_eval_allowed:false}));
