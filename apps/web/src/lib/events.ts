import { z } from "./schema";
import { isViewOnceMedia } from "./attachment-policy";
const uuid = z.string().uuid();
const file = z
  .object({
    id: uuid,
    view_once: z.literal(true).optional(),
    conversation_id: uuid,
    name: z.string().max(255),
    mime: z.string().max(127),
    key: z.string().max(64),
    prefix: z.string().max(32),
    count: z.number().int().min(1).max(50),
    size: z
      .number()
      .int()
      .min(0)
      .max(25 * 1024 * 1024),
  })
  .strict()
  .refine(
    (f) => f.count === Math.max(1, Math.ceil(f.size / (512 * 1024))),
    "Invalid chunk count",
  )
  .refine(
    (f) => !f.view_once || isViewOnceMedia(f.mime),
    "Unsupported view-once media",
  );
const event = z
  .object({
    id: uuid,
    conversation_id: uuid,
    sender: uuid,
    time: z.string().datetime({ offset: true }),
    type: z.enum([
      "text",
      "edit",
      "delete",
      "reaction",
      "file",
      "title",
      "receipt",
    ]),
    text: z.string().max(20000).optional(),
    target: uuid.optional(),
    emoji: z.string().max(32).optional(),
    file: file.optional(),
    reply: uuid.optional(),
  })
  .strict()
  .superRefine((e, c) => {
    if (
      ["text", "edit", "title"].includes(e.type) &&
      typeof e.text !== "string"
    )
      c.addIssue({ code: "custom", message: "Missing text" });
    if (["edit", "delete", "reaction", "receipt"].includes(e.type) && !e.target)
      c.addIssue({ code: "custom", message: "Missing target" });
    if (e.type === "reaction" && !e.emoji)
      c.addIssue({ code: "custom", message: "Missing reaction" });
    if (e.type === "title" && (e.text?.length || 0) > 80)
      c.addIssue({ code: "custom", message: "Title too long" });
    if (
      e.type === "file" &&
      (!e.file || e.file.conversation_id !== e.conversation_id)
    )
      c.addIssue({ code: "custom", message: "Attachment scope mismatch" });
  });
export function authenticatedEvent(input: unknown) {
  const result = event.safeParse(input);
  if (!result.success) throw new Error("Invalid authenticated event structure");
  return result.data;
}
