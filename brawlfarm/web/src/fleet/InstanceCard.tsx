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
 * match and not stuck on a popup. It refreshes every 5 s while the tab is visible and
 * stops entirely while it is hidden: a farming instance is serving the frame its worker
 * wrote anyway, but a stopped one costs an adb screencap against a live BlueStacks window
 * and a wall of cards should not spend that. An offline instance has no window to capture,
 * so its card shows the supervisor's own retry note instead.
 */
import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useState } from "react";
import { Link } from "react-router";

import {
  restartInstance,
  retryInstance,
  startInstance,
  stopInstance,
} from "../api/instances";
import { queryKeys } from "../api/queries";
import type { InstancePayload } from "../api/types";
import { Button } from "../components/ui/Button";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { StateChip } from "../components/ui/StateChip";
import { Thumb } from "../components/ui/Thumb";
import { useVisiblePolling } from "../live/useVisiblePolling";
import { NOT_SET, NOT_STARTED } from "../lib/copy";
import { num, signed } from "../lib/format";
import { STOPPABLE_STATES, phaseLabel } from "../lib/states";
import { age, duration, hhmm } from "../lib/time";
import { failureMessage, toast } from "../lib/toast";

const THUMB_MS = 5000;
const AGE_TICK_MS = 1000;
const RETRY_MINUTES_RE = /Retrying in (\d+) min/;

/** The overlay that makes the rest of the card clickable, and the card's own ring while
 * that link holds keyboard focus. Kept as names because they are one idea in two places. */
const STRETCHED_LINK = "after:absolute after:inset-0 after:content-[''] focus-visible:outline-none";
const CARD_RING =
  "has-[a:focus-visible]:outline-2 has-[a:focus-visible]:outline-offset-2 has-[a:focus-visible]:outline-accent";

/** The supervisor writes the minute count into its offline note; the fourth metric counts
 * down with it, so read the number back out rather than duplicating the backoff schedule
 * here. */
export function retryMinutes(note: string): number | null {
  const match = RETRY_MINUTES_RE.exec(note);
  if (match === null) return null;
  const minutes = Number(match[1]);
  return Number.isFinite(minutes) ? minutes : null;
}

export function breakCaption(until: string | null): string {
  return until === null ? "On a scheduled break" : `Break until ${hhmm(until)}`;
}

/** The fourth metric, label and all: "21:30" is a clock time and "4 min" is a countdown,
 * and only the label says which of the two you are reading. */
export function nextMetric(inst: InstancePayload): { label: string; value: string } {
  if (inst.state === "stopping") return { label: "Stops", value: "After this match" };
  if (inst.state === "offline") {
    const minutes = retryMinutes(inst.note);
    return { label: "Retry in", value: minutes === null ? NOT_SET : `${minutes} min` };
  }
  const idle = inst.state === "scheduled_break" || inst.state === "stopped";
  return {
    label: idle ? "Next session" : "Break at",
    value: inst.until === null ? NOT_SET : hhmm(inst.until),
  };
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] text-muted">{label}</div>
      <div className="t-figure text-[15px] text-text">{value}</div>
    </div>
  );
}

/** The note has one author, the server: the card prints the sentence it was sent and adds
 * nothing of its own to it. */
function OfflineBlock({ note, onRetry }: { note: string; onRetry: ReactNode }) {
  return (
    <div className="flex aspect-video w-full flex-col items-center justify-center gap-1.5 rounded-[6px] border border-line bg-panel-2 p-3 text-center">
      <p className="text-[13px] text-text">{note === "" ? NOT_SET : note}</p>
      <p className="text-[12px] text-muted">Open the instance, or {onRetry}.</p>
    </div>
  );
}

export interface InstanceCardProps {
  inst: InstancePayload;
}

export function InstanceCard({ inst }: InstanceCardProps) {
  const client = useQueryClient();
  const refreshMs = useVisiblePolling(THUMB_MS);
  const [confirming, setConfirming] = useState(false);
  const [frameAt, setFrameAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());

  // The frame ages on the status line now that nothing is drawn over the image, so the
  // card keeps the clock the thumbnail used to keep: one tick a second, and none at all
  // before the first frame or on an offline card that will never get one.
  useEffect(() => {
    if (frameAt === null) return;
    const tick = setInterval(() => setNow(Date.now()), AGE_TICK_MS);
    return () => clearInterval(tick);
  }, [frameAt]);

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
      toast(failureMessage(failure));
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
  const next = nextMetric(inst);
  // One line for the whole status. An empty half drops out with its comma rather than
  // leaving a card that starts or ends on one.
  const status = [phaseLabel(inst.phase), frameAt === null ? "" : `frame ${age(frameAt, now)}`]
    .filter((part) => part !== "")
    .join(", ");

  return (
    <article
      className={`relative rounded-[10px] border border-line bg-panel p-3 transition-colors duration-[120ms] hover:border-accent ${CARD_RING}`}
    >
      {inst.state === "offline" ? (
        <OfflineBlock
          note={inst.note}
          onRetry={
            <span className="relative z-10">
              <Button variant="quiet" size="sm" onClick={onRetry}>
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
          onFrame={(takenAt) => {
            setFrameAt(takenAt);
            setNow(Date.now());
          }}
        />
      )}

      <div className="mt-3 flex items-baseline gap-2">
        <Link
          to={`/instances/${inst.name}`}
          aria-label={`Open ${inst.name}`}
          className={`t-name text-[15px] font-semibold ${STRETCHED_LINK}`}
        >
          {inst.name}
        </Link>
        <StateChip state={inst.state} />
      </div>
      <p className="mt-1 truncate text-[12px] text-muted">{status}</p>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <Metric label="Games today" value={num(inst.today.games)} />
        <Metric label="Trophies today" value={signed(inst.today.trophies)} />
        {/* While it runs the minutes are this session's; once it has stopped the same
            figure is the last session's, and the label is what says so. */}
        <Metric
          label={stoppable ? "This session" : "Last session"}
          value={sessionMinutes === null ? NOT_STARTED : duration(sessionMinutes)}
        />
        <Metric label={next.label} value={next.value} />
      </div>

      <div className="relative z-10 mt-3 flex items-center gap-2 border-t border-line pt-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={!stoppable}
          disabledReason="Already stopped"
          onClick={onStop}
        >
          Stop
        </Button>
        {/* The same restart either way: a stopped instance has nothing to stop first, so
            the label says what the press will do rather than what the endpoint is called.
            Only the restart asks first: starting an instance interrupts nothing. */}
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            if (stoppable) setConfirming(true);
            else onRestart();
          }}
        >
          {stoppable ? "Restart" : "Start"}
        </Button>
      </div>

      {/* Fixed and above the stretched link either way, so it sits inside the card it
          belongs to rather than beside it. */}
      <ConfirmDialog
        open={confirming}
        onClose={() => setConfirming(false)}
        title={`Restart ${inst.name}?`}
        body="It stops now, not after this match, and starts again."
        confirmLabel="Restart"
        tone="bad"
        onConfirm={() => {
          setConfirming(false);
          onRestart();
        }}
      />
    </article>
  );
}
