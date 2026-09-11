/**
 * The instances query, in one place.
 *
 * The rail, the Fleet page and the Instance page all want the same list, and all three
 * want it fresh: `session` and `today` exist only on GET /api/instances, so the instance
 * events (which carry the supervisor's view alone) cannot keep those numbers moving. One
 * hook owns the key, the fetcher and the 15 s poll, and the poll stops while the tab is
 * hidden, so a backgrounded panel costs the supervisor nothing.
 */
import { type UseQueryResult, useQuery } from "@tanstack/react-query";

import { listInstances } from "./instances";
import { queryKeys } from "./queries";
import type { InstancePayload } from "./types";
import { useVisiblePolling } from "../live/useVisiblePolling";

export const INSTANCES_POLL_MS = 15000;

export function useInstances(): UseQueryResult<InstancePayload[], Error> {
  const refetchInterval = useVisiblePolling(INSTANCES_POLL_MS);
  return useQuery({
    queryKey: queryKeys.instances(),
    queryFn: listInstances,
    refetchInterval,
  });
}
