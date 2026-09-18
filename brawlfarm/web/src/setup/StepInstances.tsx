/**
 * Step 2: which instances brawlfarm farms.
 *
 * The table is the scan's rows plus any port typed in by hand, because BlueStacks does not
 * always list an instance in bluestacks.conf and a port that answers is worth farming
 * whatever the file says. A hand-added row is named after its port: the name becomes a
 * folder name under the data home, and the port is the only thing actually known about it.
 *
 * The scan runs when the step appears only if step 1 did not already hand one over, so
 * walking forward from step 1 does not pay for a second round trip to adb.
 *
 * Testing a row is a real probe, per row, never per keystroke, and its answer replaces only
 * that row's status. The sentence under a failed probe names the row's own port, which is
 * what makes it actionable: "No answer on 5585" is a thing to go and look at.
 */
import { useCallback, useEffect, useState } from "react";

import { type StepProps, saveStep } from "./useSetupState";
import { scanSetup, testPort } from "../api/setup";
import type { ScanInstance } from "../api/types";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";
import { type Column, Table } from "../components/ui/Table";
import type { Tone } from "../lib/states";

type Status = "untested" | "testing" | "answers" | "no-answer";

const STATUS_LABEL: Record<Status, string> = {
  untested: "Not tested",
  testing: "Testing",
  answers: "Reachable",
  "no-answer": "No answer",
};

const STATUS_TONE: Record<Status, Tone> = {
  untested: "idle",
  testing: "idle",
  answers: "ok",
  "no-answer": "bad",
};

/** The status a row starts at. The scan asked adb which serials answer, so a row it
 * called online has already been probed once and says so. */
function seed(found: readonly ScanInstance[]): Record<string, Status> {
  return Object.fromEntries(
    found.map((row): [string, Status] => [row.name, row.online ? "answers" : "untested"]),
  );
}

export function StepInstances({ setup }: StepProps) {
  const { scan, setScan, back, next, settingsPatch } = setup;
  const { patch } = settingsPatch;
  const [rows, setRows] = useState<ScanInstance[]>(scan?.instances ?? []);
  const [picked, setPicked] = useState<string[]>([]);
  const [status, setStatus] = useState<Record<string, Status>>(() => seed(scan?.instances ?? []));
  const [scanning, setScanning] = useState(false);
  const [adding, setAdding] = useState(false);
  const [port, setPort] = useState("");
  const [failure, setFailure] = useState<unknown>(null);

  const load = useCallback((found: ScanInstance[]) => {
    setRows(found);
    setStatus(seed(found));
    setPicked((kept) => kept.filter((name) => found.some((row) => row.name === name)));
  }, []);

  const run = useCallback(() => {
    setScanning(true);
    setFailure(null);
    void scanSetup().then(
      (found) => {
        setScanning(false);
        setScan(found);
        load(found.instances);
      },
      (error: unknown) => {
        setScanning(false);
        setFailure(error);
      },
    );
  }, [load, setScan]);

  // Once, on mount. Step 1 already scanned on the way here, so only a cold landing on
  // step 2 pays for one; and run() sets `scan`, so anything that watched it would loop.
  useEffect(() => {
    if (scan === null) run();
  }, []);

  const probe = (row: ScanInstance) => {
    if (row.adb_port === null) return;
    const adbPort = row.adb_port;
    setStatus((all) => ({ ...all, [row.name]: "testing" }));
    void testPort(adbPort).then(
      (answer) => {
        setStatus((all) => ({ ...all, [row.name]: answer.ok ? "answers" : "no-answer" }));
      },
      (error: unknown) => {
        setStatus((all) => ({ ...all, [row.name]: "no-answer" }));
        setFailure(error);
      },
    );
  };

  const addPort = () => {
    const value = Number(port);
    if (!Number.isInteger(value) || value < 1 || value > 65535) return;
    const name = String(value);
    if (rows.some((row) => row.name === name)) return;
    setRows((all) => [
      ...all,
      {
        name,
        display_name: "",
        adb_port: value,
        width: null,
        height: null,
        dpi: null,
        online: false,
      },
    ]);
    setStatus((all) => ({ ...all, [name]: "untested" }));
    setPort("");
    setAdding(false);
  };

  const toggle = (name: string) => {
    setPicked((all) => (all.includes(name) ? all.filter((one) => one !== name) : [...all, name]));
  };

  const forward = () => {
    const chosen = rows.filter(
      (row): row is ScanInstance & { adb_port: number } =>
        picked.includes(row.name) && row.adb_port !== null,
    );
    saveStep(
      patch,
      (draft) => {
        draft.instances = chosen.map((row) => ({
          name: row.name,
          adb_port: row.adb_port,
          player_tag: "",
        }));
      },
      setFailure,
    );
    next();
  };

  const columns: readonly Column<ScanInstance>[] = [
    {
      key: "select",
      label: "",
      width: "36px",
      render: (row) => (
        <input
          type="checkbox"
          aria-label={row.name}
          checked={picked.includes(row.name)}
          disabled={row.adb_port === null}
          onChange={() => toggle(row.name)}
          className="h-3.5 w-3.5 accent-[var(--accent)]"
        />
      ),
    },
    { key: "name", label: "Name", mono: true, render: (row) => row.name },
    {
      key: "display",
      label: "Display name",
      // A BlueStacks display name is whatever the owner typed and can be their own name, so
      // the cell carries data-private and the screenshot pass blurs it.
      render: (row) => <span data-private>{row.display_name}</span>,
    },
    {
      key: "port",
      label: "ADB port",
      mono: true,
      width: "100px",
      render: (row) => (row.adb_port === null ? "" : String(row.adb_port)),
    },
    {
      key: "status",
      label: "Status",
      render: (row) => {
        const state = status[row.name] ?? "untested";
        return (
          <div className="space-y-1">
            <Chip tone={STATUS_TONE[state]}>{STATUS_LABEL[state]}</Chip>
            {state === "no-answer" && row.adb_port !== null && (
              <p className="text-[12px] text-muted">
                {`No answer on ${row.adb_port}. Is the instance running?`}
              </p>
            )}
          </div>
        );
      },
    },
    {
      key: "test",
      label: "",
      width: "72px",
      render: (row) => (
        <Button
          variant="quiet"
          size="sm"
          disabled={row.adb_port === null || status[row.name] === "testing"}
          disabledReason="This instance has no ADB port"
          onClick={() => probe(row)}
        >
          Test
        </Button>
      ),
    },
  ];

  return (
    <div>
      <h1 className="text-[18px] font-semibold">Instances</h1>
      <p className="mt-1 text-[13px] text-muted">
        Pick the BlueStacks instances brawlfarm should farm.
      </p>

      <div className="mt-4 space-y-3">
        {failure !== null && <ErrorBlock error={failure} />}
        <Table
          columns={columns}
          rows={rows}
          rowKey={(row) => row.name}
          empty="No instances found. Start a BlueStacks instance, enable ADB, then Scan again."
        />

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" disabled={scanning} onClick={run}>
            Scan again
          </Button>
          <Button variant="quiet" size="sm" onClick={() => setAdding((on) => !on)}>
            Add a port
          </Button>
        </div>

        {adding && (
          <div className="flex flex-wrap items-end gap-2">
            <Field
              label="ADB port"
              id="setup-add-port"
              value={port}
              onChange={setPort}
              type="number"
              min={1}
            />
            <Button variant="secondary" onClick={addPort}>
              Add
            </Button>
          </div>
        )}

        <p className="text-[12px] text-muted">
          Enable ADB in BlueStacks: Settings, Advanced, Android Debug Bridge.
        </p>
      </div>

      <div className="mt-5 flex items-center gap-2">
        <Button variant="secondary" onClick={back}>
          Back
        </Button>
        <Button
          variant="primary"
          disabled={picked.length === 0}
          disabledReason="Select at least one instance"
          onClick={forward}
        >
          Continue
        </Button>
      </div>
    </div>
  );
}
