/** The newest session's narration. Only the newest session file is served; older ones
 * belong to the stats page. */
import { api } from "./client";
import type { FeedKind, FeedResponse } from "./types";

export function getFeed(name: string, kind: FeedKind, limit: number): Promise<FeedResponse> {
  return api<FeedResponse>(`/api/instances/${name}/feed?kind=${kind}&limit=${limit}`);
}
