/** A new local vault secret: 32 CSPRNG bytes, losslessly encoded as base64url. */
export function generateUnlockPassphrase(): string {
  if (!globalThis.isSecureContext || !globalThis.crypto?.getRandomValues) {
    throw new Error(
      "Secure passphrase generation is unavailable in this browser",
    );
  }
  const bytes = new Uint8Array(32);
  try {
    globalThis.crypto.getRandomValues(bytes);
    return btoa(String.fromCharCode(...bytes))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  } finally {
    bytes.fill(0);
  }
}
