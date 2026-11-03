import { z } from "./schema";
import type { Envelope, Certificate } from "./api";
import type { LocalEvent } from "./vault";
export const CLOSURE_POLICY = "mutual-local-archive-v1";
const hash = z.string().regex(/^[0-9a-f]{64}$/);
const participant = z
  .object({
    id: z.uuid(),
    user_id: z.uuid(),
    identity: z.string().max(200),
    public_key: z.string().max(44),
    role: z.enum(["owner", "moderator", "member"]),
    security_generation: z.number().int().min(1),
  })
  .strict();
const snapshot = z
  .object({
    domain: z.enum(["haven/closure/proposal/v1", "haven/closure/snapshot/v1"]),
    v: z.literal(1),
    conversation_id: z.uuid(),
    group_id: z.string().max(100),
    closure_policy: z.literal(CLOSURE_POLICY),
    restore_epoch: z.string().min(1).max(128),
    nonce: z.uuid(),
    proposer_device: z.uuid(),
    genesis_hash: hash,
    final_seq: z.number().int().min(1).max(500),
    final_epoch: z.number().int().min(0).max(Number.MAX_SAFE_INTEGER),
    final_hash: hash,
    archive_policy: z.literal("complete-text-history-on-each-device-v1"),
    participants: z.array(participant).length(2),
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
