import { z } from "./schema";
import type { Envelope, Certificate } from "./api";
import type { LocalEvent } from "./vault";
export const LEGACY_CLOSURE_POLICY = "mutual-local-archive-v1";
export const CLOSURE_POLICY = "account-wide-retirement-v2";
export const closureCertificate = (
  x: ClosureSnapshot["participants"][number],
): Certificate => ({
  id: x.id,
  user_id: x.user_id,
  identity: x.identity,
  public_key: x.public_key,
  role: x.role,
});
export function closureQuorum(
  t: ClosureSnapshot,
  records: Record<string, unknown>,
) {
  const signed = Object.keys(records).map((id) =>
    t.participants.find((x) => x.id === id),
  );
  if (signed.some((x) => !x || x.can_sign === false))
    throw new Error("Invalid account representative");
  if (t.closure_policy === LEGACY_CLOSURE_POLICY)
    return signed.length === t.participants.length;
  const ids = signed.map((x) => x!.user_id);
  if (new Set(ids).size !== ids.length)
    throw new Error("An account cannot vote from multiple devices");
  return (
    new Set(ids).size === new Set(t.participants.map((x) => x.user_id)).size
  );
}
const hash = z.string().regex(/^[0-9a-f]{64}$/);
const participant = z
  .object({
    id: z.uuid(),
    user_id: z.uuid(),
    identity: z.string().max(200),
    public_key: z.string().max(44),
    role: z.enum(["owner", "moderator", "member"]),
    security_generation: z.number().int().min(1),
    can_sign: z.boolean().optional(),
    active: z.boolean().optional(),
    valid_from_epoch: z.number().int().min(0).optional(),
    removed_at_epoch: z.number().int().min(0).nullable().optional(),
  })
  .strict();
const snapshot = z
  .object({
    domain: z.enum(["haven/closure/proposal/v1", "haven/closure/snapshot/v1"]),
    v: z.literal(1),
    conversation_id: z.uuid(),
    group_id: z.string().max(100),
    closure_policy: z.enum([CLOSURE_POLICY, LEGACY_CLOSURE_POLICY]),
    restore_epoch: z.string().min(1).max(128),
    nonce: z.uuid(),
    proposer_device: z.uuid(),
    genesis_hash: hash,
    final_seq: z.number().int().min(1).max(5000),
    final_epoch: z.number().int().min(0).max(Number.MAX_SAFE_INTEGER),
    final_hash: hash,
    archive_policy: z.enum([
      "complete-text-history-on-each-device-v1",
      "available-history-account-wide-release-v2",
    ]),
    participants: z.array(participant).min(2).max(100),
    proposal_hash: hash.optional(),
  })
  .strict();
const schema = z
  .object({
    state: z.enum(["active", "proposed", "closing", "finalized"]),
    proposal: snapshot.nullable(),
    transcript: snapshot.nullable(),
    proposal_signature: z.string().max(88),
    preparations: z.record(
      z.uuid(),
      z
        .object({ transcript_hash: hash, signature: z.string().max(88) })
        .strict(),
    ),
    consents: z.record(
      z.uuid(),
      z.object({ archive_hash: hash, signature: z.string().max(88) }).strict(),
    ),
    final_receipts: z.record(z.uuid(), z.string().max(88)),
  })
  .strict();
export type ClosureSnapshot = z.infer<typeof snapshot>;
export type ClosureRecord = z.infer<typeof schema>;
export function parseClosureRecord(value: unknown): ClosureRecord {
  return schema.parse(value);
}
export type ClosureProofBundle = {
  genesis: {
    domain: string;
    id: string;
    kind: string;
    group_id: string;
    members: Certificate[];
    closure_policy?: string;
    closure_epoch?: string;
  };
  genesis_signature: string;
  proofs: Envelope[];
};
export type ClosureArchive = {
  v: 1;
  archive_id: string;
  device_id: string;
  transcript: ClosureSnapshot;
  bundle: ClosureProofBundle;
  events: LocalEvent[];
  files?: Record<string, string>;
  unsent?: LocalEvent[];
  draft?: string;
  pending?: Record<string, unknown>;
  omissions?: { id: string; reason: string }[];
  archive_hash: string;
  prepare_request: { transcript: ClosureSnapshot; signature: string };
  consent_request?: {
    transcript_hash: string;
    archive_hash: string;
    signature: string;
  };
  certificate?: ClosureRecord;
  receipt_confirmed?: boolean;
  receipt_request?: { finality_hash: string; signature: string };
};
