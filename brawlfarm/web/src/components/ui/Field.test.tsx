/** A labelled input with a suffix, so "Goal 1000 trophies" is one control, not three. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Field } from "./Field";

describe("Field", () => {
  it("ties the label to the input and reports what was typed", async () => {
    const onChange = vi.fn();
    render(
      <Field
        label="Goal"
        id="goal"
        value="1000"
        onChange={onChange}
        type="number"
        suffix="trophies"
        min={0}
      />,
    );
    const input = screen.getByLabelText("Goal");
    expect(input).toHaveValue(1000);
    expect(input).toHaveAttribute("min", "0");
    expect(screen.getByText("trophies")).toBeInTheDocument();
    await userEvent.type(input, "1");
    expect(onChange).toHaveBeenLastCalledWith("10001");
  });

  it("passes a datalist id through so the roster can suggest brawlers", () => {
    render(
      <Field label="Fallback brawler" id="fallback" value="" onChange={vi.fn()} list="roster" disabled />,
    );
    const input = screen.getByLabelText("Fallback brawler");
    expect(input).toHaveAttribute("list", "roster");
    expect(input).toBeDisabled();
  });
});
