/** The farm plan, with the roster, the queue and the current brawler the API adds. */
import { api } from "./client";
import type { FarmPlan, PlanResponse } from "./types";

export function getPlan(name: string): Promise<PlanResponse> {
  return api<PlanResponse>(`/api/instances/${name}/plan`);
}

export function putPlan(name: string, plan: FarmPlan): Promise<PlanResponse> {
  return api<PlanResponse>(`/api/instances/${name}/plan`, {
    method: "PUT",
    body: JSON.stringify(plan),
  });
}
