"use client";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, RequestError } from "@/lib/api";
import { downloadDecrypt } from "@/lib/media";
import type { FileMeta, LocalEvent } from "@/lib/vault";
import type { Messenger } from "@/lib/messenger";
import { Icon } from "./icons";

type State = "available" | "opened" | "sent" | "unavailable";
type Session = {
  controller: AbortController;
  token: string;
  url: string;
  timer?: ReturnType<typeof setTimeout>;
};
export function ViewOnceMedia({
  meta,
  vault,
  own,
  outgoingState,
  disabled,
  t,
  onChange,
}: {
  meta: FileMeta;
  vault: Messenger;
  own: boolean;
  outgoingState: LocalEvent["state"];
  disabled: boolean;
  t: (value: string) => string;
  onChange: () => void;
}) {
  const [state, setState] = useState<State>(
    own
      ? "sent"
      : vault.state.view_once_opened?.[meta.id]
        ? "opened"
        : "available",
  );
  const [mounted, setMounted] = useState(false),
    [url, setURL] = useState(""),
    [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null),
    video = useRef<HTMLVideoElement>(null),
    image = useRef<HTMLImageElement>(null);
  const session = useRef<Session | null>(null),
    changed = useRef(onChange);
  changed.current = onChange;
  const isVideo = meta.mime.startsWith("video/");
  const remoteClose = (active: Session) =>
    api(`attachments/${meta.id}/view-once/close`, "POST", {
      token: active.token,
    }).catch(() => {});
  function release() {
    const active = session.current;
    if (!active) return;
    session.current = null;
    active.controller.abort();
    clearTimeout(active.timer);
    if (video.current) {
      video.current.pause();
      video.current.removeAttribute("src");
      video.current.load();
    }
    image.current?.removeAttribute("src");
    if (active.url) URL.revokeObjectURL(active.url);
    active.url = "";
    void remoteClose(active);
  }
  function close() {
    release();
    setURL("");
    dialog.current?.close();
  }
  useEffect(() => {
    setMounted(true);
    let live = true;
    const closeHidden = () => {
      if (document.hidden) close();
    };
    const end = () => close();
    window.addEventListener("haven:lock", end);
    window.addEventListener("pagehide", end);
    document.addEventListener("visibilitychange", closeHidden);
    const refresh = () => {
      void api<{ state: State }>(`attachments/${meta.id}/view-once`)
        .then(async (result) => {
          if (!live) return;
          if (["available", "opened", "sent"].includes(result.state))
            setState(
              result.state === "available" &&
                vault.state.view_once_opened?.[meta.id]
                ? "opened"
                : result.state,
            );
          if (
            result.state === "opened" &&
            !vault.state.view_once_opened?.[meta.id]
          ) {
            await vault.markViewOnceOpened(meta.id);
            if (live) changed.current();
          }
        })
        .catch((error) => {
          if (
            live &&
            error instanceof RequestError &&
            [403, 404].includes(error.status)
          )
            setState("unavailable");
        });
    };
    void refresh();
    window.addEventListener("focus", refresh);
    window.addEventListener("online", refresh);
    return () => {
      live = false;
      window.removeEventListener("focus", refresh);
      window.removeEventListener("online", refresh);
      window.removeEventListener("haven:lock", end);
      window.removeEventListener("pagehide", end);
      document.removeEventListener("visibilitychange", closeHidden);
      release();
    };
    // One lifecycle per attachment/vault, independent of live message rerenders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta.id, vault]);
  async function open() {
    if (state !== "available" || disabled || session.current) return;
    const original = { ...meta };
    const active: Session = {
      controller: new AbortController(),
      url: "",
      token: Array.from(crypto.getRandomValues(new Uint8Array(32)), (x) =>
        x.toString(16).padStart(2, "0"),
      ).join(""),
    };
    session.current = active;
    setURL("");
    setError("");
    dialog.current?.showModal();
    active.timer = setTimeout(close, 10 * 60 * 1000);
    let consumed = false;
    try {
      // Fail closed before retrieving any media. A crash cannot grant an offline replay.
      await vault.markViewOnceOpened(meta.id);
      consumed = true;
      setState("opened");
      changed.current();
      active.controller.signal.throwIfAborted();
      const claim = await api<{ expires_at: string }>(
        `attachments/${meta.id}/view-once`,
        "POST",
        { token: active.token },
      );
      if (active.controller.signal.aborted) {
        await remoteClose(active);
        return;
      }
      clearTimeout(active.timer);
      active.timer = setTimeout(
        close,
        Math.max(
          0,
          Math.min(10 * 60 * 1000, Date.parse(claim.expires_at) - Date.now()),
        ),
      );
      const blob = await downloadDecrypt(original, {
        signal: active.controller.signal,
        viewOnceToken: active.token,
      });
      active.controller.signal.throwIfAborted();
      active.url = URL.createObjectURL(blob);
      setURL(active.url);
    } catch {
      if (!active.controller.signal.aborted) {
        release();
        setError(
          consumed
            ? "This view was consumed. It cannot be opened again, even if loading was interrupted."
            : "Could not open media. No media was displayed.",
        );
      }
    } finally {
      // JS strings/Blob memory cannot be guaranteed securely erased.
      original.key = "";
      original.prefix = "";
    }
  }
  const label =
    state === "sent"
      ? outgoingState === "failed"
        ? "View-once media not sent"
        : ["server_accepted", "recipient_synced"].includes(outgoingState)
          ? "View-once media sent"
          : "View-once media queued"
      : state === "opened"
        ? "Opened"
        : state === "unavailable"
          ? "View-once media unavailable"
          : isVideo
            ? "Open video once"
            : "Open photo once";
  return (
    <>
      <button
        className="view-once-card"
        type="button"
        disabled={disabled || state !== "available"}
        onClick={() => void open()}
      >
        <span className="view-once-badge" aria-hidden="true">
          1
        </span>
        <span>
          <strong>{t(label)}</strong>
          <small>
            {t(isVideo ? "Video · view once" : "Photo · view once")}
          </small>
        </span>
        <Icon name={state === "available" ? "next" : "lock"} size={18} />
      </button>
      {state === "available" && (
        <small className="view-once-hint">
          {t("Opening uses your one view, even if interrupted. Stay online.")}
        </small>
      )}
      {mounted &&
        createPortal(
          <dialog
            ref={dialog}
            className="view-once-viewer"
            aria-label={t(isVideo ? "View-once video" : "View-once photo")}
            onCancel={(e) => {
              e.preventDefault();
              close();
            }}
            onClose={close}
            onContextMenu={(e) => e.preventDefault()}
            onDragStart={(e) => e.preventDefault()}
          >
            <header>
              <div>
                <span className="view-once-badge" aria-hidden="true">
                  1
                </span>
                <strong>{t("View once")}</strong>
              </div>
              <button
                type="button"
                className="icon-button"
                aria-label={t("Close view-once media")}
                onClick={close}
              >
                <Icon name="close" />
              </button>
            </header>
            <div className="view-once-stage">
              {url ? (
                isVideo ? (
                  <video
                    ref={video}
                    src={url}
                    aria-label={t("View-once video")}
                    controls
                    autoPlay
                    playsInline
                    preload="auto"
                    controlsList="nodownload noremoteplayback"
                    disablePictureInPicture
                    disableRemotePlayback
                    onEnded={close}
                    onError={() => {
                      release();
                      setURL("");
                      setError(
                        "This view was consumed. It cannot be opened again, even if loading was interrupted.",
                      );
                    }}
                  />
                ) : (
                  <img
                    ref={image}
                    src={url}
                    alt={t("View-once photo")}
                    draggable={false}
                    onError={() => {
                      release();
                      setURL("");
                      setError(
                        "This view was consumed. It cannot be opened again, even if loading was interrupted.",
                      );
                    }}
                  />
                )
              ) : (
                <p role={error ? "alert" : "status"}>
                  {t(error || "Opening encrypted media…")}
                </p>
              )}
            </div>
            <footer>
              {t(
                "Closes when you leave or after 10 minutes. Screen capture cannot be prevented.",
              )}
            </footer>
          </dialog>,
          document.body,
        )}
    </>
  );
}
