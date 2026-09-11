/** GET /api/instances and the five per-instance controls. Each control is 202 Accepted:
 * the supervisor has been poked, not finished. */
import { api } from "./client";
import type { InstancePayload, InstancesResponse } from "./types";

export interface OkResponse {
  ok: boolean;
}

export async function listInstances(): Promise<InstancePayload[]> {
  const body = await api<InstancesResponse>("/api/instances");
  return body.instances;
}

/** No hours clears the stop override; with hours the instance runs that long and stops. */
export function startInstance(name: string, hours?: number): Promise<OkResponse> {
  return api<OkResponse>(`/api/instances/${name}/start`, {
    method: "POST",
    body: JSON.stringify(hours === undefined ? {} : { hours }),
  });
}

export function stopInstance(name: string): Promise<OkResponse> {
  return api<OkResponse>(`/api/instances/${name}/stop`, { method: "POST" });
}

export function restartInstance(name: string): Promise<OkResponse> {
  return api<OkResponse>(`/api/instances/${name}/restart`, { method: "POST" });
}

export function retryInstance(name: string): Promise<OkResponse> {
  return api<OkResponse>(`/api/instances/${name}/retry`, { method: "POST" });
}
