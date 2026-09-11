/**
 * The toast queue.
 *
 * A module store rather than context: toasts are fired from event handlers deep in the
 * tree (a card's Stop button, the alerts drawer) and read by one Toaster mounted in App.
 * The queue holds every pending message; Toaster shows the head, so only one is visible.
 */
import { useSyncExternalStore } from "react";

export interface ToastOptions {
  undo?: () => void | Promise<void>;
  durationMs?: number;
}

export interface ToastItem {
  id: number;
  message: string;
  durationMs: number;
  undo?: () => void | Promise<void>;
}

export const TOAST_MS = 4000;
export const TOAST_UNDO_MS = 6000;

let queue: readonly ToastItem[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of [...listeners]) {
    try {
      listener();
    } catch (error) {
      // A subscriber that throws would otherwise abort the loop, and every subscriber
      // after it would never hear about a queue that has already changed.
      console.error("toast: a subscriber threw", error);
    }
  }
}

export function toast(message: string, opts: ToastOptions = {}): number {
  const item: ToastItem = {
    id: nextId,
    message,
    durationMs: opts.durationMs ?? (opts.undo === undefined ? TOAST_MS : TOAST_UNDO_MS),
    ...(opts.undo === undefined ? {} : { undo: opts.undo }),
  };
  nextId += 1;
  queue = [...queue, item];
  emit();
  return item.id;
}

export function dismissToast(id: number): void {
  const next = queue.filter((item) => item.id !== id);
  if (next.length === queue.length) return;
  queue = next;
  emit();
}

/** Tests only: empty the queue and restart the ids. */
export function resetToasts(): void {
  queue = [];
  nextId = 1;
  emit();
}

/** The store half of useToasts: notified on every change to the queue. Exported so a
 * test can register a plain listener of its own. */
export function subscribeToasts(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function snapshot(): readonly ToastItem[] {
  return queue;
}

export function useToasts(): readonly ToastItem[] {
  return useSyncExternalStore(subscribeToasts, snapshot, snapshot);
}
