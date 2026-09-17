/**
 * The newest unread alert, above the grid.
 *
 * One line, one action. Every kind is rewritten into a sentence that says what happened
 * and the one thing to do about it, because "misses=3" means nothing to the person
 * reading it.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { dismissAlert } from "../api/alerts";
import { retryInstance } from "../api/instances";
import { queryKeys } from "../api/queries";
import type { Alert } from "../api/types";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { REQUIRED_SIZE } from "../lib/copy";
import { alertKindLabel, alertKindTone } from "../lib/states";
import { since } from "../lib/time";
import { failureMessage, toast } from "../lib/toast";

export interface AlertStripProps {
  alert: Alert;
  unread: number;
  onOpen: () => void;
}

/**
 * One sentence per panel kind, each ending in the action that clears it. The raw fields
 * are not lost: they stay visible in the drawer (`app/AlertsDrawer.tsx:79`), and
 * `brawlfarm/api/alerts.py:66` is still the source of that text.
 */
const SENTENCES: Record<string, (instance: string, age: string) => string> = {
  offline: (instance, age) =>
    `${instance} has been offline for ${age}. Check that the BlueStacks window is open, then press Retry now on its card.`,
  recover: (instance) =>
    `${instance} got stuck on a screen and is working its way back. Open it to watch.`,
  wrong_mode: (instance) => `${instance} picked the wrong mode and switched back. Nothing to do.`,
  bad_resolution: (instance) =>
    `${instance} is not at ${REQUIRED_SIZE}. Set the BlueStacks display to ${REQUIRED_SIZE} and restart it.`,
  crash: (instance) => `${instance} crashed. Press Restart on its card.`,
  recalibrate: (instance) =>
    `${instance} needs recalibration. Open Calibration and record a new session.`,
};

export function alertSentence(alert: Alert, nowMs: number): string {
  if (!(alert.kind in SENTENCES)) {
    return `${alert.instance}: ${alert.title.toLowerCase()}. Open Alerts for the details.`;
  }
  return SENTENCES[alert.kind](alert.instance, since(Date.parse(alert.ts), nowMs));
}

export function AlertStrip({ alert, unread, onOpen }: AlertStripProps) {
  const client = useQueryClient();
  // Frozen at mount: the strip is replaced whenever the alert list changes, and a ticking
  // age here would rerender the whole Fleet page every second for no benefit.
  const [nowMs] = useState(() => Date.now());

  /** Nothing is announced until the request has settled, and a rejection speaks the
   * ApiError's own detail rather than disappearing into an unhandled promise. */
  const failed = (failure: unknown) => {
    toast(failureMessage(failure));
  };

  const onDismiss = () => {
    void dismissAlert(alert.id)
      .then(() => {
        void client.invalidateQueries({ queryKey: queryKeys.alerts() });
      })
      .catch(failed);
  };

  const onRetry = () => {
    void retryInstance(alert.instance)
      .then(() => {
        void client.invalidateQueries({ queryKey: queryKeys.instances() });
        toast(`Retrying ${alert.instance} now`);
      })
      .catch(failed);
  };

  return (
    <div className="flex items-center gap-3 rounded-[10px] border border-line bg-panel px-3 py-2">
      <Chip tone={alertKindTone(alert.kind)}>{alertKindLabel(alert.kind)}</Chip>
      <p className="min-w-0 flex-1 truncate text-[13px] text-text">
        {alertSentence(alert, nowMs)}
      </p>
      {alert.kind === "offline" && (
        <Button variant="text" size="sm" onClick={onRetry}>
          Retry now
        </Button>
      )}
      <Button variant="text" size="sm" onClick={onDismiss}>
        Dismiss
      </Button>
      {unread > 1 && (
        <Button variant="text" size="sm" onClick={onOpen}>
          {`${unread - 1} more`}
        </Button>
      )}
    </div>
  );
}
