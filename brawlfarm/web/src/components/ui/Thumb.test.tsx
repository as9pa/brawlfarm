/** The preview box: it polls, it skips the frames that have not changed, it ages, it
 * retries, it never leaks an object URL, and its image is marked private so the pull
 * request's screenshots can blur it. */
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Thumb } from "./Thumb";
import { clock } from "../../lib/format";
import { jpegResponse, jsonResponse, stubFetch } from "../../test/http";

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
  it("fetches the preview, draws nothing over it and marks the image private", async () => {
    const { calls } = stubFetch(() => jpegResponse());
    render(<Thumb name="Pie64" refreshMs={false} />);
    const image = await screen.findByRole("img", { name: "Pie64 screen" });
    expect(image).toHaveAttribute("src", "blob:fake/1");
    expect(image).toHaveAttribute("data-private");
    expect(image.parentElement).toHaveTextContent("");
    expect(calls[0].url).toBe("/api/instances/Pie64/preview.jpg");
  });

  it("hands up the frame's own timestamp, not the moment of the fetch", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-10T12:00:05Z"));
    stubFetch(() => jpegResponse({ "last-modified": "Thu, 10 Sep 2026 12:00:00 GMT" }));
    const frames: number[] = [];
    render(
      <Thumb name="Pie64" refreshMs={false} onFrame={(takenAt) => frames.push(takenAt)} />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(frames).toEqual([Date.parse("2026-09-10T12:00:00Z")]);
  });

  it("refreshes on the interval and revokes the url it replaced", async () => {
    vi.useFakeTimers();
    // No etag at all: every answer is a frame we have not seen.
    const { calls } = stubFetch(() => jpegResponse());
    render(<Thumb name="Pie64" refreshMs={1000} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(calls).toHaveLength(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(calls).toHaveLength(2);
    expect(revoked).toEqual(["blob:fake/1"]);
    expect(created).toEqual(["blob:fake/1", "blob:fake/2"]);
  });

  it("keeps the frame it is showing while the etag stays the same", async () => {
    vi.useFakeTimers();
    const { calls } = stubFetch(() => jpegResponse({ etag: '"one"' }));
    render(<Thumb name="Pie64" refreshMs={1000} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(calls).toHaveLength(2);
    expect(calls[1].init?.headers).toEqual({ "if-none-match": '"one"' });
    expect(created).toEqual(["blob:fake/1"]);
    expect(revoked).toEqual([]);
  });

  it("takes a new frame when the etag changes and revokes the one it dropped", async () => {
    vi.useFakeTimers();
    let frame = 0;
    stubFetch(() => {
      frame += 1;
      return jpegResponse({ etag: `"${frame}"` });
    });
    render(<Thumb name="Pie64" refreshMs={1000} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(created).toEqual(["blob:fake/1", "blob:fake/2"]);
    expect(revoked).toEqual(["blob:fake/1"]);
    expect(screen.getByRole("img", { name: "Pie64 screen" })).toHaveAttribute("src", "blob:fake/2");
  });

  it("fetches again as soon as refreshKey changes", async () => {
    const { calls } = stubFetch(() => jpegResponse());
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
    const { calls } = stubFetch(() => jsonResponse({ detail: "boom" }, 503));
    render(<Thumb name="Pie64" refreshMs={false} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(
      screen.getByText("No screenshot yet. Check that the instance is running."),
    ).toBeInTheDocument();
    expect(screen.getByText("Retrying in 15 s.")).toBeInTheDocument();
    expect(screen.queryByText(/boom/)).not.toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });
    expect(calls).toHaveLength(2);
  });

  it("stacks the break caption under the failure instead of over it", async () => {
    vi.useFakeTimers();
    stubFetch(() => jsonResponse({ detail: "adb did not answer" }, 503));
    render(<Thumb name="Pie64" refreshMs={false} dimmed caption="Break until 21:30" />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const error = screen.getByText("No screenshot yet. Check that the instance is running.");
    const caption = screen.getByText("Break until 21:30");
    expect(error).toBeInTheDocument();
    expect(caption).toBeInTheDocument();
    const overlay = screen.getByTestId("thumb-overlay");
    expect(overlay.className).toContain("flex-col");
    expect(overlay).toContainElement(error);
    expect(overlay).toContainElement(caption);
  });

  it("dims the image and captions it while the instance is on a break", async () => {
    stubFetch(() => jpegResponse());
    render(<Thumb name="Pie64" refreshMs={false} dimmed caption="Break until 21:30" />);
    const image = await screen.findByRole("img", { name: "Pie64 screen" });
    expect(image.className).toContain("opacity-40");
    expect(screen.getByText("Break until 21:30")).toBeInTheDocument();
  });

  it("revokes its object url when it unmounts", async () => {
    stubFetch(() => jpegResponse());
    const { unmount } = render(<Thumb name="Pie64" refreshMs={false} />);
    await screen.findByRole("img", { name: "Pie64 screen" });
    unmount();
    expect(revoked).toEqual(["blob:fake/1"]);
  });
  it("says when a pressed capture is in flight, and never says the same thing twice", async () => {
    vi.useFakeTimers();
    stubFetch(() => jpegResponse({ etag: '"one"' }));
    const busy: boolean[] = [];
    const onBusyChange = (next: boolean) => busy.push(next);
    const { rerender } = render(
      <Thumb name="Pie64" refreshMs={1000} refreshKey={0} onBusyChange={onBusyChange} />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    // Neither the load a mount starts nor the poll a second later is a press, and a
    // control that went dead once a second would flicker rather than inform.
    expect(busy).toEqual([]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(busy).toEqual([]);

    rerender(<Thumb name="Pie64" refreshMs={1000} refreshKey={1} onBusyChange={onBusyChange} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(busy).toEqual([true, false]);
    // The poll the press scheduled is background again.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(busy).toEqual([true, false]);
  });

  it("closes the in-flight signal when the pressed capture fails", async () => {
    vi.useFakeTimers();
    stubFetch(() => jsonResponse({ detail: "boom" }, 503));
    const busy: boolean[] = [];
    const onBusyChange = (next: boolean) => busy.push(next);
    const { rerender } = render(
      <Thumb name="Pie64" refreshMs={false} refreshKey={0} onBusyChange={onBusyChange} />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    rerender(<Thumb name="Pie64" refreshMs={false} refreshKey={1} onBusyChange={onBusyChange} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(busy).toEqual([true, false]);
  });

  it("frees the control when a prop change throws away the pressed capture", async () => {
    vi.useFakeTimers();
    let land = () => {};
    stubFetch(
      () =>
        new Promise<Response>((resolve) => {
          land = () => resolve(jpegResponse());
        }),
    );
    const busy: boolean[] = [];
    const onBusyChange = (next: boolean) => busy.push(next);
    const { rerender } = render(
      <Thumb name="Pie64" refreshMs={1000} refreshKey={0} onBusyChange={onBusyChange} />,
    );
    rerender(<Thumb name="Pie64" refreshMs={1000} refreshKey={1} onBusyChange={onBusyChange} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(busy).toEqual([true]);
    // The tab goes hidden mid-capture: that fetch never settles, and the control it
    // disabled has to be freed anyway.
    rerender(<Thumb name="Pie64" refreshMs={false} refreshKey={1} onBusyChange={onBusyChange} />);
    expect(busy).toEqual([true, false]);
    await act(async () => {
      land();
      await vi.advanceTimersByTimeAsync(0);
    });
  });

  it("stamps the frame with its age and the clock when the clock is asked for", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-10T12:00:05Z"));
    stubFetch(() => jpegResponse({ "last-modified": "Thu, 10 Sep 2026 12:00:00 GMT" }));
    render(<Thumb name="Pie64" refreshMs={false} showClock />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const at = clock("2026-09-10T12:00:00.000Z");
    const stamp = screen.getByText(`5 s ago (${at})`);
    expect(stamp).toHaveAttribute("title", at);
    // A corner chip, not the block that fills the frame: the picture stays readable.
    expect(stamp.className).toContain("bottom-2");
    expect(stamp.className).not.toContain("inset-0");
    expect(screen.queryByTestId("thumb-overlay")).not.toBeInTheDocument();
  });

  it("leaves the caption alone without the clock, and titles it either way", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-10T12:00:05Z"));
    stubFetch(() => jpegResponse({ "last-modified": "Thu, 10 Sep 2026 12:00:00 GMT" }));
    render(<Thumb name="Pie64" refreshMs={false} caption="Break until 21:30" />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const caption = screen.getByText("Break until 21:30");
    expect(caption.textContent).toBe("Break until 21:30");
    expect(caption).toHaveAttribute("title", clock("2026-09-10T12:00:00.000Z"));
  });
});
