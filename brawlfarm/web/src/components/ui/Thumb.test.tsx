/** The screenshot box: it fetches, it ages, it retries, it never leaks an object URL,
 * and its image is marked private so the pull request's screenshots can blur it. */
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Thumb } from "./Thumb";
import { jsonResponse, pngResponse, stubFetch } from "../../test/http";

const created: string[] = [];
const revoked: string[] = [];

beforeEach(() => {
  created.length = 0;
  revoked.length = 0;
  let counter = 0;
  URL.createObjectURL = (() => {
    counter += 1;
    const url = `blob:fake/${counter}`;
    created.push(url);
    return url;
  }) as typeof URL.createObjectURL;
  URL.revokeObjectURL = ((url: string) => {
    revoked.push(url);
  }) as typeof URL.revokeObjectURL;
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("Thumb", () => {
  it("fetches the screen, shows its age and marks the image private", async () => {
    const { calls } = stubFetch(() => pngResponse());
    render(<Thumb name="Pie64" refreshMs={false} />);
    const image = await screen.findByRole("img", { name: "Pie64 screen" });
    expect(image).toHaveAttribute("src", "blob:fake/1");
    expect(image).toHaveAttribute("data-private");
    expect(screen.getByText("0 s ago")).toBeInTheDocument();
    expect(calls[0].url).toBe("/api/instances/Pie64/screenshot.png");
  });

  it("refreshes on the interval and revokes the url it replaced", async () => {
    vi.useFakeTimers();
    const { calls } = stubFetch(() => pngResponse());
    render(<Thumb name="Pie64" refreshMs={15000} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(calls).toHaveLength(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });
    expect(calls).toHaveLength(2);
    expect(revoked).toEqual(["blob:fake/1"]);
    expect(created).toEqual(["blob:fake/1", "blob:fake/2"]);
  });

  it("fetches again as soon as refreshKey changes", async () => {
    const { calls } = stubFetch(() => pngResponse());
    const { rerender } = render(<Thumb name="Pie64" refreshMs={false} refreshKey={0} />);
    await screen.findByRole("img", { name: "Pie64 screen" });
    expect(calls).toHaveLength(1);
    rerender(<Thumb name="Pie64" refreshMs={false} refreshKey={1} />);
    await vi.waitFor(() => {
      expect(calls).toHaveLength(2);
    });
  });

  it("shows the failure detail in the box and retries 15 s later", async () => {
    vi.useFakeTimers();
    const { calls } = stubFetch(() => jsonResponse({ detail: "adb did not answer" }, 503));
    render(<Thumb name="Pie64" refreshMs={false} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText("Screenshot failed: adb did not answer")).toBeInTheDocument();
    expect(screen.getByText("Retrying in 15 s.")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });
    expect(calls).toHaveLength(2);
  });

  it("dims the image and captions it while the instance is on a break", async () => {
    stubFetch(() => pngResponse());
    render(<Thumb name="Pie64" refreshMs={false} dimmed caption="Break until 21:30" />);
    const image = await screen.findByRole("img", { name: "Pie64 screen" });
    expect(image.className).toContain("opacity-40");
    expect(screen.getByText("Break until 21:30")).toBeInTheDocument();
  });

  it("revokes its object url when it unmounts", async () => {
    stubFetch(() => pngResponse());
    const { unmount } = render(<Thumb name="Pie64" refreshMs={false} />);
    await screen.findByRole("img", { name: "Pie64 screen" });
    unmount();
    expect(revoked).toEqual(["blob:fake/1"]);
  });
});
