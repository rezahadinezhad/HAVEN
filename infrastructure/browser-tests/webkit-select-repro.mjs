// Isolates native WebKit dropdown styling under enforced CSP without HAVEN/React.
import { expect } from "/work/node_modules/@playwright/test/index.mjs";
import { webkit } from "/work/node_modules/playwright/index.mjs";
const b = await webkit.launch({ headless: true });
try {
  for (const appearance of ["auto", "none"]) {
    const p = await b.newPage();
    await p.addInitScript(() => {
      window.events = [];
      document.addEventListener("securitypolicyviolation", (e) =>
        window.events.push({
          directive: e.effectiveDirective,
          sample: e.sample,
          source: e.sourceFile,
        }),
      );
    });
    await p.route("https://127.0.0.1:8445/", (r) =>
      r.fulfill({
        contentType: "text/html",
        headers: {
          "content-security-policy":
            "default-src 'none'; style-src 'nonce-testvalue' 'report-sample'; script-src 'nonce-testvalue'",
        },
        body: `<!doctype html><style nonce="testvalue">select{appearance:${appearance}}</style><select id="one"><option value="one">One</option><option value="two">Two</option></select><script nonce="testvalue">const s=document.createElement('select');s.innerHTML='<option>A</option><option>B</option>';document.body.append(s);</script>`,
      }),
    );
    await p.goto("https://127.0.0.1:8445/");
    await p.locator("#one").selectOption("two");
    const events = await p.evaluate(() => window.events);
    expect([0, 2]).toContain(events.length);
    for (const e of events) {
      expect(e.directive).toBe("style-src-attr");
      expect(e.sample).toBe("text-overflow:inherit");
    }
    console.log(
      "Native select, no HAVEN/React code, appearance=" +
        appearance +
        ": " +
        events.length +
        " blocked text-overflow:inherit engine styles",
    );
    await p.close();
  }
} finally {
  await b.close();
}
