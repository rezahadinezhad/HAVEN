// Typed transport over the generated OpenAPI contract. Regenerate schema.ts after changing the API.
import type { paths } from "./schema";
import { api } from "../api";
type Method<P extends keyof paths> = Exclude<keyof paths[P], "parameters">;
type Operation<P extends keyof paths, M extends Method<P>> = paths[P][M];
type Body<O> = O extends {
  requestBody: { content: { "application/json": infer B } };
}
  ? B
  : never;
type Reply<O> = O extends {
  responses: { 200: { content: { "application/json": infer R } } };
}
  ? R
  : unknown;
export async function request<P extends keyof paths, M extends Method<P>>(
  path: P,
  method: M,
  options: {
    params?: Record<string, string | number>;
    body?: Body<Operation<P, M>>;
  } = {},
): Promise<Reply<Operation<P, M>>> {
  let resolved: string = path;
  for (const [key, value] of Object.entries(options.params || {}))
    resolved = resolved.replace(`{${key}}`, encodeURIComponent(String(value)));
  if (resolved.includes("{") || !resolved.startsWith("/api/v1/"))
    throw new Error("Missing API path parameters");
  return api<Reply<Operation<P, M>>>(
    resolved.slice("/api/v1/".length),
    String(method).toUpperCase(),
    options.body,
  );
}
