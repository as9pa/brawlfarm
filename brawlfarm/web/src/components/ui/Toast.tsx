/**
 * The transient confirmation strip.
 *
 * Toaster shows the head of the queue in lib/toast.ts, so exactly one is visible and the
 * rest wait their turn. The hairline bar drains over the toast's own duration, which is
 * longer when an Undo is on offer because the user has a decision to make. The drain is a
 * single CSS width transition rather than a repainting timer, so the compositor sweeps it
 * smoothly instead of stepping it. A reader who asked for less motion never starts it and
 * gets the same bar standing still.
 *
 * An Undo is usually an API call, so a failed one has to land somewhere: it becomes a
 * second toast carrying the API's own sentence, never a silent unhandled rejection and
 * never an exception thrown out of the click handler. A Retry is the same call again and
 * fails the same way, so it answers for itself the same way.
 *
 * The tone reaches the reader three ways, because the colour alone reaches nobody who
 * cannot see it: the hairline takes the tone's colour, ok and bad take an icon, and a bad
 * toast is announced as an alert rather than politely.
 */
import { CircleAlert, CircleCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "./Button";
import { ApiError } from "../../api/client";
import {
  type ToastItem,
  type ToastTone,
  dismissToast,
  failureMessage,
  toast,
  useToasts,
} from "../../lib/toast";

const UNDO_FAILED = "Undo failed";

const TONE_BAR: Record<ToastTone, string> = {
  ok: "bg-ok",
  bad: "bg-bad",
  info: "bg-accent",
};

/** The icon sits on top of the colour rather than carrying the meaning on its own, so an
 * info toast goes without one instead of reaching for a shape that says nothing. */
const TONE_ICON: Record<ToastTone, typeof CircleCheck | null> = {
  ok: CircleCheck,
  bad: CircleAlert,
  info: null,
};

/** jsdom and any non-browser render have no matchMedia; no implementation means the
 * reader has stated no preference. */
function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

export interface ToastProps {
  item: ToastItem;
}

export function Toast({ item }: ToastProps) {
  const [drained, setDrained] = useState(false);

  useEffect(() => {
    setDrained(false);
    // The full width has to reach the screen before the transition to zero is applied, or
    // there is no starting value to sweep from. A second frame covers the engines that
    // still fold a lone rAF callback into that first paint.
    let second = 0;
    // The drain is decoration, so under reduced motion it is simply not started: the bar
    // stays at its full width and only the dismissal timer keeps its own schedule. Letting
    // it run would not slow it down either, since theme.css zeroes transition durations
    // under the same media query and the bar would jump straight to nothing.
    const first = prefersReducedMotion()
      ? 0
      : requestAnimationFrame(() => {
          second = requestAnimationFrame(() => {
            setDrained(true);
          });
        });
    const expire = setTimeout(() => {
      dismissToast(item.id);
    }, item.durationMs);
    return () => {
      cancelAnimationFrame(first);
      cancelAnimationFrame(second);
      clearTimeout(expire);
    };
  }, [item.id, item.durationMs]);

  // Never two actions in one strip: a reader offered both has to work out which one puts
  // it back. The undo is the one that undoes something, so it stands and the retry goes.
  const retry = item.undo === undefined ? item.retry : undefined;
  const Icon = TONE_ICON[item.tone];
  const isBad = item.tone === "bad";

  useEffect(() => {
    if (item.undo !== undefined && item.retry !== undefined) {
      console.error("toast: a toast offered both an undo and a retry; the retry was dropped");
    }
  }, [item.id, item.undo, item.retry]);

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

  const onRetry = () => {
    dismissToast(item.id);
    // Inside the promise for the same reason the undo is: a retry that throws on its way
    // to its request has to reach the reader rather than die in the console.
    new Promise<void>((resolve) => {
      resolve(retry?.());
    }).catch((failure: unknown) => {
      console.error("toast: retry failed", failure);
      // The follow-up carries no retry of its own: one that re-arms on every failure is a
      // loop the reader has to click their way out of.
      toast(failureMessage(failure), { tone: "bad" });
    });
  };

  return (
    <div
      role={isBad ? "alert" : undefined}
      aria-live={isBad ? undefined : "polite"}
      className="pointer-events-auto w-[320px] overflow-hidden rounded-[10px] border border-line bg-panel"
    >
      <div className="flex items-center gap-3 px-3 py-2">
        {Icon !== null && <Icon size={14} strokeWidth={1.6} aria-hidden="true" />}
        <span className="flex-1 text-[13px] text-text">{item.message}</span>
        {item.undo !== undefined && (
          <Button variant="quiet" size="sm" onClick={onUndo}>
            Undo
          </Button>
        )}
        {retry !== undefined && (
          <Button variant="quiet" size="sm" onClick={onRetry}>
            Retry
          </Button>
        )}
      </div>
      <div
        aria-hidden="true"
        data-drain=""
        className={`h-px ${TONE_BAR[item.tone]}`}
        style={{
          width: drained ? "0%" : "100%",
          transition: drained ? `width ${item.durationMs}ms linear` : undefined,
        }}
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
