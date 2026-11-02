// Test-only transparent TLS byte meter. It never decrypts or records payloads.
import net from "node:net";
import fs from "node:fs";
const output = process.env.HAVEN_METER_OUTPUT;
if (!output || !output.includes("/.local/"))
  throw new Error("Private output required");
let enabled = false,
  upload = 0,
  download = 0,
  connections = 0;
const sockets = new Set();
const server = net.createServer({ allowHalfOpen: false }, (client) => {
  const ip = client.remoteAddress;
  if (!/^127\.0\.2\.(?:[1-9]|[1-9][0-9]|100)$/.test(ip || "")) {
    client.destroy();
    return;
  }
  const upstream = net.connect({
    host: "127.0.0.1",
    port: 8452,
    localAddress: ip,
  });
  sockets.add(client);
  sockets.add(upstream);
  if (enabled) connections++;
  client.on("data", (bytes) => {
    if (enabled) upload += bytes.length;
  });
  upstream.on("data", (bytes) => {
    if (enabled) download += bytes.length;
  });
  client.pipe(upstream);
  upstream.pipe(client);
  client.on("error", () => upstream.destroy());
  upstream.on("error", () => client.destroy());
  client.on("close", () => {
    sockets.delete(client);
    upstream.destroy();
  });
  upstream.on("close", () => {
    sockets.delete(upstream);
    client.destroy();
  });
});
function save() {
  fs.writeFileSync(
    output,
    JSON.stringify({
      upload_tls_bytes: upload,
      download_tls_bytes: download,
      new_connections: connections,
      scope:
        "TLS records including HTTP/WSS headers and payloads; excludes TCP/IP overhead",
    }),
    { mode: 0o600 },
  );
}
process.on("SIGUSR1", () => {
  enabled = true;
  upload = download = connections = 0;
});
process.on("SIGUSR2", save);
process.on("SIGTERM", () => {
  save();
  server.close();
  for (const socket of sockets) socket.destroy();
});
server.listen(8454, "127.0.0.1", () => process.stdout.write("READY\n"));
