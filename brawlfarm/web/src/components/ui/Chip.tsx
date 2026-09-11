/** A toned word chip: alert kinds, the schedule override, anything that is one label. */
import type { ReactNode } from "react";

import type { Tone } from "../../lib/states";
import { TONE_DOT } from "../../lib/states";

export interface ChipProps {
  tone: Tone;
  children: ReactNode;
}

export function Chip({ tone, children }: ChipProps) {
  return (
    <span
      data-tone={tone}
      className="inline-flex items-center gap-1.5 rounded-[6px] border border-line bg-panel px-2 py-0.5 text-[11px] text-text"
    >
      <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${TONE_DOT[tone]}`} />
      {children}
    </span>
  );
}
