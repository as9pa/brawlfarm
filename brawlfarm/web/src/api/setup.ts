/**
 * The three setup probes.
 *
 * Each one is a mutation with local state, never a cached query: a probe is a deliberate act
 * and takes seconds, and a stale cached scan would lie about what is plugged in right now.
 * The optional adbPath is the path the user typed, which the API prefers over the configured
 * one, so the wizard's field works before anything has reached config.toml.
 */
import { api } from "./client";
import type { DisplayCheckResponse, PortTestResponse, ScanResponse } from "./types";

/** The body's adb_path key is only sent when there is one: the route forbids extra keys and
 * treats a missing one as "use what is configured". */
function withPath(body: Record<string, number>, adbPath: string | undefined): string {
  return JSON.stringify(adbPath === undefined ? body : { ...body, adb_path: adbPath });
}

export function scanSetup(adbPath?: string): Promise<ScanResponse> {
  return api<ScanResponse>("/api/setup/scan", { method: "POST", body: withPath({}, adbPath) });
}

export function testPort(port: number, adbPath?: string): Promise<PortTestResponse> {
  return api<PortTestResponse>("/api/setup/test", {
    method: "POST",
    body: withPath({ adb_port: port }, adbPath),
  });
}

export function checkDisplay(port: number, adbPath?: string): Promise<DisplayCheckResponse> {
  return api<DisplayCheckResponse>("/api/setup/display-check", {
    method: "POST",
    body: withPath({ adb_port: port }, adbPath),
  });
}
