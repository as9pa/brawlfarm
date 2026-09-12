/**
 * The stats aggregate, and the CSV download's href.
 *
 * One query builder serves both, so the table the page shows and the file the reader
 * downloads can never describe different selections. `instances` empty means "every
 * configured instance", which is also the API's own default, so a full selection and no
 * selection send the same URL and share one cache entry. Stats.tsx is what decides which
 * of those two a click means.
 */
import { api } from "./client";
import type { StatsRange, StatsResponse } from "./types";

function statsQuery(range: StatsRange, instances: string[]): string {
  const scope = instances.length === 0 ? "" : `&instances=${instances.join(",")}`;
  return `?range=${range}${scope}`;
}

export function getStatsToday(instance?: string): Promise<StatsResponse> {
  const scope = instance === undefined ? "" : `&instances=${instance}`;
  return api<StatsResponse>(`/api/stats?range=today${scope}`);
}

export function getStats(range: StatsRange, instances: string[]): Promise<StatsResponse> {
  return api<StatsResponse>(`/api/stats${statsQuery(range, instances)}`);
}

/** The export's href for an anchor. The download is a plain link, not a fetch, so the
 * browser's own download is the feedback and there is no toast to write. */
export function statsCsvHref(range: StatsRange, instances: string[]): string {
  return `/api/stats/export.csv${statsQuery(range, instances)}`;
}
