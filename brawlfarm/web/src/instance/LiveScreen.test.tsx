/** The instance's own screen: the frame it draws, the link to the raw PNG, and the
 * Refresh button that asks for a new frame now rather than at the next poll. */
import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveScreen } from "./LiveScreen";
import { type FetchCall, jpegResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const SHOT = "/api/instances/Pie64/screenshot.png";
const PREVIEW = "/api/instances/Pie64/preview.jpg";

beforeAll(() => {
  // jsdom has no object URLs, and Thumb turns every preview blob into one.
  Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:shot"), writable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), writable: true });
});

describe("LiveScreen", () => {
  let calls: FetchCall[];

  beforeEach(() => {
    calls = stubFetch(() => jpegResponse()).calls;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  function frames(): number {
    return calls.filter((call) => call.url === PREVIEW).length;
  }

  it("shows the live frame and a full size link", async () => {
    renderWithProviders(<LiveScreen name="Pie64" />);
    const image = await screen.findByRole("img");
    expect(image).toHaveAttribute("data-private");
    const link = screen.getByRole("link", { name: "Full size" });
    expect(link).toHaveAttribute("href", SHOT);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("Refresh forces one extra fetch", async () => {
    // Fake timers, because the page polls every second on its own: with real ones a slow
    // click would leave the count ambiguous.
    vi.useFakeTimers();
    renderWithProviders(<LiveScreen name="Pie64" />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(frames()).toBe(1);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(frames()).toBe(2);
  });

  it("polls once a second while the tab is visible", async () => {
    vi.useFakeTimers();
    renderWithProviders(<LiveScreen name="Pie64" />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(frames()).toBe(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(frames()).toBe(4);
  });
});
