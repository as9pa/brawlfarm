/**
 * The second-level nav, and the table that names the seven sections.
 *
 * The table lives here rather than in Settings.tsx so the nav and the section heading read
 * the same labels and the same sentences from one place, and so the import only ever points
 * one way. NavLink rather than Link, so the section you are on gets aria-current="page"
 * without this component tracking the route itself.
 *
 * Under 820 px the column becomes a horizontal row that scrolls, which is the same move the
 * shell rail makes at the same width.
 */
import { NavLink } from "react-router";

export type SectionId =
  | "instances"
  | "connection"
  | "behavior"
  | "schedule"
  | "notifications"
  | "data"
  | "about";

export interface SettingsSection {
  id: SectionId;
  label: string;
  description: string;
}

export const SETTINGS_SECTIONS: readonly SettingsSection[] = [
  {
    id: "instances",
    label: "Instances",
    description: "Which BlueStacks instances brawlfarm farms.",
  },
  {
    id: "connection",
    label: "Connection",
    description: "How brawlfarm reaches BlueStacks and the Brawl Stars API.",
  },
  { id: "behavior", label: "Behavior", description: "How an instance plays." },
  { id: "schedule", label: "Schedule", description: "The default for new instances." },
  { id: "notifications", label: "Notifications", description: "Where alerts go." },
  { id: "data", label: "Data", description: "Files on this machine." },
  { id: "about", label: "About", description: "Theme, version and links." },
];

function linkClass(isActive: boolean): string {
  return `block rounded-[6px] border-l-2 px-2 py-1.5 text-[13px] whitespace-nowrap transition-colors duration-[120ms] ${
    isActive ? "border-accent bg-panel-2 text-text" : "border-transparent text-muted hover:text-text"
  }`;
}

export function SettingsNav() {
  return (
    <nav aria-label="Settings sections" className="shrink-0 min-[820px]:w-[200px]">
      <ul className="flex gap-1 overflow-x-auto min-[820px]:block min-[820px]:space-y-0.5">
        {SETTINGS_SECTIONS.map((section) => (
          <li key={section.id}>
            <NavLink to={`/settings/${section.id}`} className={({ isActive }) => linkClass(isActive)}>
              {section.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
