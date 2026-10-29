// Raster images only: view-once never opens HTML/SVG/documents as active content.
export const viewOnceTypes = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
  "image/avif",
  "video/mp4",
  "video/webm",
  "video/ogg",
]);
export const isViewOnceMedia = (mime: string) => viewOnceTypes.has(mime);
