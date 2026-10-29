import sodium from "libsodium-wrappers-sumo";
// Derived keys live only in this worker until lock/termination. Reusing a per-vault KDF salt is safe;
// each snapshot uses a fresh 192-bit AEAD nonce. Never repeat Argon2 for every ratchet persistence.
let cached:
  | { scope: string; secret: string; salt: Uint8Array; key: Uint8Array }
  | undefined;
let chain = Promise.resolve();
function derive(scope: string, secret: string, salt: Uint8Array) {
  if (
    cached &&
    cached.scope === scope &&
    cached.secret === secret &&
    sodium.memcmp(cached.salt, salt)
  )
    return cached.key;
  if (cached) sodium.memzero(cached.key);
  const key = sodium.crypto_pwhash(
    32,
    secret,
    salt,
    3,
    67108864,
    sodium.crypto_pwhash_ALG_ARGON2ID13,
  );
  cached = { scope, secret, salt, key };
  return key;
}
self.onmessage = (e) => {
  chain = chain.then(async () => {
    const { id, op, secret, value, scope } = e.data;
    try {
      await sodium.ready;
      if (
        typeof scope !== "string" ||
        scope.length > 200 ||
        typeof secret !== "string" ||
        secret.length < 20 ||
        secret.length > 256
      )
        throw new Error();
      const aad = sodium.from_string("haven/vault/v1:" + scope);
      if (op === "seal") {
        const salt =
            cached?.scope === scope && cached.secret === secret
              ? cached.salt
              : sodium.randombytes_buf(16),
          key = derive(scope, secret, salt),
          nonce = sodium.randombytes_buf(24);
        const plain = sodium.from_string(JSON.stringify(value));
        if (plain.length > 16000000) throw new Error();
        try {
          const ciphertext = sodium.crypto_aead_xchacha20poly1305_ietf_encrypt(
            plain,
            aad,
            null,
            nonce,
            key,
          );
          self.postMessage({
            id,
            value: {
              v: 1,
              kdf: "argon2id-3-64MiB",
              salt: sodium.to_base64(salt),
              nonce: sodium.to_base64(nonce),
              ciphertext: sodium.to_base64(ciphertext),
            },
          });
        } finally {
          sodium.memzero(plain);
        }
      } else if (op === "open") {
        if (
          value.v !== 1 ||
          value.kdf !== "argon2id-3-64MiB" ||
          typeof value.ciphertext !== "string" ||
          value.ciphertext.length > 24000000
        )
          throw new Error();
        const salt = sodium.from_base64(value.salt),
          nonce = sodium.from_base64(value.nonce);
        if (salt.length !== 16 || nonce.length !== 24) throw new Error();
        const key = derive(scope, secret, salt),
          plain = sodium.crypto_aead_xchacha20poly1305_ietf_decrypt(
            null,
            sodium.from_base64(value.ciphertext),
            aad,
            nonce,
            key,
          );
        try {
          self.postMessage({ id, value: JSON.parse(sodium.to_string(plain)) });
        } finally {
          sodium.memzero(plain);
        }
      } else throw new Error();
    } catch {
      self.postMessage({ id, error: "VAULT_REJECTED" });
    }
  });
};
