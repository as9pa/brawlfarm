/** The overlay: frame coordinates go straight into the viewBox, a found anchor is drawn
 * solid in the ok colour and a missing one dashed in the bad one. */
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FrameOverlay } from "./FrameOverlay";
import type { Anchor, CalibrationConstant } from "../api/calibration";
import { jpegResponse, stubFetch } from "../test/http";

const PLAY_BUTTON: CalibrationConstant = {
  name: "PLAY_BUTTON",
  group: "tap",
  default: [1434, 830],
  value: [1434, 826],
  source: "calibration.toml",
};

function makeAnchor(overrides: Partial<Anchor> = {}): Anchor {
  return {
    name: "play",
    threshold: 0.85,
    score: 0.93,
    found: true,
    expected: true,
    box: { x: 1380, y: 790, w: 110, h: 60 },
    ...overrides,
  };
}

beforeEach(() => {
  URL.createObjectURL = (() => "blob:fake/1") as typeof URL.createObjectURL;
  URL.revokeObjectURL = (() => undefined) as typeof URL.revokeObjectURL;
  stubFetch(() => jpegResponse());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function overlay(): SVGSVGElement {
  return screen.getByTestId("overlay") as unknown as SVGSVGElement;
}

describe("FrameOverlay", () => {
  it("writes a tap at its own frame coordinates inside a 1600x900 viewBox", () => {
    render(
      <FrameOverlay
        instance="Pie64"
        taps={[PLAY_BUTTON]}
        anchors={[]}
        show="taps"
        refreshMs={false}
      />,
    );
    expect(overlay()).toHaveAttribute("viewBox", "0 0 1600 900");
    expect(overlay()).toHaveAttribute("preserveAspectRatio", "none");
    const tap = overlay().querySelector('[data-kind="tap"]');
    expect(tap).toHaveAttribute("transform", "translate(1434 826)");
    expect(tap).toHaveTextContent("PLAY_BUTTON 1434,826");
  });

  it("draws a found anchor solid and a missing one dashed", () => {
    render(
      <FrameOverlay
        instance="Pie64"
        taps={[]}
        anchors={[makeAnchor(), makeAnchor({ name: "matchmaking", found: false, score: 0.41 })]}
        show="anchors"
        refreshMs={false}
      />,
    );
    const boxes = overlay().querySelectorAll('[data-kind="anchor"] rect');
    expect(boxes).toHaveLength(2);
    expect(boxes[0]).toHaveAttribute("stroke", "var(--ok)");
    expect(boxes[0]).not.toHaveAttribute("stroke-dasharray");
    expect(boxes[1]).toHaveAttribute("stroke", "var(--bad)");
    expect(boxes[1]).toHaveAttribute("stroke-dasharray", "8 6");
  });

  it("draws nothing for an anchor that was not located at all", () => {
    render(
      <FrameOverlay
        instance="Pie64"
        taps={[]}
        anchors={[makeAnchor({ found: false, box: { x: 0, y: 0, w: 0, h: 0 } })]}
        show="both"
        refreshMs={false}
      />,
    );
    expect(overlay().querySelectorAll('[data-kind="anchor"]')).toHaveLength(0);
  });

  it("takes no pointer events, so no click on it can move a coordinate", () => {
    render(
      <FrameOverlay
        instance="Pie64"
        taps={[PLAY_BUTTON]}
        anchors={undefined}
        show="both"
        refreshMs={false}
      />,
    );
    expect(overlay().getAttribute("class")).toContain("pointer-events-none");
  });
});
