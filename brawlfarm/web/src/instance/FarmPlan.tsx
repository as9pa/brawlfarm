/**
 * The farm plan editor. Every control writes straight through: the cache is updated
 * first so the switch moves under the finger, the PUT follows, and a failure puts the
 * previous values back and shows the API's own sentence inline. The roster arrives on
 * the same response (task 7), so the queue, the progress bar and the fallback box never
 * need a second request.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { getConnection } from "../api/connection";
import { getPlan, putPlan } from "../api/plans";
import { queryKeys } from "../api/queries";
import type { ConnectionStatus, FarmPlan as FarmPlanBody, PlanResponse } from "../api/types";
import { BrawlerIcon } from "../components/ui/BrawlerIcon";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";
import { Segmented } from "../components/ui/Segmented";
import { Switch } from "../components/ui/Switch";
import { count, NO_BRAWLER_YET, NOT_YET, QUEUE_EMPTY } from "../lib/copy";
import { hhmm } from "../lib/time";
import { toast } from "../lib/toast";

const PRESTIGE_GOAL = 1000; // core/farmplan.PRESTIGE_GOAL: prestige finishes a brawler here
const DEBOUNCE_MS = 500; // a typed field saves once the typing stops, not per keystroke

/** The five keys the API stores, lifted out of the enriched response. */
function planOf(response: PlanResponse): FarmPlanBody {
  return {
    mode: response.mode,
    prestige_start: response.prestige_start,
    goal_trophies: response.goal_trophies,
    maxed_fallback: response.maxed_fallback,
    quest_aware: response.quest_aware,
  };
}

/** Why there is no roster, in words that say what to do about it (phase 5 brief section
 * 5). The rejected branch is the same sentence Stats shows, because it is the same
 * problem: the plan route only ever says "unavailable", and the connection route is what
 * knows the token itself was refused. */
function RosterNote({
  plan,
  connection,
}: {
  plan: PlanResponse;
  connection: ConnectionStatus | undefined;
}) {
  if (plan.roster_status === "no_token") {
    return (
      <p className="text-[12px] text-muted">
        Add a Brawl Stars API token in Settings to see the roster.
      </p>
    );
  }
  if (plan.roster_status === "no_tag") {
    return (
      <p className="text-[12px] text-muted">
        Set this instance's player tag in Settings to see the roster.
      </p>
    );
  }
  if (plan.roster_status !== "unavailable") return null;
  if (connection === "rejected") {
    return (
      <p className="text-[12px] text-muted">
        The Brawl Stars API rejected the token. Check the token, and the IP address it was
        created for, in{" "}
        <Link to="/settings/connection" className="underline">
          Settings, Connection
        </Link>
        .
      </p>
    );
  }
  return (
    <p className="text-[12px] text-muted">
      {plan.roster === null
        ? "Roster unavailable right now."
        : "Roster unavailable right now; showing the last known list."}
    </p>
  );
}

export function FarmPlan({ name }: { name: string }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: queryKeys.plan(name), queryFn: () => getPlan(name) });
  const connection = useQuery({
    queryKey: queryKeys.connection(),
    queryFn: getConnection,
    staleTime: 300_000,
    refetchOnWindowFocus: false,
  });
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const [showAll, setShowAll] = useState(false);
  const [fallbackOn, setFallbackOn] = useState<boolean | null>(null);
  const [goalText, setGoalText] = useState<string | null>(null);
  const [fallbackText, setFallbackText] = useState<string | null>(null);
  const goalTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fallbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chain = useRef<Promise<void>>(Promise.resolve());

  // A navigation away must not let a debounce fire a write into a panel that is gone.
  useEffect(
    () => () => {
      if (goalTimer.current !== null) clearTimeout(goalTimer.current);
      if (fallbackTimer.current !== null) clearTimeout(fallbackTimer.current);
    },
    [],
  );

  const run = async (patch: Partial<FarmPlanBody>) => {
    const before = client.getQueryData<PlanResponse>(queryKeys.plan(name));
    if (before === undefined) return;
    client.setQueryData<PlanResponse>(queryKeys.plan(name), { ...before, ...patch });
    try {
      const saved = await putPlan(name, { ...planOf(before), ...patch });
      client.setQueryData<PlanResponse>(queryKeys.plan(name), saved);
      setFailure(null);
      setSavedAt(new Date().toISOString());
      toast("Plan saved");
    } catch (error) {
      client.setQueryData<PlanResponse>(queryKeys.plan(name), before);
      // Only the box whose save failed goes back to the stored value; text the reader is
      // still typing in the other one stays where it is. The switch follows the cache
      // too, so a failed clear leaves the fallback the worker still has on screen. The
      // cancels are the point: a debounce started while this save was in flight belongs
      // to a box that is about to show the stored value again, so it must not fire.
      if ("goal_trophies" in patch) cancelGoal();
      if ("maxed_fallback" in patch) {
        cancelFallback();
        setFallbackOn(null);
      }
      setFailure(error);
    }
  };

  /**
   * One save at a time, on a single chain. Each one reads the cache only once the save
   * before it has settled, so the values it keeps for a rollback are ones the API
   * confirmed rather than another save's optimistic guess. The catch is there so a link
   * that breaks in some unforeseen way cannot stop every later save: run() reports its
   * own failures inline already.
   */
  const save = (patch: Partial<FarmPlanBody>) => {
    chain.current = chain.current.then(() => run(patch)).catch(() => undefined);
  };

  /**
   * A debounce that is still pending when its box goes away is dropped, never flushed,
   * along with the text that was typed into it: the panel never persists a setting it
   * has stopped showing.
   */
  const cancelGoal = () => {
    if (goalTimer.current !== null) clearTimeout(goalTimer.current);
    goalTimer.current = null;
    setGoalText(null);
  };

  const cancelFallback = () => {
    if (fallbackTimer.current !== null) clearTimeout(fallbackTimer.current);
    fallbackTimer.current = null;
    setFallbackText(null);
  };

  const onGoal = (value: string) => {
    setGoalText(value);
    if (goalTimer.current !== null) clearTimeout(goalTimer.current);
    if (!/^\d+$/.test(value.trim())) return; // an integer >= 0; anything else waits
    const goal_trophies = Number(value.trim());
    goalTimer.current = setTimeout(() => {
      goalTimer.current = null;
      setGoalText(null);
      save({ goal_trophies });
    }, DEBOUNCE_MS);
  };

  const onFallback = (value: string) => {
    setFallbackText(value);
    if (fallbackTimer.current !== null) clearTimeout(fallbackTimer.current);
    const trimmed = value.trim();
    fallbackTimer.current = setTimeout(() => {
      fallbackTimer.current = null;
      setFallbackText(null);
      save({ maxed_fallback: trimmed === "" ? null : trimmed });
    }, DEBOUNCE_MS);
  };

  if (query.isPending) {
    return <section className="rounded-[10px] border border-line bg-panel p-3" />;
  }
  if (query.isError) {
    return <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />;
  }

  const plan = query.data;
  const prestige = plan.mode === "prestige";
  const goal = prestige ? PRESTIGE_GOAL : plan.goal_trophies;
  const roster = plan.roster ?? [];
  const trophiesOf = new Map(roster.map((b) => [b.name.toUpperCase(), b.trophies]));
  const progress =
    plan.current.trophies === null || goal <= 0
      ? 0
      : Math.min(100, Math.round((plan.current.trophies / goal) * 100));
  const showFallback = fallbackOn ?? plan.maxed_fallback !== null;
  const listId = `${name}-roster`;
  const questHelpId = `${name}-quest-help`;

  return (
    <section className="flex flex-col gap-3 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-baseline gap-2">
        <h2 className="text-[13px] font-semibold">Farm plan</h2>
        {savedAt === null ? null : (
          <span className="ml-auto text-[11px] text-muted">Saved {hhmm(savedAt)}</span>
        )}
      </div>
      {failure === null ? null : <ErrorBlock error={failure} />}

      <Segmented
        label="Plan"
        value={plan.mode}
        options={[
          { value: "ladder", label: "Ladder" },
          { value: "prestige", label: "Prestige" },
        ]}
        onChange={(mode) => {
          // Prestige takes the goal box away, so anything half typed into it goes too.
          if (mode !== plan.mode) cancelGoal();
          save({ mode });
        }}
      />

      {prestige ? (
        <Segmented
          label="Start with"
          value={plan.prestige_start}
          options={[
            { value: "highest", label: "Highest" },
            { value: "lowest", label: "Lowest" },
          ]}
          onChange={(prestige_start) => save({ prestige_start })}
        />
      ) : null}

      {prestige ? (
        <p className="text-[12px] text-muted">Goal {count(PRESTIGE_GOAL)}, the prestige threshold</p>
      ) : (
        <Field
          label="Goal"
          id={`${name}-goal`}
          type="number"
          min={0}
          suffix="trophies"
          value={goalText ?? String(plan.goal_trophies)}
          onChange={onGoal}
        />
      )}

      <Switch
        label="Maxed fallback"
        checked={showFallback}
        onChange={(on) => {
          setFallbackOn(on);
          // Turning it off drops a name still being typed and clears the stored one;
          // turning it on only reveals the box, because a blank fallback is the same as
          // no fallback to the worker.
          if (!on) {
            cancelFallback();
            if (plan.maxed_fallback !== null) save({ maxed_fallback: null });
          }
        }}
      />
      {showFallback ? (
        <>
          <Field
            label="Fallback brawler"
            id={`${name}-fallback`}
            value={fallbackText ?? plan.maxed_fallback ?? ""}
            onChange={onFallback}
            list={listId}
            placeholder="Brawler name"
          />
          <datalist id={listId}>
            {roster.map((b) => (
              <option key={b.id} value={b.name} />
            ))}
          </datalist>
        </>
      ) : null}

      {/* The worker ignores the flag in prestige mode, so prestige hides the switch rather
          than offering one that does nothing. Hiding writes nothing: the stored quest_aware
          is still there when the plan goes back to ladder. */}
      {prestige ? null : (
        <>
          <Switch
            label="Pick quest brawlers"
            checked={plan.quest_aware}
            describedBy={questHelpId}
            onChange={(quest_aware) => save({ quest_aware })}
          />
          <p id={questHelpId} className="text-[12px] text-muted">
            Applies at session start only. The worker reads the quests screen and picks an owned
            brawler that clears a quest. Your plan target wins when it clears one; otherwise the
            lowest-trophy candidate.
          </p>
        </>
      )}

      <div className="flex flex-col gap-1">
        <span className="text-[12px] text-muted">Current brawler</span>
        <div className="flex items-center gap-2">
          <BrawlerIcon name={plan.current.brawler} />
          {/* A name is mono because it is data; the stand-in sentence is prose. */}
          <span className={plan.current.brawler === null ? "text-[13px]" : "font-mono text-[13px]"}>
            {plan.current.brawler ?? NO_BRAWLER_YET}
          </span>
          <span className="ml-auto font-mono text-[12px] tabular-nums text-muted">
            {plan.current.trophies === null ? NOT_YET : count(plan.current.trophies)} /{" "}
            {count(goal)}
          </span>
        </div>
        <div className="h-[3px] w-full bg-line">
          <div
            data-testid="plan-progress"
            role="progressbar"
            aria-label="Progress to goal"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
            className="h-full bg-accent"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-[12px] text-muted">Next in queue</span>
        {plan.queue.length === 0 ? (
          <span className="text-[13px] text-muted">{QUEUE_EMPTY}</span>
        ) : (
          <ul>
            {plan.queue.map((brawler) => (
              <li key={brawler} className="flex items-center gap-2 text-[13px]">
                <BrawlerIcon name={brawler} />
                <span className="font-mono">{brawler}</span>
                <span className="ml-auto font-mono text-[12px] tabular-nums text-muted">
                  {trophiesOf.get(brawler.toUpperCase()) ?? "none"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {roster.length === 0 ? null : (
        <div className="flex flex-col gap-1">
          <Button variant="text" size="sm" onClick={() => setShowAll((open) => !open)}>
            {showAll ? "Hide all brawlers" : "Show all brawlers"}
          </Button>
          {/* The API already sorts the roster by trophies descending. */}
          {showAll ? (
            <ul data-testid="plan-roster">
              {roster.map((b) => (
                <li key={b.id} className="flex items-center gap-2 text-[13px]">
                  <BrawlerIcon name={b.name} />
                  <span className="font-mono">{b.name}</span>
                  <span className="ml-auto font-mono text-[12px] tabular-nums text-muted">
                    {b.trophies}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      )}

      <RosterNote plan={plan} connection={connection.data?.status} />
    </section>
  );
}
