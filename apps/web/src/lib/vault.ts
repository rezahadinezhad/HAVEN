import { openDB } from "idb";
import type { Certificate } from "./api";
import type { ClosureArchive } from "./closure-protocol";
export type SealedRecord = {
  v: 1;
  kdf: string;
  salt: string;
  nonce: string;
  ciphertext: string;
};
export type Sealed =
  | SealedRecord
  | {
      v: 2;
      checkpoint: SealedRecord;
      pages: { key: string; sealed: SealedRecord }[];
      archives?: { key: string; sealed: SealedRecord }[];
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
  format?: 2;
  padded_size?: number;
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
  rejected_events?: { conversation_id: string; seq: number; id: string }[];
  rejected_event_count?: number;
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
      closure_policy?: string;
      closure_epoch?: string;
      members: Certificate[];
      epoch_start_seq?: number;
    }
  >;
  crypto: string;
  revision: number;
  pins: Record<string, string>;
  closure_archives?: Record<string, ClosureArchive>;
  retired_history?: Record<
    string,
    { events: LocalEvent[]; draft: string; pending: Record<string, unknown> }
  >;
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
let generation = 0;
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
  binding?: string,
  expectedGeneration = generation,
): Promise<T> {
  if (expectedGeneration !== generation)
    return Promise.reject(new Error("Vault locked"));
  if (location.protocol !== "https:" || !isSecureContext)
    return Promise.reject(new Error("Trusted HTTPS required"));
  if (!worker) {
    worker = new Worker("/vault-worker-v2.js");
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
    worker!.postMessage({ id, op, secret, scope, value, binding });
  });
}
export function stopVaultWorker() {
  generation++;
  historyCache.clear();
  worker?.terminate();
  worker = undefined;
  for (const h of waiting.values()) h.reject(new Error("Vault locked"));
  waiting.clear();
}
type HistoryRef = { id: string; key: string };
type Checkpoint = VaultState & {
  history_records?: HistoryRef[];
  closure_records?: HistoryRef[];
  history_pages?: { key: string; count: number }[];
};
type StoredVault = { sealed: SealedRecord; revision: number; format?: 2 };
const historyCache = new Map<
  string,
  {
    revision: number;
    keyTag: string;
    refs: HistoryRef[];
    events: Map<string, LocalEvent>;
    archiveRefs: HistoryRef[];
    archives: Map<string, ClosureArchive>;
  }
>();
const secretTag = async (scope: string, secret: string) =>
  Array.from(
    new Uint8Array(
      await crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(JSON.stringify([scope, secret])),
      ),
    ),
  ).join(",");
const rawSeal = (
  secret: string,
  scope: string,
  value: unknown,
  binding?: string,
  expectedGeneration = generation,
) =>
  work<SealedRecord>("seal", secret, scope, value, binding, expectedGeneration);
const rawOpen = <T>(
  secret: string,
  scope: string,
  value: SealedRecord,
  binding?: string,
  expectedGeneration = generation,
) => work<T>("open", secret, scope, value, binding, expectedGeneration);

// Portable encrypted exports use bounded pages too; old v1 kits remain readable.
export async function seal(
  secret: string,
  scope: string,
  value: unknown,
): Promise<Sealed> {
  const started = generation;
  const history = value as VaultState;
  if (!history || !Array.isArray(history.events))
    return rawSeal(secret, scope, value);
  const pages: { key: string; sealed: SealedRecord }[] = [];
  const refs: { key: string; count: number }[] = [];
  for (let i = 0; i < history.events.length; i += 32) {
    const key = crypto.randomUUID(),
      events = history.events.slice(i, i + 32);
    pages.push({
      key,
      sealed: await rawSeal(secret, scope, events, "history:" + key, started),
    });
    refs.push({ key, count: events.length });
  }
  const archives: { key: string; sealed: SealedRecord }[] = [],
    archiveRefs: HistoryRef[] = [];
  for (const [id, archive] of Object.entries(history.closure_archives || {})) {
    const key = crypto.randomUUID();
    archiveRefs.push({ id, key });
    archives.push({
      key,
      sealed: await rawSeal(secret, scope, archive, "archive:" + key, started),
    });
  }
  return {
    v: 2,
    archives,
    checkpoint: await rawSeal(
      secret,
      scope,
      {
        ...history,
        events: [],
        history_pages: refs,
        closure_archives: undefined,
        closure_records: archiveRefs,
      },
      undefined,
      started,
    ),
    pages,
  };
}
export async function unseal<T>(
  secret: string,
  scope: string,
  value: Sealed,
): Promise<T> {
  const started = generation;
  if (value.v === 1) return rawOpen<T>(secret, scope, value);
  if (value.v !== 2 || !Array.isArray(value.pages) || value.pages.length > 3125)
    throw new Error("Invalid history bundle");
  const state = await rawOpen<Checkpoint>(
    secret,
    scope,
    value.checkpoint,
    undefined,
    started,
  );
  if (
    !Array.isArray(state.history_pages) ||
    state.history_pages.length !== value.pages.length
  )
    throw new Error("Incomplete history bundle");
  state.events = [];
  for (let i = 0; i < value.pages.length; i++) {
    const page = value.pages[i],
      ref = state.history_pages[i];
    if (page.key !== ref.key) throw new Error("History page binding rejected");
    const events = await rawOpen<LocalEvent[]>(
      secret,
      scope,
      page.sealed,
      "history:" + ref.key,
      started,
    );
    if (
      !Array.isArray(events) ||
      events.length !== ref.count ||
      events.length > 32
    )
      throw new Error("Invalid history page");
    state.events.push(...events);
  }
  const archiveRefs = state.closure_records || [],
    archives = value.archives || [];
  if (
    archives.length > 256 ||
    archiveRefs.length !== archives.length ||
    new Set(archiveRefs.map((x) => x.id)).size !== archiveRefs.length ||
    new Set(archiveRefs.map((x) => x.key)).size !== archiveRefs.length
  )
    throw new Error("Invalid archive export manifest");
  if (archives.length) state.closure_archives = {};
  for (let i = 0; i < archiveRefs.length; i++) {
    if (archives[i].key !== archiveRefs[i].key)
      throw new Error("Archive export binding mismatch");
    const archive = await rawOpen<ClosureArchive>(
      secret,
      scope,
      archives[i].sealed,
      "archive:" + archiveRefs[i].key,
      started,
    );
    if (archive.transcript.conversation_id !== archiveRefs[i].id)
      throw new Error("Archive export scope mismatch");
    state.closure_archives![archiveRefs[i].id] = archive;
  }
  delete state.closure_records;
  delete state.history_pages;
  return state as T;
}
export async function vaultDB() {
  return openDB("haven-v1", 3, {
    upgrade(db) {
      for (const name of ["vault", "ciphertextChunks", "history"])
        if (!db.objectStoreNames.contains(name)) db.createObjectStore(name);
    },
  });
}
export async function loadVault(
  user: string,
): Promise<StoredVault | undefined> {
  const db = await vaultDB();
  return db.get("vault", user);
}
export async function openVault(
  user: string,
  secret: string,
  stored: StoredVault,
): Promise<VaultState> {
  const started = generation;
  const state = await rawOpen<Checkpoint>(
    secret,
    user,
    stored.sealed,
    undefined,
    started,
  );
  if (stored.format !== 2) return state; // Migrated atomically on the first save.
  const refs = state.history_records;
  if (
    !Array.isArray(refs) ||
    new Set(refs.map((r) => r.id)).size !== refs.length ||
    new Set(refs.map((r) => r.key)).size !== refs.length
  )
    throw new Error("Invalid history manifest");
  const db = await vaultDB(),
    tx = db.transaction(["vault", "history"], "readonly");
  const current = (await tx.objectStore("vault").get(user)) as
    StoredVault | undefined;
  if (
    current?.revision !== stored.revision ||
    current.sealed.nonce !== stored.sealed.nonce
  ) {
    await tx.done;
    throw new Error("Vault changed while unlocking. Retry unlock.");
  }
  const archiveRefs = state.closure_records || [];
  if (
    archiveRefs.length > 256 ||
    new Set(archiveRefs.map((x) => x.id)).size !== archiveRefs.length ||
    new Set([...refs, ...archiveRefs].map((x) => x.key)).size !==
      refs.length + archiveRefs.length
  )
    throw new Error("Invalid encrypted archive manifest");
  const records = await Promise.all(
    refs.map((r) => tx.objectStore("history").get([user, r.key])),
  );
  const archiveRecords = await Promise.all(
    archiveRefs.map((r) => tx.objectStore("history").get([user, r.key])),
  );
  await tx.done;
  state.events = [];
  for (let i = 0; i < refs.length; i++) {
    if (!records[i]) throw new Error("Encrypted history record missing");
    const event = await rawOpen<LocalEvent>(
      secret,
      user,
      records[i],
      "history:" + refs[i].key,
      started,
    );
    if (event.id !== refs[i].id)
      throw new Error("History record binding rejected");
    state.events.push(event);
  }
  if (archiveRefs.length) state.closure_archives = {};
  for (let i = 0; i < archiveRefs.length; i++) {
    if (!archiveRecords[i]) throw new Error("Encrypted archive record missing");
    const archive = await rawOpen<ClosureArchive>(
      secret,
      user,
      archiveRecords[i],
      "archive:" + archiveRefs[i].key,
      started,
    );
    if (archive.transcript.conversation_id !== archiveRefs[i].id)
      throw new Error("Archive record scope mismatch");
    state.closure_archives![archiveRefs[i].id] = Object.freeze(archive);
  }
  delete state.closure_records;
  const keyTag = await secretTag(user, secret);
  if (started !== generation) throw new Error("Vault locked");
  delete state.history_records;
  for (const event of state.events) {
    if (event.file) Object.freeze(event.file);
    Object.freeze(event);
  }
  historyCache.set(user, {
    revision: stored.revision,
    keyTag,
    refs,
    events: new Map(state.events.map((e) => [e.id, e])),
    archiveRefs,
    archives: new Map(Object.entries(state.closure_archives || {})),
  });
  return state;
}
export async function saveVault(
  user: string,
  secret: string,
  value: VaultState,
  expected: number,
) {
  if (!navigator.locks)
    throw new Error("Browser lacks safe multi-tab storage locking");
  const started = generation;
  await navigator.locks.request("haven-vault:" + user, async () => {
    if (started !== generation) throw new Error("Vault locked");
    const db = await vaultDB();
    const old = (await db.get("vault", user)) as StoredVault | undefined;
    if ((old?.revision ?? 0) !== expected)
      throw new Error(
        "Vault conflict: another tab changed state. Lock and reload.",
      );
    const keyTag = await secretTag(user, secret);
    const cached = historyCache.get(user);
    const reusable =
      cached?.revision === expected && cached.keyTag === keyTag
        ? cached
        : undefined;
    const baseline =
      cached?.revision !== expected && old?.format === 2
        ? await rawOpen<Checkpoint>(
            secret,
            user,
            old.sealed,
            undefined,
            started,
          )
        : undefined;
    const existingRefs =
      (cached?.revision === expected ? cached.refs : undefined) ||
      baseline?.history_records ||
      [];
    const existingArchiveRefs =
      (cached?.revision === expected ? cached.archiveRefs : undefined) ||
      baseline?.closure_records ||
      [];
    const archivePrior = new Map(existingArchiveRefs.map((r) => [r.id, r]));
    const archiveRefs: HistoryRef[] = [],
      archiveWrites: { key: string; sealed: SealedRecord }[] = [];
    for (const [id, archive] of Object.entries(value.closure_archives || {})) {
      const oldRef = archivePrior.get(id);
      if (oldRef && reusable?.archives.get(id) === archive)
        archiveRefs.push(oldRef);
      else {
        const key = crypto.randomUUID();
        archiveRefs.push({ id, key });
        archiveWrites.push({
          key,
          sealed: await rawSeal(
            secret,
            user,
            archive,
            "archive:" + key,
            started,
          ),
        });
      }
    }
    const prior = new Map(reusable?.refs.map((r) => [r.id, r]) ?? []);
    const refs: HistoryRef[] = [],
      writes: { key: string; sealed: SealedRecord }[] = [];
    const ids = new Set<string>();
    for (const event of value.events) {
      if (ids.has(event.id))
        throw new Error("Duplicate local history identity");
      ids.add(event.id);
      const previous = prior.get(event.id);
      if (previous && reusable?.events.get(event.id) === event)
        refs.push(previous);
      else {
        const key = crypto.randomUUID();
        refs.push({ id: event.id, key });
        writes.push({
          key,
          sealed: await rawSeal(secret, user, event, "history:" + key, started),
        });
      }
    }
    const sealed = await rawSeal(
      secret,
      user,
      {
        ...value,
        events: [],
        history_records: refs,
        closure_archives: undefined,
        closure_records: archiveRefs,
      },
      undefined,
      started,
    );
    // Both encrypted history and ratchet/cursor/outbox checkpoint commit in one
    // transaction. Never ACK a snapshot whose history failed to persist.
    if (started !== generation) throw new Error("Vault locked");
    const tx = db.transaction(["vault", "history"], "readwrite");
    try {
      const current = (await tx.objectStore("vault").get(user)) as
        StoredVault | undefined;
      if (
        (current?.revision ?? 0) !== expected ||
        current?.sealed.nonce !== old?.sealed.nonce
      ) {
        tx.abort();
        await tx.done.catch(() => {});
        throw new Error(
          "Vault conflict: another tab changed state. Lock and reload.",
        );
      }
      const keep = new Set([...refs, ...archiveRefs].map((r) => r.key));
      for (const ref of [...existingRefs, ...existingArchiveRefs])
        if (!keep.has(ref.key))
          await tx.objectStore("history").delete([user, ref.key]);
      for (const record of [...writes, ...archiveWrites])
        await tx.objectStore("history").put(record.sealed, [user, record.key]);
      await tx
        .objectStore("vault")
        .put({ sealed, revision: expected + 1, format: 2 }, user);
      await tx.done;
    } catch (error) {
      try {
        tx.abort();
      } catch {
        /* Already completed/aborted. */
      }
      await tx.done.catch(() => {});
      if (error instanceof DOMException && error.name === "QuotaExceededError")
        throw new Error("VAULT_CAPACITY_REACHED");
      throw error;
    }
    if (started !== generation) throw new Error("Vault locked");
    for (const event of value.events) {
      if (event.file) Object.freeze(event.file);
      Object.freeze(event);
    }
    for (const archive of Object.values(value.closure_archives || {}))
      Object.freeze(archive);
    historyCache.set(user, {
      revision: expected + 1,
      keyTag,
      refs,
      events: new Map(value.events.map((e) => [e.id, e])),
      archiveRefs,
      archives: new Map(Object.entries(value.closure_archives || {})),
    });
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
