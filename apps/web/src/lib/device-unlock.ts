import { openDB } from "idb";

// An optional, origin-bound shortcut. The vault itself is still sealed with its
// strong passphrase; only a PRF-gated, encrypted copy of that passphrase is kept
// locally. A plain WebAuthn assertion without PRF never unlocks anything.
type DeviceUnlockRecord = {
  version: 1;
  origin: string;
  rpId: string;
  deviceId: string;
  credentialId: string;
  salt: string;
  nonce: string;
  ciphertext: string;
};

export type DeviceUnlockEnvironment =
  | "ready"
  | "ip-address"
  | "insecure"
  | "unsupported";

const random = (size: number) => crypto.getRandomValues(new Uint8Array(size));
const bytes = (value: BufferSource) =>
  value instanceof ArrayBuffer
    ? new Uint8Array(value)
    : new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
const b64url = (value: Uint8Array) =>
  btoa(String.fromCharCode(...value))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
const decode = (value: string) => {
  if (!/^[A-Za-z0-9_-]+$/.test(value))
    throw new Error("Invalid device unlock record");
  return Uint8Array.from(
    atob(value.replace(/-/g, "+").replace(/_/g, "/")),
    (c) => c.charCodeAt(0),
  );
};
const aad = (
  user: string,
  record: Pick<
    DeviceUnlockRecord,
    "origin" | "rpId" | "deviceId" | "credentialId"
  >,
) =>
  new TextEncoder().encode(
    JSON.stringify([
      "haven/device-unlock/v1",
      user,
      record.origin,
      record.rpId,
      record.deviceId,
      record.credentialId,
    ]),
  );

function trustedHost() {
  if (
    location.protocol !== "https:" ||
    !isSecureContext ||
    window.top !== window.self
  )
    return "insecure" as const;
  const host = location.hostname;
  // The WebAuthn RP ID must be a domain-format host; direct IPv4/IPv6 is
  // forbidden by the standard even when the IP certificate is trusted.
  if (host.includes(":") || /^\d+(?:\.\d+){3}$/.test(host))
    return "ip-address" as const;
  if (!/^[a-z0-9.-]+$/i.test(host)) return "unsupported" as const;
  if (
    !("PublicKeyCredential" in window) ||
    !navigator.credentials?.create ||
    !navigator.credentials?.get
  )
    return "unsupported" as const;
  return "ready" as const;
}

export async function deviceUnlockEnvironment(): Promise<DeviceUnlockEnvironment> {
  const state = trustedHost();
  if (state !== "ready") return state;
  try {
    return (await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable())
      ? "ready"
      : "unsupported";
  } catch {
    return "unsupported";
  }
}

async function db() {
  return openDB("haven-device-unlock-v1", 1, {
    upgrade(database) {
      database.createObjectStore("records");
    },
  });
}

function validRecord(value: unknown): value is DeviceUnlockRecord {
  if (!value || typeof value !== "object") return false;
  const x = value as Record<string, unknown>;
  return (
    x.version === 1 &&
    [
      "origin",
      "rpId",
      "deviceId",
      "credentialId",
      "salt",
      "nonce",
      "ciphertext",
    ].every(
      (key) => typeof x[key] === "string" && (x[key] as string).length > 0,
    )
  );
}

export async function loadDeviceUnlock(user: string) {
  const value: unknown = await (await db()).get("records", user);
  return validRecord(value) ? value : undefined;
}

export async function removeDeviceUnlock(user: string) {
  if (!navigator.locks)
    throw new Error("Browser lacks safe local storage locking");
  await navigator.locks.request("haven-device-unlock:" + user, async () => {
    await (await db()).delete("records", user);
  });
}

function checkedResult(
  credential: Credential | null,
  challenge: Uint8Array,
  credentialId: string,
  rpId: string,
) {
  if (
    !(credential instanceof PublicKeyCredential) ||
    b64url(new Uint8Array(credential.rawId)) !== credentialId ||
    !(credential.response instanceof AuthenticatorAssertionResponse)
  )
    throw new Error("Device verification failed");
  const response = credential.response;
  const client = JSON.parse(
    new TextDecoder().decode(response.clientDataJSON),
  ) as Record<string, unknown>;
  if (
    client.type !== "webauthn.get" ||
    client.origin !== location.origin ||
    client.challenge !== b64url(challenge) ||
    client.crossOrigin === true
  )
    throw new Error("Device verification failed");
  const auth = new Uint8Array(response.authenticatorData);
  if (auth.length < 37 || !(auth[32] & 1) || !(auth[32] & 4))
    throw new Error("Verified device presence is required");
  return crypto.subtle
    .digest("SHA-256", new TextEncoder().encode(rpId))
    .then((digest) => {
      const expected = new Uint8Array(digest);
      if (!expected.every((value, index) => auth[index] === value))
        throw new Error("Device verification failed");
      const result = credential.getClientExtensionResults().prf?.results?.first;
      if (!result || bytes(result).byteLength !== 32)
        throw new Error(
          "This authenticator does not support secure device unlock (PRF)",
        );
      return new Uint8Array(bytes(result));
    });
}

async function prfFor(
  credentialId: string,
  salt: Uint8Array<ArrayBuffer>,
  rpId: string,
) {
  const challenge = random(32);
  const credential = await navigator.credentials.get({
    publicKey: {
      challenge,
      rpId,
      allowCredentials: [{ type: "public-key", id: decode(credentialId) }],
      userVerification: "required",
      timeout: 60000,
      extensions: {
        prf: { evalByCredential: { [credentialId]: { first: salt } } },
      },
    },
  });
  try {
    return await checkedResult(credential, challenge, credentialId, rpId);
  } finally {
    challenge.fill(0);
  }
}

export async function enrollDeviceUnlock(
  user: string,
  deviceId: string,
  secret: string,
) {
  if ((await deviceUnlockEnvironment()) !== "ready")
    throw new Error(
      "Secure device unlock requires a trusted HTTPS hostname and a compatible device",
    );
  if (secret.length < 20 || secret.length > 256 || !deviceId)
    throw new Error("Unlock passphrase is unavailable");
  if (await loadDeviceUnlock(user))
    throw new Error(
      "Remove the existing device unlock before setting up another",
    );
  const challenge = random(32),
    userId = random(32),
    salt = random(32);
  let output: Uint8Array<ArrayBuffer> | undefined;
  try {
    const credential = await navigator.credentials.create({
      publicKey: {
        challenge,
        rp: { id: location.hostname, name: "HAVEN vault" },
        user: { id: userId, name: "HAVEN vault", displayName: "HAVEN vault" },
        pubKeyCredParams: [{ type: "public-key", alg: -7 }],
        authenticatorSelection: {
          authenticatorAttachment: "platform",
          residentKey: "required",
          userVerification: "required",
        },
        attestation: "none",
        timeout: 60000,
        extensions: { prf: { eval: { first: salt } } },
      },
    });
    if (
      !(credential instanceof PublicKeyCredential) ||
      credential.type !== "public-key"
    )
      throw new Error("Device credential creation failed");
    const record: DeviceUnlockRecord = {
      version: 1,
      origin: location.origin,
      rpId: location.hostname,
      deviceId,
      credentialId: b64url(new Uint8Array(credential.rawId)),
      salt: b64url(salt),
      nonce: "",
      ciphertext: "",
    };
    // Always make a fresh user-verified assertion. Some authenticators do not
    // evaluate PRF on create, and create() alone is not our unlock ceremony.
    output = await prfFor(record.credentialId, salt, record.rpId);
    const key = await crypto.subtle.importKey("raw", output, "AES-GCM", false, [
      "encrypt",
    ]);
    const nonce = random(12),
      plaintext = new TextEncoder().encode(secret);
    try {
      record.nonce = b64url(nonce);
      record.ciphertext = b64url(
        new Uint8Array(
          await crypto.subtle.encrypt(
            {
              name: "AES-GCM",
              iv: nonce,
              additionalData: aad(user, record),
              tagLength: 128,
            },
            key,
            plaintext,
          ),
        ),
      );
    } finally {
      plaintext.fill(0);
      nonce.fill(0);
    }
    if (!navigator.locks)
      throw new Error("Browser lacks safe local storage locking");
    await navigator.locks.request("haven-device-unlock:" + user, async () => {
      const database = await db();
      const tx = database.transaction("records", "readwrite");
      const prior = await tx.store.get(user);
      if (prior) {
        tx.abort();
        throw new Error("Another tab set up device unlock first");
      }
      await tx.store.put(record, user);
      await tx.done;
    });
  } finally {
    challenge.fill(0);
    userId.fill(0);
    salt.fill(0);
    output?.fill(0);
  }
}

export async function unlockWithDevice(user: string) {
  if ((await deviceUnlockEnvironment()) !== "ready")
    throw new Error(
      "Device unlock is unavailable here. Use your vault passphrase",
    );
  const record = await loadDeviceUnlock(user);
  if (
    !record ||
    record.origin !== location.origin ||
    record.rpId !== location.hostname
  )
    throw new Error(
      "Device unlock is unavailable here. Use your vault passphrase",
    );
  const salt = decode(record.salt),
    nonce = decode(record.nonce);
  if (
    salt.length !== 32 ||
    nonce.length !== 12 ||
    decode(record.ciphertext).length < 36
  )
    throw new Error(
      "Device unlock record is damaged. Use your vault passphrase",
    );
  const output = await prfFor(record.credentialId, salt, record.rpId);
  try {
    const key = await crypto.subtle.importKey("raw", output, "AES-GCM", false, [
      "decrypt",
    ]);
    const plaintext = new Uint8Array(
      await crypto.subtle.decrypt(
        {
          name: "AES-GCM",
          iv: nonce,
          additionalData: aad(user, record),
          tagLength: 128,
        },
        key,
        decode(record.ciphertext),
      ),
    );
    try {
      const secret = new TextDecoder("utf-8", { fatal: true }).decode(
        plaintext,
      );
      if (secret.length < 20 || secret.length > 256)
        throw new Error("Device unlock record is damaged");
      return { secret, deviceId: record.deviceId };
    } finally {
      plaintext.fill(0);
    }
  } catch {
    throw new Error(
      "Device unlock failed. Use your vault passphrase, then reset device unlock in Settings",
    );
  } finally {
    output.fill(0);
    salt.fill(0);
    nonce.fill(0);
  }
}
