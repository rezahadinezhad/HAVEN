"use client";
import { useEffect, useState } from "react";
import type { Conversation } from "@/lib/api";
import type { Messenger } from "@/lib/messenger";
import type { ClosureRecord } from "@/lib/closure-protocol";
import { uiError } from "@/lib/ui-error";

export function ClosureControls({
  vault,
  conversation,
  t,
  changed,
}: {
  vault: Messenger;
  conversation: Conversation;
  t: (text: string) => string;
  changed: () => void;
}) {
  const [record, setRecord] = useState<ClosureRecord | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    void vault
      .refreshClosure(conversation)
      .then((value) => {
        if (active) setRecord(value);
      })
      .catch((e) => {
        if (active) setError(uiError(e));
      });
    return () => {
      active = false;
    };
  }, [vault, conversation.id, conversation.status, conversation.closure_state]);
  async function run(action: () => Promise<ClosureRecord>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await action();
      setRecord(result);
      changed();
    } catch (e) {
      setError(uiError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label={t("Mutual conversation closure")}>
      <h3>{t("Mutual conversation closure")}</h3>
      <p>
        {t(
          "Experimental: both devices must save verified text history. Preparing stops this device from sending; this prototype cannot reopen a prepared conversation. Server deletion is disabled.",
        )}
      </p>
      <p role="status">
        {t(
          record?.state === "finalized"
            ? "Finalized"
            : record?.state === "closing"
              ? "Both devices prepared; save your final archive"
              : record?.state === "proposed"
                ? "Closure proposed; both devices must prepare the same head"
                : "Text-only direct conversation; one approved device per account",
        )}
      </p>
      {error && <p role="alert">{t(error)}</p>}
      <div className="actions">
        <button
          disabled={busy}
          onClick={() => void run(() => vault.refreshClosure(conversation))}
        >
          {t("Check closure status")}
        </button>
        {record?.state === "active" && (
          <button
            disabled={busy}
            onClick={() => void run(() => vault.proposeClosure(conversation))}
          >
            {t("Propose mutual closure")}
          </button>
        )}
        {record?.state === "proposed" && (
          <button
            disabled={busy}
            onClick={() => {
              if (
                confirm(
                  t(
                    "Finish pending sends and drafts first. Preparing permanently pauses this device in this conversation. Continue?",
                  ),
                )
              )
                void run(() => vault.prepareClosure(conversation));
            }}
          >
            {t("Prepare this device")}
          </button>
        )}
        {record?.state === "closing" && (
          <>
            <button
              disabled={busy}
              onClick={() => void run(() => vault.prepareClosure(conversation))}
            >
              {t("Save verified archive")}
            </button>
            <button
              disabled={busy}
              onClick={() => void run(() => vault.consentClosure(conversation))}
            >
              {t("Confirm my archive and close")}
            </button>
          </>
        )}
      </div>
    </section>
  );
}

export function ClosureArchiveImport({
  vault,
  t,
  changed,
}: {
  vault: Messenger;
  t: (text: string) => string;
  changed: () => void;
}) {
  const [secret, setSecret] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <section className="card">
      <h2>{t("Restore a closed conversation archive")}</h2>
      <p>
        {t(
          "Use the unlock passphrase from when you exported it. Restoring adds local history; it does not restore live device keys or verify a friend's identity.",
        )}
      </p>
      <label>
        {t("Archive passphrase")}
        <input
          type="password"
          autoComplete="off"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
        />
      </label>
      <label>
        {t("Encrypted conversation archive")}
        <input
          type="file"
          accept="application/json"
          disabled={busy || !secret}
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (!file || busy) return;
            setBusy(true);
            setError("");
            void (async () => {
              try {
                if (file.size > 6 * 1024 * 1024)
                  throw new Error(
                    "Closure archive exceeds the prototype limit",
                  );
                await vault.importClosureArchive(await file.text(), secret);
                setSecret("");
                changed();
              } catch (err) {
                setError(uiError(err));
              } finally {
                setBusy(false);
              }
            })();
          }}
        />
      </label>
      {error && <p role="alert">{t(error)}</p>}
    </section>
  );
}
