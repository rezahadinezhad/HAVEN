"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import { positionPopover } from "./chat-thread";
import { fileSizeLabel } from "@/lib/chat-presentation";
import { isViewOnceMedia } from "@/lib/attachment-policy";
import { SelectedFilePreview } from "./selected-file-preview";

const emojiChoices = [
  "😊",
  "❤️",
  "👍",
  "🙏",
  "😂",
  "🎉",
  "👋",
  "✨",
  "🤍",
  "👌",
  "🌱",
  "💙",
];
type Translate = (text: string) => string;

export function ChatComposer({
  draft,
  change,
  saveDraft,
  send,
  attach,
  voice,
  discardRecording,
  recording,
  disabled,
  reply,
  cancelReply,
  online,
  blockedReason,
  t,
}: {
  draft: string;
  change: (text: string) => void;
  saveDraft: () => void;
  send: () => void;
  attach: (file: File, viewOnce: boolean) => void;
  voice: () => void;
  discardRecording: () => void;
  recording: boolean;
  disabled: boolean;
  reply?: { editing: boolean; author: string; text: string };
  cancelReply: () => void;
  online: boolean;
  blockedReason: string;
  t: Translate;
}) {
  const input = useRef<HTMLTextAreaElement>(null),
    picker = useRef<HTMLDivElement>(null),
    attachmentMenu = useRef<HTMLDivElement>(null),
    mediaInput = useRef<HTMLInputElement>(null),
    audioInput = useRef<HTMLInputElement>(null),
    fileInput = useRef<HTMLInputElement>(null),
    selectionId = useRef(0);
  const composing = useRef(false),
    selection = useRef({ start: 0, end: 0 });
  const [elapsed, setElapsed] = useState(0);
  const [selectionFile, setSelectionFile] = useState<{
    id: number;
    file: File;
    viewOnce: boolean;
  } | null>(null);
  const selectedFile = selectionFile?.file;
  const supportsViewOnce = !!selectedFile && isViewOnceMedia(selectedFile.type);
  const viewOnce = supportsViewOnce && selectionFile?.viewOnce === true;
  const [fileError, setFileError] = useState("");
  useEffect(() => {
    const clear = () => setSelectionFile(null);
    window.addEventListener("haven:lock", clear);
    window.addEventListener("pagehide", clear);
    return () => {
      window.removeEventListener("haven:lock", clear);
      window.removeEventListener("pagehide", clear);
    };
  }, []);
  function selectFile(
    file: File | undefined,
    category: "media" | "audio" | "file",
  ) {
    if (!file || disabled || recording) return;
    setFileError("");
    if (file.size > 25 * 1024 * 1024) {
      setFileError("File exceeds 25 MiB");
      setSelectionFile(null);
      return;
    }
    if (category === "media" && !/^(image|video)\//.test(file.type)) {
      setFileError("Choose a photo or video, or use File for other types.");
      setSelectionFile(null);
      return;
    }
    if (category === "audio" && !file.type.startsWith("audio/")) {
      setFileError("Choose an audio file, or use File for other types.");
      setSelectionFile(null);
      return;
    }
    setSelectionFile({ id: ++selectionId.current, file, viewOnce: false });
  }
  const cancel = () => {
    cancelReply();
    input.current?.focus();
  };
  useLayoutEffect(() => {
    const node = input.current;
    if (!node) return;
    node.style.height = "44px";
    node.style.height = `${Math.min(144, node.scrollHeight)}px`;
  }, [draft]);
  useEffect(() => {
    if (!reply) return;
    input.current?.focus();
  }, [reply?.editing, reply?.author, reply?.text]);
  useEffect(() => {
    if (!recording) {
      setElapsed(0);
      return;
    }
    const started = Date.now();
    const timer = setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, [recording]);
  return (
    <div className="composer-area">
      {blockedReason && (
        <p className="composer-status" role="status">
          <Icon name="lock" size={15} />
          {t(blockedReason)}
        </p>
      )}
      {!online && !blockedReason && (
        <p className="composer-status" role="status">
          <Icon name="clock" size={15} />
          {t(
            "Offline · messages will wait on this device until you reconnect.",
          )}
        </p>
      )}
      {reply && (
        <div className="reply composer-context">
          <Icon name={reply.editing ? "edit" : "reply"} size={20} />
          <span>
            <strong dir="auto">
              {reply.editing
                ? t("Edit message")
                : `${t("Reply to")} ${reply.author}`}
            </strong>
            <span dir="auto">{reply.text}</span>
          </span>
          <button
            type="button"
            className="quiet icon-button"
            aria-label={t(reply.editing ? "Cancel edit" : "Cancel reply")}
            onClick={cancel}
          >
            <Icon name="close" size={18} />
          </button>
        </div>
      )}
      {recording && (
        <div className="recording-status" role="status">
          <span className="recording-dot" />
          {t("Recording voice note")}
          <bdi>
            {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
          </bdi>
          <span>{t("Stop to send · up to 2 minutes")}</span>
          <button type="button" className="quiet" onClick={discardRecording}>
            {t("Discard recording")}
          </button>
        </div>
      )}
      {selectedFile && (
        <section
          className="attachment-confirmation"
          aria-label={t("Attachment preview")}
        >
          <header className="attachment-preview-heading">
            <Icon name="attachment" size={22} />
            <span>
              <strong dir="auto">{selectedFile.name}</strong>
              <small>
                <bdi>
                  {fileSizeLabel(
                    selectedFile.size,
                    document.documentElement.lang,
                  )}
                </bdi>{" "}
                · {t(viewOnce ? "View once" : "Ordinary attachment")}
              </small>
            </span>
            <button
              type="button"
              className="quiet icon-button"
              aria-label={t("Remove attachment")}
              onClick={() => setSelectionFile(null)}
            >
              <Icon name="close" size={18} />
            </button>
          </header>
          <div
            className="attachment-preview-body"
            tabIndex={0}
            aria-label={t("Preview content")}
          >
            <SelectedFilePreview
              key={selectionFile!.id}
              file={selectedFile}
              t={t}
            />
            {supportsViewOnce && (
              <div className="attachment-view-mode">
                <label className="view-once-toggle">
                  <input
                    type="checkbox"
                    checked={viewOnce}
                    aria-label={t("View once photos and videos")}
                    aria-describedby={
                      viewOnce ? "attachment-view-once-notice" : undefined
                    }
                    disabled={disabled || recording}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setSelectionFile((current) =>
                        current ? { ...current, viewOnce: checked } : null,
                      );
                    }}
                  />
                  <span className="view-once-badge" aria-hidden="true">
                    1
                  </span>
                  {t("View once")}
                </label>
                {viewOnce && (
                  <p
                    id="attachment-view-once-notice"
                    className="view-once-explanation"
                  >
                    {t(
                      "No reopening in HAVEN. Recipients can still capture the screen. One view per person across devices.",
                    )}{" "}
                    {t(
                      "Opening is recorded to enforce the limit, even with read receipts off.",
                    )}
                  </p>
                )}
              </div>
            )}
          </div>
          <footer className="attachment-preview-actions">
            <button
              type="button"
              className="primary"
              disabled={disabled || recording}
              onClick={() => {
                if (disabled || recording) return;
                attach(selectedFile, viewOnce);
                setSelectionFile(null);
              }}
            >
              {t("Send attachment")}
            </button>
          </footer>
        </section>
      )}
      {fileError && (
        <p className="composer-status error" role="alert">
          {t(fileError)}
        </p>
      )}
      <form
        className="composer"
        aria-label={t("Message composer")}
        onSubmit={(e) => {
          e.preventDefault();
          if (!disabled && !recording && draft.trim()) send();
        }}
      >
        <button
          type="button"
          className="quiet icon-button file-button"
          title={t("Add attachment")}
          aria-label={t("Add attachment")}
          disabled={disabled || recording}
          popoverTarget="attachment-menu"
          onClick={(e) =>
            positionPopover(
              e.currentTarget,
              attachmentMenu.current,
              224,
              280,
              true,
            )
          }
        >
          <Icon name="attachment" size={23} />
        </button>
        <div
          ref={attachmentMenu}
          id="attachment-menu"
          popover="auto"
          className="attachment-menu"
          aria-label={t("Choose an attachment type")}
        >
          {(
            [
              [
                "media",
                "image",
                "Photos & videos",
                "Choose from your gallery",
                mediaInput,
              ],
              ["audio", "music", "Audio", "Music and audio files", audioInput],
              ["file", "file", "File", "Documents and other files", fileInput],
            ] as const
          ).map(([category, icon, label, description, ref]) => (
            <button
              type="button"
              key={category}
              aria-label={t(label)}
              disabled={disabled || recording}
              onClick={() => {
                ref.current?.click();
                attachmentMenu.current?.hidePopover();
              }}
            >
              <span className={`attachment-type-icon ${category}`}>
                <Icon name={icon} size={24} />
              </span>
              <span>
                <strong>{t(label)}</strong>
                <small>{t(description)}</small>
              </span>
            </button>
          ))}
        </div>
        <input
          className="attachment-picker"
          hidden
          ref={mediaInput}
          type="file"
          accept="image/*,video/*"
          aria-label={t("Choose photos and videos")}
          disabled={disabled || recording}
          onChange={(e) => {
            selectFile(e.target.files?.[0], "media");
            e.target.value = "";
          }}
        />
        <input
          className="attachment-picker"
          hidden
          ref={audioInput}
          type="file"
          accept="audio/*"
          aria-label={t("Choose audio")}
          disabled={disabled || recording}
          onChange={(e) => {
            selectFile(e.target.files?.[0], "audio");
            e.target.value = "";
          }}
        />
        <input
          className="attachment-picker"
          hidden
          ref={fileInput}
          type="file"
          aria-label={t("Choose a file")}
          disabled={disabled || recording}
          onChange={(e) => {
            selectFile(e.target.files?.[0], "file");
            e.target.value = "";
          }}
        />
        <textarea
          ref={input}
          value={draft}
          rows={1}
          dir="auto"
          placeholder={t(
            reply?.editing ? "Edit your message" : "Write a message…",
          )}
          aria-label={t("Message")}
          disabled={disabled || recording}
          onCompositionStart={() => {
            composing.current = true;
          }}
          onCompositionEnd={() => {
            composing.current = false;
          }}
          onChange={(e) => change(e.target.value)}
          onBlur={saveDraft}
          onSelect={(e) => {
            selection.current = {
              start: e.currentTarget.selectionStart,
              end: e.currentTarget.selectionEnd,
            };
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape" && reply) {
              e.preventDefault();
              cancel();
            }
            // Mobile keyboards keep Return as a newline. Never send an IME confirmation.
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing &&
              !composing.current &&
              e.nativeEvent.keyCode !== 229 &&
              window.matchMedia("(hover: hover) and (pointer: fine)").matches
            ) {
              e.preventDefault();
              if (!disabled && draft.trim()) send();
            }
          }}
        />
        <button
          type="button"
          className="quiet icon-button emoji-trigger"
          aria-label={t("Add emoji")}
          title={t("Add emoji")}
          disabled={disabled || recording}
          popoverTarget="composer-emoji"
          onClick={(e) => positionPopover(e.currentTarget, picker.current, 156)}
        >
          <Icon name="emoji" size={23} />
        </button>
        <div
          ref={picker}
          id="composer-emoji"
          popover="auto"
          className="emoji-picker"
          aria-label={t("Choose an emoji")}
        >
          {emojiChoices.map((emoji) => (
            <button
              type="button"
              key={emoji}
              aria-label={emoji}
              onClick={() => {
                const { start, end } = selection.current;
                const next = draft.slice(0, start) + emoji + draft.slice(end);
                change(next);
                picker.current?.hidePopover();
                requestAnimationFrame(() => {
                  input.current?.focus();
                  input.current?.setSelectionRange(
                    start + emoji.length,
                    start + emoji.length,
                  );
                });
              }}
            >
              {emoji}
            </button>
          ))}
        </div>
        <button
          type="button"
          className={`voice-button icon-button ${recording ? "is-recording" : ""}`}
          title={t(recording ? "Stop recording" : "Record voice note")}
          aria-label={t(recording ? "Stop recording" : "Record voice note")}
          disabled={disabled}
          onClick={voice}
        >
          <Icon name={recording ? "stop" : "microphone"} size={22} />
        </button>
        <button
          type="submit"
          className="primary send-button icon-button"
          title={t(reply?.editing ? "Save edit" : "Send")}
          aria-label={t("Send")}
          disabled={disabled || recording || !draft.trim()}
        >
          <Icon name={reply?.editing ? "check" : "send"} size={22} />
        </button>
      </form>
    </div>
  );
}
