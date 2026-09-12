/** Whether the Brawl Stars API is answering for this install. Always 200: the route
 * reports a failure, it does not have one. */
import { api } from "./client";
import type { ConnectionCheck } from "./types";

export function getConnection(): Promise<ConnectionCheck> {
  return api<ConnectionCheck>("/api/connection/check");
}
