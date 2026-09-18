/** The Calibration page: it preselects the running instance, scores its last frame, says
 * what calibration.toml has changed, and never offers a way to write a coordinate. */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Calibration } from "./Calibration";
import type { Calibration as CalibrationPayload, Recorder, Scores } from "../api/calibration";
import { Toaster } from "../components/ui/Toast";
import { resetToasts } from "../lib/toast";
import { makeInstance } from "../test/fixtures";
import { type FetchCall, jpegResponse, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function makeCalibration(overrides: Partial<CalibrationPayload["file"]> = {}): CalibrationPayload {
  return {
    file: { present: true, changed_since_start: false, problems: [], ...overrides },
    constants: [
      {
        name: "PLAY_BUTTON",
        group: "tap",
        default: [1434, 830],
        value: [1434, 826],
        source: "calibration.toml",
      },
      {
        name: "MATCH_THRESHOLD",
        group: "threshold",
        default: 0.85,
        value: 0.85,
        source: "package",
      },
    ],
    templates: [{ name: "play", source: "package", width: 110, height: 60, threshold: 0.85 }],
  };
}

const SCORES: Scores = {
  at: "2026-09-12T19:05:40+00:00",
  width: 1600,
  height: 900,
  state: "at_menu",
  phase: "at_menu",
  anchors: [
    {
      name: "play",
      threshold: 0.85,
      score: 0.93,
      found: true,
      expected: true,
      box: { x: 1380, y: 790, w: 110, h: 60 },
    },
    {
      name: "matchmaking",
      threshold: 0.85,
      score: 0.41,
      found: false,
      expected: true,
      box: { x: 611, y: 112, w: 276, h: 45 },
    },
  ],
};

const RECORDER: Recorder = {
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
};

/** Two configured instances, the second one stopped; `file` reshapes calibration.toml,
 * `scoresStatus` makes the scores route fail, `folderStatus` the folder button. */
function server(
  options: {
    file?: Partial<CalibrationPayload["file"]>;
    calibrationStatus?: number;
    scoresStatus?: number;
    folderStatus?: number;
  } = {},
): FetchCall[] {
  return stubFetch((url) => {
    if (url === "/api/instances") {
      return jsonResponse({
        instances: [
          makeInstance({ name: "Pie64_1", adb_port: 5565, state: "stopped" }),
          makeInstance({ name: "Pie64", state: "farming" }),
        ],
      });
    }
    if (url === "/api/calibration") {
      if (options.calibrationStatus !== undefined) {
        return jsonResponse({ detail: "calibration.toml is unreadable" }, options.calibrationStatus);
      }
      return jsonResponse(makeCalibration(options.file));
    }
    if (url === "/api/calibration/open-folder") {
      if (options.folderStatus !== undefined) {
        return jsonResponse({ detail: "Only on Windows" }, options.folderStatus);
      }
      return jsonResponse(null, 204);
    }
    if (url.endsWith("/calibration/scores")) {
      if (options.scoresStatus !== undefined) {
        return jsonResponse({ detail: "no frame yet" }, options.scoresStatus);
      }
      return jsonResponse(SCORES);
    }
    if (url.endsWith("/recorder")) return jsonResponse(RECORDER);
    if (url.endsWith("/preview.jpg")) return jpegResponse();
    throw new Error(`unstubbed request: ${url}`);
  }).calls;
}

function mount() {
  return renderWithProviders(
    <>
      <Routes>
        <Route path="/calibration" element={<Calibration />} />
      </Routes>
      <Toaster />
    </>,
    { route: "/calibration" },
  );
}

function overlay(): SVGSVGElement {
  return screen.getByTestId("overlay") as unknown as SVGSVGElement;
}

beforeEach(() => {
  URL.createObjectURL = (() => "blob:fake/1") as typeof URL.createObjectURL;
  URL.revokeObjectURL = (() => undefined) as typeof URL.revokeObjectURL;
});

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Calibration", () => {
  it("names itself and preselects the first running instance", async () => {
    server();
    mount();
    expect(screen.getAllByRole("heading", { level: 1 }).map((h) => h.textContent)).toEqual([
      "Calibration",
    ]);
    expect(
      await screen.findByText(
        "What brawlfarm sees. The page reads; calibration.toml and the templates folder write.",
      ),
    ).toBeInTheDocument();
    // Pie64_1 is listed first and is stopped, so the running Pie64 is the one preselected.
    expect(await screen.findByRole("button", { name: "Pie64" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Pie64_1" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("scores every anchor and marks the one that drifted", async () => {
    server();
    mount();
    const play = (await screen.findByText("play")).closest("tr");
    expect(within(play as HTMLElement).getByText("Found")).toBeInTheDocument();
    expect(within(play as HTMLElement).getByText("0.93")).toBeInTheDocument();
    expect(within(play as HTMLElement).getByText("now")).toBeInTheDocument();
    const drifted = screen.getByText("matchmaking").closest("tr");
    expect(within(drifted as HTMLElement).getByText("Drift")).toBeInTheDocument();
    expect(within(drifted as HTMLElement).getByText("never")).toBeInTheDocument();
  });

  it("lists the overridden constant with its default, its value and its source", async () => {
    server();
    mount();
    const row = (await screen.findByText("PLAY_BUTTON")).closest("tr") as HTMLElement;
    expect(within(row).getByText("1434, 830")).toBeInTheDocument();
    expect(within(row).getByText("1434, 826")).toBeInTheDocument();
    expect(within(row).getByText("calibration.toml")).toBeInTheDocument();
    // A threshold is listed whether or not anyone has overridden it.
    expect(screen.getByText("MATCH_THRESHOLD")).toBeInTheDocument();
  });

  it("prints every problem the file has", async () => {
    server({ file: { problems: ["PLAY_BUTTON: expected two integers"] } });
    mount();
    expect(await screen.findByText("PLAY_BUTTON: expected two integers")).toBeInTheDocument();
  });

  it("warns that a changed file does not reach an instance already running", async () => {
    server({ file: { changed_since_start: true } });
    mount();
    expect(
      await screen.findByText(
        "calibration.toml changed. Instances started before that run the old values until restarted.",
      ),
    ).toBeInTheDocument();
  });

  it("asks for the first capture when there is no frame yet", async () => {
    server({ scoresStatus: 404 });
    mount();
    // Twice: once where the frame would be, once as the anchor table's empty row.
    await waitFor(() => {
      expect(
        screen.getAllByText(
          "Start Pie64 to see its frame. Scores appear after the first capture.",
        ),
      ).toHaveLength(2);
    });
    expect(screen.queryByTestId("overlay")).toBeNull();
  });

  it("shows a failed read and retries it", async () => {
    const calls = server({ calibrationStatus: 500 });
    mount();
    expect(await screen.findByText("calibration.toml is unreadable")).toBeInTheDocument();
    const before = calls.filter((call) => call.url === "/api/calibration").length;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(calls.filter((call) => call.url === "/api/calibration").length).toBeGreaterThan(
        before,
      );
    });
  });

  it("draws both layers, then one at a time", async () => {
    server();
    mount();
    await waitFor(() => {
      expect(overlay().querySelectorAll('[data-kind="anchor"]')).toHaveLength(2);
    });
    expect(overlay().querySelectorAll('[data-kind="tap"]')).toHaveLength(1);

    await userEvent.click(screen.getByRole("radio", { name: "Taps" }));
    expect(overlay().querySelectorAll('[data-kind="anchor"]')).toHaveLength(0);
    expect(overlay().querySelectorAll('[data-kind="tap"]')).toHaveLength(1);

    await userEvent.click(screen.getByRole("radio", { name: "Anchors" }));
    expect(overlay().querySelectorAll('[data-kind="tap"]')).toHaveLength(0);
    expect(overlay().querySelectorAll('[data-kind="anchor"]')).toHaveLength(2);
  });

  it("opens the calibration folder, and says so when the platform cannot", async () => {
    const calls = server();
    mount();
    await userEvent.click(
      await screen.findByRole("button", { name: "Open calibration folder" }),
    );
    await waitFor(() => {
      expect(calls.some((call) => call.url === "/api/calibration/open-folder")).toBe(true);
    });
    expect(
      calls.find((call) => call.url === "/api/calibration/open-folder")?.init?.method,
    ).toBe("POST");
  });

  it("toasts the API's own sentence when the folder cannot be opened", async () => {
    server({ folderStatus: 501 });
    mount();
    await userEvent.click(
      await screen.findByRole("button", { name: "Open calibration folder" }),
    );
    expect(await screen.findByText("Only on Windows")).toBeInTheDocument();
  });
});
