/** This session's narration: what it loads per chip, what it appends from the stream, and
 * what Follow does when the reader scrolls back to read. */
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Feed, appendRecord } from "./Feed";
import { createQueryClient, queryKeys } from "../api/queries";
import type { FeedResponse } from "../api/types";
import { makeFeedRecord } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const handlers: ((payload: unknown) => void)[] = [];

// Feed installs its own "feed" subscriber, so the test delivers frames straight to it.
// The real stream, its backoff and its de-duplication are task 2's own tests.
vi.mock("../live/useEvents", () => ({
  subscribe: (_kind: string, handler: (payload: unknown) => void) => {
    handlers.push(handler);
    return () => {
      handlers.splice(handlers.indexOf(handler), 1);
    };
  },
  useConnection: () => "live" as const,
}));

const SESSION = "session-20260911-101500.jsonl";
const FEED = "/api/instances/Pie64/feed";

function query(url: string): URLSearchParams {
  return new URLSearchParams(url.slice(url.indexOf("?") + 1));
}

/** Answer every feed request with whatever `records` makes of the chip it asked for. */
function stubFeed(records: (kind: string) => ReturnType<typeof makeFeedRecord>[]): FetchCall[] {
  return stubFetch((url) =>
    jsonResponse({ session: SESSION, records: records(query(url).get("kind") ?? "all") }),
  ).calls;
}

function lastFeedQuery(calls: FetchCall[]): URLSearchParams {
  return query(calls.filter((call) => call.url.startsWith(FEED)).at(-1)?.url ?? "");
}

function emit(record: ReturnType<typeof makeFeedRecord>, session = SESSION): void {
  act(() => {
    for (const handler of [...handlers]) {
      handler({ instance: "Pie64", session, record });
    }
  });
}

beforeEach(() => {
  handlers.length = 0;
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Feed", () => {
  it("loads 200 lines of the chosen kind and reloads when the chip changes", async () => {
    const calls = stubFeed((kind) =>
      kind === "errors"
        ? [makeFeedRecord({ seq: 9, event: "crash", category: "errors", fields: { err: "boom" } })]
        : [makeFeedRecord({ seq: 1 })],
    );
    renderWithProviders(<Feed name="Pie64" session={SESSION} />);
    expect(await screen.findByText("Playing")).toBeInTheDocument();
    const first = lastFeedQuery(calls);
    expect([first.get("kind"), first.get("limit")]).toEqual(["all", "200"]);
    await userEvent.click(screen.getByRole("radio", { name: "Errors" }));
    expect(await screen.findByText("Crash: boom")).toBeInTheDocument();
    const second = lastFeedQuery(calls);
    expect([second.get("kind"), second.get("limit")]).toEqual(["errors", "200"]);
  });

  it("shows the filter's own empty copy", async () => {
    stubFeed(() => []);
    renderWithProviders(<Feed name="Pie64" session={SESSION} />);
    expect(
      await screen.findByText("No lines yet. The feed fills as the instance plays."),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Interrupts" }));
    expect(await screen.findByText("No interrupts this session.")).toBeInTheDocument();
  });

  it("appends a live line once, however many times it arrives", async () => {
    stubFeed(() => [makeFeedRecord({ seq: 1 })]);
    renderWithProviders(<Feed name="Pie64" session={SESSION} />);
    await screen.findByText("Playing");
    const line = makeFeedRecord({
      seq: 2,
      event: "recap",
      category: "matches",
      fields: { trophies: 8, games: 1, skins: 0 },
    });
    emit(line);
    emit(line); // the same seq again: a reconnect replay, not a second line
    expect(await screen.findAllByText("Session ended, 1 game, +8 trophies")).toHaveLength(1);
  });

  // The pair is two real records with two seqs; only the drawing of them collapses.
  it("draws the step mirror of an event once", async () => {
    stubFeed(() => [
      makeFeedRecord({
        ts: "2026-09-11T19:05:40",
        seq: 1,
        event: "launch_game",
        category: "other",
        fields: { method: "monkey" },
      }),
      makeFeedRecord({
        ts: "2026-09-11T19:05:40",
        seq: 2,
        event: "step",
        category: "other",
        fields: { step: "launch", label: "Brawl Stars opened", status: "ok" },
      }),
    ]);
    renderWithProviders(<Feed name="Pie64" session={SESSION} />);
    expect(await screen.findAllByText("Brawl Stars opened")).toHaveLength(1);
  });

  it("ignores a line from another instance", async () => {
    stubFeed(() => [makeFeedRecord({ seq: 1 })]);
    renderWithProviders(<Feed name="Pie64" session={SESSION} />);
    await screen.findByText("Playing");
    act(() => {
      for (const handler of [...handlers]) {
        handler({
          instance: "Pie64_1",
          session: SESSION,
          record: makeFeedRecord({ seq: 2, event: "farming", fields: { brawler: "TARA" } }),
        });
      }
    });
    await waitFor(() => {
      expect(screen.queryByText("Farming TARA")).not.toBeInTheDocument();
    });
  });

  // The app's own client, not the test one: this is the case staleTime and gcTime decide,
  // and testQueryClient's gcTime of 0 would collect a wrongly seeded entry before the
  // assertion could see it.
  it("leaves a chip nobody has opened to fetch its own history", async () => {
    const calls = stubFeed((kind) =>
      kind === "interrupts"
        ? [makeFeedRecord({ seq: 2, event: "popup_close", category: "interrupts", fields: {} })]
        : [makeFeedRecord({ seq: 1 })],
    );
    const client = createQueryClient();
    renderWithProviders(<Feed name="Pie64" session={SESSION} />, { client });
    await screen.findByText("Playing");
    emit(makeFeedRecord({ seq: 2, event: "popup_close", category: "interrupts", fields: {} }));
    // All has loaded, so it takes the line; Interrupts has not, so it is not seeded.
    expect(await screen.findByText("Popup closed")).toBeInTheDocument();
    expect(client.getQueryData(queryKeys.feed("Pie64", "interrupts"))).toBeUndefined();

    await userEvent.click(screen.getByRole("radio", { name: "Interrupts" }));
    // What fills the chip is its own history, in one request. A seeded entry would have
    // counted as fresh and never asked, leaving the matches line on screen.
    await waitFor(() => {
      expect(screen.queryByText("Playing")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Popup closed")).toBeInTheDocument();
    const asked = calls.filter(
      (call) => call.url.startsWith(FEED) && query(call.url).get("kind") === "interrupts",
    );
    expect(asked).toHaveLength(1);
    client.clear(); // the app's gcTime would leave this client's timers behind
  });

  it("keeps the newest 500 lines and drops the oldest", () => {
    let feed: FeedResponse = { session: SESSION, records: [makeFeedRecord({ seq: 1 })] };
    for (let seq = 2; seq <= 520; seq += 1) {
      feed = appendRecord(feed, SESSION, makeFeedRecord({ seq }));
    }
    expect(feed.records).toHaveLength(500);
    expect(feed.records[0].seq).toBe(21);
    expect(feed.records.at(-1)?.seq).toBe(520);
  });

  it("turns Follow off when the reader scrolls up, and back on scrolls to the bottom", async () => {
    stubFeed(() => [makeFeedRecord({ seq: 1 })]);
    renderWithProviders(<Feed name="Pie64" session={SESSION} />);
    await screen.findByText("Playing");
    const list = screen.getByTestId("feed-list");
    Object.defineProperty(list, "scrollHeight", { value: 400, configurable: true });
    Object.defineProperty(list, "clientHeight", { value: 200, configurable: true });
    const follow = screen.getByRole("switch", { name: "Follow" });
    expect(follow).toHaveAttribute("aria-checked", "true");

    list.scrollTop = 190; // 400 - 190 - 200 = 10 px from the bottom: still following
    fireEvent.scroll(list);
    expect(follow).toHaveAttribute("aria-checked", "true");

    list.scrollTop = 100; // 100 px from the bottom, past the 40 px slack
    fireEvent.scroll(list);
    expect(follow).toHaveAttribute("aria-checked", "false");

    await userEvent.click(follow);
    expect(follow).toHaveAttribute("aria-checked", "true");
    expect(list.scrollTop).toBe(400);
  });
});
