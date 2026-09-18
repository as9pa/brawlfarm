/**
 * The home screen.
 *
 * The list comes from useInstances, which carries the 15 s visible poll: `session` and
 * `today` only exist on GET /api/instances, and the instance events carry the
 * supervisor's view alone, so without the poll a card's numbers would freeze between
 * route changes. The totals row's "farmed" figure is the only thing here that needs
 * GET /api/stats.
 *
 * Start all and Stop all fire one request per instance in parallel; there is no
 * fleet-wide route, and inventing one in the client would hide a partial failure.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";

import { AlertStrip, stripAlert } from "./AlertStrip";
import { InstanceCard } from "./InstanceCard";
import { listAlerts } from "../api/alerts";
import { startInstance, stopInstance } from "../api/instances";
import { queryKeys } from "../api/queries";
import { getStatsToday } from "../api/stats";
import type { InstanceState } from "../api/types";
import { useInstances } from "../api/useInstances";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { openAlertsDrawer } from "../lib/alertsDrawer";
import { num, plural, signed } from "../lib/format";
import { hoursText } from "../lib/time";
import { failureMessage, toast } from "../lib/toast";

const GRID_COLUMNS = "repeat(auto-fill, minmax(340px, 1fr))";

/** Running means here what a card's Stop button means by it: a state the supervisor can
 * still be asked to stop. Kept beside InstanceCard's own STOPPABLE_STATES until one of
 * the two moves into lib/states.ts. */
const RUNNING_STATES: ReadonlySet<InstanceState> = new Set<InstanceState>([
  "farming",
  "starting",
  "stopping",
  "reconnecting",
]);

/** A card's shape before the first list arrives: the thumbnail, the name and the four
 * metrics as bones, so the grid does not jump when the real cards land. aria-hidden
 * because there is nothing to read here yet, and the cards that arrive are what a screen
 * reader should announce. */
function SkeletonCard() {
  return (
    <div
      data-testid="fleet-skeleton-card"
      aria-hidden="true"
      className="animate-pulse rounded-[10px] border border-line bg-panel p-3"
    >
      <div data-block="" className="aspect-video w-full rounded-[6px] bg-panel-2" />
      <div data-block="" className="mt-3 h-[18px] w-[120px] rounded-[4px] bg-panel-2" />
      <div className="mt-3 grid grid-cols-2 gap-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} data-block="" className="h-[32px] rounded-[4px] bg-panel-2" />
        ))}
      </div>
    </div>
  );
}

export function Fleet() {
  const client = useQueryClient();

  const { data: instances, error, refetch } = useInstances();
  const { data: alerts } = useQuery({ queryKey: queryKeys.alerts(), queryFn: listAlerts });
  // Only summary.hours_farmed is read here; games and trophies come from the cards' own
  // payload, so the totals row always agrees with the grid below it.
  const { data: stats } = useQuery({
    queryKey: queryKeys.statsToday(),
    queryFn: () => getStatsToday(),
  });

  // Nothing numeric before the first response: an empty fleet and a fleet that has not
  // arrived yet look identical here, and "0 instances" would be a claim about a list the
  // panel has not seen.
  const loading = instances === undefined;
  const fleet = instances ?? [];
  const newest = stripAlert(alerts?.alerts ?? []);
  const running = fleet.filter((inst) => RUNNING_STATES.has(inst.state));
  const farming = fleet.filter((inst) => inst.state === "farming").length;
  const games = fleet.reduce((total, inst) => total + inst.today.games, 0);
  const trophies = fleet.reduce((total, inst) => total + inst.today.trophies, 0);
  const hours = stats?.summary.hours_farmed ?? 0;

  const refresh = () => {
    void client.invalidateQueries({ queryKey: queryKeys.instances() });
  };

  /** One instance refusing fails the whole fan-out: nothing is announced until every
   * request has settled, and the rejection speaks the ApiError's own detail so a partial
   * failure is not mistaken for a fleet that started. */
  const failed = (failure: unknown) => {
    toast(failureMessage(failure));
  };

  const onStartAll = () => {
    void Promise.all(fleet.map((inst) => startInstance(inst.name)))
      .then(() => {
        refresh();
        toast(`Starting ${plural(fleet.length, "instance")}`);
      })
      .catch(failed);
  };

  const onStopAll = () => {
    // The names are read before the requests go out. By the time the undo is pressed the
    // poll has moved every one of them to stopping, so starting the whole fleet again
    // would also start the instances that were not running when the button was pressed.
    const wasRunning = running.map((inst) => inst.name);
    void Promise.all(fleet.map((inst) => stopInstance(inst.name)))
      .then(() => {
        refresh();
        toast(
          `Stopping ${plural(fleet.length, "instance")} after ${
            fleet.length === 1 ? "its match" : "their matches"
          }`,
          {
            tone: "ok",
            undo: async () => {
              try {
                await Promise.all(wasRunning.map((name) => startInstance(name)));
                refresh();
              } catch (failure) {
                // The undo's own failure is the last word: a second offer to put it back
                // is a loop the reader has to click their way out of.
                toast(failureMessage(failure), { tone: "bad" });
              }
            },
          },
        );
      })
      .catch(failed);
  };

  if (error !== null) {
    return (
      <ErrorBlock
        error={error}
        onRetry={() => {
          void refetch();
        }}
      />
    );
  }

  if (instances !== undefined && fleet.length === 0) {
    return (
      <section className="max-w-[560px]">
        <h1 className="text-[28px] font-semibold tracking-tight">No instances yet.</h1>
        <p className="mt-2 text-[13px] text-muted">
          Open setup to find your BlueStacks instances.
        </p>
        <div className="mt-4">
          {/* A link, not a Button with a navigate: it goes somewhere, so it should open in
              a new tab on a middle click like every other link does. */}
          <Link
            to="/setup"
            className="inline-flex h-8 items-center gap-1.5 rounded-[6px] bg-accent px-3 text-[13px] font-medium text-accent-ink transition-[background-color,border-color,color] duration-[120ms] hover:brightness-110"
          >
            Open setup
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-4">
      <header className="flex items-center gap-3">
        <h1 className="text-[28px] font-semibold tracking-tight">Fleet</h1>
        <span className="flex-1 text-[13px] text-muted">
          {loading ? "Loading fleet" : plural(fleet.length, "instance")}
        </span>
        {/* A fleet of one is the card's own Stop and Start under another name, so the
            fleet-wide pair only appears once it means more than the card below it. */}
        {fleet.length >= 2 && (
          <>
            <Button
              variant="secondary"
              size="sm"
              disabled={running.length === fleet.length}
              disabledReason="Everything is running"
              onClick={onStartAll}
            >
              Start all
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={running.length === 0}
              disabledReason="Nothing is running"
              onClick={onStopAll}
            >
              Stop all
            </Button>
          </>
        )}
      </header>

      {!loading && newest !== undefined && (
        <AlertStrip alert={newest} total={alerts?.unread ?? 0} onOpen={openAlertsDrawer} />
      )}

      {fleet.length >= 2 && (
        <dl className="flex flex-wrap gap-x-6 gap-y-2">
          {[
            ["Farming", `${farming} of ${fleet.length}`],
            ["Games today", num(games)],
            ["Trophies today", signed(trophies)],
            ["Farmed", hoursText(hours)],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-[11px] text-muted">{label}</dt>
              <dd className="t-figure text-[15px] text-text">{value}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="grid gap-4" style={{ gridTemplateColumns: GRID_COLUMNS }}>
        {loading
          ? [0, 1, 2].map((i) => <SkeletonCard key={i} />)
          : fleet.map((inst) => <InstanceCard key={inst.name} inst={inst} />)}
      </div>
    </section>
  );
}
