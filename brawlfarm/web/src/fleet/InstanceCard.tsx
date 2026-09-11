/**
 * One instance, at a glance.
 *
 * The whole card is a link to the instance page, so the largest target does the most
 * likely thing. The three controls in the footer are buttons inside that link, so each
 * one stops the click from reaching it; that is the price of making the card itself
 * clickable, and it is paid in one helper rather than in every handler.
 *
 * The thumbnail is the headline: a screen is the fastest way to see that a bot is in a
 * match and not stuck on a popup. It refreshes every 15 s while the tab is visible and
 * stops entirely while it is hidden, because every frame is an adb screencap against a
 * live BlueStacks window. An offline instance has no window to capture, so its card shows
 * the supervisor's own retry note instead.
 */
import { useQueryClient } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import type { MouseEvent, ReactNode } from "react";
import { Link, useNavigate } from "react-router";

import { ApiError } from "../api/client";
import {
  restartInstance,
  retryInstance,
  startInstance,
  stopInstance,
} from "../api/instances";
import { queryKeys } from "../api/queries";
import type { InstancePayload, InstanceState } from "../api/types";
import { Button } from "../components/ui/Button";
import { StateChip } from "../components/ui/StateChip";
import { Thumb } from "../components/ui/Thumb";
import { useVisiblePolling } from "../live/useVisiblePolling";
import { signed } from "../lib/format";
import { phaseLabel } from "../lib/states";
import { duration, hhmm } from "../lib/time";
import { toast } from "../lib/toast";

const THUMB_MS = 15000;
const RETRY_MINUTES_RE = /Retrying in (\d+) min/;

const STOPPABLE_STATES: ReadonlySet<InstanceState> = new Set<InstanceState>([
  "farming",
  "starting",
  "stopping",
  "reconnecting",
]);

export const NEXT_LABELS: Record<InstanceState, string> = {
  farming: "Next break",
  starting: "Next break",
  stopping: "Next break",
  reconnecting: "Next break",
  scheduled_break: "Next session",
  stopped: "Next session",
  offline: "Next retry",
};

/** The supervisor writes "BlueStacks window not found. Retrying in 4 min."; the card
 * shows the number on its own as well, so read it back out rather than duplicating the
 * backoff schedule here. */
export function retryMinutes(note: string): number | null {
  const match = RETRY_MINUTES_RE.exec(note);
  if (match === null) return null;
  const minutes = Number(match[1]);
  return Number.isFinite(minutes) ? minutes : null;
}

export function breakCaption(until: string | null): string {
  return until === null ? "On a scheduled break" : `Break until ${hhmm(until)}`;
}

export function nextValue(inst: InstancePayload): string {
  if (inst.state === "offline") {
    const minutes = retryMinutes(inst.note);
    return minutes === null ? "soon" : `${minutes} min`;
  }
  return inst.until === null ? "none" : hhmm(inst.until);
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] text-muted">{label}</div>
      <div className="font-mono text-[15px] tabular-nums text-text">{value}</div>
    </div>
  );
}

function OfflineBlock({ note, onRetry }: { note: string; onRetry: ReactNode }) {
  const minutes = retryMinutes(note);
  return (
    <div className="flex aspect-video w-full flex-col items-center justify-center gap-1.5 rounded-[6px] border border-line bg-panel-2 p-3 text-center">
      <StateChip state="offline" />
      <p className="text-[13px] text-text">
        {minutes === null
          ? "BlueStacks window not found. Retrying soon."
          : `BlueStacks window not found. Retrying in ${minutes} min.`}
      </p>
      <p className="text-[12px] text-muted">Open the instance, or {onRetry}.</p>
    </div>
  );
}

export interface InstanceCardProps {
  inst: InstancePayload;
}

export function InstanceCard({ inst }: InstanceCardProps) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const refreshMs = useVisiblePolling(THUMB_MS);

  const refresh = () => {
    void client.invalidateQueries({ queryKey: queryKeys.instances() });
  };

  /** Every footer control lives inside the card's own link. Nothing is announced until
   * the request has settled either: a rejection speaks the ApiError's own detail -- the
   * API's sentence, or the "cannot reach brawlfarm" one a dead server produces -- and the
   * success toast never fires. */
  const act = (event: MouseEvent<HTMLButtonElement>, run: () => Promise<void>) => {
    event.preventDefault();
    event.stopPropagation();
    void run().catch((failure: unknown) => {
      toast(failure instanceof ApiError ? failure.detail : "Request failed");
    });
  };

  const onStop = (event: MouseEvent<HTMLButtonElement>) =>
    act(event, async () => {
      await stopInstance(inst.name);
      refresh();
      toast(`Stopping ${inst.name} after this match`, {
        undo: async () => {
          await startInstance(inst.name);
          refresh();
        },
      });
    });

  const onRestart = (event: MouseEvent<HTMLButtonElement>) =>
    act(event, async () => {
      await restartInstance(inst.name);
      refresh();
      toast(`Restarting ${inst.name}`);
    });

  const onRetry = (event: MouseEvent<HTMLButtonElement>) =>
    act(event, async () => {
      await retryInstance(inst.name);
      refresh();
      toast(`Retrying ${inst.name} now`);
    });

  const stoppable = STOPPABLE_STATES.has(inst.state);
  const sessionMinutes = inst.session?.minutes_elapsed ?? null;

  return (
    <Link
      to={`/instances/${inst.name}`}
      className="block rounded-[10px] border border-line bg-panel p-3 transition-colors duration-[120ms] hover:border-accent"
    >
      {inst.state === "offline" ? (
        <OfflineBlock
          note={inst.note}
          onRetry={
            <Button variant="text" size="sm" onClick={onRetry}>
              Retry now
            </Button>
          }
        />
      ) : (
        <Thumb
          name={inst.name}
          refreshMs={refreshMs}
          dimmed={inst.state === "scheduled_break"}
          caption={inst.state === "scheduled_break" ? breakCaption(inst.until) : undefined}
          overlay={<StateChip state={inst.state} />}
        />
      )}

      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-[15px] font-semibold">{inst.name}</span>
        <span className="font-mono text-[12px] tabular-nums text-muted">{inst.adb_port}</span>
        <span className="flex-1 truncate text-right text-[12px] text-muted">
          {phaseLabel(inst.phase)}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <Metric label="Games today" value={String(inst.today.games)} />
        <Metric label="Trophies today" value={signed(inst.today.trophies)} />
        <Metric
          label="Session"
          value={sessionMinutes === null ? "none" : duration(sessionMinutes)}
        />
        <Metric label={NEXT_LABELS[inst.state]} value={nextValue(inst)} />
      </div>

      <div className="mt-3 flex items-center gap-2 border-t border-line pt-2">
        <Button
          variant="quiet"
          size="sm"
          disabled={!stoppable}
          disabledReason="Not running"
          onClick={onStop}
        >
          Stop
        </Button>
        <Button variant="quiet" size="sm" onClick={onRestart}>
          Restart
        </Button>
        <span className="flex-1" />
        <Button
          variant="text"
          size="sm"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            void navigate(`/instances/${inst.name}`);
          }}
        >
          Open
          <ChevronRight size={16} strokeWidth={1.6} aria-hidden="true" />
        </Button>
      </div>
    </Link>
  );
}
