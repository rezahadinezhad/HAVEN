"use client";
import { useState, type FormEvent } from "react";
import { Messenger } from "@/lib/messenger";
import { unseal, type Sealed, type VaultState } from "@/lib/vault";
import { api, type User } from "@/lib/api";
export function AccountRecovery({
  complete,
  t,
}: {
  complete: (user: User, vault: Messenger) => void;
  t: (text: string) => string;
}) {
  const [file, setFile] = useState<File>(),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      if (!file || file.size > 256 * 1024 * 1024)
        throw new Error(
          "Select your encrypted recovery kit (maximum 256 MiB).",
        );
      const kit = JSON.parse(await file.text()) as {
        format: string;
        scope: string;
        sealed: Sealed;
      };
      if (kit.format !== "haven-recovery-v2-history-only")
        throw new Error("Unsupported recovery kit");
      const history = await unseal<VaultState>(
        String(data.get("recovery")),
        kit.scope,
        kit.sealed,
      );
      const vault = await Messenger.recover(
        kit.scope,
        String(data.get("unlock")),
        history,
        String(data.get("password")),
        String(data.get("label")),
      );
      const result = await api<{ user: User }>("auth/me");
      complete(result.user, vault);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recovery failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <details>
      <summary>{t("Recover an account using an offline recovery kit")}</summary>
      <p>
        {t(
          "Use a separate browser profile. Recovery revokes every old device and pauses affected groups. Saved history is restored locally; contacts must independently verify and add your fresh device. Account passwords cannot recover message keys.",
        )}
      </p>
      <form onSubmit={submit}>
        <label>
          {t("Encrypted recovery kit")}
          <input
            type="file"
            accept="application/json"
            required
            onChange={(e) => setFile(e.target.files?.[0])}
          />
        </label>
        <label>
          {t("Separate recovery key")}
          <input name="recovery" type="password" required autoComplete="off" />
        </label>
        <label>
          {t("New account password")}
          <input
            name="password"
            type="password"
            minLength={12}
            maxLength={256}
            required
            autoComplete="new-password"
          />
        </label>
        <label>
          {t("New device unlock secret")}
          <input
            name="unlock"
            type="password"
            minLength={20}
            required
            autoComplete="new-password"
          />
        </label>
        <label>
          {t("Device label")}
          <input name="label" required maxLength={80} />
        </label>
        <button disabled={busy}>
          {t("Reset account security and recover saved history")}
        </button>
        {error && <p role="alert">{error}</p>}
      </form>
    </details>
  );
}
