// Bucketing changes only new media framing; legacy v1 AAD stays byte-for-byte identical.
export const ATTACHMENT_CHUNK = 512 * 1024;
export const MAX_ATTACHMENT = 25 * 1024 * 1024;
export function paddedAttachmentSize(size: number): number {
  if (!Number.isSafeInteger(size) || size < 0 || size > MAX_ATTACHMENT)
    throw new Error("Invalid attachment length");
  const step = size <= 64 * 1024 ? 4096 : size <= 1024 * 1024 ? 16384 : 65536;
  return Math.max(4096, Math.ceil(size / step) * step);
}
export function attachmentLayout(meta: {
  size: number;
  count: number;
  format?: 2;
  padded_size?: number;
}) {
  if (
    !Number.isSafeInteger(meta.size) ||
    meta.size < 0 ||
    meta.size > MAX_ATTACHMENT
  )
    throw new Error("Invalid attachment length");
  const padded =
    meta.format === 2 ? paddedAttachmentSize(meta.size) : meta.size;
  if (
    (meta.format !== undefined && meta.format !== 2) ||
    (meta.format === 2
      ? meta.padded_size !== padded
      : meta.padded_size !== undefined) ||
    meta.count !== Math.max(1, Math.ceil(padded / ATTACHMENT_CHUNK))
  )
    throw new Error("Invalid attachment framing");
  return padded;
}
