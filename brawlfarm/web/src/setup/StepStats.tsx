/**
 * Step 4: the optional half.
 *
 * Nothing here is needed to farm, and the copy says so first, because a required-looking
 * token field is the commonest reason someone abandons a setup wizard. "Skip for now" is a
 * real answer, not a trap: it marks the step finished for this visit and moves on.
 *
 * The token reaches the masked Field, the PUT body and nowhere else: not a log, not a toast,
 * not the summary on the next step, which says only "set" or "skipped".
 *
 * A tag is its own field per instance, because the model upper-cases it and puts its # back,
 * and a refused one has to land under the instance it belongs to rather than at the top of
 * the step.
 */
import { useState } from "react";

import { type StepProps, saveStepAsync } from "./useSetupState";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";
import { type SettingsPatch, fieldError, useDebouncedSave } from "../settings/useSettingsPatch";

function TagField({
  settingsPatch,
  name,
  onFailure,
}: {
  settingsPatch: SettingsPatch;
  name: string;
  onFailure: (error: unknown) => void;
}) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const at = settings?.instances.findIndex((one) => one.name === name) ?? -1;
  const stored = at < 0 ? "" : (settings?.instances[at].player_tag ?? "");
  const box = useDebouncedSave(stored, (value) =>
    saveStepAsync(
      patch,
      (draft) => {
        const row = draft.instances.find((one) => one.name === name);
        if (row !== undefined) row.player_tag = value;
      },
      onFailure,
    ),
  );
  // pydantic names a list item by its index, so this is the loc a 422 for this row arrives
  // under.
  const message = fieldError(fieldErrors, `instances.${at}.player_tag`);

  return (
    <div onBlur={box.onBlur}>
      <Field
        label={name}
        id={`setup-tag-${name}`}
        value={box.value}
        onChange={box.onChange}
        width="full"
        placeholder="#TAG"
      />
      {message !== undefined && <p className="mt-1 text-[12px] text-bad">{message}</p>}
    </div>
  );
}

export function StepStats({ setup }: StepProps) {
  const { back, next, skipStats, settingsPatch } = setup;
  const { settings, patch, fieldErrors } = settingsPatch;
  const [failure, setFailure] = useState<unknown>(null);
  const instances = settings?.instances ?? [];

  const token = useDebouncedSave(settings?.connection.brawl_api_token ?? "", (value) =>
    saveStepAsync(
      patch,
      (draft) => {
        draft.connection.brawl_api_token = value;
      },
      setFailure,
    ),
  );
  const tokenError = fieldError(fieldErrors, "connection.brawl_api_token");

  const skip = () => {
    skipStats();
    next();
  };

  return (
    <div>
      <h1 className="text-[18px] font-semibold">Stats (optional)</h1>
      <p className="mt-1 text-[13px] text-muted">
        A token and your player tags let brawlfarm show per-brawler stats. Farming works
        without them.
      </p>

      <div className="mt-4 space-y-3">
        {failure !== null && <ErrorBlock error={failure} />}

        <div onBlur={token.onBlur}>
          <Field
            label="Brawl Stars API token"
            id="setup-token"
            value={token.value}
            onChange={token.onChange}
            type="password"
            width="full"
          />
          {tokenError !== undefined && <p className="mt-1 text-[12px] text-bad">{tokenError}</p>}
        </div>

        {instances.map((one) => (
          <TagField
            key={one.name}
            settingsPatch={settingsPatch}
            name={one.name}
            onFailure={setFailure}
          />
        ))}

        <p className="text-[12px] text-muted">
          {"Create a key at "}
          <a
            href="https://developer.brawlstars.com"
            target="_blank"
            rel="noreferrer"
            className="text-accent hover:underline"
          >
            developer.brawlstars.com
          </a>
          {" and allow this machine's IP address."}
        </p>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <Button variant="secondary" onClick={back}>
          Back
        </Button>
        <Button variant="quiet" size="sm" onClick={skip}>
          Skip for now
        </Button>
        <Button variant="primary" onClick={next}>
          Continue
        </Button>
      </div>
    </div>
  );
}
