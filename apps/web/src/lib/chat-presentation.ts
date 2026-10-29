import type { LocalEvent } from "./vault";

export type Message = {
  event: LocalEvent;
  text: string;
  deleted: boolean;
  edited: boolean;
  reactions: LocalEvent[];
};

export function fileSizeLabel(bytes: number, locale = "en") {
  const divisor = bytes >= 1_000_000 ? 1_000_000 : bytes >= 1_000 ? 1_000 : 1;
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(bytes / divisor)} ${divisor === 1_000_000 ? "MB" : divisor === 1_000 ? "KB" : "B"}`;
}

// Presentation only. Signature, sender binding and sequence validation happen
// in Messenger before these events enter the encrypted local vault.
export function conversationMessages(
  events: LocalEvent[],
  cid: string,
): Message[] {
  const controls = new Map<string, LocalEvent[]>();
  const messages: LocalEvent[] = [];
  for (const event of events) {
    if (event.conversation_id !== cid) continue;
    if (event.type === "text" || event.type === "file") messages.push(event);
    else if (event.target) {
      const list = controls.get(event.target) || [];
      list.push(event);
      controls.set(event.target, list);
    }
  }
  return messages
    .sort(
      (a, b) =>
        (a.seq ?? Number.MAX_SAFE_INTEGER) -
          (b.seq ?? Number.MAX_SAFE_INTEGER) ||
        Date.parse(a.time) - Date.parse(b.time),
    )
    .map((event) => {
      const related = controls.get(event.id) || [];
      const deleted = related.some(
        (x) => x.type === "delete" && x.sender === event.sender,
      );
      const edit = related
        .filter((x) => x.type === "edit" && x.sender === event.sender)
        .at(-1);
      return {
        event,
        deleted,
        edited: !!edit,
        text: deleted ? "" : (edit?.text ?? event.text ?? ""),
        reactions: deleted ? [] : related.filter((x) => x.type === "reaction"),
      };
    });
}

export function messagePreview(
  message: Message,
  t: (s: string) => string,
): string {
  if (message.deleted) return t("Message deleted");
  const file = message.event.file;
  if (file?.view_once)
    return t(
      file.mime.startsWith("video/") ? "View-once video" : "View-once photo",
    );
  if (file?.mime.startsWith("audio/"))
    return t(file.name.startsWith("voice-note.") ? "Voice note" : "Audio");
  return message.text || file?.name || t("Attachment");
}

// A server acceptance is not evidence that a person received or read a message.
export function deliveryLabel(
  state: LocalEvent["state"],
  read: boolean,
): string {
  if (read) return "Read (receipt shared)";
  return {
    local_only: "Saved on this device",
    encrypting: "Encrypting…",
    queued: "Queued for sending",
    server_accepted: "Sent to server",
    recipient_synced: "Synced to this device",
    failed: "Could not send",
  }[state];
}
