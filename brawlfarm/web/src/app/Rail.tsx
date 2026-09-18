/**
 * The left rail: wordmark, sections, instances.
 *
 * Under 820 px it becomes a top row of section links: the instance list hides and a fifth
 * link opens the same list as a sheet, so Stats and Settings still have a path to an
 * instance on a phone. NavLink is used rather than Link so the current page gets
 * aria-current="page" without the component tracking the route itself.
 */
import { useState } from "react";
import { NavLink } from "react-router";

import type { InstancePayload } from "../api/types";
import { useInstances } from "../api/useInstances";
import { Drawer } from "../components/ui/Drawer";
import { StateChip } from "../components/ui/StateChip";
import { NO_INSTANCES_YET } from "../lib/copy";

const SECTIONS: { to: string; label: string; soon: boolean }[] = [
  { to: "/", label: "Fleet", soon: false },
  { to: "/stats", label: "Stats", soon: false },
  { to: "/calibration", label: "Calibration", soon: false },
  { to: "/settings", label: "Settings", soon: false },
];

/** The one focus ring, restated on the control so it survives an ancestor that sets
 * outline-none. theme.css carries the same rule as the fallback. */
const FOCUS_RING =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

function linkClass(isActive: boolean): string {
  return `flex items-center gap-2 rounded-[6px] border-l-2 px-2 py-1.5 text-[13px] transition-colors duration-[120ms] ${FOCUS_RING} ${
    isActive ? "border-accent bg-panel-2 text-text" : "border-transparent text-muted hover:text-text"
  }`;
}

/** One instance row, rendered by the desktop list and by the sheet, so the two can never
 * disagree. onNavigate lets the sheet close itself when a row is chosen. */
function InstanceLink({ inst, onNavigate }: { inst: InstancePayload; onNavigate?: () => void }) {
  return (
    <NavLink
      to={`/instances/${inst.name}`}
      className={({ isActive }) => linkClass(isActive)}
      onClick={onNavigate}
    >
      <span className="t-name min-w-0 truncate text-[13px]">{inst.name}</span>
      <StateChip state={inst.state} />
    </NavLink>
  );
}

export function Rail() {
  const { data: instances } = useInstances();
  const [sheetOpen, setSheetOpen] = useState(false);

  return (
    <>
      <nav
        aria-label="Sections"
        className="border-b border-line bg-panel min-[820px]:border-b-0 min-[820px]:border-r"
      >
        <div className="flex h-[52px] items-center gap-2 px-4">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-[2px] bg-accent" />
          <span className="text-[15px] font-semibold tracking-tight">brawlfarm</span>
        </div>

        <ul className="flex gap-1 px-2 pb-2 min-[820px]:block min-[820px]:space-y-0.5">
          {SECTIONS.map((section) => (
            <li key={section.to}>
              <NavLink
                to={section.to}
                end={section.to === "/"}
                className={({ isActive }) => linkClass(isActive)}
              >
                <span className="flex-1">{section.label}</span>
                {section.soon && <> <span className="text-[11px] text-muted">soon</span></>}
              </NavLink>
            </li>
          ))}
          <li className="min-[820px]:hidden">
            <button
              type="button"
              onClick={() => setSheetOpen(true)}
              aria-haspopup="dialog"
              aria-expanded={sheetOpen}
              className={linkClass(false)}
            >
              <span className="flex-1">Instances</span>
            </button>
          </li>
        </ul>

        <div className="hidden min-[820px]:block">
          <p className="px-3 pb-1 pt-3 text-[11px] uppercase tracking-wide text-muted">Instances</p>
          <ul className="space-y-0.5 px-2 pb-2">
            {(instances ?? []).map((inst) => (
              <li key={inst.name}>
                <InstanceLink inst={inst} />
              </li>
            ))}
          </ul>
        </div>
      </nav>

      <Drawer open={sheetOpen} onClose={() => setSheetOpen(false)} title="Instances">
        {(instances ?? []).length === 0 ? (
          <p className="px-3 py-2 text-[13px] text-muted">{NO_INSTANCES_YET}</p>
        ) : (
          <ul className="space-y-0.5 p-2">
            {(instances ?? []).map((inst) => (
              <li key={inst.name}>
                <InstanceLink inst={inst} onNavigate={() => setSheetOpen(false)} />
              </li>
            ))}
          </ul>
        )}
      </Drawer>
    </>
  );
}
