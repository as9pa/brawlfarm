/** GET /api/health: which version is running, where its data lives, how many instances it
 * manages and how long this process has been up. About shows the version; Data puts the
 * home folder in one tooltip and nowhere else. */
import { api } from "./client";
import type { HealthResponse } from "./types";

export function getHealth(): Promise<HealthResponse> {
  return api<HealthResponse>("/api/health");
}
