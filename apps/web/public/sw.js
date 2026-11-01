const SHELL_BUILD_REVISION = "ba34aec777fe30037dc396e3ed6e5c6dd19879f07c44332947fcff7a56d3e1c8";
// Only the explicitly public shell and immutable build resources enter this cache. API/data never do.
const PREFIX="haven-shell-";
// Bind this worker to its build even when the browser terminates/restarts it
// between install and activate. Never select an arbitrary previous shell cache.
async function cacheName(){return PREFIX+SHELL_BUILD_REVISION;}
self.addEventListener("install",event=>event.waitUntil((async()=>{
  const response=await fetch("/sw-assets.json",{cache:"no-store",credentials:"omit"});if(!response.ok)throw new Error("Offline manifest unavailable");
  const manifest=await response.json();if(manifest.revision!==SHELL_BUILD_REVISION||!/^[0-9a-f]{64}$/.test(manifest.revision)||!Array.isArray(manifest.assets)||manifest.assets.length>1000)throw new Error("Invalid offline manifest");
  const name=PREFIX+manifest.revision,cache=await caches.open(name);
  try{for(const asset of manifest.assets){if(asset!=="/"&&!/^\/(?:_next\/static\/|crypto\/|(?:crypto-worker|vault-worker)\.js$|offline\.(?:html|css)$)/.test(asset))throw new Error("Invalid shell path");const r=await fetch(asset,{credentials:"omit",cache:"reload"});if(!r.ok||(asset==="/"&&r.headers.get("x-haven-public-shell")!=="1"))throw new Error("Uncacheable shell");await cache.put(asset,r);}}catch(e){await caches.delete(name);throw e;}
})()));
self.addEventListener("activate",event=>event.waitUntil((async()=>{const name=await cacheName();for(const key of await caches.keys())if(key.startsWith(PREFIX)&&key!==name)await caches.delete(key);await self.clients.claim();})()));
self.addEventListener("fetch",event=>{
  const u=new URL(event.request.url);if(event.request.method!=="GET"||u.origin!==location.origin||u.pathname.startsWith("/api/")||u.pathname.startsWith("/ws/"))return;
  if(event.request.mode==="navigate"){event.respondWith(fetch(event.request).catch(async()=>{const name=await cacheName(),cache=name&&await caches.open(name);return cache&&(await cache.match("/"))||Response.error();}));return;}
  if(u.pathname.startsWith("/_next/static/")||u.pathname.startsWith("/crypto/")||["/crypto-worker.js","/vault-worker.js"].includes(u.pathname))event.respondWith((async()=>{const name=await cacheName(),cache=name&&await caches.open(name);return cache&&(await cache.match(u.pathname))||fetch(event.request);})());
});
