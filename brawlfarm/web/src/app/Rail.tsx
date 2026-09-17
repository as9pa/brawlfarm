/**
 * The left rail: wordmark, sections, instances.
 *
 * Under 820 px it becomes a top row of section links and the instance list hides -- on a
 * phone the fleet grid is the navigation. NavLink is used rather than Link so the current
 * page gets aria-current="page" without the component tracking the route itself.
 */
import { NavLink } from "react-router";

import { useInstances } from "../api/useInstances";
import { TONE_DOT, stateTone } from "../lib/states";

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

export function Rail() {
  const { data: instances } = useInstances();

  return (
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
      </ul>

      <div className="hidden min-[820px]:block">
        <p className="px-3 pb-1 pt-3 text-[11px] uppercase tracking-wide text-muted">Instances</p>
        <ul className="space-y-0.5 px-2 pb-2">
          {(instances ?? []).map((inst) => {
            const tone = stateTone(inst.state);
            return (
              <li key={inst.name}>
                <NavLink
                  to={`/instances/${inst.name}`}
                  className={({ isActive }) => linkClass(isActive)}
                >
                  <span
                    data-tone={tone}
                    aria-hidden="true"
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${TONE_DOT[tone]}`}
                  />
                  <span className="truncate font-mono text-[12px]">{inst.name}</span>
                </NavLink>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
