/** The overlay: frame coordinates go straight into the viewBox, a found anchor is drawn
 * solid in the ok colour and a missing one dashed in the bad one. The picture carries no
 * words and no handler; the labels are a layer of their own, shown on hover. */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

/** One tap per screen bucket, for the filter: the card is on the brawler screen and the
 * attack point is in a match. */
const BRAWLER_CARD: CalibrationConstant = {
  name: "BRAWLER_CARD",
  group: "tap",
  default: [420, 500],
  value: [420, 500],
  source: "package",
};

const ATTACK_POINT: CalibrationConstant = {
  name: "ATTACK_POINT",
  group: "tap",
  default: [1360, 700],
  value: [1360, 700],
  source: "package",
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

function labels(): HTMLElement {
  return screen.getByTestId("overlay-labels");
}

describe("FrameOverlay", () => {
  it("writes a tap at its own frame coordinates inside a 1600x900 viewBox", () => {
    render(
      <FrameOverlay
        instance="Pie64"
        taps={[PLAY_BUTTON]}
        anchors={[]}
        show="taps"
        screen="all"
        highlight={null}
        onHighlight={() => undefined}
        refreshMs={false}
      />,
    );
    expect(overlay()).toHaveAttribute("viewBox", "0 0 1600 900");
    expect(overlay()).toHaveAttribute("preserveAspectRatio", "none");
    const tap = overlay().querySelector('[data-kind="tap"]');
    expect(tap).toHaveAttribute("transform", "translate(1434 826)");
  });

  it("draws a found anchor solid and a missing one dashed", () => {
    render(
      <FrameOverlay
        instance="Pie64"
        taps={[]}
        anchors={[makeAnchor(), makeAnchor({ name: "matchmaking", found: false, score: 0.41 })]}
        show="anchors"
        screen="all"
        highlight={null}
        onHighlight={() => undefined}
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
        screen="all"
        highlight={null}
        onHighlight={() => undefined}
        refreshMs={false}
      />,
    );
    expect(overlay().querySelectorAll('[data-kind="anchor"]')).toHaveLength(0);
  });

  it("puts no words in the picture, and no way to click it", () => {
    render(
      <FrameOverlay
        instance="Pie64"
        taps={[PLAY_BUTTON]}
        anchors={[makeAnchor()]}
        show="both"
        screen="all"
        highlight={null}
        onHighlight={() => undefined}
        refreshMs={false}
      />,
    );
    expect(overlay().querySelectorAll("text")).toHaveLength(0);
    expect(overlay()).toHaveAttribute("aria-hidden", "true");
    const frame = screen.getByTestId("frame");
    expect(frame.querySelectorAll("button")).toHaveLength(0);
    expect(frame.querySelectorAll("a")).toHaveLength(0);
  });

  it("leaves out a point that belongs to another screen", () => {
    const { rerender } = render(
      <FrameOverlay
        instance="Pie64"
        taps={[BRAWLER_CARD, ATTACK_POINT]}
        anchors={[]}
        show="taps"
        screen="match"
        highlight={null}
        onHighlight={() => undefined}
        refreshMs={false}
      />,
    );
    expect(overlay().querySelectorAll('[data-kind="tap"]')).toHaveLength(1);
    expect(overlay().querySelector('[data-kind="tap"]')).toHaveAttribute(
      "transform",
      "translate(1360 700)",
    );

    rerender(
      <FrameOverlay
        instance="Pie64"
        taps={[BRAWLER_CARD, ATTACK_POINT]}
        anchors={[]}
        show="taps"
        screen="all"
        highlight={null}
        onHighlight={() => undefined}
        refreshMs={false}
      />,
    );
    expect(overlay().querySelectorAll('[data-kind="tap"]')).toHaveLength(2);
  });

  it("hides every label until one is hovered or highlighted", () => {
    const { rerender } = render(
      <FrameOverlay
        instance="Pie64"
        taps={[PLAY_BUTTON]}
        anchors={[]}
        show="taps"
        screen="all"
        highlight={null}
        onHighlight={() => undefined}
        refreshMs={false}
      />,
    );
    // classList rather than the class string: hover:opacity-100 is in there either way.
    const label = within(labels()).getByText("Play button");
    expect(label.classList.contains("opacity-0")).toBe(true);
    expect(label.classList.contains("opacity-100")).toBe(false);

    rerender(
      <FrameOverlay
        instance="Pie64"
        taps={[PLAY_BUTTON]}
        anchors={[]}
        show="taps"
        screen="all"
        highlight="PLAY_BUTTON"
        onHighlight={() => undefined}
        refreshMs={false}
      />,
    );
    expect(within(labels()).getByText("Play button").classList.contains("opacity-100")).toBe(
      true,
    );
  });

  it("names an anchor in words, with how well it matched", () => {
    render(
      <FrameOverlay
        instance="Pie64"
        taps={[]}
        anchors={[makeAnchor()]}
        show="anchors"
        screen="all"
        highlight={null}
        onHighlight={() => undefined}
        refreshMs={false}
      />,
    );
    expect(within(labels()).getByText("Play button 93%")).toBeInTheDocument();
  });

  it("tells the caller which point the pointer is on", async () => {
    const seen: (string | null)[] = [];
    render(
      <FrameOverlay
        instance="Pie64"
        taps={[PLAY_BUTTON]}
        anchors={[]}
        show="taps"
        screen="all"
        highlight={null}
        onHighlight={(name) => seen.push(name)}
        refreshMs={false}
      />,
    );
    const label = within(labels()).getByText("Play button");
    await userEvent.hover(label);
    await userEvent.unhover(label);
    expect(seen).toEqual(["PLAY_BUTTON", null]);
  });

  it("takes no pointer events, so no click on it can move a coordinate", () => {
    render(
      <FrameOverlay
        instance="Pie64"
        taps={[PLAY_BUTTON]}
        anchors={undefined}
        show="both"
        screen="all"
        highlight={null}
        onHighlight={() => undefined}
        refreshMs={false}
      />,
    );
    expect(overlay().getAttribute("class")).toContain("pointer-events-none");
  });
});
