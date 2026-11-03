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
    [busy, setBusy] = useState(false),
    [agreed, setAgreed] = useState(false);
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
          "One approved participating device acts for your entire account. Preparing pauses all your devices. After every affected account agrees, the server removes this conversation and its media. Your archive contains history available on this device; other devices may have additional history or unsent messages. View-once content is never archived.",
        )}
      </p>
      <p role="status">
        {t(
          record?.state === "finalized"
            ? "Finalized"
            : record?.state === "closing"
              ? "All accounts prepared; review your archive"
              : record?.state === "proposed"
                ? "Closure proposed; each account chooses one device to prepare"
                : "Direct chats need both accounts; groups need every affected account, including former members",
        )}
      </p>
      {record?.state === "finalized" && (
        <p>
          {t(
            "Deletion authorized. Cleanup runs automatically after delivery, open media sessions and required security retention finish. Your archive stays local.",
          )}
        </p>
      )}
      <p>
        {t(
          "Preparation cannot be undone. If any account withholds consent or loses authorization, server history is retained.",
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
                    "Prepare this account for closure? Your pending requests and drafts are retained locally. Other devices will stop sending. This conversation cannot reopen after finalization.",
                  ),
                )
              )
                void run(() => vault.prepareClosure(conversation));
            }}
          >
            {t("Prepare my account")}
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
            <label>
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
              />
              {t(
                "I authorize deletion for all my devices, including history or queued messages unavailable here, and files listed as unavailable in my archive.",
              )}
            </label>
            <p>
              {t("Saved local messages")}:{" "}
              {vault.state.closure_archives?.[conversation.id]?.events.length ||
                0}{" "}
              · {t("Saved files")}:{" "}
              {
                Object.keys(
                  vault.state.closure_archives?.[conversation.id]?.files || {},
                ).length
              }{" "}
              · {t("Unconfirmed local messages")}:{" "}
              {vault.state.closure_archives?.[conversation.id]?.unsent
                ?.length || 0}
            </p>
            <p>
              {t("Unavailable or excluded files")}:{" "}
              {vault.state.closure_archives?.[conversation.id]?.omissions
                ?.length || 0}
            </p>
            <button
              disabled={busy || !agreed}
              onClick={() => void run(() => vault.consentClosure(conversation))}
            >
              {t("Authorize account-wide server deletion")}
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
                if (file.size > 90 * 1024 * 1024)
                  throw new Error(
                    "Closure archive exceeds the supported storage limit",
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

export function ClosureInbox({
  vault,
  t,
  changed,
}: {
  vault: Messenger;
  t: (text: string) => string;
  changed: () => void;
}) {
  const [items, setItems] = useState<Conversation[]>([]),
    [selected, setSelected] = useState<string>(),
    [cursor, setCursor] = useState<string | null>(null),
    [error, setError] = useState("");
  async function load(after?: string) {
    try {
      const { api } = await import("@/lib/api");
      const page = await api<{
        items: Conversation[];
        next_cursor: string | null;
      }>("closures/pending" + (after ? "?after=" + after : ""));
      setItems((old) => (after ? [...old, ...page.items] : page.items));
      setCursor(page.next_cursor);
      setError("");
    } catch (e) {
      setError(uiError(e));
    }
  }
  useEffect(() => {
    void load();
  }, [vault]);
  return (
    <section className="card">
      <h2>{t("Conversation closure requests")}</h2>
      <p>
        {t(
          "You can respond here even after leaving a group. One device per account is enough.",
        )}
      </p>
      <button onClick={() => void load()}>{t("Refresh")}</button>
      {error && <p role="alert">{t(error)}</p>}
      {items.map((c) => (
        <details key={c.id} open={selected === c.id}>
          <summary
            onClick={(e) => {
              e.preventDefault();
              setSelected(selected === c.id ? undefined : c.id);
            }}
          >
            {c.kind} · {c.id.slice(0, 8)}
          </summary>
          {selected === c.id && (
            <ClosureControls
              vault={vault}
              conversation={c}
              t={t}
              changed={changed}
            />
          )}
        </details>
      ))}
      {cursor && (
        <button onClick={() => void load(cursor)}>{t("Load more")}</button>
      )}
    </section>
  );
}
