/** The thresholds table: the shipped confidences are listed whether or not anyone has
 * edited them, one column holds the value in use, and the source is a word with a legend
 * under the table rather than a file name in a cell. */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ThresholdsTable, thresholdRows } from "./ThresholdsTable";
import type { CalibrationConstant, CalibrationTemplate } from "../api/calibration";

const FILE = { present: true, changed_since_start: false, problems: [] };

const THRESHOLDS: CalibrationConstant[] = [
  {
    name: "MATCH_THRESHOLD",
    group: "threshold",
    default: 0.85,
    value: 0.85,
    source: "package",
  },
  {
    name: "IN_MATCH_THRESHOLD",
    group: "threshold",
    default: 0.8,
    value: 0.8,
    source: "package",
  },
  {
    name: "MATCHMAKING_THRESHOLD",
    group: "threshold",
    default: 0.85,
    value: 0.85,
    source: "package",
  },
];

const OVERRIDDEN_TIMING: CalibrationConstant = {
  name: "MATCH_POLL_SECONDS",
  group: "timing",
  default: 2,
  value: 5,
  source: "calibration.toml",
};

const PACKAGED_TAP: CalibrationConstant = {
  name: "PLAY_BUTTON",
  group: "tap",
  default: [1434, 830],
  value: [1434, 830],
  source: "package",
};

const TEMPLATE_OVERRIDE: CalibrationTemplate = {
  name: "play",
  source: "override",
  width: 110,
  height: 60,
  threshold: 0.9,
};

function rowOf(label: string): HTMLElement {
  return screen.getByText(label).closest("tr") as HTMLElement;
}

describe("thresholdRows", () => {
  it("lists every threshold, then the overridden constants, then the overridden templates", () => {
    const rows = thresholdRows([...THRESHOLDS, OVERRIDDEN_TIMING, PACKAGED_TAP], [
      TEMPLATE_OVERRIDE,
      { name: "exit", source: "package", width: 80, height: 40, threshold: 0.85 },
    ]);
    expect(rows.map((row) => row.name)).toEqual([
      "MATCH_THRESHOLD",
      "IN_MATCH_THRESHOLD",
      "MATCHMAKING_THRESHOLD",
      "MATCH_POLL_SECONDS",
      "play",
    ]);
    expect(rows.map((row) => row.source)).toEqual([
      "package",
      "package",
      "package",
      "file",
      "templates",
    ]);
  });
});

describe("ThresholdsTable", () => {
  it("shows the shipped thresholds as packaged values on a clean install", () => {
    render(<ThresholdsTable constants={THRESHOLDS} templates={[]} file={FILE} />);
    expect(screen.getByRole("heading", { level: 2, name: "Thresholds" })).toBeInTheDocument();
    expect(screen.queryByText("Overrides")).toBeNull();
    expect(screen.getByText("Packaged values, no overrides.")).toBeInTheDocument();
    const row = rowOf("Match confidence");
    expect(within(row).getByText("0.85")).toBeInTheDocument();
    expect(within(row).getByText("package")).toBeInTheDocument();
    expect(screen.queryByText("override")).toBeNull();
  });

  it("names three columns and no default of its own", () => {
    render(<ThresholdsTable constants={THRESHOLDS} templates={[]} file={FILE} />);
    const headers = screen.getAllByRole("columnheader").map((cell) => cell.textContent);
    expect(headers).toEqual(["Setting", "Value", "Source"]);
  });

  it("prints the packaged value as a note under a value that was changed", () => {
    const changed: CalibrationConstant = { ...THRESHOLDS[0], value: 0.9, source: "calibration.toml" };
    render(<ThresholdsTable constants={[changed]} templates={[]} file={FILE} />);
    const row = rowOf("Match confidence");
    expect(within(row).getByText("0.9")).toBeInTheDocument();
    expect(within(row).getByText("Packaged value 0.85")).toBeInTheDocument();
    expect(within(row).getByText("override")).toBeInTheDocument();
    expect(screen.queryByText("Packaged values, no overrides.")).toBeNull();
  });

  it("marks an overridden timing constant as an override", () => {
    render(
      <ThresholdsTable constants={[...THRESHOLDS, OVERRIDDEN_TIMING]} templates={[]} file={FILE} />,
    );
    const row = rowOf("Match poll seconds");
    expect(within(row).getByText("5")).toBeInTheDocument();
    expect(within(row).getByText("Packaged value 2")).toBeInTheDocument();
    expect(within(row).getByText("override")).toBeInTheDocument();
  });

  it("lists a replaced template once and never names its folder", () => {
    render(
      <ThresholdsTable constants={THRESHOLDS} templates={[TEMPLATE_OVERRIDE]} file={FILE} />,
    );
    const row = rowOf("Play button");
    expect(within(row).getByText("0.9")).toBeInTheDocument();
    expect(within(row).getByText("override")).toBeInTheDocument();
    expect(screen.queryByText("calibration/templates")).toBeNull();
    expect(screen.queryByText("play.png")).toBeNull();
  });

  it("explains the two source words under the table", () => {
    render(<ThresholdsTable constants={THRESHOLDS} templates={[]} file={FILE} />);
    expect(
      screen.getByText(
        "Package means the value brawlfarm ships. Override means you changed it in the calibration folder.",
      ),
    ).toBeInTheDocument();
  });

  it("keeps the file's own problems and its changed warning", () => {
    render(
      <ThresholdsTable
        constants={THRESHOLDS}
        templates={[]}
        file={{ present: true, changed_since_start: true, problems: ["PLAY_BUTTON: expected two integers"] }}
      />,
    );
    expect(screen.getByText("PLAY_BUTTON: expected two integers")).toHaveAttribute(
      "data-tone",
      "bad",
    );
    expect(
      screen.getByText(
        "The calibration file changed. Instances started before that keep the old values until you restart them.",
      ),
    ).toHaveAttribute("data-tone", "warn");
  });

  it("falls back to a plain line when the API reports nothing at all", () => {
    render(<ThresholdsTable constants={[]} templates={[]} file={FILE} />);
    expect(screen.getByText("No thresholds reported.")).toBeInTheDocument();
  });
});
