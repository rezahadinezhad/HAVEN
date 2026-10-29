import { isViewOnceMedia } from "./attachment-policy";
import sodium from "libsodium-wrappers-sumo";
import { vaultDB, type FileMeta } from "./vault";
import { api, uploadChunk } from "./api";
const CHUNK = 512 * 1024;
function aad(
  meta: Pick<FileMeta, "id" | "conversation_id" | "count" | "view_once">,
  i: number,
) {
  return sodium.from_string(
    JSON.stringify([
      meta.view_once ? "haven-view-once-attachment" : "haven-attachment",
      1,
      meta.conversation_id,
      meta.id,
      i,
      meta.count,
    ]),
  );
}
function nonce(prefix: Uint8Array, i: number) {
  const n = new Uint8Array(24);
  n.set(prefix);
  new DataView(n.buffer).setBigUint64(16, BigInt(i), false);
  return n;
}
export async function prepareUpload(
  file: File,
  cid: string,
  signal: AbortSignal,
  viewOnce = false,
): Promise<FileMeta> {
  await sodium.ready;
  if (viewOnce && !isViewOnceMedia(file.type))
    throw new Error("View once supports photos and videos only");
  if (file.size > 25 * 1024 * 1024) throw new Error("File exceeds 25 MiB");
  const count = Math.max(1, Math.ceil(file.size / CHUNK)),
    key = sodium.randombytes_buf(32),
    prefix = sodium.randombytes_buf(16);
  const meta: FileMeta = {
    ...(viewOnce ? { view_once: true as const } : {}),
    id: crypto.randomUUID(),
    name: file.name,
    mime: file.type || "application/octet-stream",
    key: sodium.to_base64(key),
    prefix: sodium.to_base64(prefix),
    count,
    size: file.size,
    conversation_id: cid,
  };
  const db = await vaultDB();
  try {
    for (let i = 0; i < count; i++) {
      signal.throwIfAborted();
      const plain = new Uint8Array(
        await file.slice(i * CHUNK, (i + 1) * CHUNK).arrayBuffer(),
      );
      try {
        const cipher = sodium.crypto_aead_xchacha20poly1305_ietf_encrypt(
          plain,
          aad(meta, i),
          null,
          nonce(prefix, i),
          key,
        );
        await db.put("ciphertextChunks", cipher, `${meta.id}:${i}`);
      } finally {
        sodium.memzero(plain);
      }
    }
    return meta;
  } catch (e) {
    await discardUpload(meta);
    throw e;
  } finally {
    sodium.memzero(key);
  }
}
export async function resumeUpload(
  meta: FileMeta,
  onProgress: (n: number) => void,
  signal: AbortSignal,
) {
  const start = await api<{ status?: string }>("attachments/init", "POST", {
    id: meta.id,
    conversation_id: meta.conversation_id,
    chunk_count: meta.count,
    ciphertext_size: meta.size + 16 * meta.count,
    view_once: meta.view_once === true,
  });
  if (start.status !== "complete") {
    const db = await vaultDB();
    for (let i = 0; i < meta.count; i++) {
      signal.throwIfAborted();
      const cipher = await db.get("ciphertextChunks", `${meta.id}:${i}`);
      if (!(cipher instanceof Uint8Array))
        throw new Error(
          "Encrypted upload chunks missing. Cancel the upload and select the original file again.",
        );
      await uploadChunk(meta.id, i, cipher, signal);
      onProgress((i + 1) / meta.count);
    }
    await api(`attachments/${meta.id}/complete`, "POST", {});
  }
  return meta;
}
export async function discardUpload(meta: FileMeta) {
  const db = await vaultDB(),
    tx = db.transaction("ciphertextChunks", "readwrite");
  for (let i = 0; i < meta.count; i++) await tx.store.delete(`${meta.id}:${i}`);
  await tx.done;
}
export async function encryptUpload(
  file: File,
  cid: string,
  onProgress: (n: number) => void,
  signal: AbortSignal,
) {
  const meta = await prepareUpload(file, cid, signal);
  try {
    await resumeUpload(meta, onProgress, signal);
    return meta;
  } finally {
    await discardUpload(meta);
  }
}
export async function discardDownload(meta: FileMeta) {
  const db = await vaultDB(),
    tx = db.transaction("ciphertextChunks", "readwrite");
  for (let i = 0; i < meta.count; i++)
    await tx.store.delete(`download:${meta.id}:${i}`);
  await tx.done;
}
export async function downloadDecrypt(
  meta: FileMeta,
  options: {
    signal?: AbortSignal;
    progress?: (value: number) => void;
    viewOnceToken?: string;
  } = {},
): Promise<Blob> {
  await sodium.ready;
  if (meta.view_once && (!options.viewOnceToken || !isViewOnceMedia(meta.mime)))
    throw new Error("Open view-once media in the temporary viewer");
  if (!meta.view_once && options.viewOnceToken)
    throw new Error("View-once policy mismatch");
  if (
    !Number.isInteger(meta.count) ||
    meta.count < 1 ||
    meta.count > 50 ||
    meta.size > 25 * 1024 * 1024
  )
    throw new Error("Invalid file metadata");
  const key = sodium.from_base64(meta.key),
    prefix = sodium.from_base64(meta.prefix),
    parts: Uint8Array<ArrayBuffer>[] = [];
  if (key.length !== 32 || prefix.length !== 16)
    throw new Error("Invalid attachment key");
  // Never persist received view-once chunks, even on interrupted downloads.
  const db = meta.view_once ? undefined : await vaultDB();
  const incomplete = new Set(
    (db ? await db.getAllKeys("ciphertextChunks") : [])
      .map(String)
      .filter((k) => k.startsWith("download:"))
      .map((k) => k.split(":")[1]),
  );
  try {
    if (!incomplete.has(meta.id) && incomplete.size >= 4)
      throw new Error(
        "Incomplete download limit reached. Cancel a previous download before retrying.",
      );
    for (let i = 0; i < meta.count; i++) {
      options.signal?.throwIfAborted();
      const cacheKey = `download:${meta.id}:${i}`;
      let cipher = (
        db ? await db.get("ciphertextChunks", cacheKey) : undefined
      ) as Uint8Array | undefined;
      if (!cipher) {
        const r = await fetch(`/api/v1/attachments/${meta.id}/chunks/${i}`, {
          cache: "no-store",
          headers: options.viewOnceToken
            ? { "X-Haven-View-Token": options.viewOnceToken }
            : undefined,
          signal: options.signal
            ? AbortSignal.any([options.signal, AbortSignal.timeout(120000)])
            : AbortSignal.timeout(120000),
        });
        if (!r.ok) throw new Error("Attachment unavailable");
        const body = await r.arrayBuffer();
        if (body.byteLength > CHUNK + 16) throw new Error("Oversize chunk");
        cipher = new Uint8Array(body);
      }
      try {
        parts.push(
          sodium.crypto_aead_xchacha20poly1305_ietf_decrypt(
            null,
            cipher,
            aad(meta, i),
            nonce(prefix, i),
            key,
          ) as Uint8Array<ArrayBuffer>,
        );
      } catch {
        if (db) await discardDownload(meta);
        throw new Error("Attachment authentication failed");
      }
      // Cache only authenticated ciphertext. Retry can resume verified chunks after a connection failure.
      if (db) await db.put("ciphertextChunks", cipher, cacheKey);
      options.progress?.((i + 1) / meta.count);
    }
    const blob = new Blob(parts, { type: meta.mime });
    if (blob.size !== meta.size) throw new Error("File size mismatch");
    if (db) await discardDownload(meta);
    return blob;
  } catch (e) {
    // Preserve verified encrypted chunks for transient network failures, never a corrupt cached chunk.
    if (
      db &&
      !(e instanceof TypeError) &&
      !(
        e instanceof DOMException &&
        ["AbortError", "TimeoutError"].includes(e.name)
      )
    )
      await discardDownload(meta);
    throw e;
  } finally {
    sodium.memzero(key);
    for (const part of parts) sodium.memzero(part);
  }
}
