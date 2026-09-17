/**
 * Step 3: every instance at 1600 x 900, pixel density 240.
 *
 * This is the one step that saves nothing. The controller asserts the size at startup and
 * exits otherwise, so the wizard's job here is to let someone find out now, with the
 * sentence that says where to change it, rather than later from a worker that quit.
 *
 * The fix sentence is the API's `hint`, rendered verbatim. It comes from
 * brawlfarm/setup/checks.py's DISPLAY_HINT, which is the one place that sentence is
 * written: a second copy here would drift the first time BlueStacks renames a menu.
 *
 * Each card checks itself and rechecks itself, and reports up only the one bit the step
 * needs, which is whether Continue may open.
 */
import { useCallback, useEffect, useState } from "react";

import { type StepProps } from "./useSetupState";
import { checkDisplay } from "../api/setup";
import type { DisplayCheckResponse } from "../api/types";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { ErrorBlock } from "../components/ui/ErrorBlock";

function DisplayCard({
  name,
  port,
  onResult,
}: {
  name: string;
  port: number;
  onResult: (name: string, ok: boolean) => void;
}) {
  const [checking, setChecking] = useState(true);
  const [result, setResult] = useState<DisplayCheckResponse | null>(null);
  const [failure, setFailure] = useState<unknown>(null);

  const run = useCallback(() => {
    setChecking(true);
    setFailure(null);
    void checkDisplay(port).then(
      (answer) => {
        setChecking(false);
        setResult(answer);
        onResult(name, answer.ok);
      },
      (error: unknown) => {
        setChecking(false);
        setResult(null);
        setFailure(error);
        onResult(name, false);
      },
    );
  }, [name, port, onResult]);

  useEffect(() => {
    run();
  }, [run]);

  const measured =
    result === null || result.width === null || result.height === null || result.dpi === null
      ? (result?.detail ?? "")
      : `${result.width} x ${result.height}, pixel density ${result.dpi}`;

  return (
    <article className="rounded-[10px] border border-line bg-panel p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[13px]">{name}</span>
        {checking ? (
          <Chip tone="idle">Checking…</Chip>
        ) : (
          <Chip tone={result?.ok === true ? "ok" : "bad"}>
            {result?.ok === true ? "Correct" : "Wrong size"}
          </Chip>
        )}
      </div>
      {failure !== null && (
        <div className="mt-2">
          <ErrorBlock error={failure} />
        </div>
      )}
      {!checking && measured !== "" && (
        <p className="mt-1 font-mono text-[12px] tabular-nums text-muted">{measured}</p>
      )}
      {!checking && result !== null && !result.ok && (
        <p className="mt-1 text-[12px] text-muted">{result.hint}</p>
      )}
      <div className="mt-2">
        <Button variant="quiet" size="sm" disabled={checking} onClick={run}>
          Recheck
        </Button>
      </div>
    </article>
  );
}

export function StepDisplay({ setup }: StepProps) {
  const { back, next, settingsPatch } = setup;
  const instances = settingsPatch.settings?.instances ?? [];
  const [ok, setOk] = useState<Record<string, boolean>>({});

  const report = useCallback((name: string, good: boolean) => {
    setOk((all) => ({ ...all, [name]: good }));
  }, []);

  const allOk = instances.length > 0 && instances.every((one) => ok[one.name] === true);

  return (
    <div>
      <h1 className="text-[18px] font-semibold">Display</h1>
      <p className="mt-1 text-[13px] text-muted">
        The farm reads the screen, so every instance has to be the same size.
      </p>

      <div className="mt-4 space-y-2">
        {instances.map((one) => (
          <DisplayCard key={one.name} name={one.name} port={one.adb_port} onResult={report} />
        ))}
      </div>

      <div className="mt-5 flex items-center gap-2">
        <Button variant="quiet" onClick={back}>
          Back
        </Button>
        <Button
          variant="primary"
          disabled={!allOk}
          disabledReason="Fix the display first"
          onClick={next}
        >
          Continue
        </Button>
      </div>
    </div>
  );
}
