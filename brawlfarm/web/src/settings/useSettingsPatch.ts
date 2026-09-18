/**
 * The one way a setting reaches disk.
 *
 * The API's settings route is whole-document, so every write is read-modify-write, and the
 * read is a fresh GET rather than the cached copy: the supervisor rewrites config.toml on
 * an apply and on a reset, and a stale cached section would be put straight back.
 *
 * Patches queue on a module-level chain rather than a per-hook one. Two sections can be on
 * screen at once (Instances and every inline tag field in it, or a wizard step and the
 * settings screen behind a reload), and two PUTs in flight against one file is exactly how
 * a flipped switch loses to the one before it.
 *
 * `patch` resolves when the document is on disk and rejects on every failure, including the
 * 422 it has already mapped: a 409 is the caller's to render inline, and anything else is
 * the caller's to put in an ErrorBlock. `saveSetting` is the wrapper the sections use.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { queryKeys } from "../api/queries";
import { getSettings, putSettings } from "../api/settings";
import type { AppSettings } from "../api/types";
import { hhmm } from "../lib/time";
import { toast } from "../lib/toast";

export interface SettingsPatch {
  settings: AppSettings | undefined;
  patch: (mutate: (draft: AppSettings) => void) => Promise<void>;
  /** "19:04": the wall-clock time of the last successful PUT, or null before the first. */
  savedAt: string | null;
  /** Keyed by the API's dotted loc, e.g. "connection.adb_path". */
  fieldErrors: Record<string, string>;
  /** Anything the mapper could not place under a field. */
  sectionErrors: string[];
  pending: boolean;
}

/** The chain every patch joins, shared by every mounted section. */
let chain: Promise<void> = Promise.resolve();

/** Section 4 of the brief: a text or number field saves 500 ms after the last keystroke, and
 * immediately on blur. The same debounce the phase 4 farm-plan goal uses. */
const DEBOUNCE_MS = 500;

/**
 * settings._explain joins pydantic's errors as "loc: msg; loc: msg" in one string, and that
 * string is the 422's detail. Split on "; ", then on the first ": ", so a message that has
 * a colon of its own survives. A piece that does not split is not a field error and goes to
 * `rest`, which is how a sentence the API grows later still reaches the reader.
 */
export function settingsFieldErrors(detail: string): {
  fields: Record<string, string>;
  rest: string[];
} {
  const fields: Record<string, string> = {};
  const rest: string[] = [];
  for (const piece of detail.split("; ")) {
    const text = piece.trim();
    if (text === "") continue;
    const at = text.indexOf(": ");
    if (at <= 0) {
      rest.push(text);
      continue;
    }
    fields[text.slice(0, at)] = text.slice(at + 2);
  }
  return { fields, rest };
}

/** A field's error line as its row shows it: the last segment of the dotted loc and the
 * message, so "connection.adb_path: file not found" reads "adb_path: file not found" under
 * the ADB path field. */
export function fieldError(errors: Record<string, string>, loc: string): string | undefined {
  const msg = errors[loc];
  if (msg === undefined) return undefined;
  return `${loc.split(".").pop() ?? loc}: ${msg}`;
}

/** What every settings section does with a patch: toast once the document is on disk, and
 * hand anything else back so the section can show it. A 422 is deliberately swallowed here,
 * because the hook has already put each message under its own field.
 *
 * `quiet` is for the caller that says something of its own about the write it just made:
 * "Settings saved" stacked under that sentence is two notes for one save. */
export function saveSettingAsync(
  patch: SettingsPatch["patch"],
  mutate: (draft: AppSettings) => void,
  onFailure: (error: unknown) => void,
  options: { quiet?: boolean } = {},
): Promise<void> {
  return patch(mutate).then(
    () => {
      if (options.quiet !== true) toast("Settings saved");
    },
    (error: unknown) => {
      if (!(error instanceof ApiError && error.status === 422)) onFailure(error);
      // Re-thrown so a caller that is waiting can tell a save that landed from one that
      // did not, even for the 422 this function has already dealt with.
      throw error;
    },
  );
}

/** The same thing for a switch or a card, which has nothing to wait for once the toast is
 * queued. */
export function saveSetting(
  patch: SettingsPatch["patch"],
  mutate: (draft: AppSettings) => void,
  onFailure: (error: unknown) => void,
): void {
  void saveSettingAsync(patch, mutate, onFailure).catch(() => undefined);
}

/**
 * One text or number field that saves itself.
 *
 * The typed text wins while the box is being typed in; once the save lands the box goes back
 * to showing what is on disk, which may not be what was typed (the model upper-cases a
 * player tag and puts its # back). A save that failed leaves the typed text alone, so
 * nothing the reader is still fixing is thrown away under them.
 *
 * A keystroke can arrive while the save before it is still in flight, so the box is only
 * handed back to `stored` when what landed is still the newest thing typed. Every keystroke
 * takes the next edit number and the save carries the one it was started for; a save that
 * comes back stale leaves the text alone, and the timer it scheduled, or the blur that beats
 * the timer, saves the newer value instead. Clearing unconditionally would show what is on
 * disk over text the reader is still typing, and the blur after it would then save `stored`
 * back over the newer value, losing the keystroke with nothing on screen to say so.
 *
 * `save` returns the patch promise and is expected to have reported its own failure already,
 * which is what saveSetting does.
 */
export function useDebouncedSave(
  stored: string,
  save: (value: string) => Promise<void>,
): { value: string; onChange: (next: string) => void; onBlur: () => void } {
  const [text, setText] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** The newest text typed, which a blur reads rather than the value this render closed
   * over: the two can differ for the keystroke that has not re-rendered yet. */
  const typed = useRef<string | null>(null);
  const edit = useRef(0);

  // A navigation away must not let a pending debounce write into a screen that is gone.
  useEffect(
    () => () => {
      if (timer.current !== null) clearTimeout(timer.current);
    },
    [],
  );

  const flush = (next: string, at: number): void => {
    timer.current = null;
    void save(next)
      .then(() => {
        if (edit.current !== at) return; // something newer was typed while this was in flight
        typed.current = null;
        setText(null);
      })
      .catch(() => undefined);
  };

  return {
    value: text ?? stored,
    onChange: (next: string) => {
      edit.current += 1;
      const at = edit.current;
      typed.current = next;
      setText(next);
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = setTimeout(() => flush(next, at), DEBOUNCE_MS);
    },
    onBlur: () => {
      if (timer.current === null) return; // nothing was typed, so there is nothing to flush
      clearTimeout(timer.current);
      flush(typed.current ?? stored, edit.current);
    },
  };
}

export function useSettingsPatch(): SettingsPatch {
  const client = useQueryClient();
  const { data } = useQuery({ queryKey: queryKeys.settings(), queryFn: getSettings });
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [sectionErrors, setSectionErrors] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  const patch = useCallback(
    (mutate: (draft: AppSettings) => void): Promise<void> => {
      const run = async (): Promise<void> => {
        setPending(true);
        try {
          const fresh = await getSettings();
          const draft = structuredClone(fresh);
          mutate(draft);
          const touchedInstances =
            JSON.stringify(draft.instances) !== JSON.stringify(fresh.instances);
          const saved = await putSettings(draft);
          client.setQueryData(queryKeys.settings(), saved);
          void client.invalidateQueries({ queryKey: queryKeys.settings() });
          if (touchedInstances) {
            // A row added or removed here has to reach the rail and the Fleet grid too.
            void client.invalidateQueries({ queryKey: queryKeys.instances() });
          }
          setFieldErrors({});
          setSectionErrors([]);
          setSavedAt(hhmm(new Date().toISOString()));
        } catch (error) {
          if (error instanceof ApiError && error.status === 422) {
            const mapped = settingsFieldErrors(error.detail);
            setFieldErrors(mapped.fields);
            setSectionErrors(mapped.rest);
          }
          throw error;
        } finally {
          setPending(false);
        }
      };
      // The caller waits on its own place in the queue, so a rejection reaches exactly the
      // section that asked for the write; the chain itself swallows it, so one refusal
      // cannot stop every later save.
      const queued = chain.then(run);
      chain = queued.catch(() => undefined);
      return queued;
    },
    [client],
  );

  return { settings: data, patch, savedAt, fieldErrors, sectionErrors, pending };
}
