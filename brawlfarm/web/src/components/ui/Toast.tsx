/**
 * The transient confirmation strip.
 *
 * Toaster shows the head of the queue in lib/toast.ts, so exactly one is visible and the
 * rest wait their turn. The hairline bar drains over the toast's own duration, which is
 * longer when an Undo is on offer because the user has a decision to make.
 */
import { useEffect, useState } from "react";

import { Button } from "./Button";
import { type ToastItem, dismissToast, useToasts } from "../../lib/toast";

const TICK_MS = 100;

export interface ToastProps {
  item: ToastItem;
}

export function Toast({ item }: ToastProps) {
  const [remaining, setRemaining] = useState(item.durationMs);

  useEffect(() => {
    const startedAt = Date.now();
    setRemaining(item.durationMs);
    const drain = setInterval(() => {
      setRemaining(Math.max(0, item.durationMs - (Date.now() - startedAt)));
    }, TICK_MS);
    const expire = setTimeout(() => {
      dismissToast(item.id);
    }, item.durationMs);
    return () => {
      clearInterval(drain);
      clearTimeout(expire);
    };
  }, [item.id, item.durationMs]);

  const onUndo = () => {
    dismissToast(item.id);
    void item.undo?.();
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
