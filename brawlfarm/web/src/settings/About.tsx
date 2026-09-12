/**
 * Settings > About: theme, version and links.
 *
 * The theme is a radio group of three cards rather than a Segmented, because each option
 * carries a sentence and Segmented is a row of chips. It keeps Segmented's keyboard, though:
 * one tab stop into the group, arrows between the options, and selection follows focus,
 * which is what a radio group does everywhere else.
 *
 * Picking one writes app.theme, and useSettingsPatch puts the answer straight into the
 * ["settings"] cache, which is the same query App.tsx's theme bootstrap reads: the shell
 * changes colour without a reload and without this component touching the document element.
 */
import { useQuery } from "@tanstack/react-query";
import { type KeyboardEvent, useRef, useState } from "react";

import { type SettingsPatch, fieldError, saveSetting } from "./useSettingsPatch";
import { getHealth } from "../api/health";
import { queryKeys } from "../api/queries";
import type { AppSettings } from "../api/types";
import { ErrorBlock } from "../components/ui/ErrorBlock";

type Theme = AppSettings["app"]["theme"];

const THEMES: readonly { value: Theme; label: string; subtitle: string }[] = [
  { value: "system", label: "System", subtitle: "Follows Windows." },
  { value: "light", label: "Light", subtitle: "Always light." },
  { value: "dark", label: "Dark", subtitle: "Always dark." },
];

const LINKS: readonly { label: string; href: string }[] = [
  { label: "GitHub", href: "https://github.com/as9pa/brawlfarm" },
  // The README's own sections, until docs/setup.md arrives in phase 7.
  { label: "Setup guide", href: "https://github.com/as9pa/brawlfarm#requirements" },
  { label: "Safety rails", href: "https://github.com/as9pa/brawlfarm#safety-rails" },
];

const ATTRIBUTION =
  "brawlfarm is not affiliated with or endorsed by Supercell. Brawl Stars and its art " +
  "belong to Supercell. MIT licensed.";

/** Which way each arrow moves along the group; both ends wrap. */
const ARROW_STEP: Record<string, number> = {
  ArrowLeft: -1,
  ArrowUp: -1,
  ArrowRight: 1,
  ArrowDown: 1,
};

export function About({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const [failure, setFailure] = useState<unknown>(null);
  const group = useRef<HTMLDivElement>(null);
  const { data: health } = useQuery({ queryKey: queryKeys.health(), queryFn: getHealth });

  if (settings === undefined) return null;

  const theme = settings.app.theme;
  const at = THEMES.findIndex((entry) => entry.value === theme);
  const tabStop = at < 0 ? 0 : at;

  const choose = (next: Theme) => {
    saveSetting(
      patch,
      (document) => {
        document.app.theme = next;
      },
      setFailure,
    );
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = ARROW_STEP[event.key];
    if (step === undefined) return;
    event.preventDefault();
    const to = (tabStop + step + THEMES.length) % THEMES.length;
    choose(THEMES[to].value);
    // Read from the DOM rather than waiting for the re-render, so the key press lands on
    // one frame.
    group.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[to]?.focus();
  };

  return (
    <div className="space-y-4">
      {failure !== null && <ErrorBlock error={failure} />}

      <div>
        <h3 className="text-[13px] font-semibold">Theme</h3>
        <div
          ref={group}
          role="radiogroup"
          aria-label="Theme"
          onKeyDown={onKeyDown}
          className="mt-2 grid gap-2 min-[640px]:grid-cols-3"
        >
          {THEMES.map((entry, index) => {
            const selected = entry.value === theme;
            return (
              <button
                key={entry.value}
                type="button"
                role="radio"
                aria-checked={selected}
                tabIndex={index === tabStop ? 0 : -1}
                onClick={() => choose(entry.value)}
                className={`rounded-[10px] border p-3 text-left transition-colors duration-[120ms] ${
                  selected ? "border-accent bg-panel-2" : "border-line bg-panel hover:border-accent"
                }`}
              >
                <span className="block text-[13px]">{entry.label}</span>
                <span className="block text-[12px] text-muted">{entry.subtitle}</span>
              </button>
            );
          })}
        </div>
        {fieldError(fieldErrors, "app.theme") !== undefined && (
          <p className="mt-1 text-[12px] text-bad">{fieldError(fieldErrors, "app.theme")}</p>
        )}
      </div>

      {health !== undefined && (
        <p className="font-mono text-[12px] tabular-nums text-muted">{`brawlfarm ${health.version}`}</p>
      )}

      <ul className="flex flex-wrap gap-3">
        {LINKS.map((link) => (
          <li key={link.label}>
            <a
              href={link.href}
              target="_blank"
              rel="noreferrer"
              className="text-[13px] text-accent hover:underline"
            >
              {link.label}
            </a>
          </li>
        ))}
      </ul>

      <p className="text-[12px] text-muted">{ATTRIBUTION}</p>
    </div>
  );
}
