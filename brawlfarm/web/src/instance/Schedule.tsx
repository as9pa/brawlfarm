/**
 * Today's schedule: the drawn sessions as a bar against the wall clock, the on/off
 * switch, the manual override, and the two controls that act right now. The geometry
 * lives in lib/schedule so this file is only about what the reader sees and presses.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { startInstance } from "../api/instances";
import { queryKeys } from "../api/queries";
import { getSchedule, patchSchedule } from "../api/schedule";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";
import { Switch } from "../components/ui/Switch";
import { timeline } from "../lib/schedule";
import { hhmm } from "../lib/time";
import { toast } from "../lib/toast";

const EMPTY = "No sessions drawn yet. The supervisor draws today on its next tick.";
// The draw happens on a supervisor tick, not on the request, so ask again twice: once for
// a tick that was already due, once for the poke this PUT sent.
const REDRAW_REFETCH_MS = [2000, 10_000];
const BLOCK_TONE: Record<string, string> = {
  past: "bg-idle opacity-40",
  active: "bg-ok",
  future: "bg-idle",
};

/** Today's sessions, the on/off switch, the manual override and the two manual controls. */
export function Schedule({ name }: { name: string }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: queryKeys.schedule(name),
    queryFn: () => getSchedule(name),
  });
  const [hours, setHours] = useState("2");
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
      toast(error instanceof ApiError ? error.detail : "Request failed");
      return;
    }
    if (message !== null) toast(message);
    refetch();
  };

  const patch = (body: Parameters<typeof patchSchedule>[1], message: string | null) =>
    settle(patchSchedule(name, body), message);

  if (query.isPending) {
    return <section className="rounded-[10px] border border-line bg-panel p-3" />;
  }
  if (query.isError) {
    return <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />;
  }

  const payload = query.data;
  const bar = timeline(payload, payload.now);
  const parsed = Number(hours);
  const runnable = Number.isFinite(parsed) && parsed > 0;

  return (
    <section className="flex flex-col gap-3 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-center gap-2">
        <h2 className="text-[13px] font-semibold">Schedule</h2>
        <div className="ml-auto">
          <Switch
            label="Schedule on"
            checked={payload.enabled}
            onChange={(enabled) =>
              void patch({ enabled }, enabled ? "Schedule on" : "Schedule off")
            }
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
            {`Override: ${payload.override.mode} until ${hhmm(payload.override.until)}`}
          </Chip>
          {/* An icon, not a word: the chip beside it already says what is being cleared,
              and aria-label carries the sentence for a screen reader. Clearing the chip
              is its own confirmation, so there is no toast. */}
          <button
            type="button"
            aria-label="Clear override"
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
          variant="quiet"
          size="sm"
          onClick={() => {
            void patch({ redraw: true }, "Redrawing today; new sessions appear after the next tick");
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
