/**
 * The wizard's five steps, where it opens, and the one save every step shares.
 *
 * The steps live in component state rather than in the URL. There is one route, and a
 * half-finished setup is not a place worth linking to or going back to with the browser's
 * Back button, which here means "leave the wizard", not "undo step 3".
 *
 * Where it opens is derived from what is on disk, not from the scan: the scan has not
 * answered when the wizard mounts, and a wizard that jumped a step half a second after it
 * appeared would be worse than one that always starts at the top. The done table below is
 * the other question, what the rail may tick, and that one does wait for the scan.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import type { AppSettings, ScanResponse } from "../api/types";
import type { SettingsPatch } from "../settings/useSettingsPatch";
import { toast } from "../lib/toast";

export type StepId = "bluestacks" | "instances" | "display" | "stats" | "done";

export interface SetupStep {
  id: StepId;
  label: string;
}

export const SETUP_STEPS: readonly SetupStep[] = [
  { id: "bluestacks", label: "BlueStacks" },
  { id: "instances", label: "Instances" },
  { id: "display", label: "Display" },
  { id: "stats", label: "Stats" },
  { id: "done", label: "Done" },
];

export interface SetupState {
  /** The step on screen. Always a real id: "bluestacks" until the document arrives. */
  step: StepId;
  /** Its position in SETUP_STEPS, which is what the rail compares against. */
  index: number;
  /** False until GET /api/settings has answered and the landing step is decided; the frame
   * shows nothing before that, so no step ever mounts and scans on a landing it is not on. */
  ready: boolean;
  done: Record<StepId, boolean>;
  go: (id: StepId) => void;
  next: () => void;
  back: () => void;
  /** The last scan. Step 1 runs it; steps 2 and 3 read the ports out of it. */
  scan: ScanResponse | null;
  setScan: (scan: ScanResponse | null) => void;
  /** Step 4's "Skip for now": true for this visit only, never written to disk. */
  skipStats: () => void;
  settingsPatch: SettingsPatch;
}

/** Every step takes the same one prop, and the frame is typed against it. It is declared
 * here and not in Setup.tsx because Setup.tsx imports the steps. */
export interface StepProps {
  setup: SetupState;
}

/**
 * The wizard's save, and the reason the wizard does not call Settings' saveSetting: the
 * toast is "Saved to config.toml" here, because on this page the reader has not been
 * anywhere called Settings and the reassurance they need is that it is already on disk.
 * A 422 is swallowed for the same reason it is there: useSettingsPatch has already put the
 * message under the field that caused it.
 */
export function saveStepAsync(
  patch: SettingsPatch["patch"],
  mutate: (draft: AppSettings) => void,
  onFailure: (error: unknown) => void,
): Promise<void> {
  return patch(mutate).then(
    () => {
      toast("Saved to config.toml");
    },
    (error: unknown) => {
      if (!(error instanceof ApiError && error.status === 422)) onFailure(error);
      throw error;
    },
  );
}

/** The same save for a caller with nothing to wait on. */
export function saveStep(
  patch: SettingsPatch["patch"],
  mutate: (draft: AppSettings) => void,
  onFailure: (error: unknown) => void,
): void {
  void saveStepAsync(patch, mutate, onFailure).catch(() => undefined);
}

export function useSetupState(settingsPatch: SettingsPatch): SetupState {
  const { settings } = settingsPatch;
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [step, setStep] = useState<StepId | null>(null);
  // State and not a ref: the rail has to re-render when Stats is skipped. It is still
  // "this visit only" in the sense that matters, which is that nothing is written to disk.
  const [statsSkipped, setStatsSkipped] = useState(false);
  const landed = useRef(false);

  useEffect(() => {
    if (landed.current || settings === undefined) return;
    landed.current = true;
    if (settings.connection.adb_path === "") setStep("bluestacks");
    else if (settings.instances.length === 0) setStep("instances");
    else setStep("display");
  }, [settings]);

  const done = useMemo<Record<StepId, boolean>>(
    () => ({
      // The step writes the path it found, so this turns true on the first pass without
      // anyone pressing anything.
      bluestacks: scan !== null && scan.adb_found && settings?.connection.adb_path === scan.adb_path,
      instances: (settings?.instances.length ?? 0) > 0,
      // Never stored, so never already done: it re-runs on every visit.
      display: false,
      stats:
        (settings?.connection.brawl_api_token ?? "") !== "" ||
        (settings?.instances.some((instance) => instance.player_tag !== "") ?? false) ||
        statsSkipped,
      // Reaching it is all it means, and you cannot reach it without being on it.
      done: false,
    }),
    [scan, settings, statsSkipped],
  );

  const current = step ?? "bluestacks";
  const index = SETUP_STEPS.findIndex((entry) => entry.id === current);

  const next = useCallback(() => {
    setStep((at) => {
      const from = SETUP_STEPS.findIndex((entry) => entry.id === (at ?? "bluestacks"));
      return SETUP_STEPS[Math.min(from + 1, SETUP_STEPS.length - 1)].id;
    });
  }, []);

  const back = useCallback(() => {
    setStep((at) => {
      const from = SETUP_STEPS.findIndex((entry) => entry.id === (at ?? "bluestacks"));
      return SETUP_STEPS[Math.max(from - 1, 0)].id;
    });
  }, []);

  return {
    step: current,
    index,
    ready: settings !== undefined && step !== null,
    done,
    go: setStep,
    next,
    back,
    scan,
    setScan,
    skipStats: () => setStatsSkipped(true),
    settingsPatch,
  };
}
