/**
 * One instance, at /instances/:name. There is no per-instance GET on the API, so the
 * page reads the fleet list through useInstances and picks its own row out of it. That
 * hook carries the 15 s visible poll, and App's "instance" handler invalidates the same
 * key, so the header, the session figures and today's numbers all follow a state change
 * without this page holding any state of its own.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { ApiError } from "../api/client";
import { getFeed } from "../api/feed";
import {
  restartInstance,
  retryInstance,
  startInstance,
  stopInstance,
} from "../api/instances";
import { queryKeys } from "../api/queries";
import { screenshotUrl } from "../api/screens";
import { getStatsToday } from "../api/stats";
import type { InstancePayload, InstanceState } from "../api/types";
import { useInstances } from "../api/useInstances";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { StateChip } from "../components/ui/StateChip";
import { phaseLabel } from "../lib/states";
import { failureMessage, toast } from "../lib/toast";
import { FarmPlan } from "./FarmPlan";
import { Feed } from "./Feed";
import { LiveScreen } from "./LiveScreen";
import { Schedule } from "./Schedule";
import { SessionPanel } from "./SessionPanel";

/** Stop, Restart and Retry only mean something in some states (brief section 9). */
const NOT_RUNNING: ReadonlySet<InstanceState> = new Set<InstanceState>([
  "stopped",
  "scheduled_break",
  "offline",
]);

function Header({ inst, onDone }: { inst: InstancePayload; onDone: () => void }) {
  const client = useQueryClient();
  const stoppable = !NOT_RUNNING.has(inst.state);

  /** Stopping, starting and restarting all write the schedule's override, and nothing on
   * that route arrives over the event stream. The panel below asks again once the request
   * has settled either way: a refused stop may still have cleared an override on its way
   * out, so success is not the only outcome worth a refetch. */
  const settled = <T,>(call: Promise<T>): Promise<T> =>
    call.finally(() => {
      void client.invalidateQueries({ queryKey: queryKeys.schedule(inst.name) });
    });

  /** Nothing is announced until the request has settled. A rejection speaks the ApiError's
   * own detail -- the API's sentence, or the "cannot reach brawlfarm" one a dead server
   * produces -- and the success toast never fires. */
  const run = async (call: Promise<unknown>, done: () => void) => {
    try {
      await call;
    } catch (error) {
      toast(failureMessage(error));
      return;
    }
    onDone();
    done();
  };
  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <Link to="/" className="text-[12px] text-muted hover:text-text">
        Fleet
      </Link>
      {/* An h2: the top bar's route title is this page's h1 and carries the same name. */}
      <h2 className="text-[28px] leading-none font-semibold">{inst.name}</h2>
      <StateChip state={inst.state} />
      <span className="font-mono text-[12px] tabular-nums text-muted">{inst.adb_port}</span>
      {inst.player_tag === "" ? null : (
        <span data-private className="font-mono text-[12px] text-muted">
          {inst.player_tag}
        </span>
      )}
      <span className="text-[12px] text-muted">{phaseLabel(inst.phase)}</span>
      <div className="ml-auto flex items-center gap-2">
        {/* The raw PNG, for a closer look or a copied URL; LiveScreen has its own
            Refresh and Full size controls inside the frame. */}
        <a
          className="rounded-[6px] px-2 py-1 text-[12px] text-accent hover:underline"
          href={screenshotUrl(inst.name)}
          target="_blank"
          rel="noreferrer"
        >
          Screenshot
        </a>
        <Button
          variant="secondary"
          size="sm"
          disabled={!stoppable}
          disabledReason="Already stopped"
          onClick={() => {
            void run(settled(stopInstance(inst.name)), () => {
              toast(`Stopping ${inst.name} after this match`, {
                undo: async () => {
                  await settled(startInstance(inst.name));
                  onDone();
                },
              });
            });
          }}
        >
          Stop
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            void run(settled(restartInstance(inst.name)), () =>
              toast(`Restarting ${inst.name}`),
            );
          }}
        >
          Restart
        </Button>
        {inst.state === "offline" ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              void run(retryInstance(inst.name), () => toast(`Retrying ${inst.name} now`));
            }}
          >
            Retry now
          </Button>
        ) : null}
      </div>
    </header>
  );
}

export function Instance() {
  const { name = "" } = useParams();
  const client = useQueryClient();
  const fleet = useInstances();
  const stats = useQuery({
    queryKey: queryKeys.statsToday(name),
    queryFn: () => getStatsToday(name),
  });
  // The same key the Feed component fills, so its SSE appends keep these two counts live.
  const feed = useQuery({
    queryKey: queryKeys.feed(name, "all"),
    queryFn: () => getFeed(name, "all", 200),
  });
  const refresh = () => {
    void client.invalidateQueries({ queryKey: queryKeys.instances() });
  };

  if (fleet.isPending) return <div />; // the shell is enough until the list lands
  if (fleet.isError) {
    return <ErrorBlock error={fleet.error} onRetry={() => void fleet.refetch()} />;
  }
  const inst = fleet.data.find((row) => row.name === name);
  if (inst === undefined) return <ErrorBlock error={new ApiError(404, "No instance by that name. Open Fleet to pick one.")} />;

  const records = feed.data?.records ?? [];
  const interrupts = records.filter((r) => r.category === "interrupts").length;
  const stopAt = [...records].reverse().find((r) => r.event === "stop")?.ts ?? null;

  return (
    <div className="flex flex-col gap-4">
      <Header inst={inst} onDone={refresh} />
      <div className="grid grid-cols-1 gap-4 min-[1100px]:grid-cols-[3fr_2fr]">
        <div className="flex flex-col gap-4">
          <LiveScreen name={inst.name} />
          <Feed name={inst.name} session={inst.session?.session ?? null} />
        </div>
        <div className="flex flex-col gap-4">
          <FarmPlan name={inst.name} />
          <Schedule name={inst.name} />
          <SessionPanel
            inst={inst}
            avgRank={stats.data?.summary.avg_rank ?? null}
            interrupts={interrupts}
            stopAt={stopAt}
          />
        </div>
      </div>
    </div>
  );
}
