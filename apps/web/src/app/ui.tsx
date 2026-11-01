"use client";
import {
  useCallback,
  useEffect,
  useRef,
  useMemo,
  useState,
  type FormEvent,
} from "react";
import QRCode from "qrcode";
import { Icon, HavenEmblem, type IconName } from "./icons";
import { ViewOnceMedia } from "./view-once";
import { ChatThread, type MessageAction } from "./chat-thread";
import { ChatComposer } from "./chat-composer";
import { MediaPreview, canPreview } from "./media-preview";
import {
  conversationMessages,
  messagePreview,
  type Message,
} from "@/lib/chat-presentation";
import { uiError } from "@/lib/ui-error";
import { AccountRecovery } from "./recovery";
import { ServerPrivacy } from "./privacy";
import { ConnectFlow, ConversationVerification } from "./connect";
import { DeviceUnlockSettings } from "./device-unlock-settings";
import { readContactLink, type ContactCard } from "@/lib/contact-link";
import { connectionLoop } from "@/lib/connection";
import {
  api,
  RequestError,
  type User,
  type Device,
  type Conversation,
} from "@/lib/api";
import { Messenger, fingerprintOf } from "@/lib/messenger";
import {
  loadVault,
  recoveryKit,
  historyForExport,
  unseal,
  type LocalEvent,
  type VaultState,
  type Sealed,
} from "@/lib/vault";
import { downloadDecrypt, discardDownload } from "@/lib/media";
import { translate, type Language } from "@/lib/i18n";
type Screen =
  | "connect"
  | "messages"
  | "trust"
  | "devices"
  | "backup"
  | "settings"
  | "admin"
  | "help";
type Invite = {
  id: string;
  intended_username: string;
  expires_at: string;
  consumed_at: string | null;
  revoked_at: string | null;
};
const nav: [Screen, IconName, string][] = [
  ["messages", "messages", "Messages"],
  ["trust", "people", "People & trust"],
  ["devices", "devices", "Devices"],
  ["backup", "key", "Recovery kit"],
  ["settings", "settings", "Settings"],
  ["help", "help", "Connection & help"],
];
function download(value: Blob | string, name: string) {
  const url = URL.createObjectURL(
    typeof value === "string"
      ? new Blob([value], { type: "application/json" })
      : value,
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
function QR({ value, t }: { value: string; t: (text: string) => string }) {
  const [url, setURL] = useState("");
  useEffect(() => {
    QRCode.toDataURL(value, { width: 200, margin: 2 })
      .then(setURL)
      .catch(() => {});
  }, [value]);
  return url ? (
    <img
      className="qr"
      src={url}
      width="200"
      height="200"
      alt={t("Verification QR code")}
    />
  ) : null;
}
function AudioAttachment({
  meta,
  t,
}: {
  meta: NonNullable<LocalEvent["file"]>;
  t: (text: string) => string;
}) {
  const [url, setURL] = useState(""),
    [error, setError] = useState("");
  const isVoiceNote = meta.name.startsWith("voice-note.");
  const controller = useRef<AbortController | null>(null),
    audioURL = useRef(""),
    audio = useRef<HTMLAudioElement | null>(null);
  useEffect(() => {
    const cleanup = () => {
      controller.current?.abort();
      if (audio.current) {
        audio.current.pause();
        audio.current.removeAttribute("src");
        audio.current.load();
      }
      if (audioURL.current) URL.revokeObjectURL(audioURL.current);
      audioURL.current = "";
    };
    window.addEventListener("haven:lock", cleanup);
    return () => {
      window.removeEventListener("haven:lock", cleanup);
      cleanup();
    };
  }, []);
  return (
    <div>
      {url ? (
        <audio
          ref={audio}
          controls
          src={url}
          preload="none"
          aria-label={t(isVoiceNote ? "Voice note" : "Audio")}
        />
      ) : (
        <button
          onClick={() => {
            controller.current?.abort();
            const pending = new AbortController();
            controller.current = pending;
            void downloadDecrypt(meta, { signal: pending.signal })
              .then((blob) => {
                if (!pending.signal.aborted) {
                  if (audioURL.current) URL.revokeObjectURL(audioURL.current);
                  audioURL.current = URL.createObjectURL(blob);
                  setURL(audioURL.current);
                }
              })
              .catch(() => {
                if (!pending.signal.aborted)
                  setError("Voice note unavailable or integrity check failed");
              });
          }}
        >
          {t(
            isVoiceNote
              ? "Decrypt and play voice note"
              : "Decrypt and play audio",
          )}
        </button>
      )}
      {error && <span role="alert">{t(error)}</span>}
    </div>
  );
}
export default function Haven() {
  const [language, setLanguage] = useState<Language>("en"),
    [theme, setTheme] = useState("light");
  const t = (s: string) => translate(language, s);
  const [user, setUser] = useState<User | null>(null),
    [screen, setScreen] = useState<Screen>("messages");
  const [health, setHealth] = useState<{
      crypto_ready: boolean;
      name: string;
      maintenance: string;
    } | null>(null),
    [online, setOnline] = useState(false);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [register, setRegister] = useState(false),
    [inviteToken, setInviteToken] = useState("");
  const [vault, setVault] = useState<Messenger | null>(null),
    vaultRef = useRef<Messenger | null>(null),
    vaultGeneration = useRef(0);
  const [unlock, setUnlock] = useState(""),
    [deviceLabel, setDeviceLabel] = useState(""),
    [conversations, setConversations] = useState<Conversation[]>([]),
    [current, setCurrent] = useState<Conversation | null>(null);
  const [pendingContact, setPendingContact] = useState<ContactCard | null>(
    null,
  );
  const [devices, setDevices] = useState<Device[]>([]),
    [members, setMembers] = useState<Device[]>([]),
    [events, setEvents] = useState<LocalEvent[]>([]),
    [query, setQuery] = useState(""),
    [draft, setDraft] = useState(""),
    [reply, setReply] = useState<string | undefined>();
  const [invitations, setInvitations] = useState<Invite[]>([]),
    [users, setUsers] = useState<User[]>([]),
    [system, setSystem] = useState<Record<string, unknown>>({}),
    [newToken, setNewToken] = useState(""),
    [recovery, setRecovery] = useState(""),
    [resetPassword, setResetPassword] = useState("");
  const [progress, setProgress] = useState(""),
    [recording, setRecording] = useState(false),
    recorder = useRef<MediaRecorder | null>(null),
    upload = useRef<AbortController | null>(null);
  const [fingerprints, setFingerprints] = useState<Record<string, string>>({});
  const [targetDevice, setTargetDevice] = useState(""),
    [comparison, setComparison] = useState(""),
    [kind, setKind] = useState<"direct" | "group">("direct");
  const [notifications, setNotifications] = useState(false),
    [receipts, setReceipts] = useState(false),
    [typing, setTyping] = useState(false),
    [presence, setPresence] = useState(false),
    [peerPresence, setPeerPresence] = useState(0),
    [peerTyping, setPeerTyping] = useState(0),
    [groupOpen, setGroupOpen] = useState(false);
  const [threadAtBottom, setThreadAtBottom] = useState(true);
  const [chatSearch, setChatSearch] = useState(false);
  const [listFilter, setListFilter] = useState<"all" | "unread">("all");
  const currentId = useRef(current?.id);
  currentId.current = current?.id;
  const pendingApproval =
    !!vault &&
    devices.some(
      (d) =>
        d.id === vault.state.device_id &&
        (d.trust_state !== "approved" || !!d.revoked_at),
    );
  const appName = health?.name || "HAVEN";
  const perform = async (fn: () => Promise<void>) => {
    const generation = vaultGeneration.current;
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      if (generation === vaultGeneration.current)
        setError(
          e instanceof Error &&
            (e.message.startsWith("Verify device fingerprint") ||
              e.message.startsWith("Verify fingerprint"))
            ? "A conversation needs security-code verification. Open it to continue."
            : uiError(e),
        );
    } finally {
      setBusy(false);
    }
  };
  const lock = useCallback(() => {
    vaultGeneration.current++;
    window.dispatchEvent(new Event("haven:lock"));
    upload.current?.abort();
    if (recorder.current) {
      recorder.current.onstop = null;
      recorder.current.stream.getTracks().forEach((track) => track.stop());
      if (recorder.current.state !== "inactive") recorder.current.stop();
      recorder.current = null;
      setRecording(false);
    }
    vaultRef.current?.lock();
    vaultRef.current = null;
    setVault(null);
    setEvents([]);
    setUnlock("");
    setDraft("");
    setRecovery("");
    setResetPassword("");
    setQuery("");
    setReply(undefined);
    setCurrent(null);
    setConversations([]);
    setDevices([]);
    setMembers([]);
    setComparison("");
    setTargetDevice("");
    setFingerprints({});
    setNewToken("");
    setInvitations([]);
    setUsers([]);
    setSystem({});
    setProgress("");
    setPeerPresence(0);
    setPeerTyping(0);
  }, []);
  async function logout(all = false) {
    // Local key protection never waits for an unavailable or expired remote session.
    lock();
    setUser(null);
    setPendingContact(null);
    localStorage.removeItem("haven-local-user");
    try {
      await api(all ? "auth/logout-all" : "auth/logout", "POST", {});
    } catch {
      setNotice(
        "Vault locked locally. Server session revocation is unconfirmed; sign in again when connected to revoke sessions.",
      );
    }
  }
  useEffect(() => {
    const lang = localStorage.getItem("haven-language");
    if (lang === "fa") setLanguage(lang);
    let privacy: Record<string, unknown> = {};
    try {
      const saved = JSON.parse(localStorage.getItem("haven-privacy") || "{}");
      if (saved && typeof saved === "object" && !Array.isArray(saved))
        privacy = saved;
    } catch {}
    setNotifications(privacy.notifications === true);
    setReceipts(privacy.receipts === true);
    setTyping(privacy.typing === true);
    setPresence(privacy.presence === true);
    const color = localStorage.getItem("haven-theme");
    if (color === "light" || color === "dark") setTheme(color);
    const fragment = new URLSearchParams(location.hash.slice(1));
    const token = fragment.get("invite");
    if (fragment.has("connect")) {
      try {
        setPendingContact(readContactLink(location.href, location.origin));
        setScreen("connect");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Invalid friend link");
      }
    }
    if (
      token &&
      fragment.getAll("invite").length === 1 &&
      /^[A-Za-z0-9_-]{40,100}$/.test(token)
    ) {
      setInviteToken(token);
      setRegister(true);
    }
    if (fragment.has("invite") || fragment.has("connect")) {
      history.replaceState(null, "", location.pathname);
    }
    api<typeof health>("health")
      .then((x) => {
        setHealth(x);
        setOnline(true);
      })
      .catch(() => setOnline(false));
    api<{ user: User }>("auth/me")
      .then((x) => {
        setUser(x.user);
        localStorage.setItem("haven-local-user", JSON.stringify(x.user));
      })
      .catch((e) => {
        if (!(e instanceof RequestError) || e.status >= 500) {
          const cached = localStorage.getItem("haven-local-user");
          if (cached) {
            setUser(JSON.parse(cached));
            setHealth({
              crypto_ready: true,
              name: "HAVEN",
              maintenance: "Offline: only cached device data is available",
            });
          }
        }
      });
    const off = () => setOnline(false),
      on = () => {
        void api<NonNullable<typeof health>>("health")
          .then((x) => {
            setHealth(x);
            setOnline(true);
          })
          .catch(() => setOnline(false));
      };
    window.addEventListener("offline", off);
    window.addEventListener("online", on);
    // A dormant tab locks rather than leaving keys available indefinitely.
    let last = Date.now(),
      lastMonotonic = performance.now();
    const idleExpired = () =>
      Math.max(Date.now() - last, performance.now() - lastMonotonic) >=
      5 * 60 * 1000;
    const activity = () => {
      // Background tabs may suspend timers. Input cannot reset an expired
      // deadline before its keys are locked.
      if (idleExpired()) lock();
      last = Date.now();
      lastMonotonic = performance.now();
    };
    const visible = () => {
      if (!document.hidden && idleExpired()) lock();
    };
    const restored = (event: PageTransitionEvent) => {
      if (event.persisted) lock();
    };
    window.addEventListener("pointerdown", activity);
    window.addEventListener("keydown", activity);
    window.addEventListener("pagehide", lock);
    window.addEventListener("pageshow", restored);
    document.addEventListener("visibilitychange", visible);
    const timer = setInterval(() => {
      if (idleExpired()) lock();
    }, 10000);
    if (
      isSecureContext &&
      location.protocol === "https:" &&
      "serviceWorker" in navigator
    )
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    return () => {
      window.removeEventListener("offline", off);
      window.removeEventListener("online", on);
      window.removeEventListener("pointerdown", activity);
      window.removeEventListener("keydown", activity);
      window.removeEventListener("pagehide", lock);
      window.removeEventListener("pageshow", restored);
      document.removeEventListener("visibilitychange", visible);
      clearInterval(timer);
      lock();
    };
  }, [lock]);
  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = language === "fa" ? "rtl" : "ltr";
    localStorage.setItem("haven-language", language);
  }, [language]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("haven-theme", theme);
  }, [theme]);
  useEffect(() => {
    if (!user) return;
    api<Device[]>("devices")
      .then(setDevices)
      .catch(() => {});
    if (health?.crypto_ready)
      api<Conversation[]>("conversations")
        .then(setConversations)
        .catch(() => {});
  }, [user, health?.crypto_ready]);
  useEffect(() => {
    Promise.all(
      [...devices, ...members].map(
        async (d) => [d.id, await fingerprintOf(d.public_key)] as const,
      ),
    ).then((x) => setFingerprints(Object.fromEntries(x)));
  }, [devices, members]);
  useEffect(() => {
    if (!vault || pendingApproval) return;
    let sessionCheckedAt = 0,
      sessionCheckedMonotonic = -Infinity,
      rejectedSeen = vault.state.rejected_event_count || 0;
    return connectionLoop(
      async () => {
        if (
          Math.max(
            Date.now() - sessionCheckedAt,
            performance.now() - sessionCheckedMonotonic,
          ) >= 30000
        ) {
          try {
            await api("auth/me");
            sessionCheckedAt = Date.now();
            sessionCheckedMonotonic = performance.now();
          } catch (e) {
            if (
              vaultRef.current === vault &&
              e instanceof RequestError &&
              (e.status === 401 || e.status === 403)
            ) {
              lock();
              setUser(null);
              localStorage.removeItem("haven-local-user");
              setNotice(
                "Your sign-in expired or was revoked. Your vault is locked. Sign in again to continue.",
              );
            }
            throw e;
          }
        }
        if (vaultRef.current !== vault) return;
        const liveHealth = await api<NonNullable<typeof health>>("health");
        setHealth(liveHealth);
        if (!liveHealth.crypto_ready) throw new Error("CRYPTO_NOT_READY");
        const previousIds = new Set(vault.state.events.map((e) => e.id));
        let deliveryWarning = "";
        try {
          await vault.flush();
        } catch (e) {
          deliveryWarning = e instanceof Error ? e.message : "Delivery paused";
        }
        const list = await api<Conversation[]>("conversations");
        if (vaultRef.current !== vault) return;
        setConversations(list);
        let warning = deliveryWarning;
        for (const c of list) {
          try {
            await vault.syncIfChanged(c);
          } catch (e) {
            warning =
              e instanceof Error &&
              e.message.startsWith(
                "Verify device fingerprint before accepting:",
              )
                ? warning
                : e instanceof Error
                  ? e.message
                  : "Synchronization paused";
          }
        }
        if (current) {
          const detail = await api<
            Conversation & { members: { device: Device }[] }
          >(`conversations/${current.id}`);
          if (vaultRef.current !== vault) return;
          setMembers((old) => {
            const live = detail.members.map((x) => x.device);
            return [
              ...live,
              ...old.filter((x) => !live.some((y) => y.id === x.id)),
            ];
          });
        }
        if (
          notifications &&
          document.hidden &&
          vault.state.events.some((e) => !previousIds.has(e.id)) &&
          "Notification" in window &&
          Notification.permission === "granted"
        )
          new Notification(appName, {
            body: "New encrypted activity. Open your trusted conversation.",
          });
        if (vaultRef.current !== vault) return;
        setEvents((old) =>
          old.length === vault.state.events.length &&
          old.every((event, i) => event === vault.state.events[i])
            ? old
            : [...vault.state.events],
        );
        if ((vault.state.rejected_event_count || 0) > rejectedSeen) {
          setNotice(
            "A message contained invalid content and was skipped. Newer messages remain available.",
          );
          rejectedSeen = vault.state.rejected_event_count || 0;
        }
        if (warning) setError(warning);
      },
      setOnline,
      (cid) => {
        if (typing && cid === current?.id) setPeerTyping(Date.now() + 5000);
      },
      presence
        ? {
            conversation: () => current?.id,
            received: (cid) => {
              if (cid === current?.id) setPeerPresence(Date.now() + 50000);
            },
          }
        : undefined,
    );
  }, [
    vault,
    current?.id,
    notifications,
    typing,
    presence,
    pendingApproval,
    lock,
  ]);
  useEffect(() => {
    localStorage.setItem(
      "haven-privacy",
      JSON.stringify({ notifications, receipts, typing, presence }),
    );
  }, [notifications, receipts, typing, presence]);
  useEffect(() => {
    if (
      !vault ||
      !current ||
      !receipts ||
      !online ||
      document.hidden ||
      screen !== "messages" ||
      !threadAtBottom ||
      query
    )
      return;
    const last = events
      .filter(
        (e) =>
          e.conversation_id === current.id &&
          e.sender !== vault.state.device_id &&
          ["text", "file"].includes(e.type),
      )
      .at(-1);
    if (
      last &&
      !events.some(
        (e) =>
          e.type === "receipt" &&
          e.target === last.id &&
          e.sender === vault.state.device_id,
      )
    )
      void vault
        .send(current, { type: "receipt", target: last.id })
        .then(() => setEvents([...vault.state.events]))
        .catch(() => {});
  }, [events, current, receipts, online, vault, screen, threadAtBottom, query]);
  async function adminRefresh() {
    const [i, u, s] = await Promise.all([
      api<Invite[]>("admin/invitations"),
      api<User[]>("admin/users"),
      api<Record<string, unknown>>("admin/system-status"),
    ]);
    setInvitations(i);
    setUsers(u);
    setSystem(s);
  }
  useEffect(() => {
    if (screen === "admin" && user) void perform(adminRefresh);
  }, [screen, user]);
  async function login(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    await perform(async () => {
      const body = {
        username: form.get("username"),
        password: form.get("password"),
        ...(register
          ? { token: inviteToken, display_name: form.get("display_name") }
          : {}),
      };
      const result = await api<{ user: User }>(
        register ? "invitations/redeem" : "auth/login",
        "POST",
        body,
      );
      setUser(result.user);
      localStorage.setItem("haven-local-user", JSON.stringify(result.user));
      setInviteToken("");
    });
  }
  async function openConversation(c: Conversation) {
    const generation = vaultGeneration.current;
    await perform(async () => {
      const detail = await api<
        Conversation & { members: { device: Device }[] }
      >(`conversations/${c.id}`).catch((e) => {
        const head = vault?.state.heads[c.id];
        if (!head) throw e;
        return {
          ...c,
          status: "offline_cached",
          members: head.members.map((d) => ({
            device: {
              ...d,
              label: d.id,
              trust_state: "cached",
              revoked_at: null,
              challenge: "",
              approval_signature: "",
              approved_by: null,
            } as Device,
          })),
        };
      });
      if (generation !== vaultGeneration.current) return;
      setMembers(detail.members.map((x) => x.device));
      setCurrent(detail);
      setPeerPresence(0);
      setPeerTyping(0);
      setReply(undefined);
      setChatSearch(false);
      setThreadAtBottom(true);
      setDraft(vault?.state.drafts[c.id] || "");
      setGroupOpen(false);
      if (vault && !document.hidden) await vault.markRead(c.id);
      if (vault && online) {
        await vault.sync(detail);
        setEvents([...vault.state.events]);
      }
    });
  }
  async function openVault(create = false) {
    if (!user) return;
    const generation = vaultGeneration.current;
    await perform(async () => {
      if (unlock.length < 20)
        throw new Error(
          "Use a distinct unlock passphrase with at least 20 characters",
        );
      const v = create
        ? await Messenger.create(user.id, unlock, deviceLabel || "Browser")
        : await Messenger.unlock(user.id, unlock);
      if (generation !== vaultGeneration.current) {
        v.lock();
        return;
      }
      vaultRef.current = v;
      setVault(v);
      setEvents([...v.state.events]);
      setDevices(await api<Device[]>("devices").catch(() => []));
      if (v.connectionError) setError(uiError(new Error(v.connectionError)));
      setConversations(
        await api<Conversation[]>("conversations").catch(() =>
          Object.entries(v.state.heads).map(([id, h]) => ({
            id,
            kind: h.kind || ("group" as const),
            group_id: h.group_id,
            epoch: h.epoch,
            last_seq: h.seq,
            status: "offline_cached",
            head_hash: h.hash,
          })),
        ),
      );
      setUnlock("");
      if (navigator.storage.persist) await navigator.storage.persist();
      setNotice(
        t(
          "Browser storage can be erased or evicted. A server password cannot restore your keys.",
        ),
      );
    });
  }
  async function acceptGuidedVault(v: Messenger, generation: number) {
    if (generation !== vaultGeneration.current || v.user !== user?.id) {
      v.lock();
      return;
    }
    vaultRef.current = v;
    setVault(v);
    setEvents([...v.state.events]);
    const [ownDevices, list] = await Promise.all([
      api<Device[]>("devices").catch(() => []),
      api<Conversation[]>("conversations").catch(() => []),
    ]);
    if (vaultRef.current !== v) return;
    setDevices(ownDevices);
    setConversations(list);
    if (navigator.storage.persist) await navigator.storage.persist();
  }
  async function createManualConversation() {
    if (!vault) return;
    const id = await vault.create(kind);
    const list = await api<Conversation[]>("conversations");
    if (vaultRef.current !== vault) return;
    setConversations(list);
    setScreen("messages");
    await openConversation(list.find((c) => c.id === id)!);
  }
  async function send(
    type: LocalEvent["type"] = "text",
    text = draft,
    target?: string,
    emoji?: string,
  ) {
    if (!vault || !current) return;
    const conversation = current;
    await perform(async () => {
      await vault.send(conversation, {
        type,
        text,
        target,
        emoji,
        reply:
          type === "text" && !reply?.startsWith("edit:") ? reply : undefined,
      });
      if (vaultRef.current !== vault) return;
      if (
        (type === "text" || type === "edit") &&
        currentId.current === conversation.id
      ) {
        setDraft(
          type === "edit" ? vault.state.drafts[conversation.id] || "" : "",
        );
        setReply(undefined);
      }
      setEvents([...vault.state.events]);
    });
  }

  async function attach(file: File, asViewOnce = false) {
    if (!vault || !current) return;
    const controller = new AbortController();
    upload.current = controller;
    await perform(async () => {
      const prepared = await vault.prepareAttachment(
        file,
        current.id,
        controller.signal,
        asViewOnce,
      );
      const meta = await vault.resumeAttachment(
        prepared.id,
        (n) => setProgress(Math.round(n * 100) + "%"),
        controller.signal,
      );
      await vault.send(current, {
        type: "file",
        file: meta,
        reply: reply?.startsWith("edit:") ? undefined : reply,
      });
      await vault.finishAttachment(meta.id);
      if (vaultRef.current !== vault) return;
      if (currentId.current === current.id && !reply?.startsWith("edit:"))
        setReply(undefined);
      setEvents([...vault.state.events]);
    });
    upload.current = null;
    setProgress("");
  }
  async function voice() {
    if (recording) {
      recorder.current?.stop();
      return;
    }
    await perform(async () => {
      if (
        !navigator.mediaDevices?.getUserMedia ||
        typeof MediaRecorder === "undefined"
      )
        throw new Error(t("Unsupported browser"));
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      let r: MediaRecorder;
      try {
        r = new MediaRecorder(stream);
      } catch (e) {
        stream.getTracks().forEach((track) => track.stop());
        throw e;
      }
      const chunks: BlobPart[] = [];
      recorder.current = r;
      let bytes = 0,
        oversize = false;
      r.ondataavailable = (e) => {
        bytes += e.data.size;
        if (bytes > 25 * 1024 * 1024) {
          oversize = true;
          if (r.state !== "inactive") r.stop();
          return;
        }
        if (e.data.size) chunks.push(e.data);
      };
      r.onstop = () => {
        stream.getTracks().forEach((x) => x.stop());
        setRecording(false);
        recorder.current = null;
        if (oversize) {
          setError("Voice note exceeds 25 MiB. Record a shorter note.");
          return;
        }
        void attach(
          new File(
            chunks,
            "voice-note." + (r.mimeType.includes("mp4") ? "mp4" : "webm"),
            { type: r.mimeType },
          ),
          false,
        );
      };
      r.start(1000);
      setRecording(true);
      setTimeout(() => {
        if (r.state === "recording") r.stop();
      }, 120000);
    });
  }
  function discardRecording() {
    const active = recorder.current;
    if (!active) return;
    recorder.current = null;
    active.onstop = null;
    if (active.state !== "inactive") active.stop();
    active.stream.getTracks().forEach((track) => track.stop());
    setRecording(false);
  }
  useEffect(() => () => discardRecording(), [current?.id, screen]);
  async function receive(meta: NonNullable<LocalEvent["file"]>) {
    const controller = new AbortController();
    upload.current = controller;
    try {
      const blob = await downloadDecrypt(meta, {
        signal: controller.signal,
        progress: (value) => setProgress(`${Math.round(value * 100)}%`),
      });
      controller.signal.throwIfAborted();
      return blob;
    } catch (e) {
      if (controller.signal.aborted) await discardDownload(meta);
      throw e;
    } finally {
      upload.current = null;
      setProgress("");
    }
  }
  const enabled = !!health?.crypto_ready;
  const disabled = !enabled || !vault || busy;
  const chatDisabled = disabled || !vault?.state.heads[current?.id || ""];
  const messagesByConversation = useMemo(
    () =>
      new Map(
        [
          ...new Set([
            ...conversations.map((c) => c.id),
            ...events.map((e) => e.conversation_id),
          ]),
        ].map((id) => [id, conversationMessages(events, id)] as const),
      ),
    [events, conversations],
  );
  const thread = messagesByConversation.get(current?.id || "") || [];
  const shown = thread.filter(
    (message) =>
      !query ||
      messagePreview(message, t)
        .toLocaleLowerCase()
        .includes(query.toLocaleLowerCase()),
  );
  const receiptIds = new Set(
    events
      .filter(
        (e) =>
          e.type === "receipt" &&
          e.sender !== vault?.state.device_id &&
          e.conversation_id === current?.id,
      )
      .map((e) => e.target!),
  );
  const archivedIds = [...new Set(events.map((e) => e.conversation_id))].filter(
    (id) => !conversations.some((c) => c.id === id),
  );
  const status = pendingApproval
    ? t("Browser approval needed")
    : online
      ? t("Connected to primary")
      : t("Not connected");
  const isAdmin = user && user.role !== "member";
  const renderGeneration = vaultGeneration.current;
  const conversationLabel = (c: Conversation) =>
    events
      .filter((e) => e.conversation_id === c.id && e.type === "title")
      .at(-1)?.text ||
    (c.kind === "direct"
      ? vault?.state.heads[c.id]?.members
          .map(
            (m) => m.user_id !== user?.id && vault.state.contact_names?.[m.id],
          )
          .find(Boolean)
      : undefined) ||
    t(c.kind === "group" ? "Private group" : "Direct conversation");
  const senderName = (id: string) =>
    id === vault?.state.device_id
      ? t("You")
      : vault?.state.contact_names?.[id] ||
        members.find((d) => d.id === id)?.label ||
        t("Participant");
  const replyMessage = thread.find(
    (message) => message.event.id === reply?.replace(/^edit:/, ""),
  );
  const replyContext =
    reply && replyMessage
      ? {
          editing: reply.startsWith("edit:"),
          author: senderName(replyMessage.event.sender),
          text: messagePreview(replyMessage, t).slice(0, 160),
        }
      : undefined;
  function messageAction(action: MessageAction, message: Message) {
    if (action === "reply") setReply(message.event.id);
    if (action === "edit") {
      if (!reply?.startsWith("edit:") && vault && current)
        void vault.draft(current.id, draft).catch((e) => setError(uiError(e)));
      setReply("edit:" + message.event.id);
      setDraft(message.text);
    }
    if (action === "reaction") void send("reaction", "", message.event.id, "♡");
    if (
      action === "delete" &&
      window.confirm(
        t(
          "Delete this message for the conversation? Recipients may already have saved a copy.",
        ),
      )
    )
      void send("delete", "", message.event.id);
  }
  function renderAttachment(message: Message) {
    const item = message.event;
    return (
      <>
        {item.file?.view_once && vault && (
          <ViewOnceMedia
            meta={item.file}
            outgoingState={item.state}
            vault={vault}
            own={devices.some((d) => d.id === item.sender)}
            disabled={disabled || !online}
            t={t}
            onChange={() => setEvents([...vault.state.events])}
          />
        )}
        {item.file && !item.file.view_once && (
          <div className="file-attachment">
            {canPreview(item.file) && <MediaPreview file={item.file} t={t} />}
            {item.file.mime.startsWith("audio/") && (
              <AudioAttachment meta={item.file} t={t} />
            )}
            <button
              type="button"
              className="attachment-download"
              disabled={busy}
              onClick={() =>
                void perform(async () =>
                  download(await receive(item.file!), item.file!.name),
                )
              }
            >
              <Icon name="down" size={16} />
              {t("Download")} · <span dir="auto">{item.file.name}</span>
            </button>
            <details className="download-options">
              <summary>{t("Download options")}</summary>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  void perform(async () => {
                    await discardDownload(item.file!);
                  })
                }
              >
                {t("Clear partial download")}
              </button>
            </details>
          </div>
        )}
        {!item.file?.view_once &&
          item.state === "failed" &&
          item.sender === vault?.state.device_id && (
            <button
              type="button"
              disabled={disabled}
              onClick={() =>
                void perform(async () => {
                  await vault!.send(current!, {
                    type: item.type,
                    text: message.text,
                    file: item.file,
                    reply: item.reply,
                  });
                  setEvents([...vault!.state.events]);
                })
              }
            >
              {t("Review recipients and resend")}
            </button>
          )}
      </>
    );
  }
  const unreadCount = (cid: string) =>
    (messagesByConversation.get(cid) || []).filter(
      (message) =>
        message.event.sender !== vault?.state.device_id &&
        (message.event.seq || 0) > (vault?.state.read_seq?.[cid] || 0),
    ).length;
  const visibleConversations = conversations.filter(
    (c) =>
      (listFilter !== "unread" || unreadCount(c.id) > 0) &&
      (!query ||
        conversationLabel(c)
          .toLocaleLowerCase()
          .includes(query.toLocaleLowerCase()) ||
        messagesByConversation
          .get(c.id)
          ?.some((message) =>
            messagePreview(message, t)
              .toLocaleLowerCase()
              .includes(query.toLocaleLowerCase()),
          )),
  );

  return (
    <div
      className="app-frame"
      data-authenticated={!!user}
      data-screen={screen}
      data-chat-active={screen === "messages" && !!current}
      onKeyDownCapture={() => {
        document.documentElement.dataset.interaction = "keyboard";
      }}
      onPointerDownCapture={() => {
        document.documentElement.dataset.interaction = "pointer";
      }}
    >
      <a className="skip-link" href="#main-content">
        {t("Skip to content")}
      </a>
      <header className="topbar">
        <a className="brand" href="/" aria-label={appName}>
          <span className="brand-mark">
            <Icon name="messages" size={25} filled />
          </span>
          {appName}
          <span className="brand-sub">{t("Private community")}</span>
        </a>
        <div className="top-actions">
          <span className={online ? "connection" : "connection disconnected"}>
            <i />
            {status}
          </span>
          <button
            className="quiet icon-button theme-switch"
            aria-label={t(
              theme === "light"
                ? "Switch to dark mode"
                : "Switch to light mode",
            )}
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          >
            <Icon name={theme === "light" ? "moon" : "sun"} />
          </button>
          <button
            className="quiet language-switch"
            onClick={() => setLanguage(language === "en" ? "fa" : "en")}
          >
            {language === "en" ? "فارسی" : "English"}
          </button>
        </div>
      </header>
      <div className="gate" role="status">
        <Icon name="warning" size={17} />
        <strong>{t("Security qualification pending")}</strong>
        <span>
          {t(
            health?.crypto_ready
              ? "Experimental cryptographic integration. Not approved for production use."
              : "Encryption is unavailable until the integrated security gates pass.",
          )}
        </span>
        {user && (
          <button className="gate-help" onClick={() => setScreen("help")}>
            {t("Details")} <Icon name="next" size={14} />
          </button>
        )}
      </div>
      {health?.maintenance && (
        <div className="banner">
          {t("Maintenance")}: {health.maintenance}
        </div>
      )}
      {error && (
        <div className="toast error" role="alert">
          <span>{t(error)}</span>
          <button
            className="quiet"
            onClick={() => setError("")}
            aria-label={t("Dismiss error")}
          >
            ×
          </button>
        </div>
      )}
      {notice && (
        <div className="toast" role="status">
          {t(notice)}
        </div>
      )}
      {!user ? (
        <main className="onboarding" id="main-content" tabIndex={-1}>
          <section className="intro">
            <HavenEmblem compact />
            <span className="eyebrow">
              {t("Invite only. No phone number, email, or external login.")}
            </span>
            <h1>{t("A quiet place to stay connected.")}</h1>
            <p>
              {t(
                "Use a trusted HTTPS IP address. Never bypass a certificate warning.",
              )}
            </p>
            <div className="privacy-card">
              <span className="privacy-icon">
                <Icon name="lock" size={25} />
              </span>
              <div>
                <strong>RFC 9420 · OpenMLS</strong>
                <p>{t("Message keys stay on this device.")}</p>
                <small>{t("Security qualification pending")}</small>
              </div>
            </div>
            <p className="muted">
              {t(
                "No route means no remote delivery. A compromised application origin can deliver code that exposes client secrets.",
              )}
            </p>
          </section>
          <section className="auth-card">
            <div className="tabs">
              <button
                className={!register ? "active" : ""}
                onClick={() => setRegister(false)}
              >
                {t("Sign in")}
              </button>
              <button
                className={register ? "active" : ""}
                onClick={() => setRegister(true)}
              >
                {t("Create account")}
              </button>
            </div>
            <h2>{t("Open your private space")}</h2>
            <form onSubmit={login}>
              {register && (
                <>
                  <label>
                    {t("Invitation token")}
                    <input
                      value={inviteToken}
                      onChange={(e) => setInviteToken(e.target.value)}
                      required
                      autoComplete="off"
                    />
                  </label>
                  <label>
                    {t("Display name")}
                    <input name="display_name" required maxLength={80} />
                  </label>
                </>
              )}
              <label>
                {t("Username")}
                <input
                  name="username"
                  required
                  pattern="[a-zA-Z0-9_.-]{3,64}"
                  autoComplete="username"
                  dir="ltr"
                />
              </label>
              <label>
                {t("Password")}
                <input
                  name="password"
                  type="password"
                  required
                  minLength={14}
                  maxLength={256}
                  autoComplete={register ? "new-password" : "current-password"}
                />
              </label>
              <button className="primary" disabled={busy || !online}>
                {t(register ? "Create account" : "Sign in")} <span>→</span>
              </button>
            </form>
            {enabled && (
              <AccountRecovery
                t={t}
                complete={(u, v) => {
                  setUser(u);
                  vaultRef.current = v;
                  setVault(v);
                  setEvents([...v.state.events]);
                  localStorage.setItem("haven-local-user", JSON.stringify(u));
                }}
              />
            )}
            <p className="fine">
              {t("Server password and vault passphrase must be different.")}
            </p>
          </section>
        </main>
      ) : (
        <div className="workspace">
          <aside className="sidebar">
            <div className="profile">
              <div className="avatar">{user.display_name.slice(0, 1)}</div>
              <div>
                <strong>{user.display_name}</strong>
                <small>@{user.username}</small>
              </div>
            </div>
            <button
              className="primary connect-entry"
              title={t("Start a chat")}
              aria-label={t("Start a chat")}
              onClick={() => setScreen("connect")}
            >
              <Icon name="plus" size={18} />
              <span className="connect-label">{t("Start a chat")}</span>
            </button>
            <nav aria-label={t("Main navigation")}>
              <span className="nav-indicator" aria-hidden="true" />
              {nav.map(([key, icon, label]) => (
                <button
                  key={key}
                  className={`nav-item ${screen === key ? "selected" : ""} ${["backup", "help"].includes(key) ? "nav-secondary" : ""}`}
                  aria-label={t(label)}
                  aria-current={screen === key ? "page" : undefined}
                  title={t(label)}
                  onClick={() => setScreen(key)}
                >
                  <Icon name={icon} />
                  <span className="nav-label">{t(label)}</span>
                </button>
              ))}
              {isAdmin && (
                <button
                  className={
                    screen === "admin"
                      ? "nav-item nav-secondary selected"
                      : "nav-item nav-secondary"
                  }
                  onClick={() => setScreen("admin")}
                >
                  <Icon name="admin" />
                  <span className="nav-label">{t("Operator console")}</span>
                </button>
              )}
              <button
                className="nav-item mobile-more-trigger"
                popoverTarget="mobile-more"
                aria-label={t("More")}
              >
                <Icon name="more" />
                <span className="nav-label">{t("More")}</span>
              </button>
            </nav>
            <div id="mobile-more" popover="auto" className="mobile-more">
              <div className="more-heading">
                <strong>{t("Your space")}</strong>
                <button
                  className="quiet icon-button"
                  popoverTarget="mobile-more"
                  popoverTargetAction="hide"
                  aria-label={t("Close")}
                >
                  <Icon name="close" />
                </button>
              </div>
              {[
                ...nav.filter(([key]) => ["backup", "help"].includes(key)),
                ...(isAdmin
                  ? [
                      ["admin", "admin", "Operator console"] as [
                        Screen,
                        IconName,
                        string,
                      ],
                    ]
                  : []),
              ].map(([key, icon, label]) => (
                <button
                  key={key}
                  className="nav-item"
                  onClick={() => {
                    setScreen(key);
                    document.getElementById("mobile-more")?.hidePopover();
                  }}
                >
                  <Icon name={icon} />
                  {t(label)}
                </button>
              ))}
              <button
                className="nav-item"
                onClick={() => {
                  if (vault) lock();
                  else setScreen("devices");
                  document.getElementById("mobile-more")?.hidePopover();
                }}
              >
                <Icon name="lock" />
                {t(vault ? "Lock vault" : "Open your vault")}
              </button>
              <button
                className="nav-item danger"
                onClick={() => {
                  document.getElementById("mobile-more")?.hidePopover();
                  void perform(logout);
                }}
              >
                <Icon name="logout" />
                {t("Log out")}
              </button>
            </div>
            <div className="sidebar-bottom">
              <span className="key-state">
                <Icon name="lock" size={14} />
                {t(vault ? "Verified devices only" : "Key state locked")}
              </span>
              <button
                className="quiet vault-shortcut"
                onClick={() => (vault ? lock() : setScreen("devices"))}
              >
                <Icon name={vault ? "lock" : "key"} size={17} />
                {t(vault ? "Lock vault" : "Open your vault")}
              </button>
              <button
                className="quiet"
                onClick={() =>
                  void perform(async () => {
                    await logout();
                  })
                }
              >
                <Icon name="logout" size={17} />
                {t("Log out")}
              </button>
            </div>
          </aside>
          <main className="content" id="main-content" tabIndex={-1}>
            {screen === "messages" && (
              <div className="messenger" data-chat-open={!!current}>
                <section className="conversation-panel">
                  <div className="section-heading">
                    <div>
                      <h1>{t("Conversations")}</h1>
                      <span className="conversation-subtitle">
                        {t("A little closer, wherever you are.")}
                      </span>
                    </div>
                    <button
                      title={t("New conversation")}
                      aria-label={t("New conversation")}
                      disabled={!enabled || busy}
                      onClick={() => setScreen("connect")}
                    >
                      <Icon name="plus" size={22} />
                    </button>
                  </div>
                  <label className="search">
                    <Icon name="search" size={19} />
                    <input
                      placeholder={t("Search on this device")}
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      aria-label={t("Search on this device")}
                    />
                  </label>
                  <div
                    className="list-controls chat-filters"
                    aria-label={t("Filter conversations")}
                  >
                    <button
                      type="button"
                      aria-pressed={listFilter === "all"}
                      onClick={() => setListFilter("all")}
                    >
                      {t("All chats")}
                    </button>
                    <button
                      type="button"
                      aria-pressed={listFilter === "unread"}
                      onClick={() => setListFilter("unread")}
                    >
                      {t("Unread")}
                    </button>
                  </div>
                  {visibleConversations.length ? (
                    visibleConversations.map((c) => {
                      const list = messagesByConversation.get(c.id) || [];
                      const last = list.at(-1);
                      const unread = list.filter(
                        (message) =>
                          message.event.sender !== vault?.state.device_id &&
                          (message.event.seq || 0) >
                            (vault?.state.read_seq?.[c.id] || 0),
                      ).length;
                      return (
                        <button
                          key={c.id}
                          className={`conversation-row ${current?.id === c.id ? "selected" : ""}`}
                          aria-current={
                            current?.id === c.id ? "true" : undefined
                          }
                          onClick={() => void openConversation(c)}
                        >
                          <span className="avatar">
                            <Icon
                              name={c.kind === "group" ? "people" : "messages"}
                              size={23}
                            />
                          </span>
                          <span className="conversation-copy">
                            <span className="conversation-title">
                              <strong>{conversationLabel(c)}</strong>
                              {last && (
                                <time dateTime={last.event.time}>
                                  <bdi>
                                    {new Date(
                                      last.event.time,
                                    ).toLocaleTimeString(
                                      language === "fa" ? "fa-IR" : "en",
                                      { hour: "2-digit", minute: "2-digit" },
                                    )}
                                  </bdi>
                                </time>
                              )}
                            </span>
                            <span className="conversation-preview">
                              <span dir="auto">
                                {!vault?.state.heads[c.id]
                                  ? t("Verify to start")
                                  : last
                                    ? messagePreview(last, t)
                                    : t("Say hello")}
                              </span>
                              {unread > 0 && (
                                <span
                                  className="unread-count"
                                  aria-label={`${unread} ${t("unread")}`}
                                >
                                  {unread > 99 ? "99+" : unread}
                                </span>
                              )}
                            </span>
                          </span>
                        </button>
                      );
                    })
                  ) : (
                    <div className="empty-list">
                      <span className="empty-list-icon">
                        <Icon name="messages" size={29} />
                      </span>
                      <strong>
                        {t(
                          query
                            ? "No matching conversations"
                            : listFilter === "unread"
                              ? "You’re all caught up"
                              : "No conversations yet",
                        )}
                      </strong>
                      <p>
                        {t(
                          query
                            ? "Try a name or a word from a message on this device."
                            : listFilter === "unread"
                              ? "New unread messages will appear here."
                              : !enabled
                                ? "Encryption is unavailable until the integrated security gates pass."
                                : !vault
                                  ? "Unlock this device to find your conversations."
                                  : "Start a conversation and invite a verified device. Your messages stay between you.",
                        )}
                      </p>
                      {!vault && (
                        <button
                          className="primary mobile-setup"
                          disabled={!enabled}
                          onClick={() => setScreen("connect")}
                        >
                          <Icon name="key" size={17} />
                          {t("Set up this device")}
                        </button>
                      )}
                    </div>
                  )}
                  <div className="panel-note">
                    <Icon name="lock" size={13} />{" "}
                    {t("Search stays on this device")}
                  </div>
                </section>
                <section className="chat-panel">
                  {current ? (
                    <>
                      <header className="chat-header">
                        <button
                          className="quiet icon-button mobile-back"
                          aria-label={t("Back to conversations")}
                          onClick={() => setCurrent(null)}
                        >
                          <Icon name="back" />
                        </button>
                        <span className="chat-avatar avatar">
                          <Icon
                            name={
                              current.kind === "group" ? "people" : "messages"
                            }
                            size={23}
                          />
                        </span>
                        <div className="chat-heading">
                          <h2>{conversationLabel(current)}</h2>
                          <small>
                            <Icon name="lock" size={12} />
                            {t(
                              pendingApproval
                                ? "Browser approval needed"
                                : vault?.state.heads[current.id]
                                  ? "End-to-end encrypted"
                                  : "Security code comparison needed",
                            )}
                          </small>
                        </div>
                        <button
                          type="button"
                          className="quiet icon-button chat-search-toggle"
                          aria-label={t("Search this conversation")}
                          title={t("Search this conversation")}
                          onClick={() => setChatSearch(!chatSearch)}
                        >
                          <Icon name="search" />
                        </button>
                        <button
                          className="quiet members-toggle"
                          aria-expanded={groupOpen}
                          onClick={() => setGroupOpen(!groupOpen)}
                        >
                          {t(
                            current.kind === "group"
                              ? "Group & members"
                              : "Chat details",
                          )}
                        </button>
                      </header>
                      {vault && (
                        <ConversationVerification
                          conversation={current}
                          vault={vault}
                          t={t}
                          verified={async () => {
                            await vault.sync(current);
                            if (vaultRef.current !== vault) return;
                            setEvents([...vault.state.events]);
                            setError("");
                          }}
                        />
                      )}
                      {groupOpen && (
                        <section className="member-controls">
                          <h3>
                            {t(
                              current.kind === "group"
                                ? "Group & members"
                                : "Chat details",
                            )}
                          </h3>
                          <p>
                            {t("Epoch")}{" "}
                            {vault?.state.heads[current.id]?.epoch ??
                              current.epoch}{" "}
                            · {current.status}
                          </p>
                          <button
                            disabled={disabled}
                            onClick={() =>
                              void perform(async () => {
                                await vault!.leave(current);
                                setNotice(
                                  "Departure requested. An owner or moderator must complete MLS removal before writes resume.",
                                );
                              })
                            }
                          >
                            {t("Leave conversation")}
                          </button>
                          <button
                            disabled={disabled}
                            onClick={() =>
                              void perform(async () => {
                                const self = members.find(
                                  (d) => d.id === vault!.state.device_id,
                                );
                                if (!self)
                                  throw new Error(
                                    "Current device is not a group member",
                                  );
                                await vault!.changeMember(
                                  current,
                                  self,
                                  "update",
                                );
                                setNotice(
                                  "MLS epoch refreshed through an authenticated path update.",
                                );
                              })
                            }
                          >
                            {t("Refresh cryptographic epoch")}
                          </button>
                          {Object.values(vault?.state.outbox || {}).some(
                            (p) => p.candidate,
                          ) && (
                            <button
                              onClick={() =>
                                void perform(async () => {
                                  await vault!.cancelPendingControl(current);
                                  setNotice(
                                    "Pending membership request cancelled locally and signed group history checked. Review the roster before retrying.",
                                  );
                                })
                              }
                            >
                              {t(
                                "Cancel pending membership request and check state",
                              )}
                            </button>
                          )}
                          <label>
                            {t("Group title")}
                            <input id="group-title" />
                          </label>
                          <button
                            disabled={disabled}
                            onClick={() =>
                              void send(
                                "title",
                                (
                                  document.getElementById(
                                    "group-title",
                                  ) as HTMLInputElement
                                ).value,
                              )
                            }
                          >
                            {t("Save")}
                          </button>
                          <label>
                            {t("Device ID")}
                            <input
                              value={targetDevice}
                              onChange={(e) => setTargetDevice(e.target.value)}
                            />
                          </label>
                          <button
                            disabled={disabled}
                            onClick={() =>
                              void perform(async () => {
                                const kp = await api<{ device: Device }>(
                                  `crypto/key-packages/${targetDevice}`,
                                );
                                setMembers([...members, kp.device]);
                                setScreen("trust");
                              })
                            }
                          >
                            {t("Verify fingerprint")}
                          </button>
                          {members.map((d) => (
                            <div key={d.id}>
                              <b>{d.label}</b>
                              <code>{d.id}</code>
                              <button
                                disabled={disabled}
                                onClick={() =>
                                  void perform(async () => {
                                    await vault!.changeMember(
                                      current,
                                      d,
                                      "add",
                                    );
                                  })
                                }
                              >
                                {t("Add member")}
                              </button>
                              <button
                                disabled={disabled}
                                onClick={() =>
                                  void perform(async () => {
                                    await vault!.changeMember(
                                      current,
                                      d,
                                      "remove",
                                    );
                                  })
                                }
                              >
                                {t("Remove member")}
                              </button>
                              <button
                                disabled={disabled}
                                onClick={() =>
                                  void perform(async () => {
                                    await vault!.changeMember(
                                      current,
                                      d,
                                      "transfer",
                                    );
                                    setNotice(
                                      "Ownership transferred through a signed MLS epoch update.",
                                    );
                                  })
                                }
                              >
                                {t("Transfer ownership")}
                              </button>
                              <button
                                disabled={disabled}
                                onClick={() =>
                                  void perform(async () => {
                                    await vault!.changeMember(
                                      current,
                                      d,
                                      "role",
                                      "moderator",
                                    );
                                    setNotice(
                                      "Moderator appointed through a signed MLS epoch update.",
                                    );
                                  })
                                }
                              >
                                {t("Make moderator")}
                              </button>
                            </div>
                          ))}
                        </section>
                      )}
                      {chatSearch && (
                        <div className="chat-search">
                          <Icon name="search" size={18} />
                          <input
                            autoFocus
                            aria-label={t("Search this conversation")}
                            placeholder={t("Search this conversation")}
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                          />
                          <span>
                            {shown.length} {t("results")}
                          </span>
                          <button
                            type="button"
                            className="quiet icon-button"
                            aria-label={t("Close search")}
                            onClick={() => {
                              setChatSearch(false);
                              setQuery("");
                            }}
                          >
                            <Icon name="close" size={18} />
                          </button>
                        </div>
                      )}
                      <ChatThread
                        key={`thread:${current.id}`}
                        messages={shown}
                        allMessages={thread}
                        receiptIds={receiptIds}
                        self={vault?.state.device_id}
                        language={language}
                        query={query}
                        senderName={senderName}
                        attachment={renderAttachment}
                        disabled={chatDisabled || recording}
                        action={messageAction}
                        feedback={setNotice}
                        bottomChanged={(bottom) => {
                          setThreadAtBottom(bottom);
                          if (
                            bottom &&
                            vault &&
                            !query &&
                            !document.hidden &&
                            (vault.state.read_seq?.[current.id] || 0) <
                              (vault.state.cursor[current.id] || 0)
                          )
                            void vault
                              .markRead(current.id)
                              .then(() => {
                                if (vaultRef.current === vault)
                                  setEvents([...vault.state.events]);
                              })
                              .catch(() => {});
                        }}
                        t={t}
                      />
                      {presence && peerPresence > Date.now() && (
                        <small className="peer-hint">
                          {t(
                            "Another participant has a reachable active tab (server hint)",
                          )}
                        </small>
                      )}
                      {typing && peerTyping > Date.now() && (
                        <small className="peer-hint">
                          {t("Another participant is typing…")}
                        </small>
                      )}
                      <ChatComposer
                        key={`composer:${current.id}`}
                        draft={draft}
                        change={(text) => {
                          setDraft(text);
                          if (typing)
                            window.dispatchEvent(
                              new CustomEvent("haven:typing", {
                                detail: current.id,
                              }),
                            );
                        }}
                        saveDraft={() => {
                          if (vault && !reply?.startsWith("edit:"))
                            void vault
                              .draft(current.id, draft)
                              .catch((e) => setError(uiError(e)));
                        }}
                        send={() => {
                          if (reply?.startsWith("edit:"))
                            void send("edit", draft, reply.slice(5));
                          else void send();
                        }}
                        attach={(file, once) => void attach(file, once)}
                        voice={() => void voice()}
                        discardRecording={discardRecording}
                        recording={recording}
                        disabled={chatDisabled}
                        reply={replyContext}
                        cancelReply={() => {
                          if (reply?.startsWith("edit:"))
                            setDraft(vault?.state.drafts[current.id] || "");
                          setReply(undefined);
                        }}
                        online={online}
                        blockedReason={
                          !enabled
                            ? "Messaging is unavailable until security qualification is complete."
                            : !vault
                              ? "Unlock this browser to write a message."
                              : pendingApproval
                                ? "Approve this browser before messaging."
                                : !vault.state.heads[current.id]
                                  ? "Compare security codes above to start chatting."
                                  : ""
                        }
                        t={t}
                      />
                      {vault &&
                        Object.values(vault.state.uploads || {})
                          .filter((x) => x.conversation_id === current.id)
                          .map((meta) => (
                            <div className="card" key={meta.id}>
                              <span>
                                {meta.name}
                                {t("— encrypted upload pending")}
                              </span>
                              <button
                                onClick={() =>
                                  void perform(async () => {
                                    const signal = new AbortController().signal;
                                    await vault.resumeAttachment(
                                      meta.id,
                                      (n) =>
                                        setProgress(Math.round(n * 100) + "%"),
                                      signal,
                                    );
                                    await vault.send(current, {
                                      type: "file",
                                      file: meta,
                                    });
                                    await vault.finishAttachment(meta.id);
                                    setEvents([...vault.state.events]);
                                    setProgress("");
                                  })
                                }
                              >
                                {t("Resume encrypted upload")}
                              </button>
                              <button
                                onClick={() =>
                                  void perform(async () => {
                                    await vault.cancelAttachment(meta.id);
                                    setEvents([...vault.state.events]);
                                  })
                                }
                              >
                                {t("Cancel")}
                              </button>
                            </div>
                          ))}
                      {progress && (
                        <div>
                          {progress}
                          <button onClick={() => upload.current?.abort()}>
                            {t("Cancel")}
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="welcome">
                      <HavenEmblem />
                      <h2>
                        {t(
                          vault
                            ? "Your people. Your space."
                            : "Make yourself at home.",
                        )}
                      </h2>
                      <p>
                        {t(
                          vault
                            ? "Pick a conversation or start something new. A quieter way to stay close to the people who matter."
                            : "Unlock your private space to reconnect with your people. Your keys stay right here, on this device.",
                        )}
                      </p>
                      <div className="welcome-actions">
                        {!vault ? (
                          <button
                            className="primary"
                            disabled={!enabled}
                            onClick={() => setScreen("connect")}
                          >
                            <Icon name="key" size={18} />
                            {t("Set up this device")}
                            <Icon name="next" size={17} />
                          </button>
                        ) : (
                          <button
                            className="primary"
                            onClick={() => setScreen("connect")}
                          >
                            <Icon name="people" size={18} />
                            {t("Start a chat")}
                          </button>
                        )}
                        <button
                          className="quiet welcome-help"
                          onClick={() => setScreen("help")}
                        >
                          {t("How HAVEN works")}
                          <Icon name="next" size={16} />
                        </button>
                      </div>
                      <div className="welcome-tags">
                        <span>
                          <Icon name="lock" size={14} />
                          {t("Keys stay on your devices")}
                        </span>
                        <span>{t("Invite-only community")}</span>
                      </div>
                    </div>
                  )}
                </section>
              </div>
            )}
            {screen !== "messages" && (
              <div className="page-content" key={screen}>
                <span className="eyebrow">
                  {appName} /{" "}
                  {t(
                    screen === "connect"
                      ? "Start a chat"
                      : nav.find((x) => x[0] === screen)?.[2] ||
                          "Operator console",
                  )}
                </span>
                <h1>
                  {t(
                    screen === "connect"
                      ? "Start a chat"
                      : nav.find((x) => x[0] === screen)?.[2] ||
                          "Operator console",
                  )}
                </h1>
                {screen === "connect" && (
                  <ConnectFlow
                    key={`${user.id}:${renderGeneration}`}
                    user={user}
                    vault={vault}
                    enabled={enabled}
                    initialContact={pendingContact}
                    t={t}
                    ready={(v) => acceptGuidedVault(v, renderGeneration)}
                    advanced={() => setScreen("devices")}
                    manual={createManualConversation}
                    conversationType={kind}
                    changeConversationType={setKind}
                    opened={async (c) => {
                      const list = await api<Conversation[]>("conversations");
                      if (
                        renderGeneration !== vaultGeneration.current ||
                        !vaultRef.current
                      )
                        return;
                      setPendingContact(null);
                      setConversations(list);
                      setScreen("messages");
                      await openConversation(c);
                    }}
                  />
                )}
                {(screen === "devices" || screen === "backup") && (
                  <section className="card">
                    <h2>{t(vault ? "Lock vault" : "Unlock vault")}</h2>
                    <p>
                      {t(
                        "Browser storage can be erased or evicted. A server password cannot restore your keys.",
                      )}
                    </p>
                    {!vault ? (
                      <>
                        <label>
                          {t("Local unlock passphrase")}
                          <input
                            type="password"
                            value={unlock}
                            onChange={(e) => setUnlock(e.target.value)}
                            autoComplete="off"
                            minLength={20}
                          />
                        </label>
                        <label>
                          {t("Device label")}
                          <input
                            value={deviceLabel}
                            onChange={(e) => setDeviceLabel(e.target.value)}
                          />
                        </label>
                        <div className="button-row">
                          <button
                            disabled={!enabled || busy}
                            onClick={() => void openVault()}
                          >
                            {t("Unlock vault")}
                          </button>
                          <button
                            disabled={!enabled || busy}
                            onClick={() => void openVault(true)}
                          >
                            {t("Create device vault")}
                          </button>
                        </div>
                      </>
                    ) : (
                      <button onClick={lock}>{t("Lock vault")}</button>
                    )}
                  </section>
                )}
                {screen === "trust" && (
                  <>
                    <p>
                      {t(
                        "Compare this fingerprint through an independent channel before verifying.",
                      )}
                    </p>
                    {!members.length && (
                      <div className="card">{t("No devices enrolled")}</div>
                    )}
                    <section className="card">
                      <label>
                        {t("Device ID")}
                        <input
                          value={targetDevice}
                          onChange={(e) => setTargetDevice(e.target.value)}
                        />
                      </label>
                      <button
                        disabled={disabled}
                        onClick={() =>
                          void perform(async () => {
                            const result = await api<{ device: Device }>(
                              `crypto/key-packages/${targetDevice}`,
                            );
                            setMembers((old) => [
                              ...old.filter((d) => d.id !== result.device.id),
                              result.device,
                            ]);
                          })
                        }
                      >
                        {t("Look up a known device")}
                      </button>
                    </section>
                    {[
                      ...new Map(
                        [...devices, ...members].map((d) => [d.id, d]),
                      ).values(),
                    ].map((d) => (
                      <section className="card" key={d.id}>
                        {vault?.state.pins[d.id] &&
                          vault.state.pins[d.id] !== d.public_key && (
                            <p role="alert">
                              {t(
                                "Identity key changed. Stop and independently verify this device before continuing.",
                              )}
                            </p>
                          )}
                        {(d.revoked_at || d.trust_state === "revoked") && (
                          <p role="status">
                            {t(
                              "Revoked device: verify historical signatures only. This does not authorize new membership.",
                            )}
                          </p>
                        )}
                        <small>
                          {vault?.state.pins[d.id] === d.public_key
                            ? t("Verified devices only")
                            : t("Crypto verification needed")}
                        </small>
                        <h2>{d.label}</h2>
                        <code>{d.identity}</code>
                        <code className="fingerprint">
                          {fingerprints[d.id]}
                        </code>
                        <QR
                          t={t}
                          value={`haven:device:v1:${d.id}:${fingerprints[d.id]}`}
                        />
                        <label>
                          {t("Confirm fingerprint")}
                          <input
                            value={comparison}
                            onChange={(e) => setComparison(e.target.value)}
                          />
                        </label>
                        <button
                          disabled={disabled}
                          onClick={() =>
                            void perform(async () => {
                              await vault!.pin(d, comparison);
                              setComparison("");
                              setNotice(t("Verified devices only"));
                            })
                          }
                        >
                          {t("Verify fingerprint")}
                        </button>
                      </section>
                    ))}
                  </>
                )}
                {screen === "devices" && (
                  <section className="card">
                    <div className="section-heading">
                      <h2>{t("Devices")}</h2>
                      <button
                        onClick={() =>
                          void perform(async () =>
                            setDevices(await api<Device[]>("devices")),
                          )
                        }
                      >
                        {t("Refresh")}
                      </button>
                    </div>
                    {!devices.length && <p>{t("No devices enrolled")}</p>}
                    {devices.map((d) => (
                      <div className="device-row" key={d.id}>
                        <div>
                          <strong>{d.label}</strong>
                          <code>{d.id}</code>
                          <small>{t(d.trust_state)}</small>
                          <code className="fingerprint">
                            {fingerprints[d.id]}
                          </code>
                        </div>
                        <div className="button-row">
                          <button
                            disabled={disabled}
                            onClick={() =>
                              void perform(async () => {
                                await vault!.approve(d);
                                setDevices(await api<Device[]>("devices"));
                              })
                            }
                          >
                            {t("Approve enrollment")}
                          </button>
                          <button
                            disabled={disabled}
                            className="danger"
                            onClick={() =>
                              void perform(async () => {
                                if (
                                  !confirm(
                                    "Revoke this device? All affected groups pause until cryptographic rekey.",
                                  )
                                )
                                  return;
                                await api(`devices/${d.id}/revoke`, "POST", {});
                                setDevices(await api<Device[]>("devices"));
                              })
                            }
                          >
                            {t("Revoke device")}
                          </button>
                        </div>
                      </div>
                    ))}
                  </section>
                )}
                {screen === "backup" && (
                  <>
                    {archivedIds.length > 0 && (
                      <section className="card">
                        <h2>{t("Recovered local history")}</h2>
                        <p>
                          {t(
                            "These conversations belong to your previous device. Their MLS state is never resumed.",
                          )}
                        </p>
                        {archivedIds.map((id) => (
                          <details key={id}>
                            <summary>{id.slice(0, 8)}</summary>
                            {events
                              .filter((e) => e.conversation_id === id)
                              .map((e) => (
                                <p dir="auto" key={e.id}>
                                  {e.text || e.file?.name || e.type}
                                </p>
                              ))}
                          </details>
                        ))}
                      </section>
                    )}
                    <section className="card">
                      <h2>{t("Recovery kit")}</h2>
                      <p>
                        {t(
                          "Store the key separately from the encrypted kit. Losing both permanently loses local history.",
                        )}
                      </p>
                      <label>
                        {t("Local unlock passphrase")}
                        <input
                          type="password"
                          value={unlock}
                          onChange={(e) => setUnlock(e.target.value)}
                        />
                      </label>
                      <button
                        disabled={disabled}
                        onClick={() =>
                          void perform(async () => {
                            const accountRecovery =
                              await vault!.provisionRecovery();
                            if (!accountRecovery)
                              setNotice(
                                "History-only kit: account recovery remains with the original recovery kit.",
                              );
                            const kit = await recoveryKit(
                              user.id,
                              unlock,
                              vault!.state,
                            );
                            setRecovery(kit.recovery);
                            download(kit.kit, "haven-encrypted-recovery.json");
                          })
                        }
                      >
                        {t("Download encrypted kit")}
                      </button>
                      {recovery && (
                        <div className="warning">
                          <strong>{t("Recovery key")}</strong>
                          <code>{recovery}</code>
                        </div>
                      )}
                      <hr />
                      <p>
                        {t(
                          "Recovery restores saved history only. A fresh device and explicit peer verification are required.",
                        )}
                      </p>
                      <label>
                        {t("Recovery key")}
                        <input
                          type="password"
                          value={recovery}
                          onChange={(e) => setRecovery(e.target.value)}
                        />
                      </label>
                      <label>
                        {t("New account password after security reset")}
                        <input
                          type="password"
                          value={resetPassword}
                          onChange={(e) => setResetPassword(e.target.value)}
                          autoComplete="new-password"
                        />
                      </label>
                      <p>
                        {t(
                          "Recovery always creates a fresh MLS identity and revokes old devices. Keep the kit and its separate key secure. Enter a new unlock secret on the Devices screen first.",
                        )}
                      </p>
                      <label>
                        {t("Restore encrypted kit")}
                        <input
                          type="file"
                          accept="application/json"
                          disabled={!enabled || busy}
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file)
                              void perform(async () => {
                                if (file.size > 256 * 1024 * 1024)
                                  throw new Error("Kit too large");
                                const kit = JSON.parse(await file.text()) as {
                                  format: string;
                                  scope: string;
                                  sealed: Sealed;
                                };
                                if (
                                  kit.format !==
                                    "haven-recovery-v2-history-only" ||
                                  kit.scope !== user.id
                                )
                                  throw new Error("Kit account mismatch");
                                const state = await unseal<VaultState>(
                                  recovery,
                                  user.id,
                                  kit.sealed,
                                );
                                if (vault) {
                                  await vault.importHistory(state);
                                  setEvents([...vault.state.events]);
                                  setNotice(
                                    "Saved history imported locally. Live device keys and pending messages were preserved.",
                                  );
                                  return;
                                }
                                const fresh = await Messenger.recover(
                                  user.id,
                                  unlock,
                                  state,
                                  resetPassword,
                                  deviceLabel || "Recovered browser",
                                );
                                vaultRef.current = fresh;
                                setVault(fresh);
                                setEvents([...fresh.state.events]);
                                setRecovery("");
                                setResetPassword("");
                                setUnlock("");
                                setNotice(
                                  "Account security reset completed. All old devices are revoked. Restored history is local-only; contacts must verify this fresh device and explicitly re-add it.",
                                );
                              });
                          }}
                        />
                      </label>
                    </section>
                  </>
                )}
                {screen === "settings" && (
                  <>
                    {vault && <DeviceUnlockSettings vault={vault} t={t} />}
                    <ServerPrivacy t={t} />
                    {vault && (
                      <section className="card">
                        <p>
                          {t("Device ID:")}
                          <code>{vault.state.device_id}</code>
                        </p>
                        <button
                          onClick={() =>
                            void perform(async () => {
                              await vault.connect();
                              await vault.package();
                              setDevices(await api<Device[]>("devices"));
                              setNotice(
                                "Approved device connected; a fresh key package is available.",
                              );
                            })
                          }
                        >
                          {t("Complete approved device enrollment")}
                        </button>
                      </section>
                    )}
                    <section className="card">
                      <h2>{t("Appearance & privacy")}</h2>
                      <label>
                        {t("Language")}
                        <select
                          aria-label={t("Language")}
                          value={language}
                          onChange={(e) =>
                            setLanguage(e.target.value as Language)
                          }
                        >
                          <option value="en">English</option>
                          <option value="fa">فارسی</option>
                        </select>
                      </label>
                      <label>
                        {t("Theme")}
                        <select
                          aria-label={t("Theme")}
                          value={theme}
                          onChange={(e) => setTheme(e.target.value)}
                        >
                          <option value="dark">{t("Dark")}</option>
                          <option value="light">{t("Light")}</option>
                        </select>
                      </label>
                      <label className="checkbox">
                        <input
                          type="checkbox"
                          checked={notifications}
                          onChange={(e) => {
                            setNotifications(e.target.checked);
                            if (e.target.checked && "Notification" in window)
                              void Notification.requestPermission();
                          }}
                        />
                        {t("Notifications")} · {t("Off by default")}
                      </label>
                      <label className="checkbox">
                        <input
                          type="checkbox"
                          checked={receipts}
                          disabled={!enabled}
                          onChange={(e) => setReceipts(e.target.checked)}
                        />
                        {t("Read receipts")}
                      </label>
                      <label className="checkbox">
                        <input
                          type="checkbox"
                          checked={presence}
                          disabled={!enabled}
                          onChange={(e) => setPresence(e.target.checked)}
                        />
                        {t("Online indicators")} · {t("Off by default")}
                      </label>
                      <label className="checkbox">
                        <input
                          type="checkbox"
                          checked={typing}
                          disabled={!enabled}
                          onChange={(e) => setTyping(e.target.checked)}
                        />
                        {t("Typing indicators")}
                      </label>
                    </section>
                    <section className="card">
                      <h2>{t("Local data and account")}</h2>
                      <button
                        disabled={disabled}
                        onClick={() =>
                          void perform(async () => {
                            if (
                              !confirm(
                                t(
                                  "Permanently clear delivered local history and drafts? Export a recovery kit first. Pending sends and live device keys are preserved.",
                                ),
                              )
                            )
                              return;
                            await vault!.clearDeliveredHistory();
                            setEvents([...vault!.state.events]);
                          })
                        }
                      >
                        {t("Clear delivered local history")}
                      </button>

                      <button
                        disabled={!vault}
                        onClick={() => {
                          if (
                            vault &&
                            confirm(
                              t(
                                "Export decrypted message history to this device? The downloaded file contains sensitive plaintext.",
                              ),
                            )
                          )
                            download(
                              JSON.stringify({
                                format: "haven-history-v1",
                                events: historyForExport(vault.state).events,
                              }),
                              "haven-local-history.json",
                            );
                        }}
                      >
                        {t("Export decrypted local history")}
                      </button>
                      <button onClick={() => setScreen("backup")}>
                        {t("Create an encrypted recovery kit")}
                      </button>
                      <p>
                        {t(
                          "Disabling your account revokes every session and device and pauses group delivery until authorized MLS removal. Recipients retain their copies. Ciphertext and opaque audit records follow retention policy.",
                        )}
                      </p>
                      {user.role !== "superadmin" && (
                        <form
                          onSubmit={(e) => {
                            e.preventDefault();
                            const f = new FormData(e.currentTarget);
                            void perform(async () => {
                              await api("auth/disable", "POST", {
                                password: f.get("password"),
                                confirmation: "DISABLE",
                              });
                              lock();
                              setUser(null);
                              localStorage.removeItem("haven-local-user");
                            });
                          }}
                        >
                          <label>
                            {t("Confirm password to disable account")}
                            <input
                              name="password"
                              type="password"
                              required
                              autoComplete="current-password"
                            />
                          </label>
                          <button className="danger" disabled={disabled}>
                            {t("Disable my account")}
                          </button>
                        </form>
                      )}
                    </section>
                    <section className="card">
                      <h2>{t("Change password")}</h2>
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          const f = new FormData(e.currentTarget);
                          void perform(async () => {
                            await api("auth/change-password", "POST", {
                              old_password: f.get("old"),
                              new_password: f.get("new"),
                            });
                            lock();
                            setUser(null);
                          });
                        }}
                      >
                        <label>
                          {t("Current password")}
                          <input
                            name="old"
                            type="password"
                            required
                            autoComplete="current-password"
                          />
                        </label>
                        <label>
                          {t("New password")}
                          <input
                            name="new"
                            type="password"
                            minLength={14}
                            required
                            autoComplete="new-password"
                          />
                        </label>
                        <button>{t("Change password")}</button>
                      </form>
                      <button
                        className="danger"
                        onClick={() =>
                          void perform(async () => {
                            await logout(true);
                          })
                        }
                      >
                        {t("Log out all sessions")}
                      </button>
                    </section>
                  </>
                )}
                {screen === "admin" && isAdmin && (
                  <>
                    <div className="section-heading">
                      <p>{t("No decrypted message access")}</p>
                      <button onClick={() => void perform(adminRefresh)}>
                        {t("Refresh")}
                      </button>
                    </div>
                    <div className="stat-grid">
                      {["users", "approved_devices", "envelopes", "outbox"].map(
                        (k) => (
                          <div className="stat" key={k}>
                            <small>{k.replaceAll("_", " ")}</small>
                            <strong>{String(system[k] ?? "—")}</strong>
                          </div>
                        ),
                      )}
                    </div>
                    <section className="card">
                      <h2>{t("Invitations")}</h2>
                      <button
                        className="primary"
                        onClick={() =>
                          void perform(async () => {
                            const inv = await api<{ token: string }>(
                              "admin/invitations",
                              "POST",
                              { hours: 24 },
                            );
                            setNewToken(inv.token);
                            await adminRefresh();
                          })
                        }
                      >
                        {t("Create invitation")}
                      </button>
                      {newToken && (
                        <div className="invite-output">
                          <p>
                            {t("Single use · 24h ·")}
                            {t("Invitation token")}
                          </p>
                          <code>{newToken}</code>
                          <QR
                            t={t}
                            value={`${location.origin}/#invite=${newToken}`}
                          />
                          <small>
                            {t(
                              "Share through an independently trusted channel.",
                            )}
                          </small>
                        </div>
                      )}
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>{t("ID")}</th>
                              <th>{t("Status")}</th>
                              <th>{t("Revoke")}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {invitations.map((i) => (
                              <tr key={i.id}>
                                <td>
                                  <code>{i.id.slice(0, 8)}</code>
                                </td>
                                <td>
                                  {i.consumed_at
                                    ? "consumed"
                                    : i.revoked_at
                                      ? "revoked"
                                      : new Date(i.expires_at) < new Date()
                                        ? "expired"
                                        : "available"}
                                </td>
                                <td>
                                  <button
                                    disabled={!!i.revoked_at || !!i.consumed_at}
                                    onClick={() =>
                                      void perform(async () => {
                                        await api(
                                          `admin/invitations/${i.id}/revoke`,
                                          "POST",
                                          {},
                                        );
                                        await adminRefresh();
                                      })
                                    }
                                  >
                                    {t("Revoke")}
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </section>
                    <section className="card">
                      <h2>{t("Accounts")}</h2>
                      {users.map((u) => (
                        <div className="account-row" key={u.id}>
                          <div>
                            <strong>{u.display_name}</strong>
                            {user.role === "superadmin" &&
                              u.role !== "superadmin" && (
                                <select
                                  aria-label={`Role for ${u.username}`}
                                  value={u.role}
                                  onChange={(e) =>
                                    void perform(async () => {
                                      await api(
                                        `admin/users/${u.id}`,
                                        "PATCH",
                                        { role: e.target.value },
                                      );
                                      await adminRefresh();
                                    })
                                  }
                                >
                                  <option value="member">{t("Member")}</option>
                                  <option value="community_admin">
                                    {t("Community admin")}
                                  </option>
                                </select>
                              )}
                            <small>
                              @{u.username} · {u.role}
                            </small>
                          </div>
                          <button
                            disabled={
                              u.role === "superadmin" ||
                              user.role !== "superadmin"
                            }
                            onClick={() =>
                              void perform(async () => {
                                await api(`admin/users/${u.id}`, "PATCH", {
                                  is_active: !u.is_active,
                                });
                                await adminRefresh();
                              })
                            }
                          >
                            {t(u.is_active ? "Suspend" : "Activate")}
                          </button>
                        </div>
                      ))}
                    </section>
                    <section className="card">
                      <h2>{t("Service controls")}</h2>
                      <button
                        onClick={() =>
                          void perform(async () => {
                            await api("admin/system-status", "PATCH", {
                              member_invitations: !system.member_invitations,
                            });
                            await adminRefresh();
                          })
                        }
                      >
                        {t(
                          system.member_invitations
                            ? "Disable member invitations"
                            : "Enable member invitations",
                        )}
                      </button>
                      <button
                        onClick={() =>
                          void perform(async () => {
                            await api("admin/system-status", "PATCH", {
                              invitations_paused: !system.invitations_paused,
                            });
                            await adminRefresh();
                          })
                        }
                      >
                        {system.invitations_paused
                          ? "Resume invitations"
                          : "Pause invitations"}
                      </button>
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          const f = new FormData(e.currentTarget);
                          void perform(async () => {
                            await api("admin/system-status", "PATCH", {
                              maintenance: f.get("maintenance"),
                            });
                            await adminRefresh();
                          });
                        }}
                      >
                        <label>
                          {t("Maintenance banner")}
                          <input name="maintenance" maxLength={300} />
                        </label>
                        <button>{t("Save maintenance banner")}</button>
                      </form>
                    </section>
                    <section className="card">
                      <h2>{t("System status")}</h2>
                      <pre>{JSON.stringify(system, null, 2)}</pre>
                    </section>
                  </>
                )}
                {screen === "help" && (
                  <>
                    <section className="card">
                      <h2>{t("Connection & help")}</h2>
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          const value = String(
                            new FormData(e.currentTarget).get("endpoint"),
                          );
                          void perform(async () => {
                            const u = new URL(value);
                            if (
                              u.protocol !== "https:" ||
                              u.username ||
                              u.password ||
                              u.pathname !== "/" ||
                              u.search ||
                              u.hash ||
                              !/^([0-9]{1,3}\.){3}[0-9]{1,3}$/.test(
                                u.hostname,
                              ) ||
                              u.hostname.split(".").some((x) => Number(x) > 255)
                            )
                              throw new Error(
                                "Enter a trusted HTTPS IPv4 endpoint with no path, credentials or query.",
                              );
                            location.assign(u.origin);
                          });
                        }}
                      >
                        <label>
                          {t("Independently verified standby IP URL")}
                          <input
                            name="endpoint"
                            type="url"
                            placeholder="https://203.0.113.10"
                            required
                          />
                        </label>
                        <p>
                          {t(
                            "A different origin has separate browser keys. Prepare and verify a trusted device before switching endpoints. Use only an independently verified server address.",
                          )}
                        </p>
                        <button>{t("Open verified endpoint")}</button>
                      </form>
                      <p className="connection">
                        <i />
                        {status}
                      </p>
                      <code>
                        {typeof location !== "undefined" ? location.origin : ""}
                      </code>
                      <p>
                        {t(
                          "Use a trusted HTTPS IP address. Never bypass a certificate warning.",
                        )}
                      </p>
                      <p>
                        {t(
                          "Connection lost. Encrypted pending messages remain on this device.",
                        )}
                      </p>
                    </section>
                    <section className="card">
                      <h2>{t("Chat controls")}</h2>
                      <p>
                        {t(
                          "On a computer, Enter sends and Shift + Enter adds a line. On a phone, Return adds a line; tap the arrow to send.",
                        )}
                      </p>
                      <p>
                        {t(
                          "Use the paperclip to choose Photos & videos, Audio, or File. Check the local preview before sending. Files can be up to 25 MiB.",
                        )}
                      </p>
                      <p>
                        {t(
                          "One check means the server accepted your message. A read indicator appears only when a participant shares a read receipt.",
                        )}
                      </p>
                      <p>
                        {t(
                          "Search and drafts stay on this device. Copied messages can remain in clipboard history.",
                        )}
                      </p>
                    </section>
                    <section className="card">
                      <h2>{t("Certificate trust")}</h2>
                      <p>
                        {t(
                          "Use only an independently verified IP endpoint. Public IP certificates expire and need renewal. A private root must be independently verified and installed before connecting; iOS also requires explicit full trust. An invalid certificate blocks the whole page, so this page cannot diagnose it reliably. Keep your verified connection instructions.",
                        )}
                      </p>
                    </section>
                    <section className="card">
                      <h2>{t("Connection guide")}</h2>
                      <p>
                        {t(
                          "There is no remote delivery without a working network route. A compromised device or application origin can disclose messages. Administration cannot recover lost E2EE keys. Standby promotion requires fencing and a separately trusted origin; do not switch to an address sent by an unverified party.",
                        )}
                      </p>
                      <strong>{t("Security qualification pending")}</strong>
                    </section>
                  </>
                )}
              </div>
            )}
          </main>
        </div>
      )}
      <footer>
        <span>
          <Icon name="lock" size={12} />
          {t("Private community")}
        </span>
        <span>{enabled ? "UNREVIEWED" : "CRYPTO_NOT_READY"} · v0.2.0</span>
        <span>
          {pendingApproval
            ? t("Browser approval needed")
            : online
              ? t("Local only")
              : t("Not connected")}
        </span>
      </footer>
    </div>
  );
}
