/** The instance's own screen: the frame it draws, the link to the raw PNG, and the
 * Refresh button that asks for a new frame now rather than in 15 s. */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveScreen } from "./LiveScreen";
import { type FetchCall, pngResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const SHOT = "/api/instances/Pie64/screenshot.png";

beforeAll(() => {
  // jsdom has no object URLs, and Thumb turns every screenshot blob into one.
  Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:shot"), writable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), writable: true });
});

describe("LiveScreen", () => {
  let calls: FetchCall[];

  beforeEach(() => {
    calls = stubFetch(() => pngResponse()).calls;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function shots(): number {
    return calls.filter((call) => call.url === SHOT).length;
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
    renderWithProviders(<LiveScreen name="Pie64" />);
    await waitFor(() => {
      expect(shots()).toBe(1);
    });
    await userEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => {
      expect(shots()).toBe(2);
    });
  });
});
