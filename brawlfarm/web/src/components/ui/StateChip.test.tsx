/** The chip is the state: a word and a coloured dot, never colour alone. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StateChip } from "./StateChip";
import type { InstanceState } from "../../api/types";

const CASES: [InstanceState, string, string][] = [
  ["farming", "Farming", "ok"],
  ["starting", "Starting", "idle"],
  ["stopping", "Stopping after this match", "warn"],
  ["stopped", "Stopped", "idle"],
  ["scheduled_break", "Scheduled break", "idle"],
  ["reconnecting", "Reconnecting", "warn"],
  ["offline", "Offline", "bad"],
];

describe("StateChip", () => {
  it.each(CASES)("renders %s as a word with a %s dot", (state, label, tone) => {
    const { container } = render(<StateChip state={state} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(container.querySelector("[data-tone]")).toHaveAttribute("data-tone", tone);
  });
});
