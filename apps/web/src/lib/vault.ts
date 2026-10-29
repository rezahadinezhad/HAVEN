import { openDB } from "idb";
import type { Certificate } from "./api";
export type Sealed = {
  v: 1;
  kdf: string;
  salt: string;
  nonce: string;
  ciphertext: string;
};
export type LocalEvent = {
  id: string;
  conversation_id: string;
  sender: string;
  time: string;
  type: "text" | "edit" | "delete" | "reaction" | "file" | "title" | "receipt";
  text?: string;
  target?: string;
  emoji?: string;
  file?: FileMeta;
  reply?: string;
  transport_hash?: string;
  seq?: number;
  state:
    | "local_only"
    | "encrypting"
    | "queued"
    | "server_accepted"
    | "recipient_synced"
    | "failed";
};
export type FileMeta = {
  view_once?: true;
  id: string;
  name: string;
  mime: string;
  key: string;
  prefix: string;
  count: number;
  size: number;
  conversation_id: string;
};
export type VaultState = {
  v: 1;
  device_id: string;
  profile: "haven-delivery-v2";
  device: { label: string; identity: string; public_key: string };
  recovery_seed?: string;
  needs_package?: boolean;
  uploads?: Record<string, FileMeta>;
  view_once_opened?: Record<string, true>;
  read_seq?: Record<string, number>;
  rekey_at?: Record<string, number>;
  cancelled_controls?: Record<
    string,
    {
      conversation_id: string;
      base_hash: string;
      candidate: string;
      ciphertext_hash: string;
    }
  >;
  heads: Record<
    string,
    {
      seq: number;
      hash: string;
      epoch: number;
      group_id: string;
      genesis_hash?: string;
      kind?: "direct" | "group";
      members: Certificate[];
      epoch_start_seq?: number;
    }
  >;
  crypto: string;
  revision: number;
  pins: Record<string, string>;
  contact_names?: Record<string, string>;
  connection_intents?: Record<string, string>;
  cursor: Record<string, number>;
  events: LocalEvent[];
  outbox: Record<
    string,
    {
      path: string;
      body: Record<string, unknown>;
      candidate?: string;
      base_hash?: string;
    }
  >;
  drafts: Record<string, string>;
};
let worker: Worker | undefined;
let n = 0;
const waiting = new Map<
  number,
  { resolve: (v: unknown) => void; reject: (e: Error) => void }
>();
function work<T>(
  op: string,
  secret: string,
  scope: string,
  value: unknown,
): Promise<T> {
  if (location.protocol !== "https:" || !isSecureContext)
    return Promise.reject(new Error("Trusted HTTPS required"));
  if (!worker) {
    worker = new Worker("/vault-worker.js");
    worker.onmessage = (e) => {
      const h = waiting.get(e.data.id);
      waiting.delete(e.data.id);
      if (e.data.error) h?.reject(new Error(e.data.error));
      else h?.resolve(e.data.value);
    };
    worker.onerror = () => stopVaultWorker();
  }
  return new Promise((resolve, reject) => {
    const id = ++n;
    waiting.set(id, { resolve: (v) => resolve(v as T), reject });
    worker!.postMessage({ id, op, secret, scope, value });
  });
}
export function stopVaultWorker() {
  worker?.terminate();
  worker = undefined;
  for (const h of waiting.values()) h.reject(new Error("Vault locked"));
  waiting.clear();
}
export const seal = (secret: string, scope: string, value: unknown) =>
  work<Sealed>("seal", secret, scope, value);
export const unseal = <T>(secret: string, scope: string, value: Sealed) =>
  work<T>("open", secret, scope, value);
export async function vaultDB() {
  return openDB("haven-v1", 2, {
    upgrade(db) {
      if (!db.objectStoreNames.contains("vault")) db.createObjectStore("vault");
      if (!db.objectStoreNames.contains("ciphertextChunks"))
        db.createObjectStore("ciphertextChunks");
    },
  });
}
export async function loadVault(user: string) {
  const db = await vaultDB();
  return db.get("vault", user) as Promise<
    { sealed: Sealed; revision: number } | undefined
  >;
}
export async function saveVault(
  user: string,
  secret: string,
  value: VaultState,
  expected: number,
) {
  if (!navigator.locks)
    throw new Error("Browser lacks safe multi-tab storage locking");
  await navigator.locks.request("haven-vault:" + user, async () => {
    const sealed = await seal(secret, user, value);
    const db = await vaultDB();
    const tx = db.transaction("vault", "readwrite");
    const old = await tx.store.get(user);
    if ((old?.revision ?? 0) !== expected) {
      tx.abort();
      throw new Error(
        "Vault conflict: another tab changed state. Lock and reload.",
      );
    }
    await tx.store.put({ sealed, revision: expected + 1 }, user);
    await tx.done;
  });
}
// Recovery kits are history-only. Never export view-once keys, pending uploads,
// ratchets or ciphertext outboxes as a way to reopen ephemeral media.
export function historyForExport(value: VaultState): VaultState {
  const history = structuredClone(value);
  history.events = history.events.filter((event) => !event.file?.view_once);
  history.uploads = {};
  history.outbox = {};
  history.crypto = "";
  history.heads = {};
  history.cursor = {};
  history.drafts = {};
  history.cancelled_controls = undefined;
  return history;
}
export async function recoveryKit(
  user: string,
  secret: string,
  value: VaultState,
) {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  const recovery = Array.from(bytes, (x) =>
    x.toString(16).padStart(2, "0"),
  ).join("");
  const encrypted = await seal(recovery, user, historyForExport(value));
  // User must store the separate key out-of-band; never embed it in the downloaded kit.
  return {
    recovery,
    kit: JSON.stringify({
      format: "haven-recovery-v2-history-only",
      scope: user,
      sealed: encrypted,
    }),
  };
}
