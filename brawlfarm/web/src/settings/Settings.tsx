/**
 * The settings screen's frame.
 *
 * One route, /settings/:section: the second-level nav, then the section's title, the caption
 * saying when it last saved, its one plain sentence, anything the 422 mapper could not place
 * under a field, and the section itself. A section id that is not in the table is an
 * ErrorBlock rather than a redirect, because a mistyped URL that quietly moves you somewhere
 * else is how you end up changing the wrong setting.
 *
 * useSettingsPatch is called once here and handed down, so the caption, the field errors and
 * the write queue are the same ones the section on screen is using.
 */
import type { ReactElement } from "react";
import { useParams } from "react-router";

import { About } from "./About";
import { Behavior } from "./Behavior";
import { Connection } from "./Connection";
import { Instances } from "./Instances";
import { Schedule } from "./Schedule";
import { SETTINGS_SECTIONS, type SectionId, SettingsNav } from "./SettingsNav";
import { type SettingsPatch, useSettingsPatch } from "./useSettingsPatch";
import { ErrorBlock } from "../components/ui/ErrorBlock";

/** Every section takes the same one prop, so the table below can hold all seven. Null is
 * in the return type because a section whose rows all read the settings document renders
 * nothing until the first GET lands, rather than a half-built row of empty controls. */
type SectionView = (props: { settingsPatch: SettingsPatch }) => ReactElement | null;

/** Partial while this branch is being built: task 7 fills Notifications and Data in and
 * makes this a total Record, so the compiler proves none is missing. */
const SECTION_VIEWS: Partial<Record<SectionId, SectionView>> = {
  instances: Instances,
  connection: Connection,
  behavior: Behavior,
  schedule: Schedule,
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
            {/* An h2: the top bar already carries this page's h1, and it says Settings for
                every one of the seven. */}
            <header className="flex items-baseline gap-2">
              <h2 className="text-[20px] font-semibold tracking-tight">{known.label}</h2>
              {settingsPatch.savedAt !== null && (
                <span className="text-[11px] text-muted">{`Saved ${settingsPatch.savedAt}`}</span>
              )}
            </header>
            <p className="mt-1 text-[13px] text-muted">{known.description}</p>
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
