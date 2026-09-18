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
import { type BlockState, timeline } from "../lib/schedule";
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
// Shape as well as tone: a hatched block, a solid one and an outline read apart with no
// colour at all, which is the point of the legend under the bar.
const BLOCK_TONE: Record<BlockState, string> = {
  past: "bg-idle opacity-40 hatch",
  active: "bg-accent",
  future: "border border-line bg-transparent",
};
// The legend, the blocks and the narrow-window list read from one place, so a swatch and
// the word beside it can never disagree.
const STATE_WORD: Record<BlockState, string> = {
  past: "Past",
  active: "Running now",
  future: "Later today",
};
const SWATCH = "inline-block h-2 w-4 shrink-0 rounded-[2px]";
const LEGEND: { key: string; word: string; swatch: string }[] = [
  { key: "past", word: STATE_WORD.past, swatch: `${SWATCH} ${BLOCK_TONE.past}` },
  { key: "active", word: STATE_WORD.active, swatch: `${SWATCH} ${BLOCK_TONE.active}` },
  { key: "future", word: STATE_WORD.future, swatch: `${SWATCH} ${BLOCK_TONE.future}` },
  // The now line is a rule and not a block, so its swatch is one too.
  { key: "now", word: "Now", swatch: "inline-block h-3 w-[2px] shrink-0 bg-accent" },
];
// Only the owner reads this panel, at this PC, so the offset would be noise: the one
// thing worth saying is that nothing here is in UTC.
const LOCAL = "Times are local.";
const RUN_FOR_HELP = "Starts now and ignores the schedule for this long.";
const RUN_FOR_ERROR = "Half an hour to 12 hours";
const MIN_HOURS = 0.5;
const MAX_HOURS = 12;

/** The first hour sits on the left edge and the last on the right, so neither number is
 * clipped by the bar it labels. */
function tickShift(hour: number): string | undefined {
  if (hour === 0) return undefined;
  if (hour === 24) return "translateX(-100%)";
  return "translateX(-50%)";
}

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
  const [busy, setBusy] = useState<null | "start" | "redraw">(null);
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

  /** One write in flight per button. A control is disabled by its own request only, so a
   * start does not grey out the draw beside it and neither can be sent twice. */
  const run = async (
    key: "start" | "redraw",
    call: Promise<unknown>,
    message: string | null,
  ) => {
    setBusy(key);
    try {
      await settle(call, message);
    } finally {
      setBusy(null);
    }
  };

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
  // An empty box is not a wrong number: it says nothing, so it is told nothing. Start
  // still explains itself through its own disabled reason.
  const typed = hours.trim() !== "" && Number.isFinite(parsed);
  const runnable = typed && parsed >= MIN_HOURS && parsed <= MAX_HOURS;

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
        // A group and not an image: role="img" would prune the blocks inside, and each
        // block's own span is what a reader needs once the summary has been read.
        <div
          className="flex flex-col gap-1.5"
          role="group"
          aria-label={bar.description}
          data-testid="schedule-figure"
        >
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
                title={block.label}
                className={`absolute top-1 h-4 rounded-[3px] ${BLOCK_TONE[block.state]}`}
                style={{ left: `${block.leftPct}%`, width: `${block.widthPct}%` }}
              >
                <span className="sr-only">{block.label}</span>
              </div>
            ))}
            <div
              className="absolute top-0 h-full w-[2px] bg-accent"
              style={{ left: `${bar.nowPct}%` }}
              data-testid="schedule-now"
            />
          </div>

          {/* The span is already in the bar's accessible name, so the numbers under it
              are decoration and stay out of the accessibility tree. */}
          <div className="relative h-3 w-full" aria-hidden="true">
            {bar.ticks.map((tick) => (
              <span
                key={tick.hour}
                className="absolute top-0 text-[10px] tabular-nums text-muted"
                style={{ left: `${tick.leftPct}%`, transform: tickShift(tick.hour) }}
                data-testid={`schedule-hour-${tick.hour}`}
              >
                {tick.hour}
              </span>
            ))}
          </div>

          <ul
            className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted"
            data-testid="schedule-legend"
          >
            {LEGEND.map((item) => (
              <li key={item.key} className="flex items-center gap-1.5">
                <span className={item.swatch} aria-hidden="true" />
                {item.word}
              </li>
            ))}
          </ul>

          <p className="text-[11px] text-muted">{LOCAL}</p>

          {/* A bar is hard to read in a narrow column, so the same blocks say themselves
              in words there instead. */}
          <ul
            className="flex flex-col gap-0.5 text-[12px] min-[1100px]:hidden"
            data-testid="schedule-list"
          >
            {bar.blocks.map((block) => (
              <li key={`${block.leftPct}-${block.widthPct}`} className="flex gap-2">
                <span className="t-figure">{block.label}</span>
                <span className="text-muted">{STATE_WORD[block.state]}</span>
              </li>
            ))}
          </ul>
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
          min={MIN_HOURS}
          max={MAX_HOURS}
          step={0.5}
          inputMode="decimal"
          suffix="hours"
          help={RUN_FOR_HELP}
          error={typed && !runnable ? RUN_FOR_ERROR : undefined}
          value={hours}
          onChange={setHours}
        />
        <Button
          variant="primary"
          size="sm"
          disabled={!runnable || busy === "start"}
          disabledReason={runnable ? undefined : "Enter a number of hours"}
          onClick={() => {
            void run(
              "start",
              startInstance(name, parsed),
              `Running ${name} for ${parsed} h`,
            );
          }}
        >
          Start
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={busy === "redraw"}
          onClick={() => {
            void run(
              "redraw",
              patchSchedule(name, { redraw: true }),
              "Redrawing today… new sessions appear within a minute.",
            );
            for (const delay of REDRAW_REFETCH_MS) {
              timers.current.push(setTimeout(refetch, delay));
            }
          }}
        >
          Draw new sessions
        </Button>
      </div>
    </section>
  );
}
