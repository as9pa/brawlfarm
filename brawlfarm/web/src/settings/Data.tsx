/**
 * Settings > Data: files on this machine.
 *
 * The home folder is a real path with a user name in it, so it appears in exactly one place:
 * the title of the open-folder button. Not in a heading, not in a caption, not in an error.
 * A screenshot of this page is therefore safe to paste into an issue.
 *
 * Both destructive acts go through a typed-name ConfirmDialog: the instance's own name for
 * its folder, the word "reset" for the settings. Deleting a folder does not delete the
 * instance, and a reset keeps every instance and every folder: only the other sections go
 * back to their defaults.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { type SettingsPatch } from "./useSettingsPatch";
import { getHealth } from "../api/health";
import { deleteInstanceData } from "../api/instances";
import { queryKeys } from "../api/queries";
import { openDataFolder, resetSettings } from "../api/settings";
import { Button } from "../components/ui/Button";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { failureMessage, toast } from "../lib/toast";

const RESET_SENTENCE =
  "Your instances and their data folders stay. Every other setting goes back to its default.";

export function Data({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings } = settingsPatch;
  const client = useQueryClient();
  const { data: health } = useQuery({ queryKey: queryKeys.health(), queryFn: getHealth });
  const [deleting, setDeleting] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  /** Keyed by instance name: a refusal belongs beside the row it refused. */
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});

  if (settings === undefined) return null;

  const openFolder = () => {
    void openDataFolder().catch((error: unknown) => {
      toast(failureMessage(error));
    });
  };

  const deleteData = (name: string) => {
    setRowErrors((errors) =>
      Object.fromEntries(Object.entries(errors).filter(([key]) => key !== name)),
    );
    void deleteInstanceData(name).then(
      () => {
        setDeleting(null);
        void client.invalidateQueries({ queryKey: queryKeys.instances() });
      },
      (error: unknown) => {
        setDeleting(null);
        setRowErrors((errors) => ({ ...errors, [name]: failureMessage(error) }));
      },
    );
  };

  const reset = () => {
    void resetSettings().then(
      (next) => {
        setResetting(false);
        client.setQueryData(queryKeys.settings(), next);
        void client.invalidateQueries({ queryKey: queryKeys.instances() });
        toast("Settings reset");
      },
      (error: unknown) => {
        setResetting(false);
        toast(failureMessage(error));
      },
    );
  };

  return (
    <div className="space-y-5">
      <div>
        {/* The title is on a wrapper rather than on Button, so Button's props stay exactly
            as phase 4 left them. data-private is what the screenshot pass blurs. */}
        <span title={health?.home} data-private>
          <Button variant="secondary" onClick={openFolder}>
            Open data folder
          </Button>
        </span>
      </div>

      <div>
        <h3 className="text-[13px] font-semibold">Delete one instance’s data</h3>
        <ul className="mt-2">
          {settings.instances.map((instance) => (
            <li
              key={instance.name}
              className="flex flex-wrap items-center gap-3 border-b border-line py-2 last:border-b-0"
            >
              <span className="font-mono text-[13px]">{instance.name}</span>
              <span className="text-[12px] text-muted">{`instances/${instance.name}`}</span>
              <span className="ml-auto">
                <Button variant="quiet" size="sm" onClick={() => setDeleting(instance.name)}>
                  Delete data
                </Button>
              </span>
              {rowErrors[instance.name] !== undefined && (
                <p className="w-full text-[12px] text-bad">{rowErrors[instance.name]}</p>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-[10px] border border-bad bg-panel p-3">
        <h3 className="text-[13px] font-semibold">Reset all settings</h3>
        <p className="mt-0.5 text-[12px] text-muted">{RESET_SENTENCE}</p>
        <div className="mt-2">
          <Button variant="secondary" onClick={() => setResetting(true)}>
            Reset
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title={`Delete ${deleting ?? ""}'s data?`}
        body={`Its folder instances/${deleting ?? ""} and everything in it goes: status, farm plan, schedule, games.csv and past sessions. The instance stays in your fleet.`}
        word={deleting ?? ""}
        confirmLabel="Delete data"
        tone="bad"
        onConfirm={() => {
          if (deleting !== null) deleteData(deleting);
        }}
      />

      <ConfirmDialog
        open={resetting}
        onClose={() => setResetting(false)}
        title="Reset all settings?"
        body={RESET_SENTENCE}
        word="reset"
        confirmLabel="Reset"
        tone="bad"
        onConfirm={reset}
      />
    </div>
  );
}
