/**
 * The query cache's keys and its defaults.
 *
 * Keys are built here rather than inline so an invalidation and a read can never drift
 * apart. staleTime 5 s keeps a route change from refetching everything; the live stream
 * is what makes data fresh, and retry 1 means a single blip does not paint an error.
 */
import { QueryClient } from "@tanstack/react-query";

import type { FeedKind } from "./types";

export const queryKeys = {
  instances: () => ["instances"] as const,
  alerts: () => ["alerts"] as const,
  plan: (name: string) => ["plan", name] as const,
  schedule: (name: string) => ["schedule", name] as const,
  feed: (name: string, kind: FeedKind) => ["feed", name, kind] as const,
  /** Fleet-wide with no argument, scoped to one instance for the session panel. Both
   * start with ["stats", "today"], so one invalidation covers them. */
  statsToday: (instance?: string) =>
    instance === undefined ? (["stats", "today"] as const) : (["stats", "today", instance] as const),
  /** The Stats page's own read. It deliberately does NOT start with ["stats", "today"],
   * so phase 4's invalidation still covers the Fleet and session reads without fighting
   * this one. */
  stats: (range: string, instances: string[]) =>
    ["stats", "range", range, instances.join(",")] as const,
  connection: () => ["connection"] as const,
  settings: () => ["settings"] as const,
  /** Version and home folder. About and Data both read it, so one request serves both. */
  health: () => ["health"] as const,
  /** The calibration file itself: one read for the whole panel, no instance in it. */
  calibration: () => ["calibration"] as const,
  /** Scored against one instance's last frame, so it starts with the same prefix as the
   * file read and an invalidation of ["calibration"] covers both. */
  calibrationScores: (name: string) => ["calibration", "scores", name] as const,
  recorder: (name: string) => ["recorder", name] as const,
};

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 5000, retry: 1, refetchOnWindowFocus: true },
    },
  });
}
