/**
 * Every anchor scored against the frame beside it.
 *
 * "Last seen" is the one thing the API cannot answer: each response says only what this
 * frame holds, so the page remembers the moment of the last response in which an anchor
 * was found and shows that once it is gone. The memory is a ref rather than state
 * because writing it must not paint a frame of its own; the next poll is what re-renders,
 * and a poll is two seconds away.
 */
import { useEffect, useRef } from "react";

import type { Anchor } from "../api/calibration";
import { Table, type Column } from "../components/ui/Table";
import { TONE_TEXT, type Tone } from "../lib/states";

export interface AnchorTableProps {
  anchors: readonly Anchor[];
  /** The frame's own moment, which is what "last seen" means. */
  at: string | undefined;
  empty: string;
}

/** Found, or an expectation the frame did not meet, or simply not in this frame. */
function status(anchor: Anchor): { label: string; tone: Tone } {
  if (anchor.found) return { label: "Found", tone: "ok" };
  if (anchor.expected) return { label: "Drift", tone: "bad" };
  return { label: "Absent", tone: "idle" };
}

function clock(at: string | undefined): string | null {
  if (at === undefined) return null;
  const moment = new Date(at);
  if (Number.isNaN(moment.getTime())) return null;
  const hours = String(moment.getHours()).padStart(2, "0");
  const minutes = String(moment.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
}

export function AnchorTable({ anchors, at, empty }: AnchorTableProps) {
  const seen = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    const stamp = clock(at);
    if (stamp === null) return;
    for (const anchor of anchors) {
      if (anchor.found) seen.current.set(anchor.name, stamp);
    }
  }, [anchors, at]);

  const lastSeen = (anchor: Anchor): string => {
    if (anchor.found) return "now";
    return seen.current.get(anchor.name) ?? "never";
  };

  const columns: readonly Column<Anchor>[] = [
    { key: "name", label: "Anchor", mono: true, render: (row) => row.name },
    {
      key: "threshold",
      label: "Threshold",
      mono: true,
      width: "90px",
      render: (row) => row.threshold.toFixed(2),
    },
    {
      key: "score",
      label: "Score",
      mono: true,
      width: "80px",
      render: (row) => row.score.toFixed(2),
    },
    {
      key: "status",
      label: "Status",
      width: "90px",
      render: (row) => {
        const { label, tone } = status(row);
        return (
          <span data-tone={tone} className={`text-[12px] ${TONE_TEXT[tone]}`}>
            {label}
          </span>
        );
      },
    },
    {
      key: "seen",
      label: "Last seen",
      mono: true,
      width: "90px",
      render: (row) => lastSeen(row),
    },
  ];

  return <Table columns={columns} rows={anchors} rowKey={(row) => row.name} empty={empty} />;
}
