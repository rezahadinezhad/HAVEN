// Local IP TLS proxy. Uses a test CA explicitly trusted by the test browser, never disables TLS validation.
import https from "node:https";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
const root = path.resolve(import.meta.dirname, "../../..");
// Loopback-only adversarial fixture, never included in a client/server image.
const attackFile = process.env.HAVEN_TEST_ATTACK_FILE;
if (!attackFile) throw new Error("Explicit test attack file required");
const port = Number(process.env.HAVEN_DEV_PORT || 8448);
function upstreamHeaders(req) {
  const headers = { ...req.headers, "x-forwarded-proto": "https" };
  for (const name of [
    "x-forwarded-for",
    "x-real-ip",
    "forwarded",
    "x-client-ip",
    "true-client-ip",
    "cf-connecting-ip",
    "x-forwarded-host",
  ])
    delete headers[name];
  if (req.url.split("?")[0] === "/api/v1/auth/login")
    headers["x-forwarded-for"] = req.socket.remoteAddress;
  return headers;
}
const server = https.createServer(
  {
    key: fs.readFileSync(
      process.env.HAVEN_DEV_TLS_KEY || root + "/.local/tls/leaf.key",
    ),
    cert: fs.readFileSync(
      process.env.HAVEN_DEV_TLS_CERT || root + "/.local/tls/leaf.crt",
    ),
    minVersion: "TLSv1.2",
  },
  (req, res) => {
    if (fs.existsSync(attackFile)) {
      res.writeHead(200, {
        "content-type": "text/html",
        "content-security-policy": "script-src * 'unsafe-inline'",
        location: "https://127.0.0.1:8448/evil",
        "set-cookie": "evil=1; Path=/",
      });
      res.end(
        '<script>globalThis.__originAttackExecuted=true;fetch("https://127.0.0.1:8448/stolen")</script>',
      );
      return;
    }
    const api = req.url.startsWith("/api/");
    const target = api
      ? Number(process.env.HAVEN_DEV_API_PORT || 8100)
      : Number(process.env.HAVEN_DEV_WEB_PORT || 3100);
    // Development only. Production uses nonce CSP in Next proxy and nginx defense in depth.
    const upstream = http.request(
      {
        host: "127.0.0.1",
        port: target,
        path: req.url,
        method: req.method,
        headers: upstreamHeaders(req),
      },
      (r) => {
        res.writeHead(r.statusCode, {
          ...r.headers,
          "x-content-type-options": "nosniff",
          "referrer-policy": "no-referrer",
          "x-frame-options": "DENY",
          "permissions-policy": "camera=(), microphone=(self), geolocation=()",
        });
        r.pipe(res);
      },
    );
    upstream.on("error", () => {
      res.writeHead(503);
      res.end("Service unavailable");
    });
    req.pipe(upstream);
  },
);
server.on("upgrade", (req, socket, head) => {
  if (req.url !== "/ws/v1") {
    socket.destroy();
    return;
  }
  const upstream = http.request({
    host: "127.0.0.1",
    port: Number(process.env.HAVEN_DEV_API_PORT || 8100),
    path: req.url,
    headers: upstreamHeaders(req),
  });
  upstream.on("upgrade", (res, remote, upstreamHead) => {
    socket.write(
      "HTTP/1.1 101 Switching Protocols\r\n" +
        Object.entries(res.headers)
          .map(([k, v]) => `${k}: ${v}\r\n`)
          .join("") +
        "\r\n",
    );
    if (head.length) remote.write(head);
    if (upstreamHead.length) socket.write(upstreamHead);
    remote.pipe(socket);
    socket.pipe(remote);
  });
  upstream.on("error", () => socket.destroy());
  upstream.end();
});
server.listen(port, "127.0.0.1", () =>
  console.log(`Development test TLS at https://127.0.0.1:${port}`),
);
