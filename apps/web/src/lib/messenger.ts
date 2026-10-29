import { authenticatedEvent } from "./events";
// RFC 9420 encryption stays in OpenMLS. Delivery signatures authenticate ordering and application policy.
import { prepareUpload, resumeUpload, discardUpload } from "./media";
import type { FileMeta } from "./vault";
import sodium from "libsodium-wrappers-sumo";
import canonicalize from "canonicalize";
import {
  api,
  type Conversation,
  type Device,
  type Envelope,
  type Certificate,
  type DeliveryHeader,
  type Transition,
} from "./api";
import { cryptoCall, lockCrypto, type CryptoResult } from "./crypto";
import {
  enrollDeviceUnlock,
  removeDeviceUnlock,
  unlockWithDevice,
} from "./device-unlock";
import {
  loadVault,
  saveVault,
  unseal,
  stopVaultWorker,
  type VaultState,
  type LocalEvent,
} from "./vault";
const canonical = (x: unknown) => {
  const value = canonicalize(x);
  if (!value) throw new Error("Canonical encoding failed");
  return value;
};
const encode = (x: string) =>
  btoa(String.fromCharCode(...new TextEncoder().encode(x)));
const raw = (x: string) => Uint8Array.from(atob(x), (c) => c.charCodeAt(0));
export const digest = async (x: Uint8Array | string) =>
  Array.from(
    new Uint8Array(
      await crypto.subtle.digest(
        "SHA-256",
        (typeof x === "string"
          ? new TextEncoder().encode(x)
          : x) as Uint8Array<ArrayBuffer>,
      ),
    ),
    (b) => b.toString(16).padStart(2, "0"),
  ).join("");
const hash = (x: string) => digest(raw(x));
const certificate = (
  d: Device,
  role: Certificate["role"] = "member",
): Certificate => ({
  id: d.id,
  user_id: d.user_id,
  identity: d.identity,
  public_key: d.public_key,
  role,
});
const sorted = (a: Certificate[]) =>
  [...a].sort((x, y) => x.id.localeCompare(y.id));
const same = (a: unknown, b: unknown) => canonical(a) === canonical(b);
async function signatureValid(key: string, signature: string, value: unknown) {
  await sodium.ready;
  if (
    !sodium.crypto_sign_verify_detached(
      raw(signature),
      canonical(value),
      raw(key),
    )
  )
    throw new Error("Invalid delivery signature");
}
type Head = VaultState["heads"][string];
type Detail = Conversation & {
  members: { device: Device; role: Certificate["role"] }[];
  genesis: {
    domain: string;
    id: string;
    group_id: string;
    kind: string;
    members: Certificate[];
  };
  genesis_signature: string;
};
export class Messenger {
  private constructor(
    public user: string,
    private secret: string,
    public state: VaultState,
  ) {}
  private chain: Promise<unknown> = Promise.resolve();
  private locked = false;
  private directStarts = new Map<string, Promise<Conversation>>();
  public connectionError = "";
  static async unlock(user: string, secret: string) {
    const stored = await loadVault(user);
    if (!stored)
      throw new Error(
        "No local vault. Enroll a fresh device or recover your account.",
      );
    const state = await unseal<VaultState>(secret, user, stored.sealed);
    if (
      state.v !== 1 ||
      state.profile !== "haven-delivery-v2" ||
      state.revision !== stored.revision
    )
      throw new Error(
        "Unsupported vault. History must be recovered into a fresh device.",
      );
    const instance = new Messenger(user, secret, state);
    try {
      await instance.connect();
    } catch (e) {
      instance.connectionError =
        e instanceof Error ? e.message : "Connection unavailable";
    }
    return instance;
  }
  static async unlockUsingDevice(user: string) {
    const { secret, deviceId } = await unlockWithDevice(user);
    const instance = await Messenger.unlock(user, secret);
    if (instance.state.device_id !== deviceId) {
      instance.lock();
      throw new Error(
        "The local vault changed. Unlock with its passphrase and set up device unlock again",
      );
    }
    return instance;
  }
  async enableDeviceUnlock() {
    if (this.locked) throw new Error("Vault locked");
    await enrollDeviceUnlock(this.user, this.state.device_id, this.secret);
    if (this.locked) {
      await removeDeviceUnlock(this.user);
      throw new Error("Vault locked while setting up device unlock");
    }
  }
  async disableDeviceUnlock() {
    await removeDeviceUnlock(this.user);
  }
  static async create(user: string, secret: string, label: string) {
    if (await loadVault(user))
      throw new Error(
        "Unlock the existing vault; never overwrite active MLS state.",
      );
    const id = crypto.randomUUID();
    const x = await cryptoCall("", { op: "init", identity: `${user}:${id}` });
    const state: VaultState = {
      v: 1,
      profile: "haven-delivery-v2",
      device_id: id,
      device: {
        label,
        identity: x.result.identity,
        public_key: x.result.public_key,
      },
      crypto: x.state,
      revision: 1,
      pins: { [id]: x.result.public_key },
      heads: {},
      cursor: {},
      events: [],
      outbox: {},
      drafts: {},
    };
    await saveVault(user, secret, state, 0);
    const instance = new Messenger(user, secret, state);
    // Persist identity even when another trusted device must approve it.
    try {
      await instance.connect();
      await instance.package();
    } catch (e) {
      if (
        !(e instanceof Error) ||
        !e.message.includes("Existing-device approval")
      ) {
        instance.lock();
        throw e;
      }
    }
    return instance;
  }
  async connect() {
    const d = this.state.device;
    const req = await api<Device & { signing_payload: string }>(
      "devices/enrollment/request",
      "POST",
      { id: this.state.device_id, ...d },
    );
    // Server challenge is restricted to this purpose and our exact device. It is not an arbitrary signing oracle.
    if (
      !/^haven\/session\/v1:\d+:[0-9a-f-]{36}:[0-9a-f]{64}$/.test(
        req.signing_payload,
      ) ||
      req.signing_payload.split(":")[2] !== this.state.device_id ||
      req.public_key !== d.public_key
    )
      throw new Error("Session challenge binding failed");
    const signed = await cryptoCall(this.state.crypto, {
      op: "sign",
      payload: encode(req.signing_payload),
    });
    await api("devices/enrollment/complete", "POST", {
      device_id: this.state.device_id,
      signature: signed.result.signature,
    });
  }
  static async recover(
    user: string,
    secret: string,
    history: VaultState,
    password: string,
    label: string,
  ) {
    if (await loadVault(user))
      throw new Error(
        "Preserve this vault. Use a separate browser profile for recovery.",
      );
    if (secret.length < 20 || !history.recovery_seed)
      throw new Error("Recovery material or unlock secret unavailable");
    await sodium.ready;
    const oldSeed = raw(history.recovery_seed),
      oldKey = sodium.crypto_sign_seed_keypair(oldSeed),
      seed = sodium.randombytes_buf(32),
      recoveryKey = sodium.crypto_sign_seed_keypair(seed),
      id = crypto.randomUUID();
    try {
      const x = await cryptoCall("", { op: "init", identity: `${user}:${id}` });
      const device = {
        id,
        label,
        identity: x.result.identity,
        public_key: x.result.public_key,
      };
      const challenge = await api<{ id: string; nonce: string }>(
        "recovery/start",
        "POST",
        { user_id: user },
      );
      const signed = {
        domain: "haven/recovery/v1",
        user_id: user,
        challenge_id: challenge.id,
        nonce: challenge.nonce,
        password_hash: await digest(password),
        device,
        recovery_public_key: sodium.to_base64(
          recoveryKey.publicKey,
          sodium.base64_variants.ORIGINAL,
        ),
      };
      const proof = await cryptoCall(x.state, {
        op: "sign",
        payload: encode(canonical(signed)),
      });
      // Restored ratchets are NEVER resumed. Old history is explicitly local-only.
      const state: VaultState = {
        v: 1,
        profile: "haven-delivery-v2",
        device_id: id,
        device: {
          label,
          identity: x.result.identity,
          public_key: x.result.public_key,
        },
        crypto: x.state,
        revision: 1,
        recovery_seed: sodium.to_base64(seed, sodium.base64_variants.ORIGINAL),
        pins: { ...history.pins, [id]: x.result.public_key },
        heads: {},
        cursor: {},
        events: history.events
          .filter((e) => !e.file?.view_once)
          .map((e) => ({ ...e, state: "local_only" })),
        outbox: {},
        drafts: {},
      };
      await saveVault(user, secret, state, 0);
      await api("recovery/reset", "POST", {
        challenge_id: challenge.id,
        nonce: challenge.nonce,
        new_password: password,
        device,
        recovery_public_key: signed.recovery_public_key,
        signature: sodium.to_base64(
          sodium.crypto_sign_detached(canonical(signed), oldKey.privateKey),
          sodium.base64_variants.ORIGINAL,
        ),
        device_signature: proof.result.signature,
      });
      const instance = new Messenger(user, secret, state);
      await instance.package();
      return instance;
    } finally {
      sodium.memzero(oldSeed);
      sodium.memzero(oldKey.privateKey);
      sodium.memzero(seed);
      sodium.memzero(recoveryKey.privateKey);
    }
  }
  lock() {
    this.locked = true;
    this.secret = "";
    this.state.crypto = "";
    this.state.events = [];
    this.state.drafts = {};
    this.state.recovery_seed = undefined;
    this.state.uploads = undefined;
    this.state.cancelled_controls = undefined;
    this.state.outbox = {};
    lockCrypto();
    stopVaultWorker();
  }
  private serial<T>(fn: () => Promise<T>): Promise<T> {
    const task = this.chain.then(() => {
      if (this.locked) throw new Error("Vault locked");
      return fn();
    });
    this.chain = task.catch(() => {});
    return task;
  }
  private async persist(next: VaultState) {
    if (this.locked) throw new Error("Vault locked");
    const rev = this.state.revision;
    next.revision = rev + 1;
    await saveVault(this.user, this.secret, next, rev);
    if (this.locked)
      throw new Error(
        "Vault locked during persistence; unlock the durable state before continuing",
      );
    this.state = next;
  }
  private next() {
    if (this.locked) throw new Error("Vault locked");
    return structuredClone(this.state);
  }
  private noPendingCommit() {
    if (this.locked) throw new Error("Vault locked");
    if (Object.values(this.state.outbox).some((x) => x.candidate))
      throw new Error(
        "A membership transition is pending durable acceptance; retry synchronization first.",
      );
  }
  private pinned(
    d: Pick<Certificate, "id" | "public_key" | "identity" | "user_id">,
  ) {
    if (
      d.identity !== `${d.user_id}:${d.id}` ||
      this.state.pins[d.id] !== d.public_key
    )
      throw new Error(`Verify device fingerprint before accepting: ${d.id}`);
  }
  async markViewOnceOpened(id: string) {
    return this.serial(async () => {
      const n = this.next();
      n.view_once_opened ||= {};
      n.view_once_opened[id] = true;
      for (const event of n.events) {
        if (event.file?.id === id && event.file.view_once) {
          event.file.key = "";
          event.file.prefix = "";
          event.file.name = "";
          event.text = undefined;
        }
      }
      await this.persist(n);
    });
  }
  async prepareAttachment(
    file: File,
    cid: string,
    signal: AbortSignal,
    viewOnce = false,
  ) {
    return this.serial(async () => {
      const meta = await prepareUpload(file, cid, signal, viewOnce),
        n = this.next();
      n.uploads ||= {};
      n.uploads[meta.id] = meta;
      await this.persist(n);
      return meta;
    });
  }
  async resumeAttachment(
    id: string,
    progress: (n: number) => void,
    signal: AbortSignal,
  ) {
    const meta = this.state.uploads?.[id];
    if (!meta) throw new Error("Unknown pending upload");
    return resumeUpload(meta, progress, signal);
  }
  async finishAttachment(id: string) {
    return this.serial(async () => {
      const meta = this.state.uploads?.[id];
      if (meta) {
        const n = this.next();
        delete n.uploads![id];
        await this.persist(n);
        await discardUpload(meta);
      }
    });
  }
  async cancelAttachment(id: string) {
    await api(`attachments/${id}`, "DELETE").catch(() => {});
    await this.finishAttachment(id);
  }
  async pin(device: Device, fingerprint: string, name?: string) {
    return this.serial(async () => {
      if (
        fingerprint.replace(/\s/g, "").toLowerCase() !==
        (await fingerprintOf(device.public_key))
          .replace(/\s/g, "")
          .toLowerCase()
      )
        throw new Error("Fingerprint does not match");
      const n = this.next();
      n.pins[device.id] = device.public_key;
      if (name) {
        if (name.length > 80) throw new Error("Contact name is too long");
        n.contact_names ||= {};
        n.contact_names[device.id] = name;
      }
      await this.persist(n);
    });
  }
  async clearDeliveredHistory() {
    return this.serial(async () => {
      const n = this.next();
      n.events = n.events.filter(
        (e) =>
          !!n.outbox[e.id] ||
          (e.seq !== undefined && e.seq > (n.cursor[e.conversation_id] || 0)),
      );
      n.drafts = {};
      await this.persist(n);
    });
  }
  async markRead(cid: string) {
    return this.serial(async () => {
      const seq = this.state.cursor[cid] || 0;
      if (seq === (this.state.read_seq?.[cid] || 0)) return;
      const n = this.next();
      n.read_seq ||= {};
      n.read_seq[cid] = seq;
      await this.persist(n);
    });
  }
  async draft(cid: string, text: string) {
    return this.serial(async () => {
      const n = this.next();
      n.drafts[cid] = text;
      await this.persist(n);
    });
  }
  async package() {
    return this.serial(() => this.packageInternal());
  }
  private async packageInternal() {
    this.noPendingCommit();
    const x = await cryptoCall(this.state.crypto, { op: "package" }),
      n = this.next(),
      id = crypto.randomUUID();
    n.crypto = x.state;
    n.needs_package = false;
    n.outbox[id] = {
      path: "crypto/key-packages",
      body: { package: x.result.key_package },
    };
    await this.persist(n);
    await this.flushInternal();
  }
  async approve(device: Device) {
    return this.serial(async () => {
      this.pinned(device);
      const payload = `haven/enrollment/v1:${device.user_id}:${device.id}:${device.public_key}:${device.challenge}`;
      const x = await cryptoCall(this.state.crypto, {
        op: "sign",
        payload: encode(payload),
      });
      await api("devices/enrollment/approve", "POST", {
        device_id: device.id,
        signature: x.result.signature,
      });
    });
  }
  async provisionRecovery() {
    return this.serial(async () => {
      const status = await api<{ recovery_configured: boolean }>("auth/me");
      // An additional device must not invent a replacement for the account's existing recovery authority.
      if (status.recovery_configured && !this.state.recovery_seed) return false;
      await sodium.ready;
      const seed = this.state.recovery_seed
          ? raw(this.state.recovery_seed)
          : sodium.randombytes_buf(32),
        pair = sodium.crypto_sign_seed_keypair(seed),
        n = this.next();
      n.recovery_seed = sodium.to_base64(seed, sodium.base64_variants.ORIGINAL);
      await this.persist(n);
      try {
        await api("recovery/key", "POST", {
          public_key: sodium.to_base64(
            pair.publicKey,
            sodium.base64_variants.ORIGINAL,
          ),
        });
      } finally {
        sodium.memzero(seed);
        sodium.memzero(pair.privateKey);
      }
      return true;
    });
  }
  async importHistory(history: VaultState) {
    return this.serial(async () => {
      if (history.profile !== "haven-delivery-v2")
        throw new Error("Unsupported history profile");
      const n = this.next();
      for (const event of history.events) {
        if (event.file?.view_once) continue;
        const {
          state: _state,
          seq: _seq,
          transport_hash: _hash,
          ...data
        } = event;
        const valid = authenticatedEvent(data);
        if (!n.events.some((e) => e.id === valid.id))
          n.events.push({ ...valid, state: "local_only" });
      }
      // Deliberately copy no credentials, ratchets, cursors, pins or pending sends.
      await this.persist(n);
    });
  }
  async create(kind: "direct" | "group", contactDevice?: string) {
    return this.serial(async () => {
      this.noPendingCommit();
      const id = crypto.randomUUID(),
        group_id = crypto.randomUUID();
      const x = await cryptoCall(this.state.crypto, { op: "create", group_id });
      const members = [
        certificate(
          {
            id: this.state.device_id,
            user_id: this.user,
            ...this.state.device,
          } as Device,
          "owner",
        ),
      ];
      const header = {
        domain: "haven/genesis/v1",
        id,
        kind,
        group_id,
        members,
      };
      const signed = await cryptoCall(x.state, {
        op: "sign",
        payload: encode(canonical(header)),
      });
      const n = this.next();
      n.crypto = x.state;
      n.cursor[id] = 0;
      n.rekey_at ||= {};
      n.rekey_at[id] = Date.now();
      n.heads[id] = {
        seq: 0,
        hash: await digest(
          canonical({ header, signature: signed.result.signature }),
        ),
        epoch: 0,
        group_id,
        members,
      };
      n.heads[id].genesis_hash = n.heads[id].hash;
      n.heads[id].kind = kind;
      if (contactDevice) {
        n.connection_intents ||= {};
        n.connection_intents[contactDevice] = id;
      }
      n.outbox[id] = {
        path: "conversations",
        body: {
          id,
          group_id,
          kind,
          header,
          signature: signed.result.signature,
        },
      };
      await this.persist(n);
      await this.flushInternal();
      return id;
    });
  }
  startDirect(device: Device): Promise<Conversation> {
    const pending = this.directStarts.get(device.id);
    if (pending) return pending;
    const task = this.startDirectInternal(device).finally(() =>
      this.directStarts.delete(device.id),
    );
    this.directStarts.set(device.id, task);
    return task;
  }
  private async startDirectInternal(device: Device) {
    this.pinned(device);
    if (device.user_id === this.user)
      throw new Error("This is one of your own browsers");
    await this.flush();
    let id = this.state.connection_intents?.[device.id];
    if (!id) {
      id = Object.entries(this.state.heads).find(
        ([, h]) =>
          h.kind === "direct" && h.members.some((m) => m.id === device.id),
      )?.[0];
    }
    if (!id) id = await this.create("direct", device.id);
    let conversation = await api<Conversation>(`conversations/${id}`);
    await this.sync(conversation);
    if (!this.state.heads[id].members.some((m) => m.id === device.id)) {
      if (this.state.heads[id].seq > 0)
        throw new Error(
          "This conversation's membership changed. Review it before reconnecting.",
        );
      await this.changeMember(conversation, device, "add");
      conversation = await api<Conversation>(`conversations/${id}`);
    }
    return conversation;
  }
  private async header(
    c: Conversation,
    id: string,
    ciphertext: string,
    transition: Transition | null,
  ): Promise<{ header: DeliveryHeader; signature: string }> {
    const h = this.state.heads[c.id];
    if (!h) throw new Error("Synchronize and verify conversation first");
    const header: DeliveryHeader = {
      domain: "haven/envelope/v1",
      v: 1,
      conversation_id: c.id,
      group_id: c.group_id,
      sender_device: this.state.device_id,
      client_message_id: id,
      epoch: h.epoch,
      seq: h.seq + 1,
      previous_hash: h.hash,
      ciphertext_hash: await hash(ciphertext),
      transition,
    };
    const x = await cryptoCall(this.state.crypto, {
      op: "sign",
      payload: encode(canonical(header)),
    });
    return { header, signature: x.result.signature! };
  }
  async send(
    c: Conversation,
    event: Omit<
      LocalEvent,
      "id" | "conversation_id" | "sender" | "time" | "state"
    >,
  ) {
    return this.serial(async () => {
      this.noPendingCommit();
      const h = this.state.heads[c.id];
      if (!h) throw new Error("Synchronize before sending");
      if (
        h.seq - (h.epoch_start_seq || 0) >= 1000 ||
        Date.now() - (this.state.rekey_at?.[c.id] || 0) > 7 * 24 * 3600 * 1000
      )
        throw new Error(
          "Cryptographic epoch renewal required. Ask the owner or moderator to refresh the epoch.",
        );
      if (Object.keys(this.state.outbox).length >= 100)
        throw new Error(
          "Pending message limit reached. Reconnect and synchronize before sending more.",
        );
      if (this.state.events.length >= 20000)
        throw new Error(
          "Local history limit reached; export history before continuing",
        );
      const id = crypto.randomUUID(),
        item: LocalEvent = {
          ...event,
          id,
          conversation_id: c.id,
          sender: this.state.device_id,
          time: new Date().toISOString(),
          state: "queued",
        };
      authenticatedEvent(
        JSON.parse(
          JSON.stringify({
            ...item,
            state: undefined,
            transport_hash: undefined,
          }),
        ),
      );
      const x = await cryptoCall(this.state.crypto, {
        op: "encrypt",
        group_id: c.group_id,
        plaintext: JSON.stringify({
          ...item,
          state: undefined,
          transport_hash: undefined,
        }),
      });
      if (x.result.epoch !== h.epoch)
        throw new Error("Epoch conflict: synchronize");
      const signed = await this.header(c, id, x.result.ciphertext!, null),
        n = this.next();
      n.crypto = x.state;
      item.transport_hash = signed.header.ciphertext_hash;
      // The outgoing encrypted envelope already contains the authenticated key.
      // Keep no reopenable sender copy in displayed local history.
      if (item.file?.view_once) {
        item.file = { ...item.file, key: "", prefix: "", name: "" };
        item.text = undefined;
      }
      n.events.push(item);
      // Reactions, edits, receipts and file transfers must not erase an
      // unrelated text draft. Only sending that draft consumes it.
      if (event.type === "text") delete n.drafts[c.id];
      n.outbox[id] = {
        path: `conversations/${c.id}/messages`,
        body: {
          v: 1,
          client_message_id: id,
          epoch: h.epoch,
          ciphertext: x.result.ciphertext,
          ...signed,
        },
      };
      await this.persist(n);
      // Network failure keeps exactly one durable encrypted send. The UI can clear its draft safely.
      await this.flushInternal().catch(() => {});
    });
  }
  async changeMember(
    c: Conversation,
    device: Device,
    action: "add" | "remove" | "transfer" | "role" | "update",
    role?: "moderator" | "member",
  ) {
    return this.serial(async () => {
      this.noPendingCommit();
      await this.flushInternal();
      await this.syncInternal(c);
      this.pinned(device);
      const head = this.state.heads[c.id];
      if (!head) throw new Error("Verified head required");
      let key_package_id: string | undefined,
        command: Record<string, unknown> = {
          op: action === "add" || action === "remove" ? action : "update",
          group_id: c.group_id,
        };
      let members = structuredClone(head.members);
      if (action === "add") {
        if (
          members.length >= 100 ||
          new Set([...members.map((m) => m.user_id), device.user_id]).size >
            (c.kind === "direct" ? 2 : 50)
        )
          throw new Error("Conversation member limit");
        const kp = await api<{ id: string; package: string; device: Device }>(
          `crypto/key-packages/${device.id}`,
          "POST",
          {},
        );
        if (kp.device.public_key !== device.public_key)
          throw new Error("Identity changed");
        key_package_id = kp.id;
        command.key_package = kp.package;
        members.push(certificate(device));
      } else if (action === "remove") {
        const current = await cryptoCall(this.state.crypto, {
            op: "inspect",
            group_id: c.group_id,
          }),
          member = current.result.members?.find(
            (m) =>
              m.identity === device.identity &&
              m.public_key === device.public_key,
          );
        if (!member) throw new Error("Member mismatch");
        command.index = member.index;
        members = members.filter((x) => x.id !== device.id);
      } else if (action === "transfer" || action === "role")
        for (const m of members) {
          if (action === "transfer" && m.id === this.state.device_id)
            m.role = "moderator";
          if (m.id === device.id)
            m.role = action === "transfer" ? "owner" : role || "member";
        }
      const sender = head.members.find((m) => m.id === this.state.device_id);
      if (!sender) throw new Error("Current approved membership required");
      this.validateTransition(
        head,
        {
          action,
          device_id: action === "update" ? null : device.id,
          next_epoch: head.epoch + 1,
          members: sorted(members),
          welcome_hash: "",
          state_hash: "",
        },
        sender,
        c.kind,
      );
      const x = await cryptoCall(this.state.crypto, command);
      if (x.result.epoch !== head.epoch + 1) throw new Error("Epoch mismatch");
      this.verifyMLS(x.result, members);
      const transition: Transition = {
        action,
        device_id: action === "update" ? null : device.id,
        next_epoch: head.epoch + 1,
        members: sorted(members),
        welcome_hash: await hash(x.result.welcome || ""),
        state_hash: x.result.state_hash!,
      };
      const id = crypto.randomUUID(),
        signed = await this.header(c, id, x.result.commit!, transition),
        n = this.next();
      // Candidate includes next MLS epoch, but active state stays at the accepted epoch until an authenticated ACK.
      n.outbox[id] = {
        path: `conversations/${c.id}/crypto-events`,
        candidate: x.state,
        base_hash: await digest(this.state.crypto),
        body: {
          v: 1,
          client_message_id: id,
          epoch: head.epoch,
          ciphertext: x.result.commit,
          action,
          ...(action !== "update" ? { device_id: device.id } : {}),
          ...(role ? { role } : {}),
          ...(key_package_id ? { key_package_id } : {}),
          ...(x.result.welcome ? { welcome: x.result.welcome } : {}),
          ...signed,
        },
      };
      await this.persist(n);
      await this.flushInternal();
    });
  }
  async leave(c: Conversation) {
    return this.serial(async () => {
      await this.flushInternal();
      await this.syncInternal(c);
      const head = this.state.heads[c.id],
        payload = `haven/leave/v1:${c.id}:${this.state.device_id}:${head.epoch}`;
      const signed = await cryptoCall(this.state.crypto, {
        op: "sign",
        payload: encode(payload),
      });
      await api(`conversations/${c.id}/members/propose`, "POST", {
        action: "leave",
        signature: signed.result.signature,
      });
    });
  }
  async cancelPendingControl(c: Conversation) {
    return this.serial(async () => {
      const n = this.next();
      n.cancelled_controls ||= {};
      if (Object.keys(n.cancelled_controls).length >= 10)
        throw new Error(
          "Too many unresolved membership requests. Recover through a verified fresh group.",
        );
      for (const [id, p] of Object.entries(n.outbox))
        if (
          p.candidate &&
          (p.body.header as DeliveryHeader).conversation_id === c.id
        ) {
          n.cancelled_controls[id] = {
            conversation_id: c.id,
            base_hash: p.base_hash!,
            candidate: p.candidate,
            ciphertext_hash: (p.body.header as DeliveryHeader).ciphertext_hash,
          };
          delete n.outbox[id];
        }
      await this.persist(n);
      await this.syncInternal(c);
    });
  }
  private verifyMLS(result: CryptoResult, members: Certificate[]) {
    const actual = (result.members || [])
      .map((m) => ({ identity: m.identity, public_key: m.public_key }))
      .sort((a, b) => a.identity.localeCompare(b.identity));
    const expected = members
      .map((m) => ({ identity: m.identity, public_key: m.public_key }))
      .sort((a, b) => a.identity.localeCompare(b.identity));
    for (const m of members) this.pinned(m);
    if (result.active !== false && !same(actual, expected))
      throw new Error("MLS membership differs from authenticated policy");
  }
  private validateTransition(
    h: Head,
    t: Transition,
    sender: Certificate,
    kind: string,
  ) {
    if (
      !["owner", "moderator"].includes(sender.role) ||
      t.next_epoch !== h.epoch + 1
    )
      throw new Error("Unauthorized epoch transition");
    const members = structuredClone(h.members),
      target = members.find((x) => x.id === t.device_id);
    if (t.action === "add") {
      const added = t.members.find((x) => x.id === t.device_id);
      if (target || !added || added.role !== "member")
        throw new Error("Invalid Add");
      members.push(added);
    } else if (t.action === "remove") {
      if (
        !target ||
        target.role === "owner" ||
        target.id === sender.id ||
        (sender.role === "moderator" && target.role !== "member")
      )
        throw new Error("Unauthorized Remove");
      members.splice(members.indexOf(target), 1);
    } else if (t.action === "transfer" || t.action === "role") {
      if (sender.role !== "owner" || !target || target.id === sender.id)
        throw new Error("Unauthorized authority change");
      const changed = t.members.find((x) => x.id === target.id);
      if (!changed) throw new Error("Missing authority target");
      if (t.action === "transfer") {
        members.find((x) => x.id === sender.id)!.role = "moderator";
        target.role = "owner";
      } else {
        if (!["member", "moderator"].includes(changed.role))
          throw new Error("Invalid role");
        target.role = changed.role;
      }
    } else if (t.action !== "update") throw new Error("Unknown transition");
    if (
      t.members.length > 100 ||
      new Set(t.members.map((m) => m.user_id)).size >
        (kind === "direct" ? 2 : 50)
    )
      throw new Error("Conversation member limit");
    if (!same(sorted(members), t.members))
      throw new Error("Unexpected roster change");
    for (const m of members) this.pinned(m);
    return members;
  }
  async flush() {
    return this.serial(() => this.flushInternal());
  }
  private async flushInternal() {
    for (const id of Object.keys(this.state.outbox)) {
      let pending = this.state.outbox[id];
      if (!pending) continue;
      try {
        let ack: { seq?: number; envelope?: Envelope };
        try {
          ack = await api(pending.path, "POST", pending.body);
        } catch (e) {
          if (!(e instanceof Error) || !e.message.includes("HEAD_CONFLICT"))
            throw e;
          const cid = (pending.body.header as DeliveryHeader).conversation_id;
          const c = await api<Conversation>(`conversations/${cid}`);
          if (pending.candidate) {
            const n = this.next();
            delete n.outbox[id];
            await this.persist(n);
            await this.syncInternal(c);
            throw new Error(
              "Membership changed before commit acceptance. Review the updated roster and retry.",
            );
          }
          await this.syncInternal(c);
          const h = this.state.heads[cid];
          if (h.epoch !== pending.body.epoch) {
            const n = this.next();
            const item = n.events.find((x) => x.id === id);
            if (item) item.state = "failed";
            delete n.outbox[id];
            await this.persist(n);
            throw new Error(
              "Queued message crossed a membership change. Review recipients and explicitly resend.",
            );
          }
          const signed = await this.header(
              c,
              id,
              String(pending.body.ciphertext),
              null,
            ),
            n = this.next();
          n.outbox[id].body = { ...pending.body, ...signed };
          await this.persist(n);
          pending = this.state.outbox[id];
          ack = await api(pending.path, "POST", pending.body);
        }
        if (
          (pending.body.header && String(pending.path).includes("/messages")) ||
          pending.candidate
        ) {
          if (
            !ack.envelope ||
            ack.envelope.header.ciphertext_hash !==
              (await hash(String(pending.body.ciphertext))) ||
            ack.envelope.client_message_id !== id ||
            ack.envelope.sender_device !== this.state.device_id ||
            ack.envelope.header.conversation_id !==
              (pending.body.header as DeliveryHeader).conversation_id ||
            !same(
              ack.envelope.header.transition,
              (pending.body.header as DeliveryHeader).transition,
            )
          )
            throw new Error("Invalid acceptance proof");
          await signatureValid(
            this.state.device.public_key,
            ack.envelope.signature,
            ack.envelope.header,
          );
        }
        const n = this.next();
        if (pending.candidate) {
          if ((await digest(n.crypto)) !== pending.base_hash)
            throw new Error(
              "Prepared MLS state conflicts with the live vault; stop and reconcile",
            );
          n.crypto = pending.candidate;
        }
        delete n.outbox[id];
        const item = n.events.find((x) => x.id === id);
        if (item) {
          item.state = "server_accepted";
          item.seq = ack.seq;
        }
        await this.persist(n);
        if (ack.envelope) {
          const h = ack.envelope.header;
          await this.syncInternal({
            id: h.conversation_id,
            group_id: h.group_id,
            last_seq: ack.seq!,
            epoch: h.epoch,
            status: "active",
            kind: "group",
            head_hash: ack.envelope.chain_hash,
          });
        }
      } catch (e) {
        throw new Error(
          `Pending delivery: ${e instanceof Error ? e.message : "connection unavailable"}`,
        );
      }
    }
  }
  async sync(c: Conversation, _devices: Device[] = []) {
    return this.serial(() => this.syncInternal(c));
  }
  private async syncInternal(c: Conversation) {
    this.noPendingCommit();
    const detail = await api<Detail>(`conversations/${c.id}`),
      g = detail.genesis;
    if (
      g.domain !== "haven/genesis/v1" ||
      g.id !== c.id ||
      g.group_id !== c.group_id ||
      g.kind !== detail.kind ||
      !["direct", "group"].includes(g.kind) ||
      g.members.length !== 1 ||
      g.members[0].role !== "owner"
    )
      throw new Error("Invalid signed genesis");
    this.pinned(g.members[0]);
    await signatureValid(g.members[0].public_key, detail.genesis_signature, g);
    let head: Head = {
      seq: 0,
      hash: await digest(
        canonical({ header: g, signature: detail.genesis_signature }),
      ),
      epoch: 0,
      group_id: g.group_id,
      members: g.members,
      kind: g.kind as "direct" | "group",
    };
    head.genesis_hash = head.hash;
    const saved = this.state.heads[c.id],
      cursor = this.state.cursor[c.id] || 0,
      proofs = new Map<number, { envelope: Envelope; head: Head }>();
    if (saved && saved.seq === 0 && saved.hash !== head.hash)
      throw new Error("Genesis rollback or fork detected");
    let observedSaved = !saved || saved.seq === 0;
    if (saved && (saved.seq !== cursor || saved.seq > detail.last_seq))
      throw new Error("Server rollback or inconsistent retained cursor");
    if (saved?.genesis_hash) {
      if (
        saved.genesis_hash !== head.hash ||
        saved.kind !== g.kind ||
        saved.group_id !== g.group_id
      )
        throw new Error("Signed genesis contradicts retained history");
      head = structuredClone(saved);
      observedSaved = true;
    }
    // Older v2 checkpoints acquire these public metadata fields only after full history verification.
    while (head.seq < detail.last_seq) {
      const page = await api<{ proofs: Envelope[] }>(
        `conversations/${c.id}/proofs?after_seq=${head.seq}`,
      );
      if (!page.proofs.length) throw new Error("Truncated proof history");
      const before = head.seq;
      for (const e of page.proofs) {
        if (e.seq > detail.last_seq) break;
        const h = e.header,
          sender = head.members.find((x) => x.id === h.sender_device);
        if (
          !sender ||
          h.domain !== "haven/envelope/v1" ||
          h.v !== 1 ||
          h.conversation_id !== c.id ||
          h.group_id !== g.group_id ||
          h.seq !== head.seq + 1 ||
          h.previous_hash !== head.hash ||
          h.epoch !== head.epoch ||
          e.seq !== h.seq ||
          e.client_message_id !== h.client_message_id ||
          e.sender_device !== h.sender_device ||
          e.epoch !== h.epoch
        )
          throw new Error("Delivery history gap or fork");
        this.pinned(sender);
        await signatureValid(sender.public_key, e.signature, h);
        const chain = await digest(
          canonical({ header: h, signature: e.signature }),
        );
        if (chain !== e.chain_hash) throw new Error("Delivery hash mismatch");
        let members = head.members,
          epoch = head.epoch;
        if (h.transition) {
          members = this.validateTransition(head, h.transition, sender, g.kind);
          epoch++;
          if (e.kind !== "commit") throw new Error("Commit type mismatch");
        } else if (e.kind !== "application")
          throw new Error("Application type mismatch");
        head = {
          ...head,
          seq: h.seq,
          hash: chain,
          epoch,
          members,
          epoch_start_seq: h.transition ? h.seq : head.epoch_start_seq,
        };
        if (saved?.seq === head.seq) {
          if (saved.hash !== head.hash)
            throw new Error("Server rollback or fork detected");
          observedSaved = true;
        }
        if (e.seq > cursor)
          proofs.set(e.seq, { envelope: e, head: structuredClone(head) });
      }
      if (head.seq === before) throw new Error("Truncated proof history");
    }
    if (
      !observedSaved ||
      head.hash !== detail.head_hash ||
      head.epoch !== detail.epoch
    )
      throw new Error("Server rollback detected; synchronization paused");
    if (
      (!saved && detail.last_seq === 0) ||
      (saved && !saved.genesis_hash && cursor === detail.last_seq)
    ) {
      const n = this.next();
      n.heads[c.id] = head;
      await this.persist(n);
    }
    let after = cursor;
    while (after < detail.last_seq) {
      const page = await api<{ messages: Envelope[] }>(
        `conversations/${c.id}/messages?after_seq=${after}`,
      );
      if (!page.messages.length) throw new Error("Missing encrypted history");
      const before = after;
      for (const e of page.messages) {
        if (e.seq > detail.last_seq) break;
        const proof = proofs.get(e.seq);
        if (
          !proof ||
          !same(proof.envelope.header, e.header) ||
          proof.envelope.signature !== e.signature ||
          (await hash(e.ciphertext)) !== e.header.ciphertext_hash
        )
          throw new Error("Envelope does not match signed history");
        if (e.seq !== after + 1 && !(after === 0 && e.welcome))
          throw new Error("Ciphertext sequence gap");
        const n = this.next(),
          own = e.sender_device === n.device_id,
          t = e.header.transition;
        if (own) {
          if (
            e.kind === "application" &&
            !n.events.some(
              (x) =>
                x.id === e.client_message_id &&
                x.transport_hash === e.header.ciphertext_hash,
            )
          )
            throw new Error(
              "Unexpected own-device message: restored or cloned state. Recover into a fresh device.",
            );
          if (!t) {
            const ownEvent = n.events.find(
              (x) => x.id === e.client_message_id,
            )!;
            ownEvent.state = "server_accepted";
            ownEvent.seq = e.seq;
            delete n.outbox[e.client_message_id];
          }
          if (t) {
            const cancelled = n.cancelled_controls?.[e.client_message_id];
            if (cancelled) {
              if (
                cancelled.ciphertext_hash !== e.header.ciphertext_hash ||
                (await digest(n.crypto)) !== cancelled.base_hash
              )
                throw new Error(
                  "A cancelled transition was accepted after local state changed. Stop and recover through a verified fresh device.",
                );
              n.crypto = cancelled.candidate;
              delete n.cancelled_controls![e.client_message_id];
            }
            const x = await cryptoCall(n.crypto, {
              op: "inspect",
              group_id: g.group_id,
            });
            if (x.result.state_hash !== t.state_hash)
              throw new Error("Unaccepted own commit");
            this.verifyMLS(x.result, proof.head.members);
          }
        } else {
          if (e.welcome && (!t || (await hash(e.welcome)) !== t.welcome_hash))
            throw new Error("Welcome mismatch");
          const x = await cryptoCall(
            n.crypto,
            e.welcome
              ? { op: "join", group_id: g.group_id, welcome: e.welcome }
              : {
                  op: "process",
                  group_id: g.group_id,
                  ciphertext: e.ciphertext,
                },
          );
          if (
            x.result.sender &&
            x.result.sender !==
              `${e.header.transition?.members.find((m) => m.id === e.sender_device)?.user_id || proof.head.members.find((m) => m.id === e.sender_device)?.user_id}:${e.sender_device}`
          )
            throw new Error("MLS sender binding");
          this.verifyMLS(x.result, proof.head.members);
          if (
            (t &&
              ((x.result.kind !== "commit" && !e.welcome) ||
                x.result.state_hash !== t.state_hash)) ||
            x.result.epoch !== proof.head.epoch
          )
            throw new Error("MLS epoch or type mismatch");
          if (!t && x.result.kind !== "application")
            throw new Error("Hidden membership commit rejected");
          n.crypto = x.state;
          if (e.welcome) n.needs_package = true;
          if (x.result.plaintext) {
            const event = authenticatedEvent(JSON.parse(x.result.plaintext));
            if (
              event.id !== e.client_message_id ||
              event.sender !== e.sender_device ||
              event.conversation_id !== c.id ||
              ![
                "text",
                "edit",
                "delete",
                "reaction",
                "file",
                "title",
                "receipt",
              ].includes(event.type)
            )
              throw new Error("Invalid authenticated event");
            if (!n.events.some((x) => x.id === event.id))
              n.events.push({
                ...event,
                transport_hash: e.header.ciphertext_hash,
                seq: e.seq,
                state: "recipient_synced",
              });
          }
        }
        if (t) {
          n.rekey_at ||= {};
          n.rekey_at[c.id] = Date.now();
        }
        for (const [id, old] of Object.entries(n.cancelled_controls || {}))
          if (old.conversation_id === c.id && t)
            delete n.cancelled_controls![id];
        n.cursor[c.id] = e.seq;
        n.heads[c.id] = proof.head;
        await this.persist(n);
        after = e.seq;
      }
      if (after === before) throw new Error("Missing encrypted history");
    }
    await api(`conversations/${c.id}/acks`, "POST", { seq: after });
    if (this.state.needs_package) await this.packageInternal();
    const receipts = await api<{ cursors: { last_acked_seq: number }[] }>(
      `conversations/${c.id}/acks`,
    );
    const upto = Math.max(0, ...receipts.cursors.map((x) => x.last_acked_seq));
    if (
      this.state.events.some(
        (e) =>
          e.conversation_id === c.id &&
          e.sender === this.state.device_id &&
          e.seq &&
          e.seq <= upto &&
          e.state !== "recipient_synced",
      )
    ) {
      const n = this.next();
      for (const e of n.events)
        if (
          e.conversation_id === c.id &&
          e.sender === n.device_id &&
          e.seq &&
          e.seq <= upto
        )
          e.state = "recipient_synced";
      await this.persist(n);
    }
  }
}
export async function fingerprintOf(publicKey: string) {
  return (await hash(publicKey)).match(/.{1,4}/g)!.join(" ");
}
