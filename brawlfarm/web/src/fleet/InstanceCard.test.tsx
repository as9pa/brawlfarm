/** One card per instance, in all seven states: what it shows, what it disables, and what
 * it calls. The seven cases are the whole point -- a card that looks the same when the
 * instance is farming and when it is offline is a card nobody can trust. */
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useLocation } from "react-router";

import { InstanceCard, breakCaption, nextValue, retryMinutes } from "./InstanceCard";
import type { InstanceState } from "../api/types";
import { NOT_SET } from "../lib/copy";
import { resetToasts, useToasts } from "../lib/toast";
import { makeInstance } from "../test/fixtures";
import { jpegResponse, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

/** The router's current path, so a click on the card can be shown to have moved. */
function LocationProbe() {
  const { pathname } = useLocation();
  return <span data-testid="pathname">{pathname}</span>;
}

function stubScreens() {
  return stubFetch((url) => {
    if (url.endsWith("preview.jpg")) return jpegResponse();
    if (url === "/api/instances") return jsonResponse({ instances: [] });
    return jsonResponse({ ok: true });
  });
}

// jsdom has no object URLs and Thumb turns every frame into one, so without these the
// thumbnail can only ever render its failure block.
beforeEach(() => {
  URL.createObjectURL = (() => "blob:fake/1") as typeof URL.createObjectURL;
  URL.revokeObjectURL = (() => undefined) as typeof URL.revokeObjectURL;
});

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

const CHIPS: [InstanceState, string][] = [
  ["farming", "Farming"],
  ["starting", "Starting"],
  ["stopping", "Stopping after this match"],
  ["stopped", "Stopped"],
  ["scheduled_break", "Scheduled break"],
  ["reconnecting", "Reconnecting"],
  ["offline", "Offline"],
];

describe("retryMinutes, breakCaption and nextValue", () => {
  it("reads the minutes out of the supervisor's offline note", () => {
    expect(retryMinutes("BlueStacks window not found. Retrying in 4 min.")).toBe(4);
    expect(retryMinutes("BlueStacks window not found. Retrying in 15 min.")).toBe(15);
    expect(retryMinutes("Starting; waiting for the first heartbeat")).toBeNull();
    expect(retryMinutes("")).toBeNull();
  });

  it("captions a break with its end time, or without one when there is none", () => {
    expect(breakCaption("2026-09-11T21:30:00")).toBe("Break until 21:30");
    expect(breakCaption(null)).toBe("On a scheduled break");
  });

  it("shows the next moment as a time, a countdown, or none", () => {
    expect(nextValue(makeInstance({ state: "farming", until: "2026-09-11T21:30:00" }))).toBe("21:30");
    expect(nextValue(makeInstance({ state: "stopped", until: null }))).toBe(NOT_SET);
    expect(
      nextValue(
        makeInstance({ state: "offline", until: null, note: "BlueStacks window not found. Retrying in 4 min." }),
      ),
    ).toBe("4 min");
    expect(nextValue(makeInstance({ state: "offline", until: null, note: "" }))).toBe("soon");
  });
});

describe("InstanceCard", () => {
  it.each(CHIPS)("shows the %s state as a chip", async (state, label) => {
    stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state })} />);
    expect(await screen.findByText(label)).toBeInTheDocument();
  });

  it("links the instance name to its page and names the port and phase", () => {
    stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ phase: "queuing" })} />);
    const link = screen.getByRole("link", { name: "Open Pie64" });
    expect(link).toHaveAttribute("href", "/instances/Pie64");
    expect(link).toHaveTextContent("Pie64");
    expect(screen.getByText("5555")).toBeInTheDocument();
    expect(screen.getByText("Queuing")).toBeInTheDocument();
  });

  it("stretches that one link over the whole card", async () => {
    stubScreens();
    renderWithProviders(
      <>
        <InstanceCard inst={makeInstance({ state: "farming" })} />
        <LocationProbe />
      </>,
    );
    const link = screen.getByRole("link", { name: "Open Pie64" });
    // jsdom loads no stylesheet, so the overlay that carries a click on the card body is
    // asserted as the utilities that draw it; the click itself proves the link navigates.
    expect(link.className).toContain("after:absolute");
    expect(link.className).toContain("after:inset-0");
    await userEvent.click(link);
    expect(screen.getByTestId("pathname")).toHaveTextContent("/instances/Pie64");
  });

  it("rings the card, not the name, while the link has keyboard focus", async () => {
    stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "farming" })} />);
    const link = screen.getByRole("link", { name: "Open Pie64" });
    await userEvent.tab();
    expect(link).toHaveFocus();
    expect(link.className).toContain("focus-visible:outline-none");
    expect(link.closest("article")?.className).toContain("has-[a:focus-visible]:outline-2");
  });

  it("shows the four metrics", () => {
    stubScreens();
    renderWithProviders(
      <InstanceCard
        inst={makeInstance({
          today: { games: 12, trophies: 86 },
          session: {
            minutes_elapsed: 72,
            start_trophies: 41200,
            last_trophies: 41286,
            disconnect_count: 0,
            recovery_attempts: 0,
            session: "session-20260911-190540.jsonl",
          },
          until: "2026-09-11T21:30:00",
        })}
      />,
    );
    expect(screen.getByText("Games today").nextSibling).toHaveTextContent("12");
    expect(screen.getByText("Trophies today").nextSibling).toHaveTextContent("+86");
    expect(screen.getByText("Session").nextSibling).toHaveTextContent("1 h 12 min");
    expect(screen.getByText("Next break").nextSibling).toHaveTextContent("21:30");
  });

  it("says Not started for a session that has not started", () => {
    stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "stopped", session: null, until: null })} />);
    expect(screen.getByText("Session").nextSibling).toHaveTextContent("Not started");
    expect(screen.getByText("Next session")).toBeInTheDocument();
  });

  it("replaces the thumbnail with the offline block and retries from it", async () => {
    const { calls } = stubScreens();
    renderWithProviders(
      <InstanceCard
        inst={makeInstance({
          state: "offline",
          until: null,
          note: "BlueStacks window not found. Retrying in 4 min.",
        })}
      />,
    );
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(
      screen.getByText("BlueStacks window not found. Retrying in 4 min."),
    ).toBeInTheDocument();
    const retry = screen.getByRole("button", { name: "Retry now" });
    expect(retry.closest("a")).toBeNull();
    await userEvent.click(retry);
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/retry");
    });
    expect(toastMessages()).toContain("Retrying Pie64 now");
  });

  it("says retrying soon when the note has no minute count", () => {
    stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "offline", note: "", until: null })} />);
    expect(screen.getByText("BlueStacks window not found. Retrying soon.")).toBeInTheDocument();
  });

  it("dims the thumbnail and captions it on a scheduled break", async () => {
    stubScreens();
    renderWithProviders(
      <InstanceCard inst={makeInstance({ state: "scheduled_break", until: "2026-09-11T21:30:00" })} />,
    );
    const image = await screen.findByRole("img", { name: "Pie64 screen" });
    expect(image.className).toContain("opacity-40");
    expect(screen.getByText("Break until 21:30")).toBeInTheDocument();
  });

  it("disables Stop with a reason on the three states that are not running", () => {
    for (const state of ["stopped", "scheduled_break", "offline"] as const) {
      stubScreens();
      const { unmount } = renderWithProviders(<InstanceCard inst={makeInstance({ state })} />);
      const stop = screen.getByRole("button", { name: "Stop" });
      expect(stop).toBeDisabled();
      expect(stop).toHaveAttribute("title", "Already stopped");
      unmount();
    }
  });

  it("offers Start on a card that is not running and Restart on one that is", () => {
    stubScreens();
    const { unmount } = renderWithProviders(<InstanceCard inst={makeInstance({ state: "stopped" })} />);
    expect(screen.getByRole("button", { name: "Start" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Restart" })).not.toBeInTheDocument();
    unmount();

    stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "farming" })} />);
    expect(screen.getByRole("button", { name: "Restart" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start" })).not.toBeInTheDocument();
  });

  it("stops with an undo that starts it again, without following the card link", async () => {
    const { calls } = stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "farming" })} />);
    await userEvent.click(screen.getByRole("button", { name: "Stop" }));
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/stop");
    });
    expect(toastMessages()).toContain("Stopping Pie64 after this match");

    const undo = renderHook(() => useToasts()).result.current[0]?.undo;
    expect(undo).toBeTypeOf("function");
    await undo?.();
    expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/start");
  });

  it("says why a stop failed rather than claiming the instance is stopping", async () => {
    stubFetch((url) =>
      url.endsWith("preview.jpg")
        ? jpegResponse()
        : jsonResponse({ detail: "adb did not answer" }, 503),
    );
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "farming" })} />);
    await userEvent.click(screen.getByRole("button", { name: "Stop" }));
    await vi.waitFor(() => {
      expect(toastMessages()).toContain("adb did not answer");
    });
    expect(toastMessages()).not.toContain("Stopping Pie64 after this match");
  });

  it("restarts from the footer", async () => {
    const { calls } = stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "farming" })} />);
    await userEvent.click(screen.getByRole("button", { name: "Restart" }));
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/restart");
    });
    expect(toastMessages()).toContain("Restarting Pie64");
  });

  it("has an Open control beside the two that act, none of them inside the link", () => {
    stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "farming" })} />);
    for (const name of ["Stop", "Restart", "Open"]) {
      const button = screen.getByRole("button", { name });
      expect(button).toBeInTheDocument();
      expect(button.closest("a")).toBeNull();
    }
  });
});
