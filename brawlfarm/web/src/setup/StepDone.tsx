/**
 * Step 5: what setup did, and the one thing it offers to do next.
 *
 * The summary is four lines because four is what there is to say. The token is one of them
 * and is never printed: "set" or "skipped" is the whole truth a reader needs, and a token on
 * a screen is a token in a screenshot.
 *
 * A return visit to the wizard lands here, so this is also where the checks are started
 * over from step 1, and where a fleet of nothing is told where to go and add one.
 *
 * The one start is the only process this whole phase begins. It goes through the same
 * POST /api/instances/{name}/start every other Start in the panel uses, so the supervisor
 * still owns the one-worker-per-instance rule. A refused start is said out loud and does not
 * trap anyone on this page: the fleet opens either way, and the fleet is where a refusal can
 * actually be looked at.
 */
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { type StepProps } from "./useSetupState";
import { startInstance } from "../api/instances";
import { Button } from "../components/ui/Button";
import { Switch } from "../components/ui/Switch";
import { failureMessage, toast } from "../lib/toast";

export function StepDone({ setup }: StepProps) {
  const { go, settingsPatch } = setup;
  const settings = settingsPatch.settings;
  const navigate = useNavigate();
  const [startFirst, setStartFirst] = useState(true);

  const instances = settings?.instances ?? [];
  const first = instances.length === 0 ? "" : instances[0].name;
  const tagged = instances.filter((one) => one.player_tag !== "").length;

  const open = () => {
    if (!startFirst || first === "") {
      void navigate("/");
      return;
    }
    void startInstance(first).then(
      () => {
        void navigate("/");
      },
      (error: unknown) => {
        toast(failureMessage(error));
        void navigate("/");
      },
    );
  };

  return (
    <div>
      <h1 className="text-[18px] font-semibold">Done</h1>
      <p className="mt-1 text-[13px] text-muted">Setup complete.</p>

      <ul aria-label="Setup summary" className="mt-4 space-y-1 text-[13px]">
        <li>
          {`Instances: ${instances.length} `}
          <span className="font-mono text-[12px] text-muted">
            {instances.map((one) => one.name).join(", ")}
          </span>
        </li>
        <li>
          {"adb: "}
          <span className="font-mono text-[12px] text-muted">
            {settings?.connection.adb_path ?? ""}
          </span>
        </li>
        <li>
          {(settings?.connection.brawl_api_token ?? "") === "" ? "Token: skipped" : "Token: set"}
        </li>
        <li>
          {tagged === 0 ? "Player tags: none" : `Player tags: ${tagged} of ${instances.length} set`}
        </li>
      </ul>

      {first === "" ? (
        <p className="mt-4 text-[13px]">
          <Link to="/settings/instances" className="underline">
            Add an instance to start farming.
          </Link>
        </p>
      ) : (
        <div className="mt-4">
          <Switch checked={startFirst} onChange={setStartFirst} label={`Start ${first} now`} />
        </div>
      )}

      <p className="mt-4 text-[12px] text-muted">Everything is saved as you go.</p>

      <div className="mt-5 flex items-center gap-2">
        <Button variant="secondary" onClick={() => go("bluestacks")}>
          Run the checks again
        </Button>
        <Button variant="primary" onClick={open}>
          Open Fleet
        </Button>
      </div>
    </div>
  );
}
