/**
 * The live frame with the calibration drawn on top of it.
 *
 * The SVG's viewBox is the frame's own 1600x900, so a tap at 1434,826 is written at
 * 1434,826 and nothing here has to know how wide the box happens to be on screen.
 * preserveAspectRatio="none" is what makes that true even when the browser gives the box
 * a slightly different ratio than 16:9, and the strokes are non-scaling, so a crosshair
 * stays two pixels wide however narrow the page gets.
 *
 * It is a picture and nothing else: the drawing takes no pointer events, there is no
 * click handler anywhere in this file, and nothing on it can move a coordinate.
 * calibration.toml is the only way to change what is drawn here.
 *
 * The names sit in a second layer and appear one at a time, under the pointer. Both
 * layers are aria-hidden: a label that only exists on hover is no use to a reader who
 * cannot hover, so the readable copy of the same information is the table beside the
 * frame, which is real text in real rows.
 */
import type { ReactNode } from "react";

import { anchorLabel, constantLabel, onScreen, type ScreenFilter } from "./names";
import type { Anchor, CalibrationConstant } from "../api/calibration";
import { Thumb } from "../components/ui/Thumb";

export type OverlayShow = "taps" | "anchors" | "both";

export interface FrameOverlayProps {
  instance: string;
  /** Every constant; the taps are picked out here so the caller does not have to. */
  taps: CalibrationConstant[];
  anchors: Anchor[] | undefined;
  show: OverlayShow;
  screen: ScreenFilter;
  /** The one point whose label is shown regardless of hover, or null. */
  highlight: string | null;
  onHighlight: (name: string | null) => void;
  refreshMs: number | false;
}

/** The frame's coordinate system, which is also the viewBox. */
const FRAME_W = 1600;
const FRAME_H = 900;

function tapPoint(constant: CalibrationConstant): [number, number] | null {
  const value = constant.value;
  return Array.isArray(value) ? [value[0], value[1]] : null;
}

interface LabelProps {
  name: string;
  x: number;
  y: number;
  /** Shown without a pointer on it, because the table beside the frame names this one. */
  on: boolean;
  onHighlight: (name: string | null) => void;
  children: ReactNode;
}

/** One name over the point it belongs to. It is not focusable and never will be: the
 * layer around it is aria-hidden, and a focusable node inside an aria-hidden subtree is a
 * trap for anyone tabbing through. The keyboard route to this information is the table. */
function Label({ name, x, y, on, onHighlight, children }: LabelProps) {
  return (
    <span
      data-name={name}
      onMouseEnter={() => onHighlight(name)}
      onMouseLeave={() => onHighlight(null)}
      style={{ left: `${(x / FRAME_W) * 100}%`, top: `${(y / FRAME_H) * 100}%` }}
      className={`pointer-events-auto absolute rounded-[4px] border border-line bg-panel px-1 text-[11px] text-text transition-opacity duration-[120ms] hover:opacity-100 focus-visible:opacity-100 ${
        on ? "opacity-100" : "opacity-0"
      }`}
    >
      {children}
    </span>
  );
}

export function FrameOverlay({
  instance,
  taps,
  anchors,
  show,
  screen,
  highlight,
  onHighlight,
  refreshMs,
}: FrameOverlayProps) {
  const showTaps = show === "taps" || show === "both";
  const showAnchors = show === "anchors" || show === "both";

  // Both layers draw the same points, so the filtering happens once, here. A point the
  // screen filter drops leaves the DOM rather than going invisible, which keeps the
  // picture and its labels saying the same thing.
  const drawnTaps = !showTaps
    ? []
    : taps.flatMap((constant) => {
        const point = tapPoint(constant);
        if (point === null || !onScreen(constant.name, screen)) return [];
        return [{ name: constant.name, x: point[0], y: point[1] }];
      });

  const drawnAnchors = !showAnchors
    ? []
    : (anchors ?? []).filter(
        // An all-zero box is the API saying the template was not located anywhere, so
        // there is no place on the frame to point at.
        (anchor) => anchor.box.w > 0 && anchor.box.h > 0 && onScreen(anchor.name, screen),
      );

  return (
    <div data-testid="frame" className="relative">
      <Thumb name={instance} refreshMs={refreshMs} />
      <svg
        data-testid="overlay"
        aria-hidden="true"
        viewBox={`0 0 ${FRAME_W} ${FRAME_H}`}
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 h-full w-full"
      >
        {drawnTaps.map((tap) => (
          <g key={tap.name} data-kind="tap" transform={`translate(${tap.x} ${tap.y})`}>
            <circle
              r="7"
              fill="none"
              stroke="var(--accent)"
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            />
            <line
              x1="-13"
              x2="13"
              y1="0"
              y2="0"
              stroke="var(--accent)"
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            />
            <line
              x1="0"
              x2="0"
              y1="-13"
              y2="13"
              stroke="var(--accent)"
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            />
          </g>
        ))}
        {drawnAnchors.map((anchor) => (
          <g key={anchor.name} data-kind="anchor">
            <rect
              x={anchor.box.x}
              y={anchor.box.y}
              width={anchor.box.w}
              height={anchor.box.h}
              fill="none"
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
              stroke={anchor.found ? "var(--ok)" : "var(--bad)"}
              strokeDasharray={anchor.found ? undefined : "8 6"}
            />
          </g>
        ))}
      </svg>

      <div
        data-testid="overlay-labels"
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
      >
        {drawnTaps.map((tap) => (
          <Label
            key={tap.name}
            name={tap.name}
            x={tap.x}
            y={tap.y}
            on={highlight === tap.name}
            onHighlight={onHighlight}
          >
            {constantLabel(tap.name)}
          </Label>
        ))}
        {drawnAnchors.map((anchor) => (
          <Label
            key={anchor.name}
            name={anchor.name}
            x={anchor.box.x}
            y={anchor.box.y}
            on={highlight === anchor.name}
            onHighlight={onHighlight}
          >
            {`${anchorLabel(anchor.name)} ${Math.round(anchor.score * 100)}%`}
          </Label>
        ))}
      </div>
    </div>
  );
}
