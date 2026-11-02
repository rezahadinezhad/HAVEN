// Synthetic native media fixture; same XChaCha20-Poly1305 format as lib/media.ts.
// All keys and decrypted bytes stay in this process/private stdin/stdout pipes.
import sodium from "../apps/web/node_modules/libsodium-wrappers-sumo/dist/modules-sumo/libsodium-wrappers.js";
import crypto from "node:crypto";
await sodium.ready;
let input = "";
for await (const part of process.stdin) input += part;
const request = JSON.parse(input);
const b64 = (value) => Buffer.from(value).toString("base64");
const key =
  request.op === "encrypt"
    ? sodium.randombytes_buf(32)
    : new Uint8Array(Buffer.from(request.key, "base64"));
const prefix =
  request.op === "encrypt"
    ? sodium.randombytes_buf(16)
    : new Uint8Array(Buffer.from(request.prefix, "base64"));
const chunks = [],
  hash = crypto.createHash("sha256");
try {
  for (let i = 0; i < 2; i++) {
    const nonce = new Uint8Array(24);
    nonce.set(prefix);
    new DataView(nonce.buffer).setBigUint64(16, BigInt(i), false);
    const aad = sodium.from_string(
      JSON.stringify(["haven-attachment", 1, request.cid, request.id, i, 2]),
    );
    if (request.op === "encrypt") {
      const plain = new Uint8Array(512 * 1024).fill(0x5a);
      chunks.push(
        b64(
          sodium.crypto_aead_xchacha20poly1305_ietf_encrypt(
            plain,
            aad,
            null,
            nonce,
            key,
          ),
        ),
      );
      sodium.memzero(plain);
    } else {
      const plain = sodium.crypto_aead_xchacha20poly1305_ietf_decrypt(
        null,
        Buffer.from(request.chunks[i], "base64"),
        aad,
        nonce,
        key,
      );
      hash.update(plain);
      sodium.memzero(plain);
    }
  }
  process.stdout.write(
    JSON.stringify(
      request.op === "encrypt"
        ? { key: b64(key), prefix: b64(prefix), chunks }
        : { sha256: hash.digest("hex") },
    ),
  );
} finally {
  sodium.memzero(key);
  sodium.memzero(prefix);
}
