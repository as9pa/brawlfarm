/** A Showdown finish is a placement, never a rank: no Stats or session surface may say
 * "rank" or "top 4" for it. The roster's rank tier is a different thing and lives
 * elsewhere. */
import { describe, expect, it } from "vitest";

import { BrawlerTable } from "./BrawlerTable";
import { MetricsRow } from "./MetricsRow";
import { PlacementBars } from "./PlacementBars";
import { RecentGames } from "./RecentGames";
import { TrophiesByPlacement } from "./TrophiesByPlacement";
import { SessionPanel } from "../instance/SessionPanel";
import { makeInstance, makeLastSession, makeStats } from "../test/fixtures";
import { renderWithProviders } from "../test/renderWithProviders";

const BANNED = [/\brank\b/i, /top.?4/i];

describe("placement copy", () => {
  it("never says rank or top 4 on the placement surfaces", () => {
    const stats = makeStats();
    const { container } = renderWithProviders(
      <>
        <MetricsRow summary={stats.summary} placements={stats.placements} />
        <PlacementBars rows={stats.placements} />
        <TrophiesByPlacement rows={stats.summary.trophies_by_placement} />
        <BrawlerTable rows={stats.brawlers} />
        <RecentGames rows={stats.recent} range="7d" />
        <SessionPanel inst={makeInstance()} avgPlacement={3.4} interrupts={1} stopAt={null} />
        <SessionPanel
          inst={makeInstance({ state: "stopped", last_session: makeLastSession() })}
          avgPlacement={null}
          interrupts={0}
          stopAt={null}
        />
      </>,
    );
    const text = container.textContent ?? "";
    expect(text).toContain("Average placement");
    for (const pattern of BANNED) expect(text).not.toMatch(pattern);
  });
});
