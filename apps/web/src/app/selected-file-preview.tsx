"use client";

import { useEffect, useRef, useState } from "react";
import { isViewOnceMedia } from "@/lib/attachment-policy";
import { Icon } from "./icons";

// This is the sender's unsent local File, never a recipient's view-once media.
// Do not embed documents, SVG or HTML as active same-origin content.
export function SelectedFilePreview({
  file,
  t,
}: {
  file: File;
  t: (s: string) => string;
}) {
  const kind = isViewOnceMedia(file.type)
    ? file.type.startsWith("image/")
      ? "image"
      : "video"
    : file.type.startsWith("audio/")
      ? "audio"
      : null;
  const img = useRef<HTMLImageElement>(null),
    video = useRef<HTMLVideoElement>(null),
    audio = useRef<HTMLAudioElement>(null);
  const resource = useRef<{
    url: string;
    nodes: (HTMLImageElement | HTMLMediaElement)[];
  } | null>(null);
  const [url, setURL] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    if (!kind) return;
    let live = true;
    const release = () => {
      const current = resource.current;
      resource.current = null;
      if (!current) return;
      for (const node of current.nodes) {
        if (node instanceof HTMLMediaElement) node.pause();
        node.removeAttribute("src");
        if (node instanceof HTMLMediaElement) node.load();
      }
      URL.revokeObjectURL(current.url);
    };
    try {
      const next = URL.createObjectURL(file);
      resource.current = {
        url: next,
        nodes: [img.current, video.current, audio.current].filter(
          (
            node,
          ): node is HTMLImageElement | HTMLVideoElement | HTMLAudioElement =>
            !!node,
        ),
      };
      setURL(next);
    } catch {
      setError(
        "Preview could not be prepared. Choose another file or send without a preview.",
      );
    }
    const end = () => {
      release();
      if (live) setURL("");
    };
    window.addEventListener("haven:lock", end);
    window.addEventListener("pagehide", end);
    return () => {
      live = false;
      window.removeEventListener("haven:lock", end);
      window.removeEventListener("pagehide", end);
      release();
    };
  }, [file, kind]);
  const failed = () => {
    if (resource.current)
      setError(
        "This browser cannot preview this file. Choose another file or send without a preview.",
      );
  };
  return (
    <div className={`selected-file-preview ${kind || "document"}`}>
      {kind === "image" && (
        <img
          ref={img}
          src={url || undefined}
          hidden={!!error}
          alt={t("Selected photo preview")}
          onError={failed}
        />
      )}
      {kind === "video" && (
        <video
          ref={video}
          src={url || undefined}
          hidden={!!error}
          aria-label={t("Selected video preview")}
          controls
          playsInline
          preload="auto"
          onError={failed}
          onLoadedMetadata={(e) => {
            const node = e.currentTarget;
            if (Number.isFinite(node.duration) && node.duration > 0)
              node.currentTime = Math.min(0.001, node.duration / 2);
          }}
        />
      )}
      {kind === "audio" && (
        <audio
          ref={audio}
          src={url || undefined}
          hidden={!!error}
          aria-label={t("Selected audio preview")}
          controls
          preload="metadata"
          onError={failed}
        />
      )}
      {!kind && (
        <div className="selected-file-fallback">
          <Icon name="file" size={30} />
          <span>{t("Preview is not available for this file type.")}</span>
        </div>
      )}
      {kind && !url && !error && <p role="status">{t("Preparing preview…")}</p>}
      {error && <p role="status">{t(error)}</p>}
    </div>
  );
}
