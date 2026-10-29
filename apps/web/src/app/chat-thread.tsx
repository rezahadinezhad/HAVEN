"use client";

import {
  Fragment,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { Language } from "@/lib/i18n";
import {
  deliveryLabel,
  messagePreview,
  type Message,
} from "@/lib/chat-presentation";
import { Icon, type IconName } from "./icons";

type Translate = (text: string) => string;
export type MessageAction = "reply" | "edit" | "delete" | "reaction";

// Native popovers escape the scrolling thread, dismiss on Escape/outside click,
// and return keyboard focus to their trigger. No message text goes to a service.
export function positionPopover(
  trigger: HTMLElement,
  panel: HTMLElement | null,
  height = 230,
  width = 208,
  alignStart = false,
) {
  if (!panel) return;
  const rect = trigger.getBoundingClientRect();
  const left =
    alignStart && getComputedStyle(trigger).direction !== "rtl"
      ? rect.left
      : rect.right - width;
  panel.style.left = `${Math.max(8, Math.min(left, window.innerWidth - width - 12))}px`;
  panel.style.top = `${Math.max(8, rect.bottom + height > window.innerHeight ? rect.top - height : rect.bottom + 6)}px`;
}

function MessageMenu({
  message,
  own,
  disabled,
  t,
  action,
  feedback,
}: {
  message: Message;
  own: boolean;
  disabled: boolean;
  t: Translate;
  action: (kind: MessageAction, message: Message) => void;
  feedback: (text: string) => void;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const id = `message-actions-${message.event.id}`;
  const choose = (kind: MessageAction) => {
    panel.current?.hidePopover();
    action(kind, message);
  };
  const menuButton = (kind: MessageAction, name: string, icon: IconName) => (
    <button type="button" disabled={disabled} onClick={() => choose(kind)}>
      <Icon name={icon} size={18} />
      {t(name)}
    </button>
  );
  return (
    <div className="message-tools">
      <button
        type="button"
        className="quiet icon-button"
        aria-label={t("Reply")}
        title={t("Reply")}
        disabled={disabled}
        onClick={() => action("reply", message)}
      >
        <Icon name="reply" size={17} />
      </button>
      <button
        type="button"
        className="quiet icon-button"
        aria-label={t("Message actions")}
        title={t("Message actions")}
        popoverTarget={id}
        onClick={(e) => positionPopover(e.currentTarget, panel.current)}
      >
        <Icon name="more" size={20} />
      </button>
      <div
        id={id}
        ref={panel}
        popover="auto"
        className="message-actions"
        aria-label={t("Message actions")}
      >
        {menuButton("reply", "Reply", "reply")}
        {message.text && !message.event.file?.view_once && (
          <button
            type="button"
            onClick={async () => {
              panel.current?.hidePopover();
              try {
                await navigator.clipboard.writeText(message.text);
                feedback("Message copied. Clipboard history may keep a copy.");
              } catch {
                feedback(
                  "Could not copy. Select the message text to copy it manually.",
                );
              }
            }}
          >
            <Icon name="copy" size={18} />
            {t("Copy text")}
          </button>
        )}
        {menuButton("reaction", "Send a heart", "heart")}
        {own &&
          message.event.type === "text" &&
          menuButton("edit", "Edit", "edit")}
        {own && menuButton("delete", "Delete", "delete")}
      </div>
    </div>
  );
}

export function ChatThread({
  messages,
  allMessages,
  receiptIds,
  self,
  language,
  query,
  senderName,
  attachment,
  disabled,
  action,
  feedback,
  bottomChanged,
  t,
}: {
  messages: Message[];
  allMessages: Message[];
  self?: string;
  language: Language;
  query: string;
  receiptIds: ReadonlySet<string>;
  senderName: (id: string) => string;
  attachment: (message: Message) => ReactNode;
  disabled: boolean;
  action: (kind: MessageAction, message: Message) => void;
  feedback: (text: string) => void;
  bottomChanged: (bottom: boolean) => void;
  t: Translate;
}) {
  const log = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true),
    initial = useRef(true),
    previousLast = useRef("");
  const [away, setAway] = useState(false),
    [newMessages, setNewMessages] = useState(false);
  const callback = useRef(bottomChanged);
  callback.current = bottomChanged;
  const last = messages.at(-1)?.event;
  const jump = () => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
    atBottom.current = true;
    setAway(false);
    setNewMessages(false);
    callback.current(true);
  };
  useLayoutEffect(() => {
    if (
      !query &&
      (initial.current ||
        (last?.id !== previousLast.current &&
          (atBottom.current || last?.sender === self)))
    )
      jump();
    else if (last?.id && last.id !== previousLast.current && !query)
      setNewMessages(true);
    previousLast.current = last?.id || "";
    initial.current = false;
  }, [messages.length, last?.id, query, self]);
  useEffect(() => {
    const content = log.current?.firstElementChild;
    if (!content) return;
    const observer = new ResizeObserver(() => {
      if (atBottom.current && !query) jump();
    });
    observer.observe(content);
    return () => observer.disconnect();
  }, [query]);
  const locale = language === "fa" ? "fa-IR" : "en";
  const dayKey = (time: string) => new Date(time).toDateString();
  const today = new Date().toDateString();
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const byId = new Map(
    allMessages.map((message) => [message.event.id, message]),
  );
  return (
    <div className="thread-surface">
      <div
        ref={log}
        className="message-log"
        role="log"
        aria-label={t("Messages in this conversation")}
        aria-live="polite"
        aria-relevant="additions text"
        onScroll={() => {
          const node = log.current!;
          const bottom =
            node.scrollHeight - node.scrollTop - node.clientHeight < 72;
          atBottom.current = bottom;
          setAway(!bottom);
          if (bottom) setNewMessages(false);
          callback.current(bottom);
        }}
      >
        <div className="thread-messages">
          {!messages.length && (
            <div className="thread-empty">
              <span className="thread-empty-icon">
                <Icon name={query ? "search" : "messages"} size={28} />
              </span>
              <strong>
                {t(
                  query ? "No matching messages" : "A fresh start. Say hello.",
                )}
              </strong>
              <p>
                {t(
                  query
                    ? "Try another word. Search only covers messages saved on this device."
                    : "Send a message, share a photo, or record a voice note.",
                )}
              </p>
            </div>
          )}
          {messages.map((message, index) => {
            const item = message.event,
              previous = messages[index - 1]?.event;
            const own = item.sender === self;
            const day = dayKey(item.time);
            const newDay = !previous || dayKey(previous.time) !== day;
            const grouped =
              !newDay &&
              previous?.sender === item.sender &&
              Date.parse(item.time) - Date.parse(previous.time) < 300000;
            const replied = item.reply ? byId.get(item.reply) : undefined;
            const read = receiptIds.has(item.id);
            const status = deliveryLabel(item.state, read);
            return (
              <Fragment key={item.id}>
                {newDay && (
                  <div className="day-separator">
                    <span>
                      {day === today
                        ? t("Today")
                        : day === yesterday.toDateString()
                          ? t("Yesterday")
                          : new Date(item.time).toLocaleDateString(locale, {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            })}
                    </span>
                  </div>
                )}
                <article
                  tabIndex={-1}
                  className={`bubble${own ? " own" : ""}${grouped ? " grouped" : ""}${message.deleted ? " deleted" : ""}`}
                  data-message-id={item.id}
                >
                  {!own && !grouped && (
                    <small className="message-author" dir="auto">
                      {senderName(item.sender)}
                    </small>
                  )}
                  {item.reply && (
                    <button
                      type="button"
                      className="reply-quote"
                      disabled={!replied || !!query}
                      onClick={() => {
                        const target = [
                          ...(log.current?.querySelectorAll<HTMLElement>(
                            "[data-message-id]",
                          ) || []),
                        ].find(
                          (node) =>
                            node.dataset.messageId === replied!.event.id,
                        );
                        target?.scrollIntoView({ block: "center" });
                        (target as HTMLElement | null)?.focus({
                          preventScroll: true,
                        });
                      }}
                    >
                      <Icon name="reply" size={15} />
                      <span>
                        <strong dir="auto">
                          {replied
                            ? senderName(replied.event.sender)
                            : t("Earlier message")}
                        </strong>
                        <span dir="auto">
                          {replied
                            ? messagePreview(replied, t).slice(0, 120)
                            : t("This message is not saved on this device.")}
                        </span>
                      </span>
                    </button>
                  )}
                  <p dir="auto">
                    {message.deleted ? t("[deleted]") : message.text}
                  </p>
                  {!message.deleted && attachment(message)}
                  {message.reactions.length > 0 && (
                    <div
                      className="message-reactions"
                      aria-label={t("Reactions")}
                    >
                      {[...new Set(message.reactions.map((x) => x.emoji))].map(
                        (emoji) => (
                          <span key={emoji}>
                            {emoji}{" "}
                            <b>
                              {
                                message.reactions.filter(
                                  (x) => x.emoji === emoji,
                                ).length
                              }
                            </b>
                          </span>
                        ),
                      )}
                    </div>
                  )}
                  <div className="message-footer">
                    {!message.deleted && (
                      <MessageMenu
                        message={message}
                        own={own}
                        disabled={disabled}
                        t={t}
                        action={action}
                        feedback={feedback}
                      />
                    )}
                    <span className="message-meta">
                      {message.edited && !message.deleted && (
                        <span>{t("edited")}</span>
                      )}
                      <time
                        dateTime={item.time}
                        title={new Date(item.time).toLocaleString(locale)}
                      >
                        <bdi>
                          {new Date(item.time).toLocaleTimeString(locale, {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </bdi>
                      </time>
                      {own && (
                        <span
                          className="delivery-state"
                          role="img"
                          aria-label={t(status)}
                          title={t(status)}
                          data-state={item.state}
                        >
                          <Icon
                            name={
                              read
                                ? "checks"
                                : item.state === "failed"
                                  ? "warning"
                                  : item.state === "server_accepted" ||
                                      item.state === "recipient_synced"
                                    ? "check"
                                    : "clock"
                            }
                            size={15}
                          />
                        </span>
                      )}
                    </span>
                  </div>
                </article>
              </Fragment>
            );
          })}
        </div>
      </div>
      {away && (
        <button
          type="button"
          className="jump-latest"
          onClick={jump}
          aria-label={t(
            newMessages ? "New messages · jump to latest" : "Jump to latest",
          )}
        >
          {newMessages && <span>{t("New messages")}</span>}
          <Icon name="down" size={19} />
        </button>
      )}
    </div>
  );
}
