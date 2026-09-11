/**
 * This session's six figures. The awkward part is the end of a session: the API stops
 * reporting status.json's session block the moment the worker stops, so the panel holds
 * on to the last figures it saw live rather than blanking them to zero.
 */
import { useEffect, useRef, useState } from "react";

import type { InstancePayload } from "../api/types";
import { signed } from "../lib/format";
import { duration, hhmm } from "../lib/time";

/** States in which the API has stopped reporting a session, so the figures are frozen. */
const FROZEN = new Set(["stopped", "scheduled_break", "offline"]);

type Figures = {
  Games: string;
  Trophies: string;
  "Avg rank today": string;
  Disconnects: string;
  Duration: string;
  Interrupts: string;
};

function figuresOf(inst: InstancePayload, avgRank: number | null, interrupts: number): Figures {
  const session = inst.session;
  const start = session?.start_trophies ?? null;
  const last = session?.last_trophies ?? null;
  return {
    Games: String(inst.games_played ?? 0),
    // One null end of the pair makes the difference meaningless, so it reads 0, not NaN.
    Trophies: start === null || last === null ? "0" : signed(last - start),
    // Rank lives in games.csv, not the feed, so it comes from the stats route for today.
    "Avg rank today": avgRank === null ? "none" : avgRank.toFixed(1),
    Disconnects: String(session?.disconnect_count ?? 0),
    Duration: duration(session?.minutes_elapsed ?? 0),
    Interrupts: String(interrupts),
  };
}

/**
 * This session at a glance. When the worker stops, the API drops status.json's session
 * block and every figure would snap to zero, which reads as "the session did nothing".
 * The panel keeps the last figures it saw live and captions when the session ended,
 * preferring the timestamp of the feed's own `stop` line over the moment the browser
 * happened to notice.
 */
export function SessionPanel({
  inst,
  avgRank,
  interrupts,
  stopAt,
}: {
  inst: InstancePayload;
  avgRank: number | null;
  interrupts: number;
  stopAt: string | null;
}) {
  const live = !FROZEN.has(inst.state);
  const lastLive = useRef<Figures>(figuresOf(inst, avgRank, interrupts));
  const [endedAt, setEndedAt] = useState<string | null>(null);
  const shown = live ? figuresOf(inst, avgRank, interrupts) : lastLive.current;

  useEffect(() => {
    if (live) {
      lastLive.current = figuresOf(inst, avgRank, interrupts);
      setEndedAt(null);
      return;
    }
    setEndedAt((previous) => previous ?? stopAt ?? new Date().toISOString());
  });

  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-baseline gap-2">
        <h2 className="text-[13px] font-semibold">Session</h2>
        {endedAt === null ? null : (
          <span className="ml-auto text-[11px] text-muted">Session ended {hhmm(endedAt)}</span>
        )}
      </div>
      <dl className="grid grid-cols-3 gap-x-3 gap-y-2">
        {Object.entries(shown).map(([label, value]) => (
          <div key={label} className="flex flex-col">
            <dt className="text-[11px] text-muted">{label}</dt>
            <dd className="font-mono text-[15px] tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
