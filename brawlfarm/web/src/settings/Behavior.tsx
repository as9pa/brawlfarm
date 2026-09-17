/**
 * Settings > Behavior: how a worker plays.
 *
 * Thirteen switches over two sections of the settings document, six of them plain and seven
 * behind Advanced, which starts collapsed because they are performance and safety switches
 * that are on for a reason.
 *
 * Each row is built by one of the two helpers below rather than by a literal table, so the
 * key is checked against the settings type at compile time and the dotted loc the API sends
 * a 422 under is derived from it instead of typed out twice.
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
  behavior("winrate_aware", "Win-rate aware", "Prefer brawlers that win more in the current step."),
  behavior("opportunity_cost", "Opportunity cost", "Skip brawlers whose next tier is far off."),
  behavior("gas_aware", "Gas aware", "Move away from the gas earlier."),
  behavior("bush_hide", "Bush hide", "Hide in bushes when the map allows."),
  behavior("close_game_on_stop", "Close game on stop", "Close Brawl Stars when the instance stops."),
  behavior("dnd_at_start", "DND at start", "Turn on Do Not Disturb when the instance starts."),
];

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
      <div>{rows(BASIC)}</div>

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
