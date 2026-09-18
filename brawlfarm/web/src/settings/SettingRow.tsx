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
 *
 * A row can stack instead. The control column is 280 px wide, which is right for a switch or
 * a number but cuts a file path off mid-word, so `layout="stacked"` drops the column and puts
 * the control under the sentence at the full row width. The column's width and its switch
 * rules do not travel with it, but its label rule does: the row's title is already those
 * words, so a second visible copy is noise. The label stays in the accessibility tree, which
 * is where a control's name belongs.
 */
import type { ReactNode } from "react";

export interface SettingRowProps {
  /** A node rather than a string, so a row can hang a Chip off its title. */
  title: ReactNode;
  /** A node too: an advanced row's description is two lines, not one. */
  description: ReactNode;
  error?: string;
  /** "row" is the phase 4 layout, with the control in its own 280 px column; "stacked" puts
   * the control under the sentence at the full row width. */
  layout?: "row" | "stacked";
  children: ReactNode;
}

export function SettingRow({
  title,
  description,
  error,
  layout = "row",
  children,
}: SettingRowProps) {
  const stacked = layout === "stacked";
  return (
    <div className="border-b border-line py-3 last:border-b-0">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-[220px] flex-1">
          <p className="text-[13px]">{title}</p>
          <p className="mt-0.5 text-[12px] text-muted">{description}</p>
        </div>
        {!stacked && (
          <div className="w-[280px] max-w-full shrink-0 [&_[role=switch]]:gap-0 [&_[role=switch]]:text-[0px] [&_label]:sr-only">
            {children}
          </div>
        )}
      </div>
      {stacked && <div className="mt-2 w-full [&_label]:sr-only">{children}</div>}
      {error !== undefined && <p className="mt-1 text-[12px] text-bad">{error}</p>}
    </div>
  );
}
