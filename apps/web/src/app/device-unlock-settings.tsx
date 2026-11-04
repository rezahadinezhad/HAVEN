"use client";

import { useEffect, useState } from "react";
import { Icon } from "./icons";
import { Messenger } from "@/lib/messenger";
import {
  deviceUnlockEnvironment,
  deviceUnlockError,
  loadDeviceUnlock,
  type DeviceUnlockEnvironment,
} from "@/lib/device-unlock";
import { DeviceUnlockRoute } from "./device-unlock-route";

export function DeviceUnlockSettings({
  vault,
  t,
  hostname = "",
}: {
  vault: Messenger;
  t: (text: string) => string;
  hostname?: string;
}) {
  const [environment, setEnvironment] =
    useState<DeviceUnlockEnvironment>("unsupported");
  const [enrolled, setEnrolled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void Promise.all([deviceUnlockEnvironment(), loadDeviceUnlock(vault.user)])
      .then(([status, record]) => {
        if (!active) return;
        setEnvironment(status);
        setEnrolled(!!record);
      })
      .catch(() => {
        if (active)
          setError("Could not read this browser’s device unlock settings");
      });
    return () => {
      active = false;
    };
  }, [vault]);

  async function change() {
    if (busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (enrolled) {
        await vault.disableDeviceUnlock();
        setEnrolled(false);
        setMessage("Device unlock removed. Your vault passphrase still works.");
      } else {
        await vault.enableDeviceUnlock();
        setEnrolled(true);
        setMessage(
          "Device unlock is ready. Your passphrase remains the fallback.",
        );
      }
    } catch (e) {
      setError(deviceUnlockError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="card device-unlock-settings"
      aria-labelledby="device-unlock-title"
    >
      <h2 id="device-unlock-title" className="settings-section-heading">
        <span className="section-glyph">
          <Icon name="key" size={22} />
        </span>
        {t("Unlock with this device")}
      </h2>
      <p>
        {t(
          "Set up a passkey to unlock your encrypted messages with your device or passkey provider. Your vault passphrase remains the backup.",
        )}
      </p>
      {environment === "ready" ? (
        <>
          <p>
            {t(
              enrolled
                ? "Device unlock is set up on this browser."
                : "Your browser will offer available passkey providers, devices, or security keys. Choose one that supports secure vault unlock.",
            )}
          </p>
          <button type="button" disabled={busy} onClick={() => void change()}>
            {t(
              busy
                ? "Working…"
                : enrolled
                  ? "Remove device unlock"
                  : "Set up device unlock",
            )}
          </button>
        </>
      ) : (
        <>
          <p>
            {t(
              environment === "ip-address"
                ? "This IP-only address cannot use browser passkeys. Use your password manager to fill the vault passphrase; a trusted hostname is required for built-in device unlock."
                : "Built-in device unlock is unavailable in this browser. Keep using the vault passphrase or a password manager.",
            )}
          </p>
          {environment === "ip-address" && (
            <>
              <p>
                {t(
                  "Opening HAVEN at a new hostname creates separate browser storage. Keep this trusted IP tab open to approve the new browser; old message history does not move automatically.",
                )}
              </p>
              <DeviceUnlockRoute hostname={hostname} t={t} />
            </>
          )}
        </>
      )}
      <small>
        {t(
          "Device verification may use biometrics or your device PIN. A browser profile reset, removed passkey, or lost device still requires your saved passphrase and recovery kit.",
        )}
      </small>
      {message && <p role="status">{t(message)}</p>}
      {error && <p role="alert">{t(error)}</p>}
    </section>
  );
}
