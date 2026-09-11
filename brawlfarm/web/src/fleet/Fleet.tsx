/**
 * The home screen.
 *
 * The list comes from useInstances, which carries the 15 s visible poll: `session` and
 * `today` only exist on GET /api/instances, and the instance events carry the
 * supervisor's view alone, so without the poll a card's numbers would freeze between
 * route changes. The totals line's "farmed" figure is the only thing here that needs
 * GET /api/stats.
 *
 * Start all and Stop all fire one request per instance in parallel; there is no
 * fleet-wide route, and inventing one in the client would hide a partial failure.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { AlertStrip } from "./AlertStrip";
import { InstanceCard } from "./InstanceCard";
import { listAlerts } from "../api/alerts";
import { ApiError } from "../api/client";
import { startInstance, stopInstance } from "../api/instances";
import { queryKeys } from "../api/queries";
import { getStatsToday } from "../api/stats";
import { useInstances } from "../api/useInstances";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { openAlertsDrawer } from "../lib/alertsDrawer";
import { plural, signed } from "../lib/format";
import { hoursText } from "../lib/time";
import { toast } from "../lib/toast";

const GRID_COLUMNS = "repeat(auto-fill, minmax(340px, 1fr))";

export function Fleet() {
  const client = useQueryClient();

  const { data: instances, error, refetch } = useInstances();
  const { data: alerts } = useQuery({ queryKey: queryKeys.alerts(), queryFn: listAlerts });
  // Only summary.hours_farmed is read here; games and trophies come from the cards' own
  // payload, so the totals line always agrees with the grid above it.
  const { data: stats } = useQuery({
    queryKey: queryKeys.statsToday(),
    queryFn: () => getStatsToday(),
  });

  const fleet = instances ?? [];
  const newest = alerts?.alerts[0];
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
    toast(failure instanceof ApiError ? failure.detail : "Request failed");
  };

  const onStartAll = () => {
    void Promise.all(fleet.map((inst) => startInstance(inst.name)))
      .then(() => {
        refresh();
        toast(`Starting ${fleet.length} instances`);
      })
      .catch(failed);
  };

  const onStopAll = () => {
    void Promise.all(fleet.map((inst) => stopInstance(inst.name)))
      .then(() => {
        refresh();
        toast(`Stopping ${fleet.length} instances after their matches`);
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
          Setup arrives in the next phase; until then add an [[instances]] table to
          config.toml and restart brawlfarm.
        </p>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-4">
      <header className="flex items-center gap-3">
        <h1 className="text-[28px] font-semibold tracking-tight">Fleet</h1>
        <span className="flex-1 text-[13px] text-muted">{plural(fleet.length, "instance")}</span>
        <Button variant="quiet" size="sm" onClick={onStartAll}>
          Start all
        </Button>
        <Button variant="quiet" size="sm" onClick={onStopAll}>
          Stop all
        </Button>
      </header>

      {newest !== undefined && (
        <AlertStrip alert={newest} unread={alerts?.unread ?? 0} onOpen={openAlertsDrawer} />
      )}

      <div className="grid gap-4" style={{ gridTemplateColumns: GRID_COLUMNS }}>
        {fleet.map((inst) => (
          <InstanceCard key={inst.name} inst={inst} />
        ))}
      </div>

      <p className="font-mono text-[12px] tabular-nums text-muted">
        {`${farming} farming · ${games} games today · ${signed(trophies)} trophies today · ${hoursText(hours)} farmed`}
      </p>
    </section>
  );
}
