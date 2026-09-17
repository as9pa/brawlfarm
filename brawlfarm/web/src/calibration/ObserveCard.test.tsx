/** The observe card: the switch follows the supervisor's desired mode rather than the
 * worker, it is disabled while the instance is doing anything else, and it counts frames
 * only once an observing worker is answering. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { OBSERVE_BLOCKED_MESSAGE, ObserveCard } from "./ObserveCard";
import type { Recorder } from "../api/calibration";

function makeRecorder(overrides: Partial<Recorder> = {}): Recorder {
  return {
    on: false,
    frames: 0,
    bytes: 0,
    session: null,
    path: null,
    reason: null,
    last_session: null,
    last_frames: 0,
    flag: false,
    mode: "farm",
    ...overrides,
  };
}

function mount(props: Partial<React.ComponentProps<typeof ObserveCard>> = {}) {
  const onToggle = vi.fn();
  render(
    <ObserveCard
      instance="Pie64"
      desired="stop"
      running={false}
      status={makeRecorder()}
      pending={false}
      onToggle={onToggle}
      {...props}
    />,
  );
  return onToggle;
}

describe("ObserveCard", () => {
  it("offers the switch on a stopped instance", async () => {
    const onToggle = mount();
    const control = screen.getByRole("switch", { name: "Record while I play" });
    expect(control).toHaveAttribute("aria-checked", "false");
    await userEvent.click(control);
    expect(onToggle).toHaveBeenCalledWith(true);
  });

  it("refuses to start on a farming instance and says why", () => {
    mount({ running: true, desired: "run" });
    expect(screen.getByRole("switch", { name: "Record while I play" })).toBeDisabled();
    expect(screen.getByText(OBSERVE_BLOCKED_MESSAGE)).toBeInTheDocument();
  });

  it("stays usable while it is the observer that is running", () => {
    mount({ running: true, desired: "observe" });
    expect(screen.getByRole("switch", { name: "Record while I play" })).not.toBeDisabled();
    expect(screen.getByRole("switch", { name: "Record while I play" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("waits for the worker before it counts frames", () => {
    mount({ running: true, desired: "observe", status: makeRecorder({ mode: "farm" }) });
    expect(screen.getByText(/Waiting for the recording to start…/)).toBeInTheDocument();
  });

  it("counts the frames once the observer is answering", () => {
    mount({
      running: true,
      desired: "observe",
      status: makeRecorder({ mode: "observe", on: true, frames: 37 }),
    });
    expect(screen.getByText(/37 frames so far/)).toBeInTheDocument();
  });
});
