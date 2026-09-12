/** The Stats page: the URL is the only place the range and the selection live, an unknown
 * instance in a stale link is dropped rather than 404ing, and the three states above the
 * data (skeleton, empty, error) are the ones the brief pins. */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Stats } from "./Stats";
import { makeConnection, makeInstance, makeStats } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Two configured instances, an aggregate, and an ok connection. `stats` overrides the
 * aggregate; `statsStatus` makes GET /api/stats fail, `instancesStatus` the list. */
function server(
  options: {
    stats?: ReturnType<typeof makeStats>;
    statsStatus?: number;
    instancesStatus?: number;
  } = {},
): FetchCall[] {
  return stubFetch((url) => {
    if (url === "/api/instances") {
      if (options.instancesStatus !== undefined) {
        return jsonResponse({ detail: "config.toml is unreadable" }, options.instancesStatus);
      }
      return jsonResponse({
        instances: [
          makeInstance({ name: "Pie64", player_tag: "#2P0YLQ9" }),
          makeInstance({ name: "Pie64_1", adb_port: 5565, player_tag: "#2P0YLQ9" }),
        ],
      });
    }
    if (url === "/api/connection/check") return jsonResponse(makeConnection());
    if (url.startsWith("/api/stats")) {
      if (options.statsStatus !== undefined) {
        return jsonResponse({ detail: "games.csv is unreadable" }, options.statsStatus);
      }
      return jsonResponse(options.stats ?? makeStats());
    }
    throw new Error(`unstubbed request: ${url}`);
  }).calls;
}

function mount(route = "/stats") {
  return renderWithProviders(
    <Routes>
      <Route path="/stats" element={<Stats />} />
    </Routes>,
    { route },
  );
}

function statsUrls(calls: FetchCall[]): string[] {
  return calls.filter((c) => c.url.startsWith("/api/stats?")).map((c) => c.url);
}

describe("Stats", () => {
  it("defaults to 7 days with no query string", async () => {
    const calls = server();
    mount();
    await waitFor(() => {
      expect(statsUrls(calls)).toEqual(["/api/stats?range=7d"]);
    });
    expect(await screen.findByRole("radio", { name: "7 days" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("reads the range and the selection out of the URL", async () => {
    const calls = server();
    mount("/stats?range=30d&instances=Pie64");
    await waitFor(() => {
      expect(statsUrls(calls)).toEqual(["/api/stats?range=30d&instances=Pie64"]);
    });
    expect(screen.getByRole("radio", { name: "30 days" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByRole("button", { name: "Pie64_1" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("falls back to 7 days for an unparsable range", async () => {
    const calls = server();
    mount("/stats?range=fortnight");
    await waitFor(() => {
      expect(statsUrls(calls)).toEqual(["/api/stats?range=7d"]);
    });
  });

  it("drops a name that is not configured", async () => {
    const calls = server();
    mount("/stats?instances=Pie64,Ghost");
    await waitFor(() => {
      expect(statsUrls(calls)).toEqual(["/api/stats?range=7d&instances=Pie64"]);
    });
  });

  it("rewrites the URL and refetches when a chip is toggled", async () => {
    const calls = server();
    mount();
    await screen.findByRole("button", { name: "Pie64_1" });
    await userEvent.click(screen.getByRole("button", { name: "Pie64_1" }));
    await waitFor(() => {
      expect(statsUrls(calls)).toEqual([
        "/api/stats?range=7d",
        "/api/stats?range=7d&instances=Pie64",
      ]);
    });
    expect(screen.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
      "href",
      "/api/stats/export.csv?range=7d&instances=Pie64",
    );
  });

  it("will not let the last enabled chip be turned off", async () => {
    const calls = server();
    mount("/stats?instances=Pie64");
    await screen.findByRole("button", { name: "Pie64" });
    await userEvent.click(screen.getByRole("button", { name: "Pie64" }));
    await waitFor(() => {
      expect(statsUrls(calls)).toEqual(["/api/stats?range=7d&instances=Pie64"]);
    });
  });

  it("shows the skeleton while the first request is in flight, and the toolbar with it", () => {
    stubFetch(() => new Promise<Response>(() => undefined));
    mount();
    expect(screen.getByTestId("stats-skeleton")).toBeInTheDocument();
    expect(screen.getByRole("radiogroup", { name: "Range" })).toBeInTheDocument();
    expect(screen.getByTestId("stats-skeleton").querySelectorAll("[data-block]")).toHaveLength(7);
  });

  it("shows the empty sentence and nothing below it when the range has no games", async () => {
    server({
      stats: makeStats({
        summary: {
          games: 0,
          trophies: 0,
          trophies_per_hour: null,
          avg_rank: null,
          top4_rate: null,
          hours_farmed: 0,
        },
        series: [],
        brawlers: [],
        ranks: [],
        recent: [],
      }),
    });
    mount();
    expect(await screen.findByText("Stats appear after the first match.")).toBeInTheDocument();
    expect(screen.getByRole("radiogroup", { name: "Range" })).toBeInTheDocument();
    expect(screen.queryByTestId("metrics-row")).toBeNull();
  });

  it("shows the failure, not the skeleton, when the instance list cannot load", async () => {
    server({ instancesStatus: 500 });
    mount();
    expect(await screen.findByText("config.toml is unreadable")).toBeInTheDocument();
    expect(screen.queryByTestId("stats-skeleton")).toBeNull();
    // There is nothing to pick and nothing to scope, so the toolbar stays away too.
    expect(screen.queryByRole("radiogroup", { name: "Range" })).toBeNull();
  });

  it("shows an ErrorBlock and nothing else when the request fails", async () => {
    server({ statsStatus: 500 });
    mount();
    expect(await screen.findByText("games.csv is unreadable")).toBeInTheDocument();
    expect(screen.queryByTestId("metrics-row")).toBeNull();
    expect(screen.queryByText("Stats appear after the first match.")).toBeNull();
  });

  it("shows the metrics row and the connection strip above it", async () => {
    stubFetch((url) => {
      if (url === "/api/instances") {
        return jsonResponse({ instances: [makeInstance({ name: "Pie64", player_tag: "" })] });
      }
      if (url === "/api/connection/check") {
        return jsonResponse(makeConnection({ status: "no_tag" }));
      }
      if (url.startsWith("/api/stats")) return jsonResponse(makeStats());
      throw new Error(`unstubbed request: ${url}`);
    });
    mount();
    expect(await screen.findByTestId("metrics-row")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Add a player tag for Pie64 in Settings, Instances to see its games.",
    );
  });

  it("draws the chart for the selection, legend and all", async () => {
    server();
    mount();
    expect(
      await screen.findByRole("img", { name: "Cumulative trophy change" }),
    ).toBeInTheDocument();
    expect(screen.getAllByTestId("legend-entry").map((n) => n.textContent)).toEqual([
      "Pie64",
      "Pie64_1",
    ]);
  });

  it("shows the brawler table, the rank bars and the recent games", async () => {
    server();
    mount();
    expect(await screen.findByRole("heading", { name: "Brawlers" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Rank distribution" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Recent games" })).toBeInTheDocument();
    expect(screen.getAllByRole("row", { name: /NORI/ }).length).toBeGreaterThan(0);
  });
});
