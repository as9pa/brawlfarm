/** The one fixture value a TypeScript string literal can quietly change. In "C:\Program
 * Files\..." none of \P, \B or \H is an escape, so the file compiles and the separators are
 * eaten at runtime; every wizard and settings test would then assert against a path no
 * Windows machine has. Reading the value back is the only thing that catches it. */
import { describe, expect, it } from "vitest";

import { makeSettings } from "./fixtures";

describe("makeSettings", () => {
  it("keeps the separators in the default adb path", () => {
    // brawlfarm/settings.py's DEFAULT_ADB_PATH, backslash for backslash.
    expect(makeSettings().connection.adb_path).toBe(
      "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe",
    );
  });
});
