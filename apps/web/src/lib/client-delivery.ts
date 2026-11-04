// Configuration comes only from the independently delivered entry point.
// The ordinary web edition retains its existing same-origin behavior.
type Delivery = Readonly<{
  v: 1;
  mode: "installed" | "independent-web";
  service_origin: string;
  sequence: number;
  digest: string;
}>;
let delivery: Delivery | undefined;
export function configureClientDelivery(value: unknown) {
  if (delivery || !value || typeof value !== "object")
    throw new Error("Invalid client delivery configuration");
  const v = value as Delivery;
  const u = new URL(v.service_origin);
  if (
    v.v !== 1 ||
    !["installed", "independent-web"].includes(v.mode) ||
    u.protocol !== "https:" ||
    u.origin !== v.service_origin ||
    !/^\d{1,3}(?:\.\d{1,3}){3}$/.test(u.hostname) ||
    u.hostname.split(".").some((x) => Number(x) > 255) ||
    u.username ||
    u.password ||
    !Number.isSafeInteger(v.sequence) ||
    v.sequence < 1 ||
    !/^[a-f0-9]{64}$/.test(v.digest)
  )
    throw new Error("Invalid client delivery configuration");
  delivery = Object.freeze({
    v: 1,
    mode: v.mode,
    service_origin: v.service_origin,
    sequence: v.sequence,
    digest: v.digest,
  });
}
export function clientDelivery() {
  return delivery;
}
export function serviceOrigin() {
  return delivery?.service_origin || location.origin;
}
export function readSharedLocation() {
  const local = new URL(location.href);
  return new URL(local.pathname + local.search + local.hash, serviceOrigin())
    .href;
}

export function clientAssetURL(path: string) {
  return delivery ? `/releases/${delivery.digest}${path}` : path;
}
