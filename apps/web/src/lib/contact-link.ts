import { z } from "./schema";

const contactSchema = z
  .object({
    v: z.literal(1),
    device_id: z.uuid(),
    fingerprint: z.string().regex(/^[0-9a-f]{64}$/),
    name: z.string().min(1).max(80),
  })
  .strict();
export type ContactCard = z.infer<typeof contactSchema>;

export function contactLink(
  origin: string,
  contact: ContactCard,
  invite?: string,
) {
  const card = contactSchema.parse(contact);
  const url = new URL("/", origin);
  if (url.protocol !== "https:" || url.origin !== origin)
    throw new Error("Trusted HTTPS required");
  const hash = new URLSearchParams({ connect: JSON.stringify(card) });
  if (invite) {
    if (!/^[A-Za-z0-9_-]{40,100}$/.test(invite))
      throw new Error("Invalid invitation");
    hash.set("invite", invite);
  }
  url.hash = hash.toString();
  return url.href;
}

export function readContactLink(value: string, origin: string): ContactCard {
  if (value.length > 4096) throw new Error("This friend link is too long");
  const url = new URL(value, origin);
  if (
    url.origin !== origin ||
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    url.pathname !== "/" ||
    url.search
  )
    throw new Error(
      "This friend link belongs to a different server. Use an independently trusted server address.",
    );
  const params = new URLSearchParams(url.hash.slice(1));
  if (params.getAll("connect").length !== 1)
    throw new Error("Paste a complete HAVEN friend link");
  try {
    return contactSchema.parse(JSON.parse(params.get("connect")!));
  } catch {
    throw new Error(
      "This friend link is invalid or uses an unsupported version",
    );
  }
}

export const securityCode = (fingerprint: string) =>
  fingerprint
    .replace(/\s/g, "")
    .match(/.{1,4}/g)
    ?.join(" ") || fingerprint;
