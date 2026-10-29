export type CryptoResult = {
  identity: string;
  public_key: string;
  key_package?: string;
  members?: { index: number; identity: string; public_key: string }[];
  epoch?: number;
  ciphertext?: string;
  plaintext?: string;
  commit?: string;
  welcome?: string;
  kind?: string;
  active?: boolean;
  sender?: string;
  state_hash?: string;
  signature?: string;
};
export type CryptoResponse = { state: string; result: CryptoResult };
let worker: Worker | undefined;
let nextId = 1;
const waiting = new Map<
  number,
  { resolve: (v: CryptoResponse) => void; reject: (e: Error) => void }
>();
export function cryptoCall(
  state: string,
  command: Record<string, unknown>,
): Promise<CryptoResponse> {
  if (!isSecureContext || location.protocol !== "https:")
    return Promise.reject(new Error("Trusted HTTPS required"));
  if (!worker) {
    worker = new Worker("/crypto-worker.js", { type: "module" });
    worker.onmessage = (e) => {
      const h = waiting.get(e.data.id);
      if (!h) return;
      waiting.delete(e.data.id);
      if (e.data.error) h.reject(new Error("Cryptographic operation rejected"));
      else h.resolve(e.data.value);
    };
    worker.onerror = () => {
      for (const h of waiting.values())
        h.reject(new Error("Crypto worker unavailable"));
      waiting.clear();
      worker?.terminate();
      worker = undefined;
    };
  }
  return new Promise((resolve, reject) => {
    const id = nextId++;
    waiting.set(id, { resolve, reject });
    worker!.postMessage({ id, state, command });
  });
}
export function lockCrypto() {
  worker?.terminate();
  worker = undefined;
  for (const h of waiting.values()) h.reject(new Error("Locked"));
  waiting.clear();
}
