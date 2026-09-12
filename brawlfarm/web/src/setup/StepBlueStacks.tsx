/**
 * Step 1: find adb.
 *
 * The scan runs once when the step appears, and again only when it is asked to. It shells
 * out to adb and can take seconds, which is why the waiting state is a chip and a sentence
 * rather than a spinner: a sentence says what is being waited for.
 *
 * A scan that found adb writes the path it found, so the reader never has to press Save and
 * the next visit starts from what worked. The write is skipped when the path is already the
 * stored one, so a second Scan again does not raise a second toast about a file that has
 * not moved.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { type StepProps, saveStep } from "./useSetupState";
import { scanSetup } from "../api/setup";
import type { ScanResponse } from "../api/types";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";

const DEFAULT_ADB_PATH = "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe";

export function StepBlueStacks({ setup }: StepProps) {
  const { setScan, next, settingsPatch } = setup;
  const { patch, settings } = settingsPatch;
  const [scanning, setScanning] = useState(true);
  const [result, setResult] = useState<ScanResponse | null>(null);
  const [typed, setTyped] = useState("");
  const [failure, setFailure] = useState<unknown>(null);
  // Read inside the callback rather than closed over, so re-scanning does not need a new
  // callback every time the document changes.
  const stored = useRef("");
  stored.current = settings?.connection.adb_path ?? "";

  const run = useCallback(
    (adbPath: string | undefined) => {
      setScanning(true);
      setFailure(null);
      void scanSetup(adbPath).then(
        (found) => {
          setScanning(false);
          setResult(found);
          setScan(found);
          if (found.adb_found && found.adb_path !== null && found.adb_path !== stored.current) {
            const path = found.adb_path;
            saveStep(
              patch,
              (draft) => {
                draft.connection.adb_path = path;
              },
              setFailure,
            );
          }
        },
        (error: unknown) => {
          setScanning(false);
          setResult(null);
          setScan(null);
          setFailure(error);
        },
      );
    },
    [patch, setScan],
  );

  useEffect(() => {
    run(undefined);
  }, [run]);

  const foundPath = result !== null && result.adb_found ? result.adb_path : null;

  return (
    <div>
      <h1 className="text-[18px] font-semibold">BlueStacks</h1>
      <p className="mt-1 text-[13px] text-muted">brawlfarm talks to BlueStacks through adb.</p>

      <div className="mt-4 space-y-3">
        {failure !== null && <ErrorBlock error={failure} />}

        {scanning && (
          <div className="flex items-center gap-2">
            <Chip tone="idle">Scanning</Chip>
            <span className="text-[12px] text-muted">Asking adb for devices</span>
          </div>
        )}

        {!scanning && foundPath !== null && (
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone="ok">Found</Chip>
            <span className="font-mono text-[12px] text-text">{foundPath}</span>
          </div>
        )}

        {!scanning && foundPath === null && (
          <div className="space-y-2">
            <Field
              label="Where is BlueStacks installed"
              id="setup-adb-path"
              value={typed}
              onChange={setTyped}
              width="full"
              placeholder={DEFAULT_ADB_PATH}
            />
            <p className="text-[12px] text-muted">
              brawlfarm needs HD-Adb.exe from the BlueStacks folder.
            </p>
          </div>
        )}
      </div>

      <div className="mt-5 flex items-center gap-2">
        <Button variant="quiet" disabled={scanning} onClick={() => run(typed === "" ? undefined : typed)}>
          Scan again
        </Button>
        <Button
          variant="primary"
          disabled={foundPath === null || failure !== null}
          disabledReason="Find HD-Adb.exe first"
          onClick={next}
        >
          Continue
        </Button>
      </div>
    </div>
  );
}
