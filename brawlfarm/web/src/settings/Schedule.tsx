/**
 * Settings > Schedule: the default for new instances.
 *
 * One switch. Per-instance schedules live on the Instance page, where the timeline is: this
 * is only what a freshly added instance starts out with.
 */
import { useState } from "react";

import { SettingRow } from "./SettingRow";
import { type SettingsPatch, fieldError, saveSetting } from "./useSettingsPatch";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Switch } from "../components/ui/Switch";

export function Schedule({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const [failure, setFailure] = useState<unknown>(null);

  if (settings === undefined) return null;

  return (
    <div>
      {failure !== null && <ErrorBlock error={failure} />}
      <SettingRow
        title="Schedule on by default"
        description="New instances follow the anti-ban schedule unless you turn it off per instance."
        error={fieldError(fieldErrors, "scheduler.default_enabled")}
      >
        <Switch
          checked={settings.scheduler.default_enabled}
          onChange={(next) =>
            saveSetting(
              patch,
              (document) => {
                document.scheduler.default_enabled = next;
              },
              setFailure,
            )
          }
          label="Schedule on by default"
        />
      </SettingRow>
    </div>
  );
}
