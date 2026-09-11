/** The strip above the grid: the newest alert in one sentence, with the one action that
 * kind deserves. */
import { renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AlertStrip } from "./AlertStrip";
import { resetToasts, useToasts } from "../lib/toast";
import { makeAlert } from "../test/fixtures";
import { jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

const OFFLINE = makeAlert({
  id: 9,
  instance: "Pie64_1",
  kind: "offline",
  title: "Instance offline",
  detail: "misses=3",
  ts: new Date(Date.now() - 8 * 60_000).toISOString(),
});

const CRASH = makeAlert({
  id: 8,
  instance: "Pie64",
  kind: "crash",
  title: "Bot crashed",
  detail: "err=adb did not answer",
});

describe("AlertStrip", () => {
  it("writes an offline alert as a sentence with its age", () => {
    stubFetch(() => jsonResponse({ ok: true }));
    renderWithProviders(<AlertStrip alert={OFFLINE} unread={1} onOpen={vi.fn()} />);
    expect(
      screen.getByText("Pie64_1 has been offline for 8 min. BlueStacks window not found."),
    ).toBeInTheDocument();
    expect(screen.getByText("Offline")).toBeInTheDocument();
  });

  it("writes every other kind as instance, title and detail", () => {
    stubFetch(() => jsonResponse({ ok: true }));
    renderWithProviders(<AlertStrip alert={CRASH} unread={1} onOpen={vi.fn()} />);
    expect(screen.getByText("Pie64 bot crashed: err=adb did not answer")).toBeInTheDocument();
  });

  it("offers Retry now only for an offline alert", () => {
    stubFetch(() => jsonResponse({ ok: true }));
    const { unmount } = renderWithProviders(<AlertStrip alert={OFFLINE} unread={1} onOpen={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Retry now" })).toBeInTheDocument();
    unmount();
    renderWithProviders(<AlertStrip alert={CRASH} unread={1} onOpen={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Retry now" })).not.toBeInTheDocument();
  });

  it("dismisses the alert it is showing", async () => {
    const { calls } = stubFetch(() => new Response(null, { status: 204 }));
    renderWithProviders(<AlertStrip alert={CRASH} unread={1} onOpen={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/alerts/8/dismiss");
    });
  });

  it("says why a dismiss failed rather than leaving the rejection unhandled", async () => {
    stubFetch(() => jsonResponse({ detail: "alert 8 is already dismissed" }, 409));
    renderWithProviders(<AlertStrip alert={CRASH} unread={1} onOpen={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    await vi.waitFor(() => {
      expect(toastMessages()).toContain("alert 8 is already dismissed");
    });
  });

  it("offers the rest only when there is more than one", async () => {
    stubFetch(() => jsonResponse({ ok: true }));
    const onOpen = vi.fn();
    const { unmount } = renderWithProviders(<AlertStrip alert={CRASH} unread={1} onOpen={onOpen} />);
    expect(screen.queryByRole("button", { name: /more/ })).not.toBeInTheDocument();
    unmount();
    renderWithProviders(<AlertStrip alert={CRASH} unread={4} onOpen={onOpen} />);
    await userEvent.click(screen.getByRole("button", { name: "3 more" }));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
