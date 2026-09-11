/**
 * One instance, at a glance.
 *
 * The card is an article, and only the instance name is a link. That link is stretched
 * over the whole card by a pseudo-element, so the largest target still does the most
 * likely thing without nesting four buttons inside an anchor: the controls sit on their
 * own layer above the overlay and are ordinary buttons again, and the link's accessible
 * name is "Open Pie64" rather than the entire card read aloud. The focus ring moves to
 * the card while the name has keyboard focus, because a ring around six characters does
 * not tell you which instance you are about to open.
 *
 * The thumbnail is the headline: a screen is the fastest way to see that a bot is in a
 * match and not stuck on a popup. It refreshes every 15 s while the tab is visible and
 * stops entirely while it is hidden, because every frame is an adb screencap against a
 * live BlueStacks window. An offline instance has no window to capture, so its card shows
 * the supervisor's own retry note instead.
 */
import { useQueryClient } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
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

/** The overlay that makes the rest of the card clickable, and the card's own ring while
 * that link holds keyboard focus. Kept as names because they are one idea in two places. */
const STRETCHED_LINK = "after:absolute after:inset-0 after:content-[''] focus-visible:outline-none";
const CARD_RING =
  "has-[a:focus-visible]:outline-2 has-[a:focus-visible]:outline-offset-2 has-[a:focus-visible]:outline-accent";

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

  /** Stopping, starting and restarting all write the schedule's override, and nothing on
   * that route arrives over the event stream, so the instance page's schedule panel is
   * asked again once the request has settled either way: a refused stop may still have
   * cleared an override on its way out. */
  const settled = <T,>(call: Promise<T>): Promise<T> =>
    call.finally(() => {
      void client.invalidateQueries({ queryKey: queryKeys.schedule(inst.name) });
    });

  /** Nothing is announced until the request has settled: a rejection speaks the ApiError's
   * own detail -- the API's sentence, or the "cannot reach brawlfarm" one a dead server
   * produces -- and the success toast never fires. */
  const act = (run: () => Promise<void>) => {
    void run().catch((failure: unknown) => {
      toast(failure instanceof ApiError ? failure.detail : "Request failed");
    });
  };

  const onStop = () =>
    act(async () => {
      await settled(stopInstance(inst.name));
      refresh();
      toast(`Stopping ${inst.name} after this match`, {
        undo: async () => {
          await settled(startInstance(inst.name));
          refresh();
        },
      });
    });

  const onRestart = () =>
    act(async () => {
      await settled(restartInstance(inst.name));
      refresh();
      toast(`Restarting ${inst.name}`);
    });

  const onRetry = () =>
    act(async () => {
      await retryInstance(inst.name);
      refresh();
      toast(`Retrying ${inst.name} now`);
    });

  const stoppable = STOPPABLE_STATES.has(inst.state);
  const sessionMinutes = inst.session?.minutes_elapsed ?? null;

  return (
    <article
      className={`relative rounded-[10px] border border-line bg-panel p-3 transition-colors duration-[120ms] hover:border-accent ${CARD_RING}`}
    >
      {inst.state === "offline" ? (
        <OfflineBlock
          note={inst.note}
          onRetry={
            <span className="relative z-10">
              <Button variant="text" size="sm" onClick={onRetry}>
                Retry now
              </Button>
            </span>
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
        <Link
          to={`/instances/${inst.name}`}
          aria-label={`Open ${inst.name}`}
          className={`text-[15px] font-semibold ${STRETCHED_LINK}`}
        >
          {inst.name}
        </Link>
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

      <div className="relative z-10 mt-3 flex items-center gap-2 border-t border-line pt-2">
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
          onClick={() => {
            void navigate(`/instances/${inst.name}`);
          }}
        >
          Open
          <ChevronRight size={16} strokeWidth={1.6} aria-hidden="true" />
        </Button>
      </div>
    </article>
  );
}
