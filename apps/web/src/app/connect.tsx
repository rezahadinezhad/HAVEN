"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import QRCode from "qrcode";
import {
  api,
  RequestError,
  type User,
  type Device,
  type Conversation,
} from "@/lib/api";
import { Messenger, fingerprintOf } from "@/lib/messenger";
import { loadVault } from "@/lib/vault";
import {
  deviceUnlockEnvironment,
  loadDeviceUnlock,
  type DeviceUnlockEnvironment,
} from "@/lib/device-unlock";
import { generateUnlockPassphrase } from "@/lib/passphrase";
import { uiError } from "@/lib/ui-error";
import {
  contactLink,
  readContactLink,
  securityCode,
  type ContactCard,
} from "@/lib/contact-link";
import type { components } from "@/lib/generated/schema";
import { Icon } from "./icons";

type Translate = (text: string) => string;
type Access = components["schemas"]["InvitationAccess"];
type InviteResult = { id: string; token: string; expires_at: string };

function BrowserSetup({
  user,
  ready,
  enabled,
  t,
}: {
  user: User;
  ready: (vault: Messenger) => Promise<void>;
  enabled: boolean;
  t: Translate;
}) {
  const [exists, setExists] = useState<boolean | null>(null);
  const [secret, setSecret] = useState("");
  const [confirmSecret, setConfirmSecret] = useState("");
  const [generated, setGenerated] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [accessed, setAccessed] = useState(false);
  const [saved, setSaved] = useState(false);
  const [copying, setCopying] = useState(false);
  const [copyStatus, setCopyStatus] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [deviceUnlock, setDeviceUnlock] = useState(false);
  const [deviceEnvironment, setDeviceEnvironment] =
    useState<DeviceUnlockEnvironment>("unsupported");
  const active = useRef(true);
  const generatedInput = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    active.current = true;
    void loadVault(user.id)
      .then((value) => {
        if (active.current) setExists(!!value);
      })
      .catch(() => {
        if (active.current)
          setError(
            "Browser storage is unavailable. Keep your existing data and try again.",
          );
      });
    void Promise.all([deviceUnlockEnvironment(), loadDeviceUnlock(user.id)])
      .then(([environment, record]) => {
        if (active.current) {
          setDeviceEnvironment(environment);
          setDeviceUnlock(!!record);
        }
      })
      .catch(() => {
        // Passphrase unlock remains available when this optional store fails.
      });
    return () => {
      active.current = false;
    };
  }, [user.id]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (working || copying || !enabled || exists === null) return;
    if (!exists && generated && (!saved || !accessed)) {
      setError("Save your generated passphrase and confirm before continuing");
      return;
    }
    if (!exists && !generated && secret !== confirmSecret) {
      setError("The unlock passphrases do not match");
      return;
    }
    setWorking(true);
    setError("");
    try {
      const result = exists
        ? await Messenger.unlock(user.id, secret)
        : await Messenger.create(user.id, secret, "This browser");
      if (!active.current) {
        result.lock();
        return;
      }
      setSecret("");
      setConfirmSecret("");
      setCopyStatus("");
      setRevealed(false);
      setAccessed(false);
      await ready(result);
    } catch (e) {
      if (active.current) {
        setError(
          e instanceof Error ? e.message : "Browser setup could not finish",
        );
        // A network failure after local persistence must not replace the keys.
        try {
          setExists(!!(await loadVault(user.id)));
        } catch {
          /* Storage stays fail-closed. */
        }
      }
    } finally {
      if (active.current) setWorking(false);
    }
  }
  async function unlockOnDevice() {
    if (
      working ||
      !enabled ||
      !exists ||
      !deviceUnlock ||
      deviceEnvironment !== "ready"
    )
      return;
    setWorking(true);
    setError("");
    try {
      const result = await Messenger.unlockUsingDevice(user.id);
      if (!active.current) {
        result.lock();
        return;
      }
      await ready(result);
    } catch (e) {
      if (active.current)
        setError(
          e instanceof Error
            ? e.message
            : "Device unlock failed. Use your vault passphrase",
        );
    } finally {
      if (active.current) setWorking(false);
    }
  }
  function generate() {
    if (exists !== false || working || copying || !enabled) return;
    try {
      const value = generateUnlockPassphrase();
      setSecret(value);
      setConfirmSecret("");
      setGenerated(true);
      setRevealed(false);
      setAccessed(false);
      setSaved(false);
      setCopyStatus("");
      setError("");
    } catch {
      setError(
        "Secure passphrase generation is unavailable. Enter your own passphrase or try another trusted browser.",
      );
    }
  }
  async function copyGenerated() {
    if (exists !== false || !generated || !secret || working || copying) return;
    setCopying(true);
    try {
      await navigator.clipboard.writeText(secret);
      if (active.current) {
        setAccessed(true);
        setCopyStatus(
          "Passphrase copied. Save it privately before continuing.",
        );
      }
    } catch {
      if (active.current) {
        setCopyStatus(
          "Automatic copying is unavailable. Choose Show passphrase to select and copy it, or write it down privately.",
        );
      }
    } finally {
      if (active.current) setCopying(false);
    }
  }
  const generatedSetup = exists === false && generated;
  return (
    <section className="connect-setup" aria-labelledby="setup-browser-title">
      <span className="connect-symbol">
        <Icon name="key" size={28} />
      </span>
      <h2 id="setup-browser-title">
        {t(exists ? "Unlock this browser" : "Set up this browser")}
      </h2>
      <p>
        {t(
          exists
            ? "Your private keys are already saved here. Unlock them to continue."
            : "Choose an unlock passphrase to protect your messages on this browser. It stays on this device and must differ from your account password.",
        )}
      </p>
      {!enabled && (
        <p className="connect-warning" role="status">
          {t(
            "Messaging is unavailable until security qualification is complete. An administrator cannot bypass this gate.",
          )}
        </p>
      )}
      <form onSubmit={(e) => void submit(e)}>
        {exists && deviceUnlock && deviceEnvironment === "ready" && (
          <div className="device-unlock-choice">
            <button
              type="button"
              className="primary"
              disabled={!enabled || working}
              onClick={() => void unlockOnDevice()}
            >
              <Icon name="key" size={18} />
              {t("Unlock with this device")}
            </button>
            <small>
              {t(
                "Your device will require verification, which may use fingerprint, face, or device PIN. Your vault passphrase remains the fallback.",
              )}
            </small>
          </div>
        )}
        {exists === false && !generated && (
          <button
            type="button"
            className="generate-passphrase"
            disabled={!enabled || working}
            onClick={generate}
          >
            <Icon name="key" size={18} />
            {t("Generate a secure passphrase")}
          </button>
        )}
        {generatedSetup ? (
          <div className="generated-passphrase">
            <h3>{t("Save your generated passphrase")}</h3>
            <p>
              {t(
                "This passphrase unlocks only this browser’s vault. Save it in your password manager or write it down somewhere private.",
              )}
            </p>
            {revealed ? (
              <>
                <label htmlFor="generated-unlock-passphrase">
                  {t("Generated passphrase")}
                </label>
                <textarea
                  id="generated-unlock-passphrase"
                  ref={generatedInput}
                  readOnly
                  dir="ltr"
                  rows={2}
                  spellCheck={false}
                  autoCapitalize="off"
                  autoComplete="off"
                  value={secret}
                  onFocus={() => generatedInput.current?.select()}
                />
              </>
            ) : (
              <div className="generated-secret-mask">
                {t("Passphrase hidden")}
              </div>
            )}
            <div className="passphrase-actions">
              <button
                type="button"
                disabled={working || copying}
                aria-pressed={revealed}
                onClick={() => {
                  if (!revealed) setAccessed(true);
                  setRevealed(!revealed);
                }}
              >
                {t(revealed ? "Hide passphrase" : "Show passphrase")}
              </button>
              <button
                type="button"
                disabled={working || copying}
                onClick={() => void copyGenerated()}
              >
                {t(copying ? "Copying…" : "Copy passphrase")}
              </button>
            </div>
            {copyStatus && (
              <p className="passphrase-copy-status" role="status">
                {t(copyStatus)}
              </p>
            )}
            <small>
              {t(
                "Clipboard history or sync may retain a copy. HAVEN does not send this passphrase to the server.",
              )}
            </small>
            <label className="check-row">
              <input
                type="checkbox"
                checked={saved}
                disabled={working || copying || !accessed}
                onChange={(e) => {
                  setSaved(e.target.checked);
                  if (
                    e.target.checked &&
                    error ===
                      "Save your generated passphrase and confirm before continuing"
                  )
                    setError("");
                }}
              />
              {t("I’ve saved my passphrase somewhere private")}
            </label>
            {!accessed && (
              <small>
                {t(
                  "Show or copy the passphrase before confirming you saved it.",
                )}
              </small>
            )}
            <div className="passphrase-actions">
              <button
                type="button"
                className="quiet"
                disabled={working || copying || !enabled}
                onClick={generate}
              >
                {t("Generate another")}
              </button>
              <button
                type="button"
                className="quiet"
                disabled={working || copying}
                onClick={() => {
                  setGenerated(false);
                  setSecret("");
                  setConfirmSecret("");
                  setSaved(false);
                  setAccessed(false);
                  setRevealed(false);
                  setCopyStatus("");
                  setError("");
                }}
              >
                {t("Use my own passphrase")}
              </button>
            </div>
          </div>
        ) : (
          <>
            <label>
              {t("Unlock passphrase")}
              <input
                type="password"
                name="haven-vault-passphrase"
                autoComplete={
                  exists
                    ? "section-haven-vault current-password"
                    : "section-haven-vault new-password"
                }
                minLength={20}
                required
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                disabled={working}
              />
            </label>
            <small>
              {t(
                exists
                  ? "You can save this separate vault passphrase in your password manager and use its device verification to fill it."
                  : "Use at least 20 characters. A few unrelated words are easier to remember.",
              )}
            </small>
            {exists && deviceEnvironment === "ip-address" && (
              <small>
                {t(
                  "Built-in device unlock needs a trusted hostname. Direct IP addresses cannot use browser passkeys; your vault remains protected by its passphrase.",
                )}
              </small>
            )}
            {exists === false && (
              <label>
                {t("Confirm unlock passphrase")}
                <input
                  type="password"
                  autoComplete="new-password"
                  minLength={20}
                  required
                  value={confirmSecret}
                  onChange={(e) => setConfirmSecret(e.target.value)}
                  disabled={working}
                />
              </label>
            )}
          </>
        )}
        {error && <p role="alert">{t(error)}</p>}
        <button
          className="primary"
          disabled={
            !enabled ||
            working ||
            copying ||
            exists === null ||
            (generatedSetup && (!saved || !accessed))
          }
        >
          {t(
            working
              ? "Preparing this browser…"
              : exists
                ? "Unlock and continue"
                : "Set up and continue",
          )}
          <Icon name="next" size={18} />
        </button>
      </form>
      <p className="fine">
        {t(
          "Keep a recovery kit after setup. Clearing browser data can permanently remove your keys.",
        )}
      </p>
    </section>
  );
}

function ShareCard({
  value,
  invitation,
  revoke,
  t,
}: {
  value: string;
  invitation: boolean;
  revoke?: () => Promise<void>;
  t: Translate;
}) {
  const [image, setImage] = useState("");
  const [status, setStatus] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    let active = true;
    void QRCode.toDataURL(value, { width: 256, margin: 2 })
      .then((url) => {
        if (active) setImage(url);
      })
      .catch(() => {
        if (active) setImage("");
      });
    return () => {
      active = false;
    };
  }, [value]);
  return (
    <section className="connect-share" aria-labelledby="share-link-title">
      <h2 id="share-link-title">
        {t(invitation ? "Your friend’s invitation" : "Your friend link")}
      </h2>
      <p>
        {t(
          invitation
            ? "Send this link privately. It creates one account, expires in 24 hours, and helps your friend connect with you."
            : "Share this with someone who already has a HAVEN account. They can connect without typing a device ID.",
        )}
      </p>
      <label htmlFor="share-friend-link">{t("Link to share")}</label>
      <textarea
        id="share-friend-link"
        ref={input}
        readOnly
        dir="ltr"
        value={value}
        rows={3}
        onFocus={(e) => e.currentTarget.select()}
      />
      <button
        className="primary"
        onClick={() =>
          void (async () => {
            try {
              await navigator.clipboard.writeText(value);
              setStatus("Link copied");
            } catch {
              input.current?.focus();
              input.current?.select();
              setStatus("Select and copy the link above");
            }
          })()
        }
      >
        {t("Copy link")}
      </button>
      {status && <p role="status">{t(status)}</p>}
      {image && (
        <img
          className="qr"
          src={image}
          width={256}
          height={256}
          alt={t("Friend link QR code")}
        />
      )}
      {invitation && revoke && (
        <button className="quiet" onClick={() => void revoke()}>
          {t("Revoke this invitation")}
        </button>
      )}
    </section>
  );
}

function VerifyCode({
  device,
  expectedName,
  vault,
  confirm,
  t,
}: {
  device: Device;
  expectedName?: string;
  vault: Messenger;
  confirm: (name: string) => Promise<void>;
  t: Translate;
}) {
  const [fingerprint, setFingerprint] = useState("");
  const [name, setName] = useState(
    expectedName || vault.state.contact_names?.[device.id] || "",
  );
  const [compared, setCompared] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void fingerprintOf(device.public_key)
      .then((value) => {
        if (active) setFingerprint(value);
      })
      .catch(() => {
        if (active)
          setError(
            "Could not check the security code. Reconnect and try again.",
          );
      });
    return () => {
      active = false;
    };
  }, [device.public_key]);
  const changed =
    !!vault.state.pins[device.id] &&
    vault.state.pins[device.id] !== device.public_key;
  return (
    <section className="connect-verify" aria-labelledby="verify-code-title">
      <span className="connect-symbol">
        <Icon name="shield" size={28} />
      </span>
      <h2 id="verify-code-title">{t("Compare your friend’s security code")}</h2>
      <p>
        {t(
          "Ask your friend to open Start a chat → My security code. Compare the entire code in person or through another trusted channel. A link by itself does not verify who sent it.",
        )}
      </p>
      <code className="security-code" dir="ltr">
        {securityCode(fingerprint)}
      </code>
      {changed && (
        <p role="alert">
          {t(
            "This friend’s key changed. Stop and verify the change in People & trust. This guide will not replace an existing identity.",
          )}
        </p>
      )}
      <label>
        {t("Friend’s name")}
        <input
          maxLength={80}
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="off"
        />
      </label>
      <label className="check-row">
        <input
          type="checkbox"
          checked={compared}
          onChange={(e) => setCompared(e.target.checked)}
          disabled={changed || busy}
        />
        {t(
          "I compared the entire code with my friend through another trusted channel",
        )}
      </label>
      {error && <p role="alert">{t(error)}</p>}
      <button
        className="primary"
        disabled={!compared || !fingerprint || changed || busy || !name.trim()}
        onClick={() => {
          setBusy(true);
          setError("");
          void confirm(name.trim())
            .catch((e) =>
              setError(
                e instanceof Error ? e.message : "Connection could not finish",
              ),
            )
            .finally(() => setBusy(false));
        }}
      >
        {t(busy ? "Connecting…" : "Verify and continue")}
        <Icon name="next" size={18} />
      </button>
    </section>
  );
}

export function ConnectFlow({
  user,
  vault,
  enabled,
  initialContact,
  ready,
  opened,
  advanced,
  manual,
  conversationType,
  changeConversationType,
  t,
}: {
  user: User;
  vault: Messenger | null;
  enabled: boolean;
  initialContact: ContactCard | null;
  ready: (vault: Messenger) => Promise<void>;
  opened: (conversation: Conversation) => Promise<void>;
  advanced: () => void;
  manual: () => Promise<void>;
  conversationType: "direct" | "group";
  changeConversationType: (value: "direct" | "group") => void;
  t: Translate;
}) {
  const [origin, setOrigin] = useState("");
  const [access, setAccess] = useState<Access | null>(null);
  const [self, setSelf] = useState<Device | null>(null);
  const [trustedBrowsers, setTrustedBrowsers] = useState<Device[]>([]);
  const [recoveryConfigured, setRecoveryConfigured] = useState<boolean | null>(
    null,
  );
  const [mode, setMode] = useState<"choose" | "paste" | "share" | "verify">(
    initialContact ? "paste" : "choose",
  );
  const [input, setInput] = useState("");
  const [peer, setPeer] = useState<Device | null>(null);
  const [contact, setContact] = useState<ContactCard | null>(initialContact);
  const [shared, setShared] = useState("");
  const [issued, setIssued] = useState<InviteResult | null>(null);
  const [ownCode, setOwnCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    setOrigin(location.origin);
    return () => {
      active.current = false;
    };
  }, []);
  async function refresh() {
    const [devices, capability, account] = await Promise.all([
      api<Device[]>("devices"),
      api<Access>("invitations"),
      api<{ recovery_configured: boolean }>("auth/me"),
    ]);
    if (!active.current) return;
    setSelf(
      devices.find((device) => device.id === vault?.state.device_id) || null,
    );
    setAccess(capability);
    setTrustedBrowsers(
      devices.filter(
        (device) =>
          device.trust_state === "approved" &&
          !device.revoked_at &&
          device.id !== vault?.state.device_id,
      ),
    );
    setRecoveryConfigured(account.recovery_configured);
  }
  useEffect(() => {
    if (!vault) return;
    void refresh().catch(() => {
      if (active.current)
        setError("Could not check this browser. Reconnect and try again.");
    });
    void fingerprintOf(vault.state.device.public_key)
      .then((value) => {
        if (active.current) setOwnCode(value.replace(/\s/g, ""));
      })
      .catch(() => {
        if (active.current)
          setError(
            "Could not check the security code. Reconnect and try again.",
          );
      });
  }, [vault]);
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      if (active.current)
        setError(
          e instanceof RequestError && e.status === 429
            ? "Today’s invitation limit has been reached. Try again after the daily reset."
            : uiError(e),
        );
    } finally {
      if (active.current) setBusy(false);
    }
  }
  async function lookup(card: ContactCard) {
    const result = await api<{ device: Device }>(
      `crypto/key-packages/${card.device_id}`,
    );
    if (result.device.user_id === user.id)
      throw new Error(
        "This is one of your own browsers. Share your link with your friend instead.",
      );
    if (result.device.revoked_at || result.device.trust_state !== "approved")
      throw new Error(
        "This friend’s browser is no longer approved. Ask for a new friend link.",
      );
    if (
      (await fingerprintOf(result.device.public_key)).replace(/\s/g, "") !==
      card.fingerprint
    )
      throw new Error(
        "The security code does not match this link. Stop and ask your friend for a new link.",
      );
    if (active.current) {
      setContact(card);
      setPeer(result.device);
      setMode("verify");
    }
  }
  const attempted = useRef(false);
  useEffect(() => {
    if (
      !initialContact ||
      !vault ||
      self?.trust_state !== "approved" ||
      attempted.current
    )
      return;
    attempted.current = true;
    void run(() => lookup(initialContact));
  }, [initialContact, vault, self]);
  if (!vault)
    return (
      <div className="connect-flow">
        <BrowserSetup user={user} ready={ready} enabled={enabled} t={t} />
      </div>
    );
  if (!self)
    return (
      <div className="connect-flow">
        <p role="status">{t("Checking this browser…")}</p>
        {error && <p role="alert">{t(error)}</p>}
        <button
          className="quiet"
          disabled={busy}
          onClick={() => void run(refresh)}
        >
          {t("Try again")}
        </button>
      </div>
    );
  const approved = self.trust_state === "approved" && !self.revoked_at;
  const card: ContactCard = {
    v: 1,
    device_id: vault.state.device_id,
    fingerprint: ownCode,
    name: user.display_name || user.username,
  };
  const reason: Record<string, string> = {
    paused:
      "The administrator has paused new invitations. You can still connect with someone who already has an account.",
    members_disabled:
      "Ask the administrator for a signup invitation. You can still share a friend link with an existing member.",
    daily_limit:
      "Today’s invitation limit has been reached. Try again after the daily reset.",
    pending_limit:
      "You already have three pending invitations. Revoke one before creating another.",
    browser_not_ready:
      "Finish approving this browser before inviting a friend.",
    crypto_unavailable:
      "Messaging is unavailable until security qualification is complete. An administrator cannot bypass this gate.",
  };
  return (
    <div className="connect-flow">
      <div className="connect-browser-status">
        <Icon name={approved ? "shield" : "devices"} />
        <span>
          {t(
            approved ? "This browser is ready" : "This browser needs approval",
          )}
        </span>
      </div>
      {error && (
        <p className="connect-error" role="alert">
          {t(error)}
        </p>
      )}
      {!approved ? (
        <section className="browser-approval-guide">
          <h2>{t("Approve this browser from a trusted device")}</h2>
          <p>
            {t(
              "You’re signed in. One more step protects your messages: a browser already approved for your account must approve this one.",
            )}
          </p>
          {trustedBrowsers.length > 0 && (
            <div className="approved-browser-list">
              <strong>{t("Already approved for your account")}</strong>
              {trustedBrowsers.map((device) => (
                <span key={device.id}>
                  <Icon name="devices" size={18} />
                  <b dir="auto">{device.label}</b>
                </span>
              ))}
            </div>
          )}
          <ol className="approval-steps">
            <li>
              <strong>{t("Open your approved browser")}</strong>
              <p>
                {t(
                  "Visit this same HAVEN address in that browser and unlock its existing vault.",
                )}
              </p>
            </li>
            <li>
              <strong>{t("Compare this browser’s security code")}</strong>
              <p>
                {t(
                  "In People & trust on the approved browser, find this browser, compare the full code below, and choose Verify fingerprint.",
                )}
              </p>
            </li>
            <li>
              <strong>{t("Approve, then come back here")}</strong>
              <p>
                {t(
                  "In Devices on the approved browser, choose Approve enrollment for this browser. Then return here and choose Check approval.",
                )}
              </p>
            </li>
          </ol>
          <h3>{t("This browser’s security code")}</h3>
          <p className="fine">
            {t(
              "This code identifies this browser. Compare all of it; it is not a password to enter.",
            )}
          </p>
          <code className="security-code" dir="ltr">
            {securityCode(ownCode)}
          </code>
          <button
            className="primary"
            disabled={busy || !enabled}
            onClick={() =>
              void run(async () => {
                await vault.connect();
                await vault.package();
                await refresh();
                await ready(vault);
              })
            }
          >
            {t("Check approval")}
          </button>
          <button className="quiet" onClick={advanced}>
            {t("Open device details")}
          </button>
          <details className="approval-help">
            <summary>{t("I can’t access the approved browser")}</summary>
            <p>
              {t(
                "Keep this browser’s vault. Creating another vault will not approve this browser or recover the old keys.",
              )}
            </p>
            <p>
              {t(
                recoveryConfigured === false
                  ? "No account recovery method is configured. You need the original approved browser to continue with this identity. An administrator cannot approve it using an account password."
                  : "If you previously saved a recovery kit, use account recovery from the sign-in screen in a separate browser profile. Recovery replaces the identity and requires your contacts to verify the new one.",
              )}
            </p>
            <p>
              {t(
                "If this was a test account and the original browser is gone, ask for a new invitation and create a separate account. This does not restore the old messages.",
              )}
            </p>
          </details>
        </section>
      ) : (
        <>
          {origin && new URL(origin).hostname.startsWith("127.") && (
            <p className="connect-warning" role="status">
              <Icon name="warning" size={18} />
              {t(
                "Local evaluation only: this address works on this computer. A friend on another device needs a reachable server with trusted HTTPS.",
              )}
            </p>
          )}
          {mode !== "choose" && (
            <button
              className="quiet"
              onClick={() => {
                setMode("choose");
                setPeer(null);
                setError("");
              }}
            >
              <Icon name="back" size={16} />
              {t("Back to connection options")}
            </button>
          )}
          {mode === "choose" && (
            <section>
              <h2>{t("Who would you like to talk to?")}</h2>
              <p>
                {t(
                  "Invite a friend to join, or use the friend link they shared with you. You will compare security codes before chatting.",
                )}
              </p>
              <div className="connect-actions">
                <button
                  className="primary"
                  disabled={busy || !enabled || !ownCode || !access?.allowed}
                  onClick={() =>
                    void run(async () => {
                      const invitation = await api<InviteResult>(
                        "invitations",
                        "POST",
                        { hours: 24 },
                      );
                      if (!active.current) return;
                      setIssued(invitation);
                      setShared(contactLink(origin, card, invitation.token));
                      setMode("share");
                      await refresh();
                    })
                  }
                >
                  <Icon name="plus" />
                  {t("Invite a friend")}
                </button>
                <button
                  disabled={busy}
                  onClick={() => {
                    setMode("paste");
                    setError("");
                  }}
                >
                  <Icon name="people" />
                  {t("I have a friend link")}
                </button>
                <button
                  className="quiet"
                  disabled={busy || !ownCode}
                  onClick={() => {
                    setIssued(null);
                    setShared(contactLink(origin, card));
                    setMode("share");
                  }}
                >
                  {t("Share my friend link")}
                </button>
              </div>
              {access && !access.allowed && (
                <p role="status">
                  {t(reason[access.reason] || "Invitations are unavailable")}
                </p>
              )}
              {access?.remaining_today !== null &&
                access?.remaining_today !== undefined && (
                  <small>
                    {t("Signup invitations left today: {count}").replace(
                      "{count}",
                      String(access.remaining_today),
                    )}
                  </small>
                )}
            </section>
          )}
          {mode === "paste" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void run(() => lookup(readContactLink(input, origin)));
              }}
            >
              <h2>{t("Connect with your friend")}</h2>
              <label htmlFor="paste-friend-link">{t("Friend link")}</label>
              <textarea
                id="paste-friend-link"
                dir="ltr"
                rows={4}
                maxLength={4096}
                required
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="https://…/#connect=…"
              />
              <button className="primary" disabled={busy || !enabled}>
                {t(busy ? "Checking link…" : "Continue")}
              </button>
            </form>
          )}
          {mode === "share" && (
            <ShareCard
              value={shared}
              invitation={!!issued}
              t={t}
              revoke={
                issued
                  ? async () => {
                      await run(async () => {
                        await api(
                          `invitations/${issued.id}/revoke`,
                          "POST",
                          {},
                        );
                        setIssued(null);
                        setShared(contactLink(origin, card));
                        await refresh();
                      });
                    }
                  : undefined
              }
            />
          )}
          {mode === "verify" && peer && (
            <VerifyCode
              key={peer.id}
              device={peer}
              expectedName={contact?.name}
              vault={vault}
              t={t}
              confirm={async (name) => {
                await vault.pin(
                  peer,
                  await fingerprintOf(peer.public_key),
                  name,
                );
                const conversation = await vault.startDirect(peer);
                if (active.current) await opened(conversation);
              }}
            />
          )}
          <details className="connect-own-code">
            <summary>{t("My security code")}</summary>
            <p>
              {t(
                "Your friend compares this code with the one shown for you on their browser.",
              )}
            </p>
            <code className="security-code" dir="ltr">
              {securityCode(ownCode)}
            </code>
          </details>
          {!!access?.pending_invitations.length && (
            <details>
              <summary>{t("Manage pending invitations")}</summary>
              {access.pending_invitations.map((invite) => (
                <div className="connect-invite-row" key={invite.id}>
                  <span>
                    {t("Expires")}:{" "}
                    {new Date(invite.expires_at).toLocaleString()}
                  </span>
                  <button
                    className="quiet"
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        await api(
                          `invitations/${invite.id}/revoke`,
                          "POST",
                          {},
                        );
                        if (issued?.id === invite.id) {
                          setIssued(null);
                          setShared(contactLink(origin, card));
                        }
                        await refresh();
                      })
                    }
                  >
                    {t("Revoke")}
                  </button>
                </div>
              ))}
            </details>
          )}
          <details>
            <summary>{t("Advanced conversation tools")}</summary>
            <p>
              {t(
                "Use manual group creation or device details only when you need them. The guided flow above creates a private chat for you.",
              )}
            </p>
            <label>
              {t("Conversation type")}
              <select
                value={conversationType}
                onChange={(e) =>
                  changeConversationType(e.target.value as "direct" | "group")
                }
              >
                <option value="direct">{t("Direct")}</option>
                <option value="group">{t("Group")}</option>
              </select>
            </label>
            <button disabled={busy} onClick={() => void run(manual)}>
              {t("Create conversation manually")}
            </button>
            <button className="quiet" onClick={advanced}>
              {t("Open device details")}
            </button>
          </details>
        </>
      )}
    </div>
  );
}

export function ConversationVerification({
  conversation,
  vault,
  verified,
  t,
}: {
  conversation: Conversation;
  vault: Messenger;
  verified: () => Promise<void>;
  t: Translate;
}) {
  const [devices, setDevices] = useState<Device[]>([]);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    void api<
      Conversation & {
        members: { device: Device }[];
        genesis: { members: { id: string }[] };
      }
    >(`conversations/${conversation.id}`)
      .then(async (detail) => {
        const list = detail.members.map((member) => member.device);
        for (const historic of detail.genesis.members)
          if (!list.some((device) => device.id === historic.id))
            list.push(
              (
                await api<{ device: Device }>(
                  `crypto/key-packages/${historic.id}`,
                )
              ).device,
            );
        if (active)
          setDevices(
            list.filter(
              (device) => vault.state.pins[device.id] !== device.public_key,
            ),
          );
      })
      .catch(() => {
        if (active)
          setError(
            "Could not check this conversation. Reconnect and try again.",
          );
      });
    return () => {
      active = false;
    };
  }, [conversation.id, vault, revision]);
  if (error) return <p role="alert">{t(error)}</p>;
  if (!devices.length) return null;
  const device = devices[0];
  return (
    <div className="incoming-verification">
      <VerifyCode
        key={device.id}
        device={device}
        vault={vault}
        t={t}
        confirm={async (name) => {
          await vault.pin(device, await fingerprintOf(device.public_key), name);
          if (devices.length === 1) await verified();
          setRevision((value) => value + 1);
        }}
      />
    </div>
  );
}
