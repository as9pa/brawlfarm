/** The anchor table: a plain name, a match percentage, one of three status words and how
 * long ago an anchor was last found. The memory of that moment is a ref, so the test
 * renders twice rather than mocking a clock. */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnchorTable } from "./AnchorTable";
import type { Anchor } from "../api/calibration";
import { clock } from "../lib/format";

const EMPTY = "No frame yet.";

const AT = "2026-09-17T05:25:00+00:00";
const LATER = "2026-09-17T05:26:00+00:00";

function anchor(over: Partial<Anchor> = {}): Anchor {
  return {
    name: "play",
    threshold: 0.85,
    score: 0.97,
    found: true,
    expected: true,
    box: { x: 1380, y: 790, w: 110, h: 60 },
    ...over,
  };
}

function table(anchors: readonly Anchor[], at: string | undefined, onHighlight = vi.fn()) {
  return (
    <AnchorTable
      anchors={anchors}
      at={at}
      empty={EMPTY}
      highlight={null}
      onHighlight={onHighlight}
    />
  );
}

function rowOf(label: string): HTMLElement {
  return screen.getByText(label).closest("tr") as HTMLElement;
}

describe("AnchorTable", () => {
  it("names four columns and no threshold of its own", () => {
    render(table([anchor()], AT));
    const headers = screen.getAllByRole("columnheader").map((cell) => cell.textContent);
    expect(headers).toEqual(["Name", "Match", "Status", "Last seen"]);
  });

  it("reads a found anchor as a plain name, a percentage, Found and just now", () => {
    render(table([anchor()], AT));
    const row = rowOf("Play button");
    expect(within(row).getByText("97%")).toBeInTheDocument();
    expect(within(row).getByText("Found")).toBeInTheDocument();
    expect(within(row).getByText("just now")).toBeInTheDocument();
    expect(screen.queryByText("play")).toBeNull();
  });

  it("keeps the threshold as the tooltip on the percentage it qualifies", () => {
    render(table([anchor()], AT));
    expect(within(rowOf("Play button")).getByText("97%")).toHaveAttribute("title", "Needs 85%");
  });

  it("calls an expected miss Missing and an unexpected one Not on this screen", () => {
    render(
      table(
        [
          anchor({ found: false, expected: true, score: 0.41 }),
          anchor({ name: "teams_left", found: false, expected: false, score: 0.12 }),
        ],
        AT,
      ),
    );
    expect(within(rowOf("Play button")).getByText("Missing")).toBeInTheDocument();
    expect(within(rowOf("Teams left counter")).getByText("Not on this screen")).toBeInTheDocument();
    expect(screen.queryByText("Drift")).toBeNull();
    expect(screen.queryByText("Absent")).toBeNull();
  });

  it("clamps a negative score to nought per cent", () => {
    render(table([anchor({ found: false, expected: true, score: -0.31 })], AT));
    expect(within(rowOf("Play button")).getByText("0%")).toBeInTheDocument();
  });

  it("dates the last sighting of an anchor that has gone", () => {
    const { rerender } = render(table([anchor()], AT));
    rerender(table([anchor({ found: false, expected: true, score: 0.4 })], LATER));
    const seen = within(rowOf("Play button")).getByText(/ ago$/);
    expect(seen).toHaveAttribute("title", clock(AT));
  });

  it("says never, without a tooltip, for an anchor it has not seen", () => {
    render(table([anchor({ found: false, expected: true, score: 0.4 })], AT));
    const seen = within(rowOf("Play button")).getByText("never");
    expect(seen).not.toHaveAttribute("title");
  });

  it("lights the frame with the raw name rather than the label", async () => {
    const onHighlight = vi.fn();
    render(table([anchor()], AT, onHighlight));
    await userEvent.hover(rowOf("Play button"));
    expect(onHighlight).toHaveBeenCalledWith("play");
    await userEvent.unhover(rowOf("Play button"));
    expect(onHighlight).toHaveBeenLastCalledWith(null);
  });
});
