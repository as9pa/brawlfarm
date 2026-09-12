/** The 22 px brawler square: the image while it loads, the initial when it cannot, and the
 * same box in both states so no row ever shifts. */
import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BrawlerIcon } from "./BrawlerIcon";
import { renderWithProviders } from "../../test/renderWithProviders";

function box(): HTMLElement {
  return screen.getByTestId("brawler-icon");
}

describe("BrawlerIcon", () => {
  it("points the image at the icon route with the name encoded", () => {
    renderWithProviders(<BrawlerIcon name="Mr. P" />);
    const img = box().querySelector("img");
    expect(img).toHaveAttribute("src", "/api/brawlers/Mr.%20P/icon.png");
    expect(img).toHaveAttribute("alt", "");
    expect(img).toHaveAttribute("loading", "lazy");
    expect(img).toHaveAttribute("decoding", "async");
  });

  it("falls back to the upper-cased initial when the image errors", () => {
    renderWithProviders(<BrawlerIcon name="nori" />);
    const img = box().querySelector("img");
    expect(img).not.toBeNull();
    fireEvent.error(img as HTMLImageElement);
    expect(box().querySelector("img")).toBeNull();
    expect(box()).toHaveTextContent("N");
  });

  it("falls back for a null name and for a blank one", () => {
    const { unmount } = renderWithProviders(<BrawlerIcon name={null} />);
    expect(box().querySelector("img")).toBeNull();
    expect(box()).toHaveTextContent("");
    unmount();
    renderWithProviders(<BrawlerIcon name="   " />);
    expect(box().querySelector("img")).toBeNull();
  });

  it("keeps the same box in both states, at the default size and a given one", () => {
    const { unmount } = renderWithProviders(<BrawlerIcon name="Nori" />);
    expect(box()).toHaveStyle({ width: "22px", height: "22px" });
    const img = box().querySelector("img") as HTMLImageElement;
    fireEvent.error(img);
    expect(box()).toHaveStyle({ width: "22px", height: "22px" });
    unmount();
    renderWithProviders(<BrawlerIcon name="Nori" size={16} />);
    expect(box()).toHaveStyle({ width: "16px", height: "16px" });
  });

  it("is hidden from a screen reader, because the name is always beside it", () => {
    renderWithProviders(<BrawlerIcon name="Nori" />);
    expect(box()).toHaveAttribute("aria-hidden", "true");
  });

  it("goes back to the image when the name changes after an error", () => {
    const { rerender } = renderWithProviders(<BrawlerIcon name="Nori" />);
    fireEvent.error(box().querySelector("img") as HTMLImageElement);
    expect(box().querySelector("img")).toBeNull();
    rerender(<BrawlerIcon name="Shelly" />);
    expect(box().querySelector("img")).toHaveAttribute("src", "/api/brawlers/Shelly/icon.png");
  });
});
