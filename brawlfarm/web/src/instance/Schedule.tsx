/**
 * Today's schedule: the drawn sessions as a bar against the wall clock, the on/off
 * switch, the manual override, and the two controls that act right now. The geometry
 * lives in lib/schedule so this file is only about what the reader sees and presses.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { startInstance } from "../api/instances";
import { queryKeys } from "../api/queries";
import { getSchedule, patchSchedule } from "../api/schedule";
import type { SchedulePayload } from "../api/types";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";
import { PanelSkeleton } from "../components/ui/PanelSkeleton";
import { Switch } from "../components/ui/Switch";
import { useVisiblePolling } from "../live/useVisiblePolling";
import { timeline } from "../lib/schedule";
import { hhmm } from "../lib/time";
import { failureMessage, toast } from "../lib/toast";

const EMPTY = "No sessions drawn yet. brawlfarm draws today’s sessions within a minute.";
// The draw happens on a supervisor tick, not on the request, so ask again twice: once for
// a tick that was already due, once for the poke this PUT sent.
const REDRAW_REFETCH_MS = [2000, 10_000];
// Nothing on this route is pushed over the event stream: the supervisor draws the day and
// writes an override on its own tick, and a stop from another window is invisible here.
// The same cadence as the instances list (api/useInstances.ts), and it stops with the tab.
const POLL_MS = 15000;
const BLOCK_TONE: Record<string, string> = {
  past: "bg-idle opacity-40",
  active: "bg-ok",
  future: "bg-idle",
};

/** Today's sessions, the on/off switch, the manual override and the two manual controls. */
export function Schedule({ name }: { name: string }) {
  const client = useQueryClient();
  const refetchInterval = useVisiblePolling(POLL_MS);
  const query = useQuery({
    queryKey: queryKeys.schedule(name),
    queryFn: () => getSchedule(name),
    refetchInterval,
  });
  const [hours, setHours] = useState("2");
  const [switching, setSwitching] = useState(false);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(
    () => () => {
      for (const id of timers.current) clearTimeout(id);
    },
    [],
  );

  const refetch = () => {
    void client.invalidateQueries({ queryKey: queryKeys.schedule(name) });
  };

  /** Nothing is announced until the request has settled. A rejection speaks the ApiError's
   * own detail -- the API's sentence, or the "cannot reach brawlfarm" one a dead server
   * produces -- and the success message never fires. A null message is a control whose
   * result is already visible, like the override chip disappearing. */
  const settle = async (call: Promise<unknown>, message: string | null) => {
    try {
      await call;
    } catch (error) {
      toast(failureMessage(error));
      return;
    }
    if (message !== null) toast(message);
    refetch();
  };

  const patch = (body: Parameters<typeof patchSchedule>[1], message: string | null) =>
    settle(patchSchedule(name, body), message);

  /** The switch is the one control whose result is the switch itself, so it moves under
   * the finger and the cache is corrected when the write lands, the same shape as the
   * farm plan's saves. It is disabled until then: a second click on a switch that had
   * not moved yet would send the opposite value and leave the two disagreeing. */
  const onSwitch = async (enabled: boolean) => {
    const before = client.getQueryData<SchedulePayload>(queryKeys.schedule(name));
    if (before === undefined) return;
    client.setQueryData<SchedulePayload>(queryKeys.schedule(name), { ...before, enabled });
    setSwitching(true);
    try {
      await patchSchedule(name, { enabled });
    } catch (error) {
      client.setQueryData<SchedulePayload>(queryKeys.schedule(name), before);
      toast(failureMessage(error));
      return;
    } finally {
      setSwitching(false);
    }
    toast(enabled ? "Schedule on" : "Schedule off");
    refetch();
  };

  if (query.isPending) {
    return <PanelSkeleton label="the schedule" rows={3} />;
  }
  if (query.isError) {
    return <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />;
  }

  const payload = query.data;
  const bar = timeline(payload, payload.now);
  const parsed = Number(hours);
  // The same half hour the field asks for. Without it the button disagreed with its own
  // box: a typed 0.3 stayed in the input as invalid and still started a run.
  const runnable = Number.isFinite(parsed) && parsed >= 0.5;

  return (
    <section className="flex flex-col gap-3 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-center gap-2">
        <h2 className="text-[13px] font-semibold">Schedule</h2>
        <div className="ml-auto">
          <Switch
            label="Schedule on"
            checked={payload.enabled ?? false}
            disabled={switching}
            onChange={(enabled) => void onSwitch(enabled)}
          />
        </div>
      </div>

      {payload.sessions.length === 0 ? (
        <p className="text-[13px] text-muted">{EMPTY}</p>
      ) : (
        <div
          className="relative h-6 w-full overflow-hidden rounded-[6px] bg-panel-2"
          data-testid="schedule-bar"
        >
          {bar.ticks.map((tick) => (
            <div
              key={tick.hour}
              className="absolute top-0 h-full w-px bg-line"
              style={{ left: `${tick.leftPct}%` }}
            />
          ))}
          {bar.blocks.map((block) => (
            <div
              key={`${block.leftPct}-${block.widthPct}`}
              className={`absolute top-1 h-4 rounded-[3px] ${BLOCK_TONE[block.state]}`}
              style={{ left: `${block.leftPct}%`, width: `${block.widthPct}%` }}
            />
          ))}
          <div
            className="absolute top-0 h-full w-[2px] bg-accent"
            style={{ left: `${bar.nowPct}%` }}
            data-testid="schedule-now"
          />
        </div>
      )}

      {payload.override === null ? null : (
        <div className="flex items-center gap-2">
          <Chip tone={payload.override.mode === "run" ? "ok" : "warn"}>
            {payload.override.mode === "run"
              ? `Running until ${hhmm(payload.override.until)}`
              : `Paused until ${hhmm(payload.override.until)}`}
          </Chip>
          {/* An icon, not a word: the chip beside it already says what is being cleared,
              and aria-label carries the sentence for a screen reader. Clearing the chip
              is its own confirmation, so there is no toast. */}
          <button
            type="button"
            aria-label="Resume schedule"
            onClick={() => void patch({ clear_override: true }, null)}
            className="rounded-[6px] p-1 text-muted transition-colors duration-[120ms] hover:text-text"
          >
            <X size={16} strokeWidth={1.6} aria-hidden="true" />
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <Field
          label="Run for"
          id={`${name}-hours`}
          type="number"
          min={0.5}
          step={0.5}
          suffix="hours"
          value={hours}
          onChange={setHours}
        />
        <Button
          variant="primary"
          size="sm"
          disabled={!runnable}
          disabledReason="Enter a number of hours"
          onClick={() => {
            void settle(startInstance(name, parsed), `Running ${name} for ${parsed} h`);
          }}
        >
          Start
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            void patch(
              { redraw: true },
              "Redrawing today… new sessions appear within a minute.",
            );
            for (const delay of REDRAW_REFETCH_MS) {
              timers.current.push(setTimeout(refetch, delay));
            }
          }}
        >
          Redraw today
        </Button>
      </div>
    </section>
  );
}
