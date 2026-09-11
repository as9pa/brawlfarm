/** Today's drawn sessions, the manual override and the schedule switch. PUT is a patch:
 * only the keys present act, so { redraw: true } leaves `enabled` alone. */
import { api } from "./client";
import type { SchedulePatch, SchedulePayload } from "./types";

export function getSchedule(name: string): Promise<SchedulePayload> {
  return api<SchedulePayload>(`/api/instances/${name}/schedule`);
}

export function patchSchedule(name: string, patch: SchedulePatch): Promise<SchedulePayload> {
  return api<SchedulePayload>(`/api/instances/${name}/schedule`, {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}
