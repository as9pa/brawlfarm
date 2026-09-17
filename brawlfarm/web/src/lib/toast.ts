/**
 * The toast queue.
 *
 * A module store rather than context: toasts are fired from event handlers deep in the
 * tree (a card's Stop button, the alerts drawer) and read by one Toaster mounted in App.
 * The queue holds every pending message; Toaster shows the head, so only one is visible.
 *
 * failureMessage lives here too, because a rejected request is the commonest reason to
 * raise one and every caller had been writing the same two branches out by hand.
 */
import { useSyncExternalStore } from "react";

import { ApiError } from "../api/client";

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

/** What a rejected request should say: the API's own sentence when it answered with one
 * -- including the "cannot reach brawlfarm" wording a dead server produces -- and one
 * plain fallback for a failure that came from somewhere else entirely. */
export function failureMessage(error: unknown): string {
  return error instanceof ApiError ? error.detail : "That did not go through. Try again.";
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
