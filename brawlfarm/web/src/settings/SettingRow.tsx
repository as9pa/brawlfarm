/**
 * One setting: what it is called, one plain sentence saying what it does, the control that
 * changes it, and the API's own message when that control's last save was refused.
 *
 * Every Connection, Behavior, Schedule and Notifications row goes through here, which is
 * what turns "one plain sentence per setting" into a structure rather than a habit.
 *
 * Two arbitrary variants sit on the control column. Switch and Field each render their own
 * visible label, and that label is this row's title, so without them the reader would see
 * the same words twice: the switch's copy is shrunk to nothing and the field's label is
 * made screen-reader-only. Both stay in the accessibility tree as the control's name, which
 * is where they belong, and neither component's props change, which is what phase 4
 * promised.
 */
import type { ReactNode } from "react";

export interface SettingRowProps {
  /** A node rather than a string, so a row can hang a Chip off its title. */
  title: ReactNode;
  /** A node too: an advanced row's description is two lines, not one. */
  description: ReactNode;
  error?: string;
  children: ReactNode;
}

export function SettingRow({ title, description, error, children }: SettingRowProps) {
  return (
    <div className="border-b border-line py-3 last:border-b-0">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-[220px] flex-1">
          <p className="text-[13px]">{title}</p>
          <p className="mt-0.5 text-[12px] text-muted">{description}</p>
        </div>
        <div className="w-[280px] max-w-full shrink-0 [&_[role=switch]]:gap-0 [&_[role=switch]]:text-[0px] [&_label]:sr-only">
          {children}
        </div>
      </div>
      {error !== undefined && <p className="mt-1 text-[12px] text-bad">{error}</p>}
    </div>
  );
}
