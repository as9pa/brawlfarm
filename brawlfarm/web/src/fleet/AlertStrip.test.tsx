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

/** One row per panel kind, then a kind the panel does not write a sentence for. Every row
 * carries the same raw detail, so a sentence that leaked it would fail the exact match. */
const SENTENCES: [string, string, string][] = [
  [
    "offline",
    "Instance offline",
    "Pie64 has been offline for 8 min. Check that the BlueStacks window is open, then press Retry now on its card.",
  ],
  [
    "recover",
    "Recovering",
    "Pie64 got stuck on a screen and is working its way back. Open it to watch.",
  ],
  ["wrong_mode", "Wrong mode", "Pie64 picked the wrong mode and switched back. Nothing to do."],
  [
    "bad_resolution",
    "Wrong resolution",
    "Pie64 is not at 1600 by 900. Set the BlueStacks display to 1600 by 900 and restart it.",
  ],
  ["crash", "Bot crashed", "Pie64 crashed. Press Restart on its card."],
  [
    "recalibrate",
    "Recalibration due",
    "Pie64 needs recalibration. Open Calibration and record a new session.",
  ],
  ["stop", "Farm stopped", "Pie64: farm stopped. Open Alerts for the details."],
];

describe("AlertStrip", () => {
  it.each(SENTENCES)("says one sentence with an action for %s", (kind, title, expected) => {
    stubFetch(() => jsonResponse({ ok: true }));
    const alert = makeAlert({
      kind,
      title,
      detail: "score=0.456, recovered=True",
      ts: new Date(Date.now() - 8 * 60_000).toISOString(),
    });
    renderWithProviders(<AlertStrip alert={alert} unread={1} onOpen={vi.fn()} />);
    expect(screen.getByText(expected)).toBeInTheDocument();
  });

  it("keeps the kind's own chip beside the sentence", () => {
    stubFetch(() => jsonResponse({ ok: true }));
    renderWithProviders(<AlertStrip alert={OFFLINE} unread={1} onOpen={vi.fn()} />);
    expect(screen.getByText("Offline")).toBeInTheDocument();
  });

  it("shows none of the raw fields the API packed into the detail", () => {
    stubFetch(() => jsonResponse({ ok: true }));
    const alert = makeAlert({ detail: "score=0.456, recovered=True" });
    const { container } = renderWithProviders(
      <AlertStrip alert={alert} unread={1} onOpen={vi.fn()} />,
    );
    expect(container.textContent).not.toContain("=");
    expect(container.textContent).not.toContain("True");
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
