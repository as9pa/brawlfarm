/**
 * The Stats screen.
 *
 * The URL is the single source of the range and the instance selection, so a reload keeps
 * the view and a link carries it. A name in ?instances= that is not configured is dropped
 * before the request goes out, which turns a stale link into a narrower selection rather
 * than a 404 from the route's own _selected. Every change is a replace, not a push, so
 * Back leaves Stats instead of walking the ranges.
 *
 * The stats query waits for GET /api/instances: dropping an unknown name needs the
 * configured list, and firing once without it and again with it would double every load.
 */
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";

import { BrawlerTable } from "./BrawlerTable";
import { ConnectionStrip } from "./ConnectionStrip";
import { MetricsRow } from "./MetricsRow";
import { RankBars } from "./RankBars";
import { RecentGames } from "./RecentGames";
import { StatsToolbar } from "./StatsToolbar";
import { TrophyChart } from "./TrophyChart";
import { getConnection } from "../api/connection";
import { queryKeys } from "../api/queries";
import { getStats, statsCsvHref } from "../api/stats";
import type { StatsRange } from "../api/types";
import { useInstances } from "../api/useInstances";
import { ErrorBlock } from "../components/ui/ErrorBlock";

export const RANGES: readonly StatsRange[] = ["today", "7d", "30d", "all"];
const DEFAULT_RANGE: StatsRange = "7d";
/** The server caches its answer for five minutes, so asking again inside that window only
 * costs a round trip to be told the same thing. */
const CONNECTION_STALE_MS = 300_000;

/** An absent or unparsable range is 7 days: Today is empty every morning until the first
 * match, and an empty page is a worse first impression than a slightly wider one. */
export function parseRange(raw: string | null): StatsRange {
  return RANGES.includes((raw ?? "") as StatsRange) ? (raw as StatsRange) : DEFAULT_RANGE;
}

function Skeleton() {
  return (
    <div data-testid="stats-skeleton" className="flex flex-col gap-3">
      <div className="flex gap-3 rounded-[10px] border border-line bg-panel px-3 py-2">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} data-block="" className="h-[18px] flex-1 rounded-[4px] bg-panel-2" />
        ))}
      </div>
      <div data-block="" className="h-[180px] rounded-[10px] bg-panel-2" />
    </div>
  );
}

export function Stats() {
  const [params, setParams] = useSearchParams();
  const instancesQuery = useInstances();
  const configured = (instancesQuery.data ?? []).map((inst) => inst.name);

  const range = parseRange(params.get("range"));
  const asked = (params.get("instances") ?? "")
    .split(",")
    .map((name) => name.trim())
    .filter((name) => name !== "");
  const narrowed = configured.filter((name) => asked.includes(name));
  const selected = narrowed.length === 0 ? configured : narrowed;
  // Empty means "every configured instance", which is the API's own default, so a full
  // selection and no selection share one URL and one cache entry.
  const scope = selected.length === configured.length ? [] : selected;

  const stats = useQuery({
    queryKey: queryKeys.stats(range, scope),
    queryFn: () => getStats(range, scope),
    enabled: instancesQuery.isSuccess,
  });
  const connection = useQuery({
    queryKey: queryKeys.connection(),
    queryFn: getConnection,
    staleTime: CONNECTION_STALE_MS,
    refetchOnWindowFocus: false,
  });

  const write = (next: { range?: StatsRange; instances?: string[] }) => {
    const params2 = new URLSearchParams();
    const wantRange = next.range ?? range;
    const wantInstances = next.instances ?? selected;
    if (wantRange !== DEFAULT_RANGE) params2.set("range", wantRange);
    if (wantInstances.length !== configured.length) {
      params2.set("instances", wantInstances.join(","));
    }
    setParams(params2, { replace: true });
  };

  const instanceWithoutTag =
    (instancesQuery.data ?? []).find(
      (inst) => selected.includes(inst.name) && inst.player_tag.trim() === "",
    )?.name ?? null;

  const toolbar = (
    <StatsToolbar
      range={range}
      instances={configured}
      selected={selected}
      onRange={(next) => write({ range: next })}
      onInstances={(next) => write({ instances: next })}
      csvHref={statsCsvHref(range, scope)}
    />
  );
  const strip = (
    <ConnectionStrip
      status={connection.data?.status ?? "ok"}
      instanceWithoutTag={instanceWithoutTag}
    />
  );

  // Without the instance list there is nothing to pick and nothing to scope, so the
  // toolbar stays out of this one and the skeleton is left to the pending state alone:
  // a failed list would otherwise sit on the skeleton forever.
  if (instancesQuery.isError) {
    return (
      <section className="flex flex-col gap-3">
        <h1 className="text-[28px] font-semibold tracking-tight">Stats</h1>
        <ErrorBlock
          error={instancesQuery.error}
          onRetry={() => void instancesQuery.refetch()}
        />
      </section>
    );
  }

  if (stats.isError) {
    return (
      <section className="flex flex-col gap-3">
        <h1 className="text-[28px] font-semibold tracking-tight">Stats</h1>
        {toolbar}
        <ErrorBlock error={stats.error} onRetry={() => void stats.refetch()} />
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-[28px] font-semibold tracking-tight">Stats</h1>
      {toolbar}
      {/* Above the empty state on purpose: a missing token explains the empty page. */}
      {strip}
      {stats.data === undefined ? (
        <Skeleton />
      ) : stats.data.summary.games === 0 ? (
        <p className="text-[13px] text-muted">Stats appear after the first match.</p>
      ) : (
        <>
          <div data-testid="metrics-row">
            <MetricsRow summary={stats.data.summary} />
          </div>
          <TrophyChart series={stats.data.series} instances={selected} range={range} />
          <div className="grid gap-3 min-[900px]:grid-cols-[1fr_320px]">
            <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
              <h2 className="text-[13px] font-semibold">Brawlers</h2>
              <BrawlerTable rows={stats.data.brawlers} />
            </section>
            <RankBars rows={stats.data.ranks} />
          </div>
          <RecentGames rows={stats.data.recent} range={range} />
        </>
      )}
    </section>
  );
}
