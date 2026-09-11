/** The filter chips are a radio group, so a screen reader keeps the "one of these is
 * selected" relationship. Each option is tabbable; there is no arrow-key roving. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Segmented } from "./Segmented";

const OPTIONS = [
  { value: "all", label: "All" },
  { value: "matches", label: "Matches" },
  { value: "errors", label: "Errors" },
];

describe("Segmented", () => {
  it("marks the pressed option and reports the one that was clicked", async () => {
    const onChange = vi.fn();
    render(<Segmented value="all" options={OPTIONS} onChange={onChange} label="Feed filter" />);
    expect(screen.getByRole("radiogroup", { name: "Feed filter" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "All" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Errors" })).toHaveAttribute("aria-checked", "false");
    await userEvent.click(screen.getByRole("radio", { name: "Errors" }));
    expect(onChange).toHaveBeenCalledWith("errors");
  });
});
