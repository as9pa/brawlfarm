/** Today's aggregates. Phase 4 reads only `summary`; the Stats page is phase 6. */
import { api } from "./client";
import type { StatsResponse } from "./types";

export function getStatsToday(instance?: string): Promise<StatsResponse> {
  const scope = instance === undefined ? "" : `&instances=${instance}`;
  return api<StatsResponse>(`/api/stats?range=today${scope}`);
}
