/**
 * This session's six figures. The awkward part is the end of a session: the API stops
 * reporting status.json's session block the moment the worker stops, so the panel holds
 * on to the last figures it saw live rather than blanking them to zero. On a cold load
 * there is nothing live to hold on to, so it reads inst.last_session instead, which is the
 * same session as told by the files the worker left behind.
 */
import { useEffect, useRef, useState } from "react";

import type { InstancePayload, LastSession } from "../api/types";
import { count, NO_GAMES_YET, NOT_YET } from "../lib/copy";
import { signed } from "../lib/format";
import { dayTime, duration } from "../lib/time";

/** States in which the API has stopped reporting a session, so the figures are frozen. */
const FROZEN = new Set(["stopped", "scheduled_break", "offline"]);

/** One figure and whether it is a phrase rather than a number. A phrase set in the mono
 * column reads as data, so the two are drawn differently. */
type Figure = { value: string; prose: boolean };

type Figures = {
  Games: Figure;
  Trophies: Figure;
  "Avg rank": Figure;
  Disconnects: Figure;
  Duration: Figure;
  Interrupts: Figure;
};

function num(value: string): Figure {
  return { value, prose: false };
}

function words(value: string): Figure {
  return { value, prose: true };
}

function figuresOf(inst: InstancePayload, avgRank: number | null, interrupts: number): Figures {
  const session = inst.session;
  const start = session?.start_trophies ?? null;
  const last = session?.last_trophies ?? null;
  return {
    Games: num(count(inst.games_played ?? 0)),
    // One null end of the pair makes the difference meaningless, so it says so rather
    // than claiming a round zero.
    Trophies: start === null || last === null ? words(NOT_YET) : num(signed(last - start)),
    // Rank lives in games.csv, not the feed, so it comes from the stats route for today.
    "Avg rank": avgRank === null ? words(NO_GAMES_YET) : num(avgRank.toFixed(1)),
    Disconnects: num(count(session?.disconnect_count ?? 0)),
    Duration: num(duration(session?.minutes_elapsed ?? 0)),
    Interrupts: num(count(interrupts)),
  };
}

/** The same six figures as api/sessions.py read them off the files. */
function figuresOfLast(last: LastSession): Figures {
  return {
    Games: num(count(last.games)),
    Trophies: num(signed(last.trophies)),
    "Avg rank": last.avg_rank === null ? words(NO_GAMES_YET) : num(last.avg_rank.toFixed(1)),
    Disconnects: num(count(last.disconnects)),
    Duration: num(duration(Math.floor(last.duration_s / 60))),
    Interrupts: num(count(last.interrupts)),
  };
}

/**
 * This session at a glance. When the worker stops, the API drops status.json's session
 * block and every figure would snap to zero, which reads as "the session did nothing".
 * The panel keeps the last figures it saw live and captions when the session ended,
 * preferring the timestamp of the feed's own `stop` line over the moment the browser
 * happened to notice, including when that line only arrives on a later poll.
 *
 * A panel that mounts already frozen has no live figures to keep, so it starts from
 * inst.last_session and from that session's own end. The moment a worker goes live the
 * panel follows it and never reads last_session again for that mount.
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
  const cold = !live && inst.last_session !== null;
  const lastLive = useRef<Figures>(
    cold && inst.last_session !== null
      ? figuresOfLast(inst.last_session)
      : figuresOf(inst, avgRank, interrupts),
  );
  const [endedAt, setEndedAt] = useState<string | null>(
    cold && inst.last_session !== null ? inst.last_session.ended_at : null,
  );
  const shown = live ? figuresOf(inst, avgRank, interrupts) : lastLive.current;

  useEffect(() => {
    if (live) {
      lastLive.current = figuresOf(inst, avgRank, interrupts);
      setEndedAt(null);
      return;
    }
    // The feed's own stop line is the better answer whenever it exists, and it usually
    // arrives a poll after the state does. The browser's clock is only a stand-in until
    // then, so it is replaced rather than kept. The seeded last_session end counts as a
    // previous answer, so a cold load keeps its real caption until a stop line turns up.
    setEndedAt((previous) => stopAt ?? previous ?? new Date().toISOString());
  });

  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-baseline gap-2">
        <h2 className="text-[13px] font-semibold">Session</h2>
        {endedAt === null ? null : (
          <span className="ml-auto text-[11px] text-muted">Session ended {dayTime(endedAt)}</span>
        )}
      </div>
      <dl className="grid grid-cols-3 gap-x-3 gap-y-2">
        {Object.entries(shown).map(([label, figure]) => (
          <div key={label} className="flex flex-col">
            <dt className="text-[11px] text-muted">{label}</dt>
            <dd
              className={
                figure.prose ? "text-[13px] text-muted" : "font-mono text-[15px] tabular-nums"
              }
            >
              {figure.value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
