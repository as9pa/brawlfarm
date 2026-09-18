/**
 * The instance's screen, refreshed once a second while the tab is visible. "Refresh" bumps
 * refreshKey, which is Thumb's "fetch one now" signal; "Full size" is a real link, so it
 * opens in a tab, can be copied, and reaches the keyboard like any other link.
 *
 * The button is the only sign that a capture is in flight: the label changes and the
 * control goes dead until the frame lands, which costs no icon and no spinner.
 */
import { useState } from "react";

import { screenshotUrl } from "../api/screens";
import { Button } from "../components/ui/Button";
import { Thumb } from "../components/ui/Thumb";
import { useVisiblePolling } from "../live/useVisiblePolling";

// The worker writes a frame a second, so this is as live as the page can be; a poll that
// lands between two frames is a 304 with no body.
const REFRESH_MS = 1000;

export function LiveScreen({ name }: { name: string }) {
  const refreshMs = useVisiblePolling(REFRESH_MS);
  const [refreshKey, setRefreshKey] = useState(0);
  const [busy, setBusy] = useState(false);
  return (
    <section className="rounded-[10px] border border-line bg-panel p-3">
      <div className="mb-2 flex items-center gap-2">
        <h2 className="text-[13px] font-semibold">Live screen</h2>
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="quiet"
            size="sm"
            disabled={busy}
            onClick={() => setRefreshKey((k) => k + 1)}
          >
            {busy ? "Refreshing…" : "Refresh"}
          </Button>
          <a
            className="rounded-[6px] px-2 py-1 text-[12px] text-accent hover:underline focus-visible:outline-2"
            href={screenshotUrl(name)}
            target="_blank"
            rel="noreferrer"
          >
            Full size
          </a>
        </div>
      </div>
      {/* Only the width lives here; Thumb draws the frame itself, and a second border
          around it would clip against the first. */}
      <div className="w-full">
        <Thumb
          name={name}
          refreshMs={refreshMs}
          refreshKey={refreshKey}
          showClock
          onBusyChange={setBusy}
        />
      </div>
    </section>
  );
}
