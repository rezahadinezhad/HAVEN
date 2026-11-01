import { test, expect } from "./fixtures";
import fs from "node:fs";
// This is a characterization of a release-blocking limitation, not a passing security invariant.
// Restoring a complete earlier provider snapshot can resurrect an already-used receive ratchet.
test("characterize snapshot rollback: integration must not silently trust restored ratchets", async ({
  page,
}) => {
  await page.goto("/pof.html");
  await page.waitForFunction(() => !!(window as any).havenPoF);
  const result = await page.evaluate(() => {
    const call = (state: string, command: any) =>
      (window as any).havenPoF.call(state, command);
    let a = call("", { op: "init", identity: "rollback-a" }).state;
    let b = call("", { op: "init", identity: "rollback-b" }).state;
    let x = call(b, { op: "package" });
    b = x.state;
    const kp = x.result.key_package;
    a = call(a, { op: "create", group_id: "rollback" }).state;
    x = call(a, { op: "add", group_id: "rollback", key_package: kp });
    a = x.state;
    b = call(b, {
      op: "join",
      group_id: "rollback",
      welcome: x.result.welcome,
    }).state;
    const previous = b;
    x = call(a, {
      op: "encrypt",
      group_id: "rollback",
      plaintext: "test data",
    });
    const ciphertext = x.result.ciphertext;
    const consumed = call(b, {
      op: "process",
      group_id: "rollback",
      ciphertext,
    });
    b = consumed.state;
    let normalReplayRejected = false;
    try {
      call(b, { op: "process", group_id: "rollback", ciphertext });
    } catch {
      normalReplayRejected = true;
    }
    const restored = call(previous, {
      op: "process",
      group_id: "rollback",
      ciphertext,
    });
    return {
      normalReplayRejected,
      restoredSnapshotDecryptsAgain: restored.result.plaintext === "test data",
      gate: "BLOCKED",
      reason:
        "OpenMLS cannot detect restoration of its entire earlier state. Application restore needs reviewed reset/checkpoint reconciliation; this is not a library defect.",
    };
  });
  fs.writeFileSync(
    "../../docs/evidence/rollback-characterization.json",
    JSON.stringify(result, null, 2) + "\n",
  );
  expect(result.normalReplayRejected).toBeTruthy();
  expect(result.restoredSnapshotDecryptsAgain).toBeTruthy();
});
