/** The section nav's narrow-screen edge: the row that scrolls carries a fade a reader sees
 * and a screen reader ignores, and the row itself still scrolls inside the wrapper. */
import { describe, expect, it } from "vitest";

import { SettingsNav } from "./SettingsNav";
import { renderWithProviders } from "../test/renderWithProviders";

describe("SettingsNav", () => {
  it("marks the scrolling edge with a fade the reader sees and a screen reader ignores", () => {
    const { container } = renderWithProviders(<SettingsNav />);

    const fade = container.querySelector("[data-edge-fade]");
    expect(fade).not.toBeNull();
    expect(fade?.getAttribute("aria-hidden")).toBe("true");
    expect(fade?.className).toContain("pointer-events-none");
    expect(fade?.className).toContain("min-[820px]:hidden");
  });

  it("keeps the section row scrolling inside the wrapper", () => {
    const { container } = renderWithProviders(<SettingsNav />);

    const list = container.querySelector("ul");
    expect(list?.className).toContain("overflow-x-auto");
    expect(list?.parentElement?.className).toContain("relative");
  });
});
