/** The Fleet drawer's alerts. Both dismiss calls answer 204 with no body. */
import { api } from "./client";
import type { AlertsResponse } from "./types";

export function listAlerts(): Promise<AlertsResponse> {
  return api<AlertsResponse>("/api/alerts");
}

export function dismissAlert(id: number): Promise<void> {
  return api<void>(`/api/alerts/${id}/dismiss`, { method: "POST" });
}

export function dismissAllAlerts(): Promise<void> {
  return api<void>("/api/alerts/dismiss-all", { method: "POST" });
}
