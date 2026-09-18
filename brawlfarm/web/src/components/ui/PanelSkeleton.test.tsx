/** A panel that has nothing to show yet still says so: one announcement, a busy flag, and
 * as many bones as the panel it stands in for. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PanelSkeleton } from "./PanelSkeleton";

describe("PanelSkeleton", () => {
  it("announces what is loading and marks itself busy", () => {
    render(<PanelSkeleton label="the feed" />);
    const panel = screen.getByRole("status", { name: "Loading the feed" });
    expect(panel).toHaveAttribute("aria-busy", "true");
    expect(panel).toHaveClass("border");
  });

  it("drops the shell when it stands inside a panel that already drew one", () => {
    render(<PanelSkeleton label="the feed" bare />);
    const panel = screen.getByRole("status", { name: "Loading the feed" });
    expect(panel).not.toHaveClass("border");
    expect(panel).not.toHaveClass("p-3");
    expect(panel.querySelectorAll("[data-block]")).toHaveLength(3);
  });

  it("draws one bar per row", () => {
    const { container } = render(<PanelSkeleton label="the schedule" rows={5} />);
    expect(container.querySelectorAll("[data-block]")).toHaveLength(5);
  });

  it("draws three bars when no row count is given", () => {
    const { container } = render(<PanelSkeleton label="the farm plan" />);
    expect(container.querySelectorAll("[data-block]")).toHaveLength(3);
  });
});
