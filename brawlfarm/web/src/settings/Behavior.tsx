/**
 * Settings > Behavior: how a worker plays.
 *
 * Thirteen switches over two sections of the settings document, six of them plain and seven
 * behind Advanced, which starts collapsed because they are performance and safety switches
 * that are on for a reason. The schedule new instances start with sits under the plain six,
 * because a schedule is a default you set once and then forget about.
 *
 * Each row is built by one of the two helpers below rather than by a literal table, so the
 * key is checked against the settings type at compile time and the dotted loc the API sends
 * a 422 under is derived from it instead of typed out twice. The schedule row is written out
 * instead, because it writes scheduler.default_enabled rather than a behavior key.
 */
import { useState } from "react";

import { SettingRow } from "./SettingRow";
import { type SettingsPatch, fieldError, saveSetting } from "./useSettingsPatch";
import type { AppSettings } from "../api/types";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Switch } from "../components/ui/Switch";

interface Toggle {
  /** The API's dotted loc, which is also the key a 422 for this row arrives under. */
  loc: string;
  title: string;
  description: string;
  read: (settings: AppSettings) => boolean;
  write: (settings: AppSettings, next: boolean) => void;
}

function behavior<K extends keyof AppSettings["behavior"]>(
  key: K,
  title: string,
  description: string,
): Toggle {
  return {
    loc: `behavior.${key}`,
    title,
    description,
    read: (settings) => settings.behavior[key],
    write: (settings, next) => {
      settings.behavior[key] = next;
    },
  };
}

function advanced<K extends keyof AppSettings["advanced"]>(
  key: K,
  title: string,
  description: string,
): Toggle {
  return {
    loc: `advanced.${key}`,
    title,
    description,
    read: (settings) => settings.advanced[key],
    write: (settings, next) => {
      settings.advanced[key] = next;
    },
  };
}

const BASIC: readonly Toggle[] = [
  behavior(
    "winrate_aware",
    "Prefer brawlers that win",
    "Picks the brawler with the best win rate in the current step.",
  ),
  behavior(
    "opportunity_cost",
    "Skip far-off tiers",
    "Skips brawlers whose next tier is more than a session away.",
  ),
  behavior("gas_aware", "Leave the gas early", "Moves away from the gas one ring sooner."),
  behavior("bush_hide", "Hide in bushes", "Hides in bushes when the map allows."),
  behavior(
    "close_game_on_stop",
    "Close the game on stop",
    "Closes Brawl Stars when the instance stops.",
  ),
  behavior(
    "dnd_at_start",
    "Do Not Disturb on start",
    "Turns on Do Not Disturb when the instance starts.",
  ),
];

/** What the schedule row promises, taken from brawlfarm/core/scheduler.py: the session and
 * break ranges it draws from, the longer outing, the start window and the daily total. */
const SCHEDULE_DESCRIPTION =
  "Sessions run 30 minutes to 2 hours, sometimes up to 2 and a half, with breaks of 45 " +
  "minutes to 2 hours between them and one or two longer outings of 2 to 4 hours. Play " +
  "starts within 2 hours of midnight and adds up to about 9 hours a day. Change the hours " +
  "for one instance on its own page.";

const ADVANCED: readonly Toggle[] = [
  advanced("fast_input", "Fast input", "Send taps through the faster adb path."),
  advanced("raw_cap", "Raw capture", "Read frames without re-encoding them."),
  advanced("gray_match", "Gray matching", "Match templates in grayscale."),
  advanced("phase_classify", "Phase classify", "Work out the match phase from the screen."),
  advanced("ability_buttons", "Ability buttons", "Use the gadget and super buttons."),
  advanced(
    "recalib_tripwire",
    "Recalibration tripwire",
    "Warn when a detector looks season-blind.",
  ),
  advanced(
    "dnd_off_on_stop",
    "DND off on stop",
    "Turn Do Not Disturb back off when the instance stops.",
  ),
];

export function Behavior({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [failure, setFailure] = useState<unknown>(null);

  if (settings === undefined) return null;

  const rows = (list: readonly Toggle[]) =>
    list.map((row) => (
      <SettingRow
        key={row.loc}
        title={row.title}
        description={row.description}
        error={fieldError(fieldErrors, row.loc)}
      >
        <Switch
          checked={row.read(settings)}
          onChange={(next) =>
            saveSetting(patch, (document) => row.write(document, next), setFailure)
          }
          label={row.title}
        />
      </SettingRow>
    ));

  return (
    <div>
      {failure !== null && <ErrorBlock error={failure} />}
      <div>
        {rows(BASIC)}
        <SettingRow
          title="Schedule"
          description={SCHEDULE_DESCRIPTION}
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

      <div className="mt-4">
        <div className="flex items-center gap-2">
          <h3 className="text-[13px] font-semibold">Advanced</h3>
          <Button variant="quiet" size="sm" onClick={() => setShowAdvanced((on) => !on)}>
            {showAdvanced ? "Hide" : "Show"}
          </Button>
        </div>
        {showAdvanced && <div className="mt-2">{rows(ADVANCED)}</div>}
      </div>

      <p className="mt-4 text-[12px] text-muted">Applies the next time an instance starts.</p>
    </div>
  );
}
