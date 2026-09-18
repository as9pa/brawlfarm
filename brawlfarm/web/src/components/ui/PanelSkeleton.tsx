/**
 * A panel's shape while its data is still in flight: the panel shell and a few bones.
 *
 * The bars are aria-hidden, because bones read as nothing; the sr-only line is what the
 * page says out loud, and it doubles as the region's accessible name so a screen reader
 * hears "Loading the feed" rather than an unnamed busy box. The pulse is motion-safe only:
 * a reduced-motion reader gets the same panel, still.
 */
import { useId } from "react";

export interface PanelSkeletonProps {
  label: string;
  rows?: number;
}

export function PanelSkeleton({ label, rows = 3 }: PanelSkeletonProps) {
  const labelId = useId();
  return (
    <div
      role="status"
      aria-busy="true"
      aria-labelledby={labelId}
      className="rounded-[10px] border border-line bg-panel p-3"
    >
      <span id={labelId} className="sr-only">
        Loading {label}
      </span>
      <div aria-hidden="true" className="flex flex-col gap-2 motion-safe:animate-pulse">
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} data-block="" className="h-3 rounded-[3px] bg-panel-2" />
        ))}
      </div>
    </div>
  );
}
