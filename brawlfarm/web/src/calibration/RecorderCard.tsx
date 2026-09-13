/**
 * The frame recorder's switch and whatever it last reported.
 *
 * The switch shows `flag`, not `on`: the button sets record.flag and the worker picks it
 * up a few ticks later, so showing `on` would leave the switch sitting in the old
 * position after a click that worked. `on` is what the session line reports, which is
 * why a freshly flipped switch can read "on" above a session that has not opened yet.
 *
 * A cap is not a failure: the recorder stopped on purpose, and the strip says which cap
 * it hit and what to do about it.
 *
 * An observe worker raises and drops the same flag itself, so while one is recording this
 * switch steps aside rather than offering a second way to close that session.
 */
import type { Recorder } from "../api/calibration";
import { Switch } from "../components/ui/Switch";

export interface RecorderCardProps {
  instance: string;
  status: Recorder | undefined;
  pending: boolean;
  onToggle: (on: boolean) => void;
}

export const FRAME_CAP_MESSAGE =
  "Recorder stopped at 2000 frames for this session. Start it again for a new session folder.";

export function diskCapMessage(instance: string): string {
  return `Recordings for ${instance} use 512 MB. Delete old session folders from the calibration folder to record again.`;
}

export const WRITE_ERROR_MESSAGE =
  "Recorder stopped after a frame could not be written. Check the disk, then start it again.";

function megabytes(bytes: number): string {
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

/** A session id is YYYYMMDD-HHMMSS, so its clock is four characters in the middle. Any
 * other shape is printed as it arrived rather than sliced into nonsense. */
export function sessionClock(session: string): string | null {
  const match = /^\d{8}-(\d{2})(\d{2})\d{2}$/.exec(session);
  return match === null ? null : `${match[1]}:${match[2]}`;
}

function capMessage(status: Recorder, instance: string): string | null {
  if (status.reason === "frame_cap") return FRAME_CAP_MESSAGE;
  if (status.reason === "disk_cap") return diskCapMessage(instance);
  if (status.reason === "error") return WRITE_ERROR_MESSAGE;
  return null;
}

export function RecorderCard({ instance, status, pending, onToggle }: RecorderCardProps) {
  const cap = status === undefined ? null : capMessage(status, instance);
  const observing = status?.mode === "observe";
  const clock = status?.session === null || status?.session === undefined
    ? null
    : sessionClock(status.session);

  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[13px] font-semibold">Recorder</h2>
        <Switch
          label="Record frames"
          checked={status?.flag === true}
          disabled={status === undefined || pending || observing}
          onChange={onToggle}
        />
      </div>

      {observing && (
        <p className="text-[12px] text-muted">
          Observe mode owns the recorder. Use Record while I play.
        </p>
      )}

      {status !== undefined && status.on && (
        <p className="text-[12px] text-muted">
          <span className="font-mono tabular-nums text-text">{`${status.frames} frames`}</span>
          {", "}
          <span className="font-mono tabular-nums text-text">{megabytes(status.bytes)}</span>
          {clock === null ? "" : `, session ${clock}`}
        </p>
      )}

      {status !== undefined && !status.on && (
        <p className="text-[12px] text-muted">
          {status.last_session === null
            ? "Off. Nothing has recorded here yet."
            : `Off. Last session ${status.last_session}, ${status.last_frames} frames.`}
        </p>
      )}

      {status?.path !== undefined && status.path !== null && (
        <p className="font-mono text-[11px] text-muted">{status.path}</p>
      )}

      {cap !== null && (
        <p
          data-tone="bad"
          className="rounded-[6px] border border-line bg-panel-2 px-2 py-1.5 text-[12px] text-bad"
        >
          {cap}
        </p>
      )}
    </section>
  );
}
