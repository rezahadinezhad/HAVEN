import type { components } from "./generated/schema";
export type User = components["schemas"]["User"];
export type Device = components["schemas"]["Device"];
export type Conversation = {
  id: string;
  kind: "direct" | "group";
  group_id: string;
  epoch: number;
  last_seq: number;
  status: string;
  head_hash: string;
  receipt_version?: number;
};
export type Envelope = {
  id: string;
  client_message_id: string;
  sender_device: string;
  v: 1;
  seq: number;
  epoch: number;
  kind: "application" | "commit";
  ciphertext: string;
  received_at: string | null;
  ciphertext_retired?: boolean;
  welcome?: string;
  transition?: Record<string, unknown>;
  signature: string;
  header: DeliveryHeader;
  chain_hash: string;
};
export type Certificate = Pick<
  Device,
  "id" | "user_id" | "identity" | "public_key"
> & { role: "owner" | "moderator" | "member" };
export type Transition = {
  action: string;
  device_id: string | null;
  next_epoch: number;
  members: Certificate[];
  welcome_hash: string;
  state_hash: string;
};
export type DeliveryHeader = {
  domain: "haven/envelope/v1";
  v: 1;
  conversation_id: string;
  group_id: string;
  sender_device: string;
  client_message_id: string;
  epoch: number;
  seq: number;
  previous_hash: string;
  ciphertext_hash: string;
  transition: Transition | null;
};
export class RequestError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
let csrf = "";
export async function api<T>(
  path: string,
  method = "GET",
  value?: unknown,
  csrfRetried = false,
): Promise<T> {
  if (location.protocol !== "https:" || !isSecureContext)
    throw new Error("Trusted HTTPS required");
  if (method !== "GET" && !csrf) {
    const r = await fetch("/api/v1/auth/csrf", {
      cache: "no-store",
      signal: AbortSignal.timeout(60000),
    });
    csrf = (await r.json()).csrf;
  }
  const response = await fetch("/api/v1/" + path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    signal: AbortSignal.timeout(60000),
    headers:
      method === "GET"
        ? {}
        : { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: value === undefined ? undefined : JSON.stringify(value),
  });
  let data = await response.json();
  // Preserve the array API for callers while following bounded server pages.
  if (
    method === "GET" &&
    response.ok &&
    (path === "conversations" || path.startsWith("conversations?cursor="))
  ) {
    const cursor = response.headers.get("X-Haven-Next-Cursor");
    if (cursor)
      data = [
        ...data,
        ...(await api<Conversation[]>(
          "conversations?cursor=" + encodeURIComponent(cursor),
        )),
      ];
  }
  if (
    !response.ok &&
    response.status === 403 &&
    data.error === "csrf_rejected" &&
    method !== "GET" &&
    !csrfRetried
  ) {
    csrf = "";
    return api<T>(path, method, value, true);
  }
  if (!response.ok)
    throw new RequestError(
      response.status,
      data.error === "history_retired_use_verified_fresh_device"
        ? "This device requests history already removed from the server after delivery. Keep this vault and use a verified fresh device to reconnect."
        : data.error === "request_rejected"
          ? JSON.stringify(data.details)
          : data.error || "Request failed",
    );
  if (
    path === "auth/login" ||
    path === "invitations/redeem" ||
    path === "recovery/reset"
  )
    csrf = "";
  return data as T;
}
export async function uploadChunk(
  id: string,
  index: number,
  bytes: Uint8Array,
  signal?: AbortSignal,
) {
  if (!csrf) {
    const r = await api<{ csrf: string }>("auth/csrf");
    csrf = r.csrf;
  }
  const r = await fetch(`/api/v1/attachments/${id}/chunks/${index}`, {
    method: "PUT",
    headers: {
      "X-CSRFToken": csrf,
      "Content-Type": "application/octet-stream",
    },
    body: new Blob([bytes as Uint8Array<ArrayBuffer>]),
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(120000)])
      : AbortSignal.timeout(120000),
  });
  if (!r.ok) throw new Error("Encrypted upload failed");
}
