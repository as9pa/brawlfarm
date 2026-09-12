/**
 * One quiet strip saying why there are no per-game numbers, and what to do about it.
 *
 * Never a modal and never a toast: the page below it still shows everything that was
 * logged, and the reader decides when to go and fix the credential. The sentences are the
 * spec's, letter for letter.
 */
import { Link } from "react-router";

import type { ConnectionStatus } from "../api/types";
import type { Tone } from "../lib/states";

export interface ConnectionStripProps {
  status: ConnectionStatus;
  /** The selected instance whose player_tag is blank, which the no_tag sentence names.
   * Null when there is none, and then no_tag says nothing at all. */
  instanceWithoutTag: string | null;
}

const TONE_BORDER: Record<Tone, string> = {
  ok: "border-l-ok",
  warn: "border-l-warn",
  bad: "border-l-bad",
  idle: "border-l-idle",
};

export function ConnectionStrip({ status, instanceWithoutTag }: ConnectionStripProps) {
  if (status === "ok") return null;
  if (status === "no_tag" && instanceWithoutTag === null) return null;

  const tone: Tone = status === "rejected" ? "bad" : "warn";

  return (
    <p
      role="status"
      data-tone={tone}
      className={`rounded-[6px] border border-line border-l-[3px] bg-panel-2 px-3 py-2 text-[12px] text-text ${TONE_BORDER[tone]}`}
    >
      {status === "no_token" && (
        <>
          Battle log unavailable. Add a Brawl Stars API token in{" "}
          <Link to="/settings/connection" className="underline">
            Settings
          </Link>{" "}
          to see per-game stats.
        </>
      )}
      {status === "no_tag" && (
        <>
          Add a player tag for {instanceWithoutTag} in{" "}
          <Link to="/settings/instances" className="underline">
            Settings, Instances
          </Link>{" "}
          to see its games.
        </>
      )}
      {status === "rejected" && (
        <>
          The Brawl Stars API rejected the token. Check the token, and the IP address it was
          created for, in{" "}
          <Link to="/settings/connection" className="underline">
            Settings, Connection
          </Link>
          .
        </>
      )}
      {status === "unreachable" && (
        <>The Brawl Stars API did not answer. Stats show what was logged so far.</>
      )}
    </p>
  );
}
