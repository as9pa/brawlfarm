/**
 * The live frame with the calibration drawn on top of it.
 *
 * The SVG's viewBox is the worker's own 1600x900 frame, so a tap at 1434,826 is written
 * at 1434,826 and nothing here has to know how wide the box happens to be on screen.
 * preserveAspectRatio="none" is what makes that true even when the browser gives the box
 * a slightly different ratio than 16:9.
 *
 * It is a picture and nothing else: pointer-events are off, there are no handlers, and
 * no click anywhere on it can move a coordinate. calibration.toml is the only way to
 * change what is drawn here.
 */
import type { Anchor, CalibrationConstant } from "../api/calibration";
import { Thumb } from "../components/ui/Thumb";

export type OverlayShow = "taps" | "anchors" | "both";

export interface FrameOverlayProps {
  instance: string;
  /** Every constant; the taps are picked out here so the caller does not have to. */
  taps: CalibrationConstant[];
  anchors: Anchor[] | undefined;
  show: OverlayShow;
  refreshMs: number | false;
}

/** The frame's coordinate system, which is also the viewBox. */
const FRAME_W = 1600;
const FRAME_H = 900;

function tapPoint(constant: CalibrationConstant): [number, number] | null {
  const value = constant.value;
  return Array.isArray(value) ? [value[0], value[1]] : null;
}

export function FrameOverlay({ instance, taps, anchors, show, refreshMs }: FrameOverlayProps) {
  const showTaps = show === "taps" || show === "both";
  const showAnchors = show === "anchors" || show === "both";

  return (
    <div className="relative">
      <Thumb name={instance} refreshMs={refreshMs} />
      <svg
        data-testid="overlay"
        aria-hidden="true"
        viewBox={`0 0 ${FRAME_W} ${FRAME_H}`}
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 h-full w-full"
      >
        {showTaps &&
          taps.map((constant) => {
            const point = tapPoint(constant);
            if (point === null) return null;
            const [x, y] = point;
            return (
              <g key={constant.name} data-kind="tap" transform={`translate(${x} ${y})`}>
                <circle r="7" fill="none" stroke="var(--accent)" strokeWidth="2" />
                <line x1="-13" x2="13" y1="0" y2="0" stroke="var(--accent)" strokeWidth="2" />
                <line x1="0" x2="0" y1="-13" y2="13" stroke="var(--accent)" strokeWidth="2" />
                <text x="10" y="-10" className="font-mono" fontSize="16" fill="var(--accent)">
                  {`${constant.name} ${x},${y}`}
                </text>
              </g>
            );
          })}
        {showAnchors &&
          (anchors ?? []).map((anchor) => {
            // An all-zero box is the API saying the template was not located anywhere,
            // so there is no place on the frame to point at.
            if (anchor.box.w === 0 || anchor.box.h === 0) return null;
            const stroke = anchor.found ? "var(--ok)" : "var(--bad)";
            return (
              <g key={anchor.name} data-kind="anchor">
                <rect
                  x={anchor.box.x}
                  y={anchor.box.y}
                  width={anchor.box.w}
                  height={anchor.box.h}
                  fill="none"
                  strokeWidth="2"
                  stroke={stroke}
                  strokeDasharray={anchor.found ? undefined : "8 6"}
                />
                <text
                  x={anchor.box.x}
                  y={anchor.box.y - 6}
                  className="font-mono"
                  fontSize="16"
                  fill={stroke}
                >
                  {`${anchor.name} ${anchor.score.toFixed(2)}`}
                </text>
              </g>
            );
          })}
      </svg>
    </div>
  );
}
