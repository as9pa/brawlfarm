/**
 * One instance, at /instances/:name. There is no per-instance GET on the API, so the
 * page reads the fleet list through useInstances and picks its own row out of it. That
 * hook carries the 15 s visible poll, and App's "instance" handler invalidates the same
 * key, so the header, the session figures and today's numbers all follow a state change
 * without this page holding any state of its own.
 */
import { useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { ApiError } from "../api/client";
import {
  restartInstance,
  retryInstance,
  startInstance,
  stopInstance,
} from "../api/instances";
import { queryKeys } from "../api/queries";
import { screenshotUrl } from "../api/screens";
import type { InstancePayload, InstanceState } from "../api/types";
import { useInstances } from "../api/useInstances";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { StateChip } from "../components/ui/StateChip";
import { phaseLabel } from "../lib/states";
import { toast } from "../lib/toast";
import { Feed } from "./Feed";
import { LiveScreen } from "./LiveScreen";

/** Stop, Restart and Retry only mean something in some states (brief section 9). */
const NOT_RUNNING: ReadonlySet<InstanceState> = new Set<InstanceState>([
  "stopped",
  "scheduled_break",
  "offline",
]);

function Header({ inst, onDone }: { inst: InstancePayload; onDone: () => void }) {
  const stoppable = !NOT_RUNNING.has(inst.state);
  /** Nothing is announced until the request has settled. A rejection speaks the ApiError's
   * own detail -- the API's sentence, or the "cannot reach brawlfarm" one a dead server
   * produces -- and the success toast never fires. */
  const run = async (call: Promise<unknown>, done: () => void) => {
    try {
      await call;
    } catch (error) {
      toast(error instanceof ApiError ? error.detail : "Request failed");
      return;
    }
    onDone();
    done();
  };
  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <Link to="/" className="text-[12px] text-muted hover:text-text">
        Fleet
      </Link>
      <h1 className="text-[28px] leading-none font-semibold">{inst.name}</h1>
      <StateChip state={inst.state} />
      <span className="font-mono text-[12px] tabular-nums text-muted">{inst.adb_port}</span>
      {inst.player_tag === "" ? null : (
        <span data-private className="font-mono text-[12px] text-muted">
          {inst.player_tag}
        </span>
      )}
      <span className="text-[12px] text-muted">{phaseLabel(inst.phase)}</span>
      <div className="ml-auto flex items-center gap-2">
        {/* The raw PNG, for a closer look or a copied URL; LiveScreen has its own
            Refresh and Full size controls inside the frame. */}
        <a
          className="rounded-[6px] px-2 py-1 text-[12px] text-accent hover:underline"
          href={screenshotUrl(inst.name)}
          target="_blank"
          rel="noreferrer"
        >
          Screenshot
        </a>
        <Button
          variant="quiet"
          size="sm"
          disabled={!stoppable}
          disabledReason="Not running"
          onClick={() => {
            void run(stopInstance(inst.name), () => {
              toast(`Stopping ${inst.name} after this match`, {
                undo: async () => {
                  await startInstance(inst.name);
                  onDone();
                },
              });
            });
          }}
        >
          Stop
        </Button>
        <Button
          variant="quiet"
          size="sm"
          onClick={() => {
            void run(restartInstance(inst.name), () => toast(`Restarting ${inst.name}`));
          }}
        >
          Restart
        </Button>
        {inst.state === "offline" ? (
          <Button
            variant="quiet"
            size="sm"
            onClick={() => {
              void run(retryInstance(inst.name), () => toast(`Retrying ${inst.name} now`));
            }}
          >
            Retry now
          </Button>
        ) : null}
      </div>
    </header>
  );
}

export function Instance() {
  const { name = "" } = useParams();
  const client = useQueryClient();
  const fleet = useInstances();
  const refresh = () => {
    void client.invalidateQueries({ queryKey: queryKeys.instances() });
  };

  if (fleet.isPending) return <div />; // the shell is enough until the list lands
  if (fleet.isError) {
    return <ErrorBlock error={fleet.error} onRetry={() => void fleet.refetch()} />;
  }
  const inst = fleet.data.find((row) => row.name === name);
  if (inst === undefined) return <ErrorBlock error={new ApiError(404, "unknown instance")} />;

  return (
    <div className="flex flex-col gap-4">
      <Header inst={inst} onDone={refresh} />
      <div className="grid grid-cols-1 gap-4 min-[1100px]:grid-cols-[3fr_2fr]">
        <div className="flex flex-col gap-4">
          <LiveScreen name={inst.name} />
          <Feed name={inst.name} session={inst.session?.session ?? null} />
        </div>
        <div className="flex flex-col gap-4" />
      </div>
    </div>
  );
}
