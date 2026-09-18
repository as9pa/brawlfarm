/**
 * Every anchor scored against the frame beside it.
 *
 * "Last seen" is the one thing the API cannot answer: each response says only what this
 * frame holds, so the page remembers the moment of the last response in which an anchor
 * was found and shows that once it is gone. The memory is a ref rather than state
 * because writing it must not paint a frame of its own; the next poll is what re-renders,
 * and a poll is two seconds away.
 *
 * The stored moment is a millisecond stamp and its ISO string together: the age is
 * relative and has to be measured against now, while the tooltip is the wall clock of the
 * moment itself, and neither can be recovered from the other's wording.
 *
 * Hovering a row lights the same anchor on the frame above, so the two halves of the
 * page answer each other. The lit row is owned by the page, because the frame lights rows
 * the same way.
 */
import { useEffect, useRef } from "react";

import { anchorLabel } from "./names";
import type { Anchor } from "../api/calibration";
import { Table, type Column } from "../components/ui/Table";
import { clock } from "../lib/format";
import { TONE_TEXT, type Tone } from "../lib/states";
import { age } from "../lib/time";

export interface AnchorTableProps {
  anchors: readonly Anchor[];
  /** The frame's own moment, which is what "last seen" means. */
  at: string | undefined;
  empty: string;
  highlight: string | null;
  onHighlight: (name: string | null) => void;
}

/** The moment of a sighting, kept both ways: milliseconds for the age, the stamp for the
 * clock in the tooltip. */
interface Sighting {
  ms: number;
  iso: string;
}

/** Found, or an expectation the frame did not meet, or simply not in this frame. */
function status(anchor: Anchor): { label: string; tone: Tone } {
  if (anchor.found) return { label: "Found", tone: "ok" };
  if (anchor.expected) return { label: "Missing", tone: "bad" };
  return { label: "Not on this screen", tone: "idle" };
}

/** A whole percentage, the same figure the frame's own label carries. A miss can score
 * below zero because the match bottoms out at minus one and the route passes that
 * through, and a negative percentage would read as a measurement rather than as nothing
 * found. */
function percent(score: number): string {
  return `${Math.max(0, Math.round(score * 100))}%`;
}

export function AnchorTable({ anchors, at, empty, highlight, onHighlight }: AnchorTableProps) {
  const seen = useRef<Map<string, Sighting>>(new Map());

  useEffect(() => {
    if (at === undefined) return;
    const ms = Date.parse(at);
    if (Number.isNaN(ms)) return;
    for (const anchor of anchors) {
      if (anchor.found) seen.current.set(anchor.name, { ms, iso: at });
    }
  }, [anchors, at]);

  const lastSeen = (anchor: Anchor) => {
    if (anchor.found) return "just now";
    const sighting = seen.current.get(anchor.name);
    if (sighting === undefined) return "never";
    return <span title={clock(sighting.iso)}>{age(sighting.ms, Date.now())}</span>;
  };

  const columns: readonly Column<Anchor>[] = [
    { key: "name", label: "Name", render: (row) => anchorLabel(row.name) },
    {
      key: "score",
      label: "Match",
      width: "90px",
      render: (row) => (
        <span className="t-figure" title={`Needs ${percent(row.threshold)}`}>
          {percent(row.score)}
        </span>
      ),
    },
    {
      key: "status",
      label: "Status",
      width: "150px",
      render: (row) => {
        const { label, tone } = status(row);
        return (
          <span data-tone={tone} className={`text-[12px] ${TONE_TEXT[tone]}`}>
            {label}
          </span>
        );
      },
    },
    { key: "seen", label: "Last seen", width: "100px", render: (row) => lastSeen(row) },
  ];

  return (
    <Table
      columns={columns}
      rows={anchors}
      rowKey={(row) => row.name}
      empty={empty}
      headers="sentence"
      onRowHover={(row) => onHighlight(row === null ? null : row.name)}
      rowActive={(row) => highlight === row.name}
    />
  );
}
