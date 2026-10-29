import { z } from "zod";
// The optional Function-based JIT probe itself emits CSP violations in WebKit,
// even when its exception is caught. Parsing remains strict without compilation.
z.config({ jitless: true });
export { z };
