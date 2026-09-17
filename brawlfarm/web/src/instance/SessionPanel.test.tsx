/** Six figures, and what happens to them when the worker stops. No providers: the panel
 * is handed everything it draws. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SessionPanel } from "./SessionPanel";
import { makeInstance, makeLastSession } from "../test/fixtures";
import { renderWithProviders } from "../test/renderWithProviders";

/** One <dd> by the label in the <dt> beside it. */
function figure(label: string): HTMLElement {
  const term = screen.getByText(label);
  return term.parentElement?.querySelector("dd") as HTMLElement;
}

const SESSION = {
  minutes_elapsed: 72,
  start_trophies: 41000,
  last_trophies: 41086,
  disconnect_count: 1,
  recovery_attempts: 0,
  session: "session-20260911-101500.jsonl",
};

const farming = makeInstance({
  name: "Pie64",
  state: "farming",
  games_played: 12,
  session: SESSION,
});

describe("SessionPanel", () => {
  it("shows the six figures of a live session", () => {
    render(<SessionPanel inst={farming} avgRank={3.42} interrupts={4} stopAt={null} />);
    expect(screen.getByText("12")).toBeInTheDocument(); // Games
    expect(screen.getByText("+86")).toBeInTheDocument(); // Trophies
    expect(screen.getByText("3.4")).toBeInTheDocument(); // Avg rank
    expect(screen.getByText("1")).toBeInTheDocument(); // Disconnects
    expect(screen.getByText("1 h 12 min")).toBeInTheDocument(); // Duration
    expect(screen.getByText("4")).toBeInTheDocument(); // Interrupts
    expect(screen.queryByText(/Session ended/)).not.toBeInTheDocument();
  });

  it("reads a missing session in words, not as blanks", () => {
    render(
      <SessionPanel
        inst={makeInstance({ name: "Pie64", state: "starting", games_played: null, session: null })}
        avgRank={null}
        interrupts={0}
        stopAt={null}
      />,
    );
    expect(figure("Avg rank")).toHaveTextContent("No games yet");
    expect(figure("Trophies")).toHaveTextContent("Not yet");
    expect(screen.queryByText("none")).not.toBeInTheDocument();
    expect(screen.getByText("0 min")).toBeInTheDocument(); // Duration
    expect(screen.getAllByText("0")).toHaveLength(3); // Games, Disconnects, Interrupts
  });

  it("keeps the last live figures and captions the end of the session", () => {
    const { rerender } = render(
      <SessionPanel inst={farming} avgRank={3.42} interrupts={4} stopAt={null} />,
    );
    expect(screen.getByText("12")).toBeInTheDocument();
    rerender(
      <SessionPanel
        inst={makeInstance({
          name: "Pie64",
          state: "stopped",
          games_played: null,
          session: null,
        })}
        avgRank={null}
        interrupts={0}
        stopAt="2026-09-11T14:15:40"
      />,
    );
    expect(screen.getByText("12")).toBeInTheDocument(); // the figures do not blank out
    expect(screen.getByText("+86")).toBeInTheDocument();
    expect(screen.getByText("Session ended Sep 11, 14:15")).toBeInTheDocument();
  });

  it("takes the real stop time once the feed's stop line arrives", () => {
    const stopped = makeInstance({
      name: "Pie64",
      state: "stopped",
      games_played: null,
      session: null,
    });
    const { rerender } = render(
      <SessionPanel inst={stopped} avgRank={null} interrupts={0} stopAt={null} />,
    );
    // Nothing has said when it stopped yet, so the caption is the moment the panel
    // noticed. The feed's own stop line arrives a poll later and is the better answer.
    expect(screen.getByText(/^Session ended \w\w\w \d+, \d\d:\d\d$/)).toBeInTheDocument();

    rerender(
      <SessionPanel inst={stopped} avgRank={null} interrupts={0} stopAt="2026-09-11T14:15:40" />,
    );
    expect(screen.getByText("Session ended Sep 11, 14:15")).toBeInTheDocument();
  });

  it("seeds a cold load from last_session and captions when it ended", () => {
    renderWithProviders(
      <SessionPanel
        inst={makeInstance({
          state: "stopped",
          games_played: 0,
          session: null,
          last_session: makeLastSession(),
        })}
        avgRank={null}
        interrupts={0}
        stopAt={null}
      />,
    );
    expect(screen.getByText("Session ended Sep 12, 22:14")).toBeInTheDocument();
    expect(figure("Games")).toHaveTextContent("12");
    expect(figure("Trophies")).toHaveTextContent("+86");
    expect(figure("Avg rank")).toHaveTextContent("3.4");
    expect(figure("Disconnects")).toHaveTextContent("1");
    expect(figure("Duration")).toHaveTextContent("1 h 14 min");
    expect(figure("Interrupts")).toHaveTextContent("2");
  });

  it("behaves exactly as it does today when last_session is null", () => {
    renderWithProviders(
      <SessionPanel
        inst={makeInstance({
          state: "stopped",
          games_played: 0,
          session: null,
          last_session: null,
        })}
        avgRank={null}
        interrupts={0}
        stopAt={null}
      />,
    );
    expect(figure("Games")).toHaveTextContent("0");
    expect(figure("Trophies")).toHaveTextContent("Not yet");
    expect(figure("Avg rank")).toHaveTextContent("No games yet");
    expect(figure("Duration")).toHaveTextContent("0 min");
  });

  it("follows a live worker and never reads last_session again for that mount", () => {
    const live = makeInstance({
      state: "farming",
      games_played: 4,
      last_session: makeLastSession({ games: 99 }),
    });
    const { rerender } = renderWithProviders(
      <SessionPanel inst={live} avgRank={2.5} interrupts={1} stopAt={null} />,
    );
    expect(figure("Games")).toHaveTextContent("4");
    rerender(
      <SessionPanel
        inst={{ ...live, state: "stopped" }}
        avgRank={2.5}
        interrupts={1}
        stopAt="2026-09-12T23:05:00"
      />,
    );
    // Frozen on what it saw live, not on the 99 games last_session carries.
    expect(figure("Games")).toHaveTextContent("4");
    expect(screen.getByText("Session ended Sep 12, 23:05")).toBeInTheDocument();
  });
  it("says Not yet when only one end of the trophy pair was recorded", () => {
    render(
      <SessionPanel
        inst={makeInstance({
          name: "Pie64",
          state: "farming",
          games_played: 3,
          session: { ...SESSION, last_trophies: null },
        })}
        avgRank={2.5}
        interrupts={0}
        stopAt={null}
      />,
    );
    expect(figure("Trophies")).toHaveTextContent("Not yet");
  });

  it("groups thousands in the counts and keeps a phrase out of the mono column", () => {
    render(
      <SessionPanel
        inst={makeInstance({
          name: "Pie64",
          state: "farming",
          games_played: 1234,
          session: SESSION,
        })}
        avgRank={null}
        interrupts={0}
        stopAt={null}
      />,
    );
    expect(figure("Games")).toHaveTextContent("1,234");
    expect(figure("Games").className).toContain("font-mono");
    const rank = figure("Avg rank");
    expect(rank).toHaveTextContent("No games yet");
    expect(rank.className).not.toContain("font-mono");
    expect(rank.className).toContain("text-muted");
  });
});
