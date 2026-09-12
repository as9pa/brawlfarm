/**
 * What the workers see: the calibration file, the anchor scores against one live frame,
 * and the frame recorder's switch.
 *
 * Every one of these is a read except the recorder toggle and the folder button, and
 * neither of those carries a coordinate: the page never writes a tap or a threshold, so
 * calibration.toml and the templates folder stay the only way to change them.
 *
 * A tap constant is a pair, and JSON has no tuple, so the API sends it as a two-item
 * list. `scores` answers 404 until the instance has written its first preview frame,
 * which is the page's empty state rather than a failure.
 */
import { api } from "./client";

export type ConstantGroup = "tap" | "threshold" | "timing";

/** A number for a threshold or a timing, a pair of pixels for a tap. */
export type ConstantValue = number | [number, number];

export interface CalibrationConstant {
  name: string;
  group: ConstantGroup;
  default: ConstantValue;
  value: ConstantValue;
  source: "package" | "calibration.toml";
}

export interface CalibrationTemplate {
  name: string;
  source: "package" | "override";
  width: number;
  height: number;
  threshold: number;
}

export interface Calibration {
  file: { present: boolean; changed_since_start: boolean; problems: string[] };
  constants: CalibrationConstant[];
  templates: CalibrationTemplate[];
}

/** Top-left plus size in the 1600x900 frame the worker captures. All zeros means the
 * template was not located at all, so there is nothing to draw. */
export interface AnchorBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Anchor {
  name: string;
  threshold: number;
  score: number;
  found: boolean;
  expected: boolean;
  box: AnchorBox;
}

export interface Scores {
  /** The frame's own moment, not the moment of the request. */
  at: string;
  width: number;
  height: number;
  state: string;
  /** The worker's own phase word, or null when it has not written one. */
  phase: string | null;
  anchors: Anchor[];
}

export interface Recorder {
  on: boolean;
  frames: number;
  bytes: number;
  session: string | null;
  path: string | null;
  reason: null | "frame_cap" | "disk_cap" | "error";
  last_session: string | null;
  last_frames: number;
  /** Whether record.flag is set right now. The worker answers in its own time, so this
   * is what the switch shows and `on` is what the session line reports. */
  flag: boolean;
}

export function getCalibration(): Promise<Calibration> {
  return api<Calibration>("/api/calibration");
}

export function getScores(name: string): Promise<Scores> {
  return api<Scores>(`/api/instances/${encodeURIComponent(name)}/calibration/scores`);
}

export function getRecorder(name: string): Promise<Recorder> {
  return api<Recorder>(`/api/instances/${encodeURIComponent(name)}/recorder`);
}

export function setRecorder(name: string, on: boolean): Promise<Recorder> {
  return api<Recorder>(`/api/instances/${encodeURIComponent(name)}/recorder`, {
    method: "POST",
    body: JSON.stringify({ on }),
  });
}

/** POST /api/calibration/open-folder. 204 on Windows; 501 "Only on Windows" anywhere
 * else, which the caller toasts. The path itself never crosses the wire. */
export function openCalibrationFolder(): Promise<void> {
  return api<void>("/api/calibration/open-folder", { method: "POST" });
}
