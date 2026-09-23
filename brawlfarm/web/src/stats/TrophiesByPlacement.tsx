/**
 * What each finish was worth: the average trophy change for 1st to 4th, one tile each.
 *
 * The figure is signed to one decimal and tinted by its sign, the same accent and red the
 * trophy figures use everywhere else, with the game count under it so an average over
 * two games never passes for one over fifty. Under five games the value goes muted for
 * that reason. A placement nobody reached says "Not yet" and drops the count line, since
 * "n = 0" under a placeholder only repeats it.
 *
 * Four tiles fit one row on a desktop and wrap to two by two on a phone.
 */
import type { StatsTrophiesByPlacement } from "../api/types";
import { NOT_YET } from "../lib/copy";
import { num, ordinal, signedOne } from "../lib/format";

export interface TrophiesByPlacementProps {
  rows: StatsTrophiesByPlacement[];
}

/** Under this many games the average reads muted. */
const FEW_GAMES = 5;

function valueTone(row: StatsTrophiesByPlacement): string {
  if (row.avg === null || row.games < FEW_GAMES) return "text-muted";
  if (row.avg > 0) return "text-accent";
  if (row.avg < 0) return "text-bad";
  return "text-muted";
}

export function TrophiesByPlacement({ rows }: TrophiesByPlacementProps) {
  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <h2 className="text-[13px] font-semibold">Trophies by placement</h2>
      <ul className="grid grid-cols-2 gap-2 min-[520px]:grid-cols-4">
        {rows.map((row) => (
          <li
            key={row.placement}
            data-testid="trophies-tile"
            className="flex min-w-0 flex-col gap-0.5"
          >
            <span className="text-[11px] text-muted">{ordinal(row.placement)}</span>
            <span
              data-testid="trophies-value"
              className={`t-figure whitespace-nowrap text-[18px] ${valueTone(row)}`}
            >
              {row.avg === null ? NOT_YET : signedOne(row.avg)}
            </span>
            {row.avg !== null && (
              <span data-testid="trophies-games" className="t-figure text-[11px] text-muted">
                n = {num(row.games)}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
