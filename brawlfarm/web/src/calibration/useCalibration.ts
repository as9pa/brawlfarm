/**
 * The page's three reads and its one write, in one hook.
 *
 * The two per-instance reads poll only while that instance is running: a stopped
 * instance writes no new frame, so asking twice a second would score the same picture
 * over and over. They also set retry false, because a 404 from the scores route is the
 * page's empty state ("no frame yet") and a retried 404 only delays showing it.
 *
 * The recorder mutation writes the response straight into the cache rather than
 * invalidating: the POST's own body is the fresh status, so a refetch would ask for
 * something already in hand and let the switch flicker back on the way.
 */
import {
  type UseMutationResult,
  type UseQueryResult,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  type Calibration,
  type Recorder,
  type Scores,
  getCalibration,
  getRecorder,
  getScores,
  setRecorder,
} from "../api/calibration";
import { ApiError } from "../api/client";
import { queryKeys } from "../api/queries";

export const CALIBRATION_POLL_MS = 10000;
export const LIVE_POLL_MS = 2000;

export function useCalibrationFile(): UseQueryResult<Calibration, Error> {
  return useQuery({
    queryKey: queryKeys.calibration(),
    queryFn: getCalibration,
    refetchInterval: CALIBRATION_POLL_MS,
  });
}

export function useScores(
  instance: string | null,
  running: boolean,
): UseQueryResult<Scores, Error> {
  return useQuery({
    queryKey: queryKeys.calibrationScores(instance ?? ""),
    queryFn: () => getScores(instance as string),
    enabled: instance !== null,
    retry: false,
    refetchInterval: running ? LIVE_POLL_MS : false,
  });
}

export function useRecorder(
  instance: string | null,
  running: boolean,
): UseQueryResult<Recorder, Error> {
  return useQuery({
    queryKey: queryKeys.recorder(instance ?? ""),
    queryFn: () => getRecorder(instance as string),
    enabled: instance !== null,
    retry: false,
    refetchInterval: running ? LIVE_POLL_MS : false,
  });
}

export function useRecorderToggle(
  instance: string | null,
): UseMutationResult<Recorder, Error, boolean> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (on: boolean) => setRecorder(instance as string, on),
    onSuccess: (status) => {
      client.setQueryData(queryKeys.recorder(instance ?? ""), status);
    },
  });
}

/** Whether a failed read is the scores route saying "no frame yet" rather than a fault.
 * Only a 404 means it, so anything else still belongs in an ErrorBlock. */
export function isNoFrameYet(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}
