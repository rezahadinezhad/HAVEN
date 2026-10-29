// Public-shell lifecycle regression: exercise the shipped worker after restart,
// when both the previous and newly installed build caches already exist.
import vm from "node:vm";
import fs from "node:fs";
import assert from "node:assert/strict";
const source = fs.readFileSync("public/sw.js", "utf8");
const revision = source.match(
  /const SHELL_BUILD_REVISION = "([0-9a-f]{64})";/,
)?.[1];
assert.ok(revision, "Build the worker before testing it");
const current = "haven-shell-" + revision;
const previous = "haven-shell-" + "0".repeat(64);
const stores = new Map([
  [previous, new Map([["/", new Response("previous shell")]])],
  [current, new Map([["/", new Response("current shell")]])],
  ["unrelated-app", new Map()],
]);
const listeners = {};
const context = {
  URL,
  Response,
  location: { origin: "https://127.0.0.1:8445" },
  fetch: async () => {
    throw new Error("Offline");
  },
  self: {
    addEventListener: (name, fn) => {
      listeners[name] = fn;
    },
    clients: { claim: async () => {} },
  },
  caches: {
    keys: async () => [...stores.keys()],
    open: async (key) => {
      assert.ok(stores.has(key));
      return { match: async (path) => stores.get(key).get(path)?.clone() };
    },
    delete: async (key) => stores.delete(key),
  },
};
vm.runInNewContext(source, context);
let response;
listeners.fetch({
  request: {
    method: "GET",
    mode: "navigate",
    url: context.location.origin + "/",
  },
  respondWith: (value) => {
    response = value;
  },
});
assert.equal(await (await response).text(), "current shell");
let activated;
listeners.activate({
  waitUntil: (value) => {
    activated = value;
  },
});
await activated;
assert.ok(stores.has(current));
assert.ok(stores.has("unrelated-app"));
assert.ok(!stores.has(previous));
for (const path of ["/api/v1/auth/me", "/ws/v1", "https://other.invalid/"]) {
  listeners.fetch({
    request: {
      method: "GET",
      mode: "cors",
      url: new URL(path, context.location.origin).href,
    },
    respondWith: () =>
      assert.fail("Private/foreign requests must bypass shell cache"),
  });
}
// A concurrently changed manifest must fail rather than combine two builds.
context.fetch = async () =>
  new Response(JSON.stringify({ revision: "f".repeat(64), assets: ["/"] }));
let install;
listeners.install({
  waitUntil: (value) => {
    install = value;
  },
});
await assert.rejects(install, /Invalid offline manifest/);
console.log(
  "PASS public-shell update after worker restart: current cached shell, previous-cache cleanup, unrelated cache preserved, API/WS/foreign bypass, mismatched manifest rejected.",
);
