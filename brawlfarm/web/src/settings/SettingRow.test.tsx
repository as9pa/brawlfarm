/** One setting: its name, the plain sentence under it, the control beside it, and the
 * API's own message when that control's last save was refused. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SettingRow } from "./SettingRow";
import { Field } from "../components/ui/Field";
import { Switch } from "../components/ui/Switch";

describe("SettingRow", () => {
  it("shows the title, the sentence and the control", () => {
    render(
      <SettingRow title="Gas aware" description="Move away from the gas earlier.">
        <Switch checked onChange={vi.fn()} label="Gas aware" />
      </SettingRow>,
    );
    expect(screen.getByText("Move away from the gas earlier.")).toBeInTheDocument();
    // The words appear twice in the DOM and once on screen: the row prints the title, and
    // the switch keeps the same string as its accessible name with its own copy shrunk
    // away. Switch's props are phase 4's and do not change, so the row is what hides it.
    expect(screen.getAllByText("Gas aware").map((el) => el.tagName)).toEqual(["P", "BUTTON"]);
    expect(screen.getByRole("switch", { name: "Gas aware" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("stacks the control under the sentence when the row asks for it", () => {
    render(
      <SettingRow
        title="ADB path"
        description="Where HD-Adb.exe lives."
        layout="stacked"
      >
        <Field label="ADB path" id="row-adb" value="D:/adb.exe" onChange={vi.fn()} width="full" />
      </SettingRow>,
    );
    const box = screen.getByLabelText("ADB path");
    // Not in the 280 px column, so nothing clips a long value.
    expect(box.closest('[class*="w-[280px]"]')).toBeNull();
    const slot = box.closest('[class*="mt-2"][class*="w-full"]');
    expect(slot).not.toBeNull();
    // The slot hides the label the way the column does, so the row's title is the only
    // "ADB path" on screen, and the input keeps it as its accessible name.
    expect(slot).toHaveClass("[&_label]:sr-only");
  });

  it("prints the field error under both", () => {
    render(
      <SettingRow
        title="ADB path"
        description="Where HD-Adb.exe lives."
        error="adb_path: file not found"
      >
        <Switch checked={false} onChange={vi.fn()} label="ADB path" />
      </SettingRow>,
    );
    expect(screen.getByText("adb_path: file not found")).toBeInTheDocument();
  });

  it("shows no error line when there is no error", () => {
    const { container } = render(
      <SettingRow title="Bush hide" description="Hide in bushes when the map allows.">
        <Switch checked={false} onChange={vi.fn()} label="Bush hide" />
      </SettingRow>,
    );
    expect(container.querySelector(".text-bad")).toBeNull();
  });
});
