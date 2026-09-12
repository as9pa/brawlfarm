/**
 * The five steps of the wizard: a numbered column to the left of the content at 1000 px and
 * up, and a row of numbers above it below that. The label is always in the markup, only
 * hidden from the eye in the narrow layout, so the name a screen reader reads is the step's
 * name at every width and never a bare digit.
 *
 * Buttons, not links: there is one route, and a link that does not change the address bar
 * lies to the middle mouse button. A step at or before the one you are on is pressable, so
 * you can go back and check what you typed; a later one is disabled, because the wizard
 * cannot show you step 3 before it knows which instances step 2 picked.
 */
import { Check } from "lucide-react";

import { SETUP_STEPS, type StepId } from "./useSetupState";

export interface StepRailProps {
  index: number;
  done: Record<StepId, boolean>;
  onGo: (id: StepId) => void;
}

export function StepRail({ index, done, onGo }: StepRailProps) {
  return (
    <ol className="flex justify-center gap-1 min-[1000px]:flex-col min-[1000px]:justify-start">
      {SETUP_STEPS.map((step, at) => {
        const here = at === index;
        const reachable = at <= index;
        return (
          <li key={step.id}>
            <button
              type="button"
              disabled={!reachable}
              aria-current={here ? "step" : undefined}
              onClick={() => onGo(step.id)}
              className={`inline-flex w-full items-center gap-2 whitespace-nowrap rounded-[6px] px-2 py-1.5 text-left text-[13px] transition-colors duration-[120ms] disabled:cursor-not-allowed disabled:opacity-50 ${
                here ? "bg-panel-2 text-accent" : "text-muted hover:text-text"
              }`}
            >
              <span
                aria-hidden="true"
                className={`inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px] tabular-nums ${
                  here ? "border-accent" : "border-line"
                }`}
              >
                {done[step.id] ? <Check aria-hidden="true" size={16} strokeWidth={1.6} /> : at + 1}
              </span>
              <span className="sr-only min-[1000px]:not-sr-only">{step.label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
