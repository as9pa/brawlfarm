/**
 * The settings document.
 *
 * GET and PUT are both whole-document: the API has no PATCH, so every write goes through
 * settings/useSettingsPatch.ts, which reads, mutates a clone and puts the whole thing back.
 * The response carries connection.brawl_api_token in full because the API is loopback-only
 * and masking is the panel's job: the token reaches exactly one masked Field, is never
 * logged, never stored anywhere but the query cache, and never rendered unmasked by default.
 */
import { api } from "./client";
import type { AppSettings } from "./types";

export function getSettings(): Promise<AppSettings> {
  return api<AppSettings>("/api/settings");
}

export function putSettings(doc: AppSettings): Promise<AppSettings> {
  return api<AppSettings>("/api/settings", { method: "PUT", body: JSON.stringify(doc) });
}
