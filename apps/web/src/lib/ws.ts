import { z } from "./schema";
const hint = z.discriminatedUnion("kind", [
  z
    .object({
      v: z.literal(1),
      kind: z.literal("ephemeral.presence"),
      conversation_id: z.string().uuid(),
      sender_device: z.string().uuid(),
      expires_in: z.literal(50),
    })
    .strict(),
  z
    .object({
      v: z.literal(1),
      kind: z.literal("hello"),
      sync: z.literal("http"),
      crypto_ready: z.boolean(),
    })
    .strict(),
  z.object({ v: z.literal(1), kind: z.literal("heartbeat") }).strict(),
  z.object({ v: z.literal(1), kind: z.literal("sync.required") }).strict(),
  z
    .object({
      v: z.literal(1),
      kind: z.literal("ephemeral.typing"),
      conversation_id: z.string().uuid(),
      sender_device: z.string().uuid(),
      expires_in: z.literal(5),
    })
    .strict(),
]);
export function serverHint(value: unknown) {
  const parsed = hint.safeParse(value);
  return parsed.success ? parsed.data : undefined;
}
