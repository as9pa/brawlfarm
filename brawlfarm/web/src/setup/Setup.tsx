/**
 * The wizard's page.
 *
 * Its own chrome, not the Shell's: someone on this page has no fleet, and a rail listing
 * nothing with a top bar titled nothing is worse than a plain page. The wordmark is the
 * same one the shell rail carries, pinned to the corner, so it is recognisably the same
 * program.
 *
 * The content is one 720 px column centred in the window, and the step rail hangs off its
 * left edge from 1000 px up rather than sitting in the row, so the column stays in the
 * middle of the screen instead of being pushed off it by the rail. Below 1000 px the rail
 * is a row of numbers above the column.
 *
 * STEP_VIEWS is Partial while the branch is being built. Task 10 fills the last of it in
 * and makes it a total Record, which is what then proves no step is missing.
 */
import type { ReactElement } from "react";

import { StepBlueStacks } from "./StepBlueStacks";
import { StepRail } from "./StepRail";
import { type StepId, type StepProps, useSetupState } from "./useSetupState";
import { useSettingsPatch } from "../settings/useSettingsPatch";

type StepView = (props: StepProps) => ReactElement;

const STEP_VIEWS: Partial<Record<StepId, StepView>> = {
  bluestacks: StepBlueStacks,
};

export function Setup() {
  const settingsPatch = useSettingsPatch();
  const setup = useSetupState(settingsPatch);
  const View = STEP_VIEWS[setup.step];

  return (
    <div className="min-h-screen bg-ground text-text">
      <div className="fixed left-4 top-4 flex items-center gap-2">
        <span aria-hidden="true" className="h-2.5 w-2.5 rounded-[2px] bg-accent" />
        <span className="text-[15px] font-semibold tracking-tight">brawlfarm</span>
      </div>

      <main className="relative mx-auto w-full max-w-[720px] px-4 pb-16 pt-16">
        <div className="mb-6 min-[1000px]:absolute min-[1000px]:right-full min-[1000px]:top-16 min-[1000px]:mb-0 min-[1000px]:mr-4 min-[1000px]:w-[120px]">
          <StepRail index={setup.index} done={setup.done} onGo={setup.go} />
        </div>
        <section>
          {settingsPatch.sectionErrors.map((line) => (
            <p key={line} className="mb-2 text-[12px] text-bad">
              {line}
            </p>
          ))}
          {setup.ready && View !== undefined && <View setup={setup} />}
        </section>
      </main>
    </div>
  );
}
