/** The five steps down the side: where you are, what is finished, and what you may not
 * skip to. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { StepRail } from "./StepRail";
import type { StepId } from "./useSetupState";

const NONE: Record<StepId, boolean> = {
  bluestacks: false,
  instances: false,
  display: false,
  stats: false,
  done: false,
};

describe("StepRail", () => {
  it("names the five steps in order", () => {
    render(<StepRail index={0} done={NONE} onGo={() => undefined} />);
    // The number in front of each label is decoration, so it is in the text content but
    // not in the name a screen reader reads, which is what the queries below go by.
    expect(screen.getAllByRole("button").map((button) => button.textContent)).toEqual([
      "1BlueStacks",
      "2Instances",
      "3Display",
      "4Stats",
      "5Done",
    ]);
    expect(screen.getByRole("button", { name: "BlueStacks" })).toBeInTheDocument();
  });

  it("marks the step you are on and checks the ones already finished", () => {
    render(
      <StepRail index={2} done={{ ...NONE, bluestacks: true, instances: true }} onGo={() => undefined} />,
    );
    expect(screen.getByRole("button", { name: "Display" })).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(screen.getByRole("button", { name: "BlueStacks" })).not.toHaveAttribute(
      "aria-current",
    );
    // The check is decoration: the name a screen reader reads is still the label.
    const rail = screen.getByRole("list");
    expect(rail.querySelectorAll("svg[aria-hidden='true']")).toHaveLength(2);
  });

  it("lets you go back but not skip forward", async () => {
    const gone: StepId[] = [];
    render(<StepRail index={2} done={NONE} onGo={(id) => gone.push(id)} />);
    expect(screen.getByRole("button", { name: "Stats" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Done" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Stats" }));
    expect(gone).toEqual([]);

    await userEvent.click(screen.getByRole("button", { name: "BlueStacks" }));
    expect(gone).toEqual(["bluestacks"]);
  });
});
