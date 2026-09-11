import { useState } from "react";

import { screenshotUrl } from "../api/screens";
import { Button } from "../components/ui/Button";
import { Thumb } from "../components/ui/Thumb";
import { useVisiblePolling } from "../live/useVisiblePolling";

const REFRESH_MS = 15000; // the same cadence a Fleet card's thumbnail uses

/**
 * The instance's screen, refreshed every 15 s while the tab is visible. "Refresh" bumps
 * refreshKey, which is Thumb's "fetch one now" signal; "Full size" is a real link, so it
 * opens in a tab, can be copied, and reaches the keyboard like any other link.
 */
export function LiveScreen({ name }: { name: string }) {
  const refreshMs = useVisiblePolling(REFRESH_MS);
  const [refreshKey, setRefreshKey] = useState(0);
  return (
    <section className="rounded-[10px] border border-line bg-panel p-3">
      <div className="mb-2 flex items-center gap-2">
        <h2 className="text-[13px] font-semibold">Live screen</h2>
        <div className="ml-auto flex items-center gap-1">
          <Button variant="text" size="sm" onClick={() => setRefreshKey((k) => k + 1)}>
            Refresh
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
      <div className="aspect-video w-full max-w-[760px] overflow-hidden rounded-[6px] border border-line bg-panel-2">
        <Thumb name={name} refreshMs={refreshMs} refreshKey={refreshKey} />
      </div>
    </section>
  );
}
