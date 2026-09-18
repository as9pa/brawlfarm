/**
 * Settings > Data: files on this machine.
 *
 * The home folder is a real path with a user name in it, and it is printed so it can be read
 * and copied: once as the open-folder button's title and once in a mono block beside Copy.
 * Both carry data-private, which is what the screenshot pass blurs, so a shot of this page is
 * still safe to paste into an issue. It appears nowhere else: not in a heading, not in a
 * caption, not in an error.
 *
 * Every irreversible act on the panel is here, in one Danger zone at the end: removing an
 * instance from the fleet, deleting one instance's data, and the reset. Each one is a
 * danger-variant Button behind a typed-name ConfirmDialog, and each refusal is shown on the
 * row it refused rather than in a toast that scrolls away. Each one that went through says so
 * in two words, because three buttons that all look the same need to be told apart afterwards.
 *
 * The three are not the same act. Removing an instance leaves its folder on disk, deleting a
 * folder leaves the instance in the fleet, and a reset keeps every instance and every
 * folder: only the other sections go back to their defaults.
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

/** One line of the Danger zone: what it does, what survives it, and the button. */
interface ZoneRow {
  key: string;
  title: string;
  note: string;
  action: string;
  onClick: () => void;
}

export function Data({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings, patch } = settingsPatch;
  const client = useQueryClient();
  const { data: health } = useQuery({ queryKey: queryKeys.health(), queryFn: getHealth });
  const [deleting, setDeleting] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  /** Keyed by zone row, not by instance: one instance has two rows here, and a refused
   * Remove must not print itself under Delete data. */
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});

  if (settings === undefined) return null;

  const copyPath = () => {
    void navigator.clipboard.writeText(health?.home ?? "").then(
      () => {
        toast("Path copied");
      },
      () => {
        toast("Could not copy the path. Select it and copy by hand.", { tone: "bad" });
      },
    );
  };

  const openFolder = () => {
    void openDataFolder().catch((error: unknown) => {
      toast(failureMessage(error));
    });
  };

  const removeKey = (name: string) => `remove:${name}`;
  const dataKey = (name: string) => `data:${name}`;

  const clearError = (key: string) => {
    setRowErrors((errors) =>
      Object.fromEntries(Object.entries(errors).filter(([at]) => at !== key)),
    );
  };

  const deleteData = (name: string) => {
    const key = dataKey(name);
    clearError(key);
    void deleteInstanceData(name).then(
      () => {
        setDeleting(null);
        void client.invalidateQueries({ queryKey: queryKeys.instances() });
        toast("Data deleted");
      },
      (error: unknown) => {
        setDeleting(null);
        setRowErrors((errors) => ({ ...errors, [key]: failureMessage(error) }));
      },
    );
  };

  /** The same save the Instances section uses, with this instance filtered out. */
  const removeInstance = (name: string) => {
    const key = removeKey(name);
    clearError(key);
    void patch((document) => {
      document.instances = document.instances.filter((inst) => inst.name !== name);
    }).then(
      () => {
        setRemoving(null);
        toast("Instance removed");
      },
      (error: unknown) => {
        // The dialog closes either way: a refusal belongs on the row, in front of the reader.
        setRemoving(null);
        setRowErrors((errors) => ({ ...errors, [key]: failureMessage(error) }));
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

  const zoneRows: ZoneRow[] = [
    ...settings.instances.flatMap((instance) => [
      {
        key: removeKey(instance.name),
        title: `Remove ${instance.name} from the fleet`,
        note: "Its data folder stays on disk.",
        action: "Remove",
        onClick: () => setRemoving(instance.name),
      },
      {
        key: dataKey(instance.name),
        title: `Delete the data for ${instance.name}`,
        note: "Status, farm plan, schedule, games and past sessions. The instance stays.",
        action: "Delete data",
        onClick: () => setDeleting(instance.name),
      },
    ]),
    {
      key: "reset",
      title: "Reset all settings",
      note: "Instances and their data folders stay.",
      action: "Reset",
      onClick: () => setResetting(true),
    },
  ];

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        {/* The title is on a wrapper rather than on Button, so Button's props stay exactly
            as phase 4 left them. data-private is what the screenshot pass blurs. */}
        <span title={health?.home} data-private>
          <Button variant="secondary" onClick={openFolder}>
            Open data folder
          </Button>
        </span>
        {health !== undefined && (
          <div className="flex flex-wrap items-center gap-2">
            <span data-private className="font-mono text-[12px] break-all text-muted">
              {health.home}
            </span>
            <Button variant="secondary" size="sm" onClick={copyPath}>
              Copy
            </Button>
          </div>
        )}
      </div>

      <div className="rounded-[10px] border border-bad p-3">
        <h3 className="text-[13px] font-semibold">Danger zone</h3>
        <p className="mt-0.5 text-[12px] text-muted">These cannot be undone.</p>
        <ul className="mt-2">
          {zoneRows.map((row) => (
            <li
              key={row.key}
              className="flex flex-wrap items-center gap-3 border-b border-line py-2 last:border-b-0"
            >
              <div className="min-w-0">
                <h4 className="text-[13px] font-medium">{row.title}</h4>
                <p className="text-[12px] text-muted">{row.note}</p>
              </div>
              <span className="ml-auto">
                <Button variant="danger" size="sm" onClick={row.onClick}>
                  {row.action}
                </Button>
              </span>
              {rowErrors[row.key] !== undefined && (
                <p className="w-full text-[12px] text-bad">{rowErrors[row.key]}</p>
              )}
            </li>
          ))}
        </ul>
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
        open={removing !== null}
        onClose={() => setRemoving(null)}
        title={`Remove ${removing ?? ""}?`}
        body="Its data folder stays on disk. Type the name to confirm."
        word={removing ?? ""}
        confirmLabel="Remove"
        tone="bad"
        onConfirm={() => {
          if (removing !== null) removeInstance(removing);
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
