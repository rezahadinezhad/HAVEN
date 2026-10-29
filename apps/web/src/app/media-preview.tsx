"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { FileMeta } from "@/lib/vault";
import { downloadDecrypt } from "@/lib/media";
import { fileSizeLabel } from "@/lib/chat-presentation";
import { Icon } from "./icons";

const images = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
  "image/avif",
]);
const videos = new Set(["video/mp4", "video/webm", "video/ogg"]);

export function canPreview(file: FileMeta) {
  return !file.view_once && (images.has(file.mime) || videos.has(file.mime));
}

// Ordinary media only. View-once media must always use its separate consume flow.
export function MediaPreview({
  file,
  t,
}: {
  file: FileMeta;
  t: (s: string) => string;
}) {
  const dialog = useRef<HTMLDialogElement>(null),
    video = useRef<HTMLVideoElement>(null),
    img = useRef<HTMLImageElement>(null);
  const active = useRef<{ controller: AbortController; url: string } | null>(
    null,
  );
  const [mounted, setMounted] = useState(false),
    [url, setURL] = useState(""),
    [error, setError] = useState("");
  const isVideo = videos.has(file.mime);
  function release() {
    active.current?.controller.abort();
    if (video.current) {
      video.current.pause();
      video.current.removeAttribute("src");
      video.current.load();
    }
    img.current?.removeAttribute("src");
    if (active.current?.url) URL.revokeObjectURL(active.current.url);
    active.current = null;
  }
  function close() {
    release();
    setURL("");
    dialog.current?.close();
  }
  useEffect(() => {
    setMounted(true);
    const hidden = () => {
      if (document.hidden) close();
    };
    window.addEventListener("haven:lock", close);
    window.addEventListener("pagehide", close);
    document.addEventListener("visibilitychange", hidden);
    return () => {
      release();
      window.removeEventListener("haven:lock", close);
      window.removeEventListener("pagehide", close);
      document.removeEventListener("visibilitychange", hidden);
    };
  }, []);
  async function open() {
    if (!canPreview(file) || active.current) return;
    setError("");
    setURL("");
    const session = { controller: new AbortController(), url: "" };
    active.current = session;
    dialog.current?.showModal();
    try {
      const blob = await downloadDecrypt(file, {
        signal: session.controller.signal,
      });
      if (active.current !== session || session.controller.signal.aborted)
        return;
      session.url = URL.createObjectURL(new Blob([blob], { type: file.mime }));
      setURL(session.url);
    } catch {
      if (!session.controller.signal.aborted)
        setError(
          "Media unavailable or integrity check failed. Close and try again.",
        );
    }
  }
  if (!canPreview(file)) return null;
  return (
    <>
      <button
        type="button"
        className="media-preview-trigger"
        onClick={() => void open()}
      >
        <span className="media-type-icon">
          <Icon name={isVideo ? "play" : "image"} size={25} />
        </span>
        <span>
          <strong>{t(isVideo ? "Open video" : "Open photo")}</strong>
          <small dir="auto">{file.name}</small>
          <small>
            <bdi>{fileSizeLabel(file.size, document.documentElement.lang)}</bdi>{" "}
            · {t("Decrypt on this device")}
          </small>
        </span>
      </button>
      {mounted &&
        createPortal(
          <dialog
            ref={dialog}
            className="media-viewer"
            aria-label={t(isVideo ? "Video preview" : "Photo preview")}
            onCancel={(e) => {
              e.preventDefault();
              close();
            }}
            onClose={close}
          >
            <header>
              <span dir="auto">{file.name}</span>
              <button
                type="button"
                className="quiet icon-button"
                onClick={close}
                aria-label={t("Close preview")}
              >
                <Icon name="close" />
              </button>
            </header>
            <div className="media-preview-stage">
              {error ? (
                <p role="alert">{t(error)}</p>
              ) : url ? (
                isVideo ? (
                  <video
                    ref={video}
                    src={url}
                    controls
                    playsInline
                    preload="metadata"
                  />
                ) : (
                  <img ref={img} src={url} alt={t("Shared photo")} />
                )
              ) : (
                <p role="status">{t("Decrypting media on this device…")}</p>
              )}
            </div>
          </dialog>,
          document.body,
        )}
    </>
  );
}
