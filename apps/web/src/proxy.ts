import { NextRequest, NextResponse } from "next/server";
export function proxy(request: NextRequest) {
  const host = request.headers.get("host") || "";
  const optional = process.env.HAVEN_OPTIONAL_HOSTNAME || "";
  const [hostName, hostPort, extra] = host.split(":");
  const optionalValid =
    optional.length <= 253 &&
    optional
      .split(".")
      .every((label) => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label));
  const optionalAllowed =
    optionalValid &&
    hostName === optional &&
    extra === undefined &&
    (hostPort === undefined ||
      (/^[0-9]{1,5}$/.test(hostPort) &&
        Number(hostPort) > 0 &&
        Number(hostPort) < 65536));
  if (
    !/^(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?::[0-9]{1,5})?$/.test(host) &&
    !optionalAllowed
  ) {
    return new NextResponse("IP origin required", { status: 400 });
  }
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const dev = process.env.NODE_ENV === "development";
  // wasm-unsafe-eval permits WebAssembly compilation only; general unsafe-eval is development-only.
  const csp = `default-src 'self'; script-src 'self' 'nonce-${nonce}' 'wasm-unsafe-eval'${dev ? " 'unsafe-eval'" : ""}; style-src 'self' 'nonce-${nonce}'; connect-src 'self' wss://${host}; worker-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; upgrade-insecure-requests`;
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("Cache-Control", "no-store");
  response.headers.set("X-Haven-Public-Shell", "1");
  return response;
}
export const config = { matcher: ["/"] };
