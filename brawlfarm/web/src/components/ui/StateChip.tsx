/** An instance's state as a word plus a dot. */
import type { InstanceState } from "../../api/types";
import { TONE_DOT, stateLabel, stateTone } from "../../lib/states";

export interface StateChipProps {
  state: InstanceState;
}

export function StateChip({ state }: StateChipProps) {
  const tone = stateTone(state);
  return (
    <span className="inline-flex items-center gap-1.5 rounded-[6px] border border-line bg-panel px-2 py-0.5 text-[11px] text-text">
      <span
        data-tone={tone}
        aria-hidden="true"
        className={`h-1.5 w-1.5 shrink-0 rounded-full ${TONE_DOT[tone]}`}
      />
      {stateLabel(state)}
    </span>
  );
}
