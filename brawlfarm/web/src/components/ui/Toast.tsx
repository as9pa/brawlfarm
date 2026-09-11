/**
 * The transient confirmation strip.
 *
 * Toaster shows the head of the queue in lib/toast.ts, so exactly one is visible and the
 * rest wait their turn. The hairline bar drains over the toast's own duration, which is
 * longer when an Undo is on offer because the user has a decision to make. A reader who
 * asked for less motion gets the same bar standing still rather than a sweep.
 *
 * An Undo is usually an API call, so a failed one has to land somewhere: it becomes a
 * second toast carrying the API's own sentence, never a silent unhandled rejection and
 * never an exception thrown out of the click handler.
 */
import { useEffect, useState } from "react";

import { Button } from "./Button";
import { ApiError } from "../../api/client";
import { type ToastItem, dismissToast, toast, useToasts } from "../../lib/toast";

const TICK_MS = 100;
const UNDO_FAILED = "Undo failed";

/** jsdom and any non-browser render have no matchMedia; no implementation means the
 * reader has stated no preference. */
function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

export interface ToastProps {
  item: ToastItem;
}

export function Toast({ item }: ToastProps) {
  const [remaining, setRemaining] = useState(item.durationMs);

  useEffect(() => {
    const startedAt = Date.now();
    setRemaining(item.durationMs);
    // The drain is decoration, so under reduced motion it is simply not run: the bar stays
    // at its full width and only the dismissal timer keeps its own schedule.
    const drain = prefersReducedMotion()
      ? null
      : setInterval(() => {
          setRemaining(Math.max(0, item.durationMs - (Date.now() - startedAt)));
        }, TICK_MS);
    const expire = setTimeout(() => {
      dismissToast(item.id);
    }, item.durationMs);
    return () => {
      if (drain !== null) clearInterval(drain);
      clearTimeout(expire);
    };
  }, [item.id, item.durationMs]);

  const onUndo = () => {
    dismissToast(item.id);
    // The call is made inside the promise, not handed to Promise.resolve, which would
    // have evaluated it first: an undo that throws on its way to its request would
    // otherwise escape the catch and die in the console instead of on screen.
    new Promise<void>((resolve) => {
      resolve(item.undo?.());
    }).catch((failure: unknown) => {
      console.error("toast: undo failed", failure);
      toast(failure instanceof ApiError ? failure.detail : UNDO_FAILED);
    });
  };

  return (
    <div
      aria-live="polite"
      className="pointer-events-auto w-[320px] overflow-hidden rounded-[10px] border border-line bg-panel"
    >
      <div className="flex items-center gap-3 px-3 py-2">
        <span className="flex-1 text-[13px] text-text">{item.message}</span>
        {item.undo !== undefined && (
          <Button variant="text" size="sm" onClick={onUndo}>
            Undo
          </Button>
        )}
      </div>
      <div
        aria-hidden="true"
        data-drain=""
        className="h-px bg-accent"
        style={{ width: `${(remaining / item.durationMs) * 100}%` }}
      />
    </div>
  );
}

export function Toaster() {
  const toasts = useToasts();
  const current = toasts[0];
  if (current === undefined) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex justify-center">
      <Toast key={current.id} item={current} />
    </div>
  );
}
