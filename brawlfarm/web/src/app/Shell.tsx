/**
 * The page frame: a 220 px rail, a 52 px top bar, and the content between them.
 *
 * Under 820 px the grid collapses to one column, which turns the rail into a top row of
 * section links (Rail hides its instance list at the same width). That row is sized to its
 * own content and the content area takes the rest: left to stretch, two auto rows would
 * share the leftover height and leave a blank block under the links on any page shorter
 * than the viewport. Above 820 px there is one row again, so the rail still runs the full
 * height beside the content.
 */
import type { ReactNode } from "react";

import { AlertsDrawer } from "./AlertsDrawer";
import { Rail } from "./Rail";
import { TopBar } from "./TopBar";

export interface ShellProps {
  children: ReactNode;
}

export function Shell({ children }: ShellProps) {
  return (
    <div className="min-h-screen bg-ground text-text">
      {/* First in the DOM, so it is the first tab stop. sr-only rather than display:none:
          a hidden-by-display link is not focusable and would never appear. */}
      <a
        href="#main-content"
        className="sr-only focus-visible:not-sr-only focus-visible:absolute focus-visible:left-3 focus-visible:top-3 focus-visible:z-50 focus-visible:rounded-control focus-visible:border focus-visible:border-line focus-visible:bg-panel focus-visible:px-3 focus-visible:py-2 focus-visible:text-[13px] focus-visible:text-text"
      >
        Skip to content
      </a>
      <div className="grid min-h-screen grid-cols-1 grid-rows-[auto_1fr] min-[820px]:grid-cols-[220px_1fr] min-[820px]:grid-rows-[1fr]">
        <Rail />
        <div className="flex min-w-0 flex-col">
          <TopBar />
          {/* tabIndex -1 so the skip link moves focus here and not only the scroll
              position. */}
          <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 p-4">
            {children}
          </main>
        </div>
      </div>
      <AlertsDrawer />
    </div>
  );
}
