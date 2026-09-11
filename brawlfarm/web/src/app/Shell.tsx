/**
 * The page frame: a 220 px rail, a 52 px top bar, and the content between them.
 *
 * Under 820 px the grid collapses to one column, which turns the rail into a top row of
 * section links (Rail hides its instance list at the same width).
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
      <div className="grid min-h-screen grid-cols-1 min-[820px]:grid-cols-[220px_1fr]">
        <Rail />
        <div className="flex min-w-0 flex-col">
          <TopBar />
          <main className="min-w-0 flex-1 p-4">{children}</main>
        </div>
      </div>
      <AlertsDrawer />
    </div>
  );
}
