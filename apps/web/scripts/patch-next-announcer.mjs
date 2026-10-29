// Next 16.4.3 route-announcer CSP compatibility. Keep ARIA/portal behavior intact;
// move only the two constant cssText assignments to external CSS / a shadow part.
import fs from "node:fs";
import path from "node:path";
const next = path.resolve("node_modules/next");
if (
  JSON.parse(fs.readFileSync(next + "/package.json", "utf8")).version !==
  "16.4.3"
)
  throw new Error(
    "Review the route-announcer CSP patch before changing Next versions",
  );
const replacements = [
  [
    "container.style.cssText = 'position:absolute';",
    "container.className = 'haven-route-announcer';",
  ],
  [
    "announcer.style.cssText = 'position:absolute;border:0;height:1px;margin:-1px;padding:0;width:1px;clip:rect(0 0 0 0);overflow:hidden;white-space:nowrap;word-wrap:normal';",
    "announcer.setAttribute('part', 'announcement');",
  ],
];
for (const file of [
  "dist/client/components/app-router-announcer.js",
  "dist/esm/client/components/app-router-announcer.js",
]) {
  const target = path.join(next, file);
  let source = fs.readFileSync(target, "utf8");
  for (const [before, after] of replacements) {
    if (source.includes(after) && !source.includes(before)) continue;
    if (source.split(before).length !== 2)
      throw new Error(
        "Unexpected Next announcer implementation; review required: " + file,
      );
    source = source.replace(before, after);
  }
  fs.writeFileSync(target, source);
}
console.log(
  "Next 16.4.3 accessibility announcer uses external CSS; CSP remains strict.",
);
