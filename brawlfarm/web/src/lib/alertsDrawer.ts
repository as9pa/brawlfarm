/**
 * Whether the alerts drawer is open.
 *
 * A module store rather than context: the Fleet page's alert strip opens the same drawer
 * the top bar's button does, and the two have no common parent below Shell. Same shape as
 * toast.ts, for the same reason, and it sits beside it for a second one: a store named
 * alertsDrawer cannot share a folder with the AlertsDrawer component, because a
 * case-insensitive filesystem resolves both extensionless imports to the same file.
 */
import { useSyncExternalStore } from "react";

let open = false;
const listeners = new Set<() => void>();

function set(next: boolean): void {
  if (open === next) return;
  open = next;
  for (const listener of [...listeners]) listener();
}

export function openAlertsDrawer(): void {
  set(true);
}

export function closeAlertsDrawer(): void {
  set(false);
}

function subscribeOpen(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useAlertsDrawerOpen(): boolean {
  return useSyncExternalStore(
    subscribeOpen,
    () => open,
    () => open,
  );
}
