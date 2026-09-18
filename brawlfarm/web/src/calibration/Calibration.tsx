/**
 * The Calibration screen: what the workers see, and what the file has changed about it.
 *
 * The page is a read. There is no field on it that writes a coordinate or a threshold,
 * and the only two requests it sends are the recorder switch and the button that opens
 * the folder in Explorer, neither of which carries a value from the page. Editing
 * happens in calibration.toml and the templates folder, never on this page.
 *
 * Instance selection is local state rather than the URL: unlike Stats, nothing here is
 * worth linking to, and the preselected running instance is almost always the one the
 * reader wants. A selection is only resolved once the instance list arrives, so the two
 * per-instance queries never fire against a name that is not configured.
 */
import { type ReactNode, useState } from "react";

import { AnchorTable } from "./AnchorTable";
import { FrameOverlay, type OverlayShow } from "./FrameOverlay";
import { SCREEN_OPTIONS, type ScreenFilter, screenStateLabel } from "./names";
import { ObserveCard } from "./ObserveCard";
import { OverridesTable } from "./OverridesTable";
import { RecorderCard } from "./RecorderCard";
import {
  LIVE_POLL_MS,
  isNoFrameYet,
  useCalibrationFile,
  useObserveToggle,
  useRecorder,
  useRecorderToggle,
  useScores,
} from "./useCalibration";
import { openCalibrationFolder } from "../api/calibration";
import type { InstanceState } from "../api/types";
import { useInstances } from "../api/useInstances";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Segmented } from "../components/ui/Segmented";
import { StateChip } from "../components/ui/StateChip";
import { CALIBRATION_INTRO } from "../lib/copy";
import { failureMessage, toast } from "../lib/toast";
import { phaseLabel } from "../lib/states";

/** An instance in one of these writes no new frame, so the page scores the last one once
 * and stops polling. Same three as the Instance page's Stop button. */
const NOT_RUNNING: ReadonlySet<InstanceState> = new Set<InstanceState>([
  "stopped",
  "scheduled_break",
  "offline",
]);

const SHOW_OPTIONS: readonly { value: OverlayShow; label: string }[] = [
  { value: "taps", label: "Where it taps" },
  { value: "anchors", label: "What it looks for" },
  { value: "both", label: "Both" },
];

export function noFrameYet(name: string): string {
  return `Start ${name} to see its screen. Matches appear once it sends the first picture.`;
}

function Skeleton() {
  return (
    <div data-testid="calibration-skeleton" className="flex flex-col gap-3">
      <div data-block="" className="aspect-video w-full rounded-[10px] bg-panel-2" />
      <div data-block="" className="h-[120px] rounded-[10px] bg-panel-2" />
    </div>
  );
}

export function Calibration() {
  const instancesQuery = useInstances();
  const instances = instancesQuery.data ?? [];
  const [picked, setPicked] = useState<string | null>(null);
  const [show, setShow] = useState<OverlayShow>("both");
  // The filter starts on every screen and stays where the reader put it. It deliberately
  // does not follow the detected screen: a filter that moved on its own would fight a
  // reader who had just chosen one.
  const [screen, setScreen] = useState<ScreenFilter>("all");
  // The one point named on the frame. The table beside it sets the same state, which
  // is what makes pointing at a row light up its box and the other way round.
  const [highlight, setHighlight] = useState<string | null>(null);

  // The first running instance is the one worth looking at; the first configured one is
  // the fallback so a wholly stopped fleet still has a frame to show.
  const preferred =
    instances.find((inst) => !NOT_RUNNING.has(inst.state))?.name ?? instances[0]?.name ?? null;
  const chosen = picked !== null && instances.some((inst) => inst.name === picked)
    ? picked
    : preferred;
  const instance = instances.find((inst) => inst.name === chosen);
  const running = instance !== undefined && !NOT_RUNNING.has(instance.state);

  const calibration = useCalibrationFile();
  const scores = useScores(chosen, running);
  const recorder = useRecorder(chosen, running);
  const toggle = useRecorderToggle(chosen);
  const observe = useObserveToggle(chosen);

  const openFolder = () => {
    openCalibrationFolder().catch((error: unknown) => {
      toast(failureMessage(error));
    });
  };

  const onToggle = (on: boolean) => {
    toggle.mutate(on, {
      onError: (error) => {
        toast(failureMessage(error));
      },
    });
  };

  const onObserve = (on: boolean) => {
    observe.mutate(on, {
      onError: (error) => {
        toast(failureMessage(error));
      },
    });
  };

  const header = (
    <>
      <h1 className="text-[28px] font-semibold tracking-tight">Calibration</h1>
      <p className="text-[13px] text-muted">{CALIBRATION_INTRO}</p>
    </>
  );

  // Without the instance list there is nothing to pick and no frame to ask for, so the
  // toolbar stays out of this one entirely.
  if (instancesQuery.isError) {
    return (
      <section className="flex flex-col gap-3">
        {header}
        <ErrorBlock error={instancesQuery.error} onRetry={() => void instancesQuery.refetch()} />
      </section>
    );
  }

  const toolbar = (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap gap-1">
        {instances.map((inst) => {
          const on = inst.name === chosen;
          return (
            <button
              key={inst.name}
              type="button"
              aria-pressed={on}
              onClick={() => setPicked(inst.name)}
              className={`h-6 rounded-[6px] border border-line px-2 font-mono text-[12px] transition-colors duration-[120ms] ${
                on ? "bg-panel-2 text-text" : "bg-panel text-muted hover:text-text"
              }`}
            >
              {inst.name}
            </button>
          );
        })}
      </div>

      <Segmented label="Show" value={show} options={SHOW_OPTIONS} onChange={setShow} />
      <Segmented label="Screen" value={screen} options={SCREEN_OPTIONS} onChange={setScreen} />

      {instance !== undefined && <StateChip state={instance.state} />}

      <div className="ml-auto">
        <Button variant="secondary" size="sm" onClick={openFolder}>
          Open calibration folder
        </Button>
      </div>
    </div>
  );

  const frame = (): ReactNode => {
    if (chosen === null) {
      return <p className="text-[13px] text-muted">No instances configured yet.</p>;
    }
    if (scores.isError && !isNoFrameYet(scores.error)) {
      return <ErrorBlock error={scores.error} onRetry={() => void scores.refetch()} />;
    }
    if (scores.isError) return <p className="text-[13px] text-muted">{noFrameYet(chosen)}</p>;
    return (
      <FrameOverlay
        instance={chosen}
        taps={(calibration.data?.constants ?? []).filter((c) => c.group === "tap")}
        anchors={scores.data?.anchors}
        show={show}
        screen={screen}
        highlight={highlight}
        onHighlight={setHighlight}
        refreshMs={running ? LIVE_POLL_MS : false}
      />
    );
  };

  return (
    <section className="flex flex-col gap-3">
      {header}
      {toolbar}

      {calibration.isError ? (
        <ErrorBlock error={calibration.error} onRetry={() => void calibration.refetch()} />
      ) : calibration.data === undefined ? (
        <Skeleton />
      ) : (
        <>
          <div className="grid gap-3 min-[1100px]:grid-cols-[1fr_420px]">
            <div className="flex flex-col gap-3">
              {frame()}
              {scores.data !== undefined && (
                <div className="flex flex-wrap items-center gap-2">
                  <Chip tone="idle">{`Screen: ${screenStateLabel(scores.data.state)}`}</Chip>
                  {/* A phase the page has no words for prints nothing, so the chip is
                      left out rather than shown with an empty half. */}
                  {phaseLabel(scores.data.phase) !== "" && (
                    <Chip tone="idle">{`Step: ${phaseLabel(scores.data.phase)}`}</Chip>
                  )}
                </div>
              )}
              {chosen !== null && (
                <RecorderCard
                  instance={chosen}
                  status={recorder.data}
                  pending={toggle.isPending}
                  onToggle={onToggle}
                />
              )}
              {chosen !== null && (
                <ObserveCard
                  instance={chosen}
                  desired={instance?.desired ?? "stop"}
                  running={running}
                  status={recorder.data}
                  pending={observe.isPending}
                  onToggle={onObserve}
                />
              )}
            </div>

            <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
              <h2 className="text-[13px] font-semibold">What it looks for</h2>
              <AnchorTable
                anchors={scores.data?.anchors ?? []}
                at={scores.data?.at}
                empty={chosen === null ? "No instances configured yet." : noFrameYet(chosen)}
              />
            </section>
          </div>

          <OverridesTable
            constants={calibration.data.constants}
            templates={calibration.data.templates}
            file={calibration.data.file}
          />
        </>
      )}
    </section>
  );
}
