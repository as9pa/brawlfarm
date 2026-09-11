/**
 * The newest unread alert, above the grid.
 *
 * One line, one action. An offline alert is rewritten into a sentence with its age,
 * because "misses=3" means nothing to the person reading it; every other kind is the
 * instance, the alert's own title and its detail, which the API already writes for
 * people.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { dismissAlert } from "../api/alerts";
import { retryInstance } from "../api/instances";
import { queryKeys } from "../api/queries";
import type { Alert } from "../api/types";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { alertKindLabel, alertKindTone } from "../lib/states";
import { since } from "../lib/time";
import { failureMessage, toast } from "../lib/toast";

export interface AlertStripProps {
  alert: Alert;
  unread: number;
  onOpen: () => void;
}

export function alertSentence(alert: Alert, nowMs: number): string {
  if (alert.kind === "offline") {
    const age = since(Date.parse(alert.ts), nowMs);
    return `${alert.instance} has been offline for ${age}. BlueStacks window not found.`;
  }
  return `${alert.instance} ${alert.title.toLowerCase()}: ${alert.detail}`;
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
