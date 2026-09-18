/**
 * The settings screen's frame.
 *
 * One route, /settings/:section: the second-level nav, then the section's title, its one
 * plain sentence with the caption saying when that section last saved beside it, anything the
 * 422 mapper could not place under a field, and the section itself. A section id that is not
 * in the table is an ErrorBlock rather than a redirect, because a mistyped URL that quietly
 * moves you somewhere else is how you end up changing the wrong setting.
 *
 * useSettingsPatch is called once here and handed down, so the caption, the field errors and
 * the write queue are the same ones the section on screen is using.
 */
import type { ReactElement } from "react";
import { useParams } from "react-router";

import { About } from "./About";
import { Behavior } from "./Behavior";
import { Connection } from "./Connection";
import { Data } from "./Data";
import { Instances } from "./Instances";
import { Notifications } from "./Notifications";
import { SETTINGS_SECTIONS, type SectionId, SettingsNav } from "./SettingsNav";
import { type SettingsPatch, useSettingsPatch } from "./useSettingsPatch";
import { ErrorBlock } from "../components/ui/ErrorBlock";

/** Every section takes the same one prop, so the table below can hold all six. Null is
 * in the return type because a section whose rows all read the settings document renders
 * nothing until the first GET lands, rather than a half-built row of empty controls. */
type SectionView = (props: { settingsPatch: SettingsPatch }) => ReactElement | null;

/** Total, not Partial: every id in SETTINGS_SECTIONS has a view, and the compiler is what
 * says so. Adding a section to the nav without writing it now fails typecheck. */
const SECTION_VIEWS: Record<SectionId, SectionView> = {
  instances: Instances,
  connection: Connection,
  behavior: Behavior,
  notifications: Notifications,
  data: Data,
  about: About,
};

const UNKNOWN_SECTION = new Error("unknown settings section");

export function Settings() {
  const { section } = useParams();
  const settingsPatch = useSettingsPatch();
  const known = SETTINGS_SECTIONS.find((entry) => entry.id === section);
  const View = known === undefined ? undefined : SECTION_VIEWS[known.id];

  return (
    <section className="flex flex-col gap-4 min-[820px]:flex-row">
      <SettingsNav />
      <div className="min-w-0 flex-1">
        {known === undefined ? (
          <ErrorBlock error={UNKNOWN_SECTION} />
        ) : (
          <>
            <header>
              <h1 className="text-[20px] font-semibold tracking-tight">{known.label}</h1>
            </header>
            <div className="mt-1 flex flex-wrap items-baseline gap-2">
              <p className="text-[13px] text-muted">{known.description}</p>
              {/* The caption names its section, because one bare time on a screen of six
               * sections does not say which of them wrote. The live region stays mounted
               * empty, so the first save after the section opens is announced rather than
               * missed as a region that only just appeared. */}
              <span aria-live="polite" className="text-[12px] text-muted">
                {settingsPatch.savedAt === null
                  ? null
                  : `${known.label} saved ${settingsPatch.savedAt}`}
              </span>
            </div>
            {settingsPatch.sectionErrors.map((line) => (
              <p key={line} className="mt-1 text-[12px] text-bad">
                {line}
              </p>
            ))}
            <div className="mt-4">
              {View === undefined ? null : <View settingsPatch={settingsPatch} />}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
