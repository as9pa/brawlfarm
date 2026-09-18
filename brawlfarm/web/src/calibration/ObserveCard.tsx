/**
 * Observe mode's switch: the owner plays, the worker watches and records.
 *
 * The switch shows `desired`, the supervisor's answer to the last click, not whether a
 * process is up: the worker is launched a tick later, so a switch that waited for it
 * would sit in the old position for up to a minute. The route refuses to start observing
 * on a live instance, so the switch is disabled whenever something else is running and
 * says what to do instead rather than offering a click that would come back 409.
 */
import type { Recorder } from "../api/calibration";
import { Switch } from "../components/ui/Switch";
import { RECORDING_CAP_NOTE } from "../lib/copy";

export interface ObserveCardProps {
  instance: string;
  /** The supervisor's desired mode for this instance, straight off the Fleet payload. */
  desired: string;
  running: boolean;
  status: Recorder | undefined;
  pending: boolean;
  onToggle: (on: boolean) => void;
}

export const OBSERVE_BLOCKED_MESSAGE =
  "Stop this instance first. Recording your own play never starts on top of a farming instance.";

export function ObserveCard({
  instance,
  desired,
  running,
  status,
  pending,
  onToggle,
}: ObserveCardProps) {
  const observing = desired === "observe";
  const blocked = running && !observing;
  const answering = status !== undefined && status.mode === "observe" && status.on;

  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[13px] font-semibold">Observe</h2>
        <Switch
          label="Record while I play"
          checked={observing}
          disabled={blocked || pending}
          onChange={onToggle}
        />
      </div>

      {blocked && <p className="text-[12px] text-muted">{OBSERVE_BLOCKED_MESSAGE}</p>}

      {!blocked && observing && (
        <p className="text-[12px] text-muted">
          {`Recording ${instance} while you play. It watches and never taps.`}
          {answering ? ` ${status.frames} frames so far.` : " Waiting for the recording to start…"}
        </p>
      )}

      {!blocked && !observing && (
        <p className="text-[12px] text-muted">
          Off. Turn it on and play the game yourself: every screen you visit is captured and
          labelled for calibration.
        </p>
      )}

      <p className="text-[12px] text-muted">{RECORDING_CAP_NOTE}</p>
    </section>
  );
}
