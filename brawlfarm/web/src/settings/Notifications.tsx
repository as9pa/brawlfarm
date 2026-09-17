/**
 * Settings > Notifications: where alerts go.
 *
 * Four channels, seven events and one test send. Each channel row is its own component
 * rather than four copies of the same eight lines, which is also what keeps useDebouncedSave
 * to one call per component instead of a hook inside a loop.
 *
 * The event list is written back in NOTIFY_EVENT_LABELS' order rather than in the order the
 * boxes were ticked, so config.toml reads the same however it got there and a diff between
 * two machines is about what is on, not about what was clicked first.
 *
 * Neither a URL nor a topic is ever logged or toasted: the test result names channels
 * ("ntfy", "webhook"), never their addresses.
 */
import { useState } from "react";

import { NOTIFY_EVENT_LABELS } from "./events";
import { SettingRow } from "./SettingRow";
import {
  type SettingsPatch,
  fieldError,
  saveSetting,
  saveSettingAsync,
  useDebouncedSave,
} from "./useSettingsPatch";
import { testNotifications } from "../api/settings";
import type { AppSettings } from "../api/types";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";
import { failureMessage, toast } from "../lib/toast";

type ChannelField = "ntfy_topic" | "ntfy_server" | "webhook_url" | "healthchecks_url";

const CHANNELS: readonly { field: ChannelField; label: string; description: string }[] = [
  {
    field: "ntfy_topic",
    label: "ntfy topic",
    description:
      "Free phone notifications. Install the ntfy app, pick a topic name, type it here.",
  },
  {
    field: "ntfy_server",
    label: "ntfy server",
    description: "Leave this unless you run your own ntfy server.",
  },
  {
    field: "webhook_url",
    label: "Webhook URL",
    description:
      "A URL that receives each alert as a message, for chat apps that offer incoming webhooks.",
  },
  {
    field: "healthchecks_url",
    label: "Healthchecks URL",
    description:
      "A check-in URL from healthchecks.io; it warns you when brawlfarm stops checking in.",
  },
];

function ChannelRow({
  settingsPatch,
  field,
  label,
  description,
  onFailure,
}: {
  settingsPatch: SettingsPatch;
  field: ChannelField;
  label: string;
  description: string;
  onFailure: (error: unknown) => void;
}) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const box = useDebouncedSave(settings?.notifications[field] ?? "", (value) =>
    saveSettingAsync(
      patch,
      (document) => {
        document.notifications[field] = value;
      },
      onFailure,
    ),
  );
  return (
    <SettingRow
      title={label}
      description={description}
      error={fieldError(fieldErrors, `notifications.${field}`)}
    >
      <div onBlur={box.onBlur}>
        <Field
          label={label}
          id={`notifications-${field}`}
          value={box.value}
          onChange={box.onChange}
          width="full"
        />
      </div>
    </SettingRow>
  );
}

export function Notifications({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings, patch } = settingsPatch;
  const [failure, setFailure] = useState<unknown>(null);
  const [sending, setSending] = useState(false);

  if (settings === undefined) return null;

  const on = new Set(settings.notifications.events);
  const hasChannel =
    settings.notifications.ntfy_topic !== "" ||
    settings.notifications.webhook_url !== "" ||
    settings.notifications.healthchecks_url !== "";

  const toggleEvent = (kind: string, next: boolean) => {
    const wanted = new Set(on);
    if (next) wanted.add(kind);
    else wanted.delete(kind);
    saveSetting(
      patch,
      (document: AppSettings) => {
        document.notifications.events = NOTIFY_EVENT_LABELS.filter((event) =>
          wanted.has(event.kind),
        ).map((event) => event.kind);
      },
      setFailure,
    );
  };

  const sendTest = () => {
    setSending(true);
    void testNotifications()
      .then(
        (result) => {
          // Sent first: the good news is the answer to "did that work", and the failures
          // read as the exception to it.
          if (result.sent.length > 0) toast(`Test sent to ${result.sent.join(", ")}`);
          if (result.failed.length > 0) toast(`Test failed for ${result.failed.join(", ")}`);
        },
        (error: unknown) => {
          toast(failureMessage(error));
        },
      )
      .finally(() => setSending(false));
  };

  return (
    <div>
      {failure !== null && <ErrorBlock error={failure} />}

      <div>
        {CHANNELS.map((channel) => (
          <ChannelRow
            key={channel.field}
            settingsPatch={settingsPatch}
            field={channel.field}
            label={channel.label}
            description={channel.description}
            onFailure={setFailure}
          />
        ))}
      </div>

      <div className="mt-4">
        <h3 className="text-[13px] font-semibold">Send me</h3>
        <ul className="mt-2 grid gap-1.5 min-[640px]:grid-cols-2">
          {NOTIFY_EVENT_LABELS.map((event) => (
            <li key={event.kind}>
              <label className="inline-flex items-center gap-2 text-[13px]">
                <input
                  type="checkbox"
                  aria-label={event.label}
                  checked={on.has(event.kind)}
                  onChange={(change) => toggleEvent(event.kind, change.target.checked)}
                  className="h-3.5 w-3.5 accent-[var(--accent)]"
                />
                {event.label}
              </label>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <Button
          variant="secondary"
          disabled={!hasChannel || sending}
          disabledReason={hasChannel ? undefined : "Add a channel first"}
          onClick={sendTest}
        >
          Send a test
        </Button>
        {!hasChannel && <span className="text-[12px] text-muted">Add a channel first</span>}
      </div>
    </div>
  );
}
