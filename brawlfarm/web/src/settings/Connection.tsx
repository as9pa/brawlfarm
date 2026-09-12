/**
 * Settings > Connection: how brawlfarm reaches BlueStacks and the Brawl Stars API.
 *
 * The adb path carries a chip from one scan run when the section mounts. One, not one per
 * keystroke: the scan shells out to adb and can take seconds, and a cached one would lie
 * about what is installed right now. A scan that failed outright leaves the chip off rather
 * than guessing, because "Not found" would be a claim about adb that the panel cannot make
 * when it could not reach its own server.
 *
 * Both fields save 500 ms after the last keystroke and at once on blur. Neither has a Save
 * button, and neither ever logs what was typed: the token reaches the masked Field, the PUT
 * body and nothing else.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router";

import { SettingRow } from "./SettingRow";
import {
  type SettingsPatch,
  fieldError,
  saveSettingAsync,
  useDebouncedSave,
} from "./useSettingsPatch";
import { scanSetup } from "../api/setup";
import type { ScanResponse } from "../api/types";
import { Chip } from "../components/ui/Chip";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";

const TOKEN_LINE = "Create a key at developer.brawlstars.com and allow this machine's IP address.";

export function Connection({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [failure, setFailure] = useState<unknown>(null);

  useEffect(() => {
    let alive = true;
    void scanSetup()
      .then((found) => {
        if (alive) setScan(found);
      })
      .catch(() => {
        if (alive) setScan(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  const adbPath = useDebouncedSave(settings?.connection.adb_path ?? "", (value) =>
    saveSettingAsync(
      patch,
      (document) => {
        document.connection.adb_path = value;
      },
      setFailure,
    ),
  );
  const token = useDebouncedSave(settings?.connection.brawl_api_token ?? "", (value) =>
    saveSettingAsync(
      patch,
      (document) => {
        document.connection.brawl_api_token = value;
      },
      setFailure,
    ),
  );

  return (
    <div>
      {failure !== null && <ErrorBlock error={failure} />}

      <SettingRow
        title="ADB path"
        description="brawlfarm needs HD-Adb.exe from the BlueStacks folder."
        error={fieldError(fieldErrors, "connection.adb_path")}
      >
        <div className="space-y-2" onBlur={adbPath.onBlur}>
          <Field
            label="ADB path"
            id="connection-adb-path"
            value={adbPath.value}
            onChange={adbPath.onChange}
            width="full"
          />
          <div className="flex items-center gap-2">
            {scan !== null && (
              <Chip tone={scan.adb_found ? "ok" : "bad"}>
                {scan.adb_found ? "Found" : "Not found"}
              </Chip>
            )}
            <Link
              to="/setup"
              className="inline-flex h-8 items-center rounded-[6px] border border-line bg-panel-2 px-3 text-[13px] font-medium text-text transition-colors duration-[120ms] hover:border-accent"
            >
              Run setup again
            </Link>
          </div>
        </div>
      </SettingRow>

      <SettingRow
        title="Brawl Stars API token"
        description={TOKEN_LINE}
        error={fieldError(fieldErrors, "connection.brawl_api_token")}
      >
        <div onBlur={token.onBlur}>
          <Field
            label="Brawl Stars API token"
            id="connection-token"
            value={token.value}
            onChange={token.onChange}
            type="password"
            width="full"
          />
        </div>
      </SettingRow>

      <p className="mt-3 text-[12px] text-muted">Applies to a worker the next time it starts.</p>
    </div>
  );
}
