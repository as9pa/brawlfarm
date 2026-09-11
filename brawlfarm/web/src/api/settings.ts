/** The settings document. The response also carries connection.brawl_api_token in
 * plaintext; AppSettings does not model it, and nothing in the panel may read it. */
import { api } from "./client";
import type { AppSettings } from "./types";

export function getSettings(): Promise<AppSettings> {
  return api<AppSettings>("/api/settings");
}
