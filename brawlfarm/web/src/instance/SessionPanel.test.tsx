/** Six figures, and what happens to them when the worker stops. No providers: the panel
 * is handed everything it draws. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SessionPanel } from "./SessionPanel";
import { makeInstance } from "../test/fixtures";

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
    expect(screen.getByText("3.4")).toBeInTheDocument(); // Avg rank today
    expect(screen.getByText("1")).toBeInTheDocument(); // Disconnects
    expect(screen.getByText("1 h 12 min")).toBeInTheDocument(); // Duration
    expect(screen.getByText("4")).toBeInTheDocument(); // Interrupts
    expect(screen.queryByText(/Session ended/)).not.toBeInTheDocument();
  });

  it("reads a missing session as zeros, not as blanks", () => {
    render(
      <SessionPanel
        inst={makeInstance({ name: "Pie64", state: "starting", games_played: null, session: null })}
        avgRank={null}
        interrupts={0}
        stopAt={null}
      />,
    );
    expect(screen.getByText("none")).toBeInTheDocument(); // Avg rank today
    expect(screen.getByText("0 min")).toBeInTheDocument(); // Duration
    expect(screen.getAllByText("0").length).toBeGreaterThanOrEqual(3);
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
    expect(screen.getByText("Session ended 14:15")).toBeInTheDocument();
  });
});
