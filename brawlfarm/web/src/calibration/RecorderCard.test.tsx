/** The recorder card: the switch follows the flag rather than the worker's answer, the
 * off state names the last session, and each cap says what to do about it. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FRAME_CAP_MESSAGE, RecorderCard, WRITE_ERROR_MESSAGE } from "./RecorderCard";
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

function mount(status: Recorder, onToggle = vi.fn()) {
  render(
    <RecorderCard instance="Pie64" status={status} pending={false} onToggle={onToggle} />,
  );
  return onToggle;
}

describe("RecorderCard", () => {
  it("says nothing has recorded yet when the recorder is off and has no history", () => {
    mount(makeRecorder());
    expect(screen.getByText("Off. Nothing has recorded here yet.")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Record frames" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("names the last session when there is one", () => {
    mount(makeRecorder({ last_session: "20260912-190540", last_frames: 412 }));
    expect(screen.getByText("Off. Last session 20260912-190540, 412 frames.")).toBeInTheDocument();
  });

  it("posts the flag when the switch is turned on", async () => {
    const onToggle = mount(makeRecorder());
    await userEvent.click(screen.getByRole("switch", { name: "Record frames" }));
    expect(onToggle).toHaveBeenCalledWith(true);
  });

  it("follows the flag, not what the worker has answered yet", () => {
    mount(makeRecorder({ flag: true, on: false }));
    expect(screen.getByRole("switch", { name: "Record frames" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("counts the frames, the megabytes and the session clock while it runs", () => {
    mount(
      makeRecorder({
        on: true,
        flag: true,
        frames: 5,
        bytes: 1258291,
        session: "20260912-190540",
        path: "recordings/Pie64/20260912-190540",
      }),
    );
    expect(screen.getByText("5 frames")).toBeInTheDocument();
    expect(screen.getByText("1.2 MB")).toBeInTheDocument();
    expect(screen.getByText(/session 19:05/)).toBeInTheDocument();
    expect(screen.getByText("recordings/Pie64/20260912-190540")).toBeInTheDocument();
  });

  it("explains the frame cap", () => {
    mount(makeRecorder({ reason: "frame_cap", last_session: "20260912-190540", last_frames: 2000 }));
    expect(screen.getByText(FRAME_CAP_MESSAGE)).toBeInTheDocument();
  });

  it("explains the disk cap and names the instance", () => {
    mount(makeRecorder({ reason: "disk_cap" }));
    expect(
      screen.getByText(
        "Recordings for Pie64 use 512 MB. Delete old session folders from the calibration folder to record again.",
      ),
    ).toBeInTheDocument();
  });

  it("explains a write that failed", () => {
    mount(makeRecorder({ reason: "error" }));
    expect(screen.getByText(WRITE_ERROR_MESSAGE)).toBeInTheDocument();
  });

  it("hands the recorder to observe mode while the observe worker owns the flag", () => {
    mount(makeRecorder({ mode: "observe" }));
    expect(screen.getByRole("switch", { name: "Record frames" })).toBeDisabled();
    expect(
      screen.getByText("Observe mode owns the recorder. Use Record while I play."),
    ).toBeInTheDocument();
  });

  it("disables the switch until the status has arrived", () => {
    render(
      <RecorderCard instance="Pie64" status={undefined} pending={false} onToggle={vi.fn()} />,
    );
    expect(screen.getByRole("switch", { name: "Record frames" })).toBeDisabled();
  });
});
